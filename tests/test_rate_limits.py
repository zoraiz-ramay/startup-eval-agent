"""Rate limits are waited out, not retried into, and a call that fails for good is reported.

The old behaviour: a 429 was retried after 2s and 4s — inside the same per-minute window, so
the retries failed too — and the caller's fallback produced a weaker result that looked exactly
like a normal one. At 100 reviewers the quota is what fails first, so this is the scaling bug
that would have reached people as quietly worse evaluations rather than as errors.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import llm as llm_mod, pipeline  # noqa: E402
from api import flight  # noqa: E402
from tests.test_evaluate_stream import offline, _run  # noqa: E402,F401  (fixture reuse)


class _RateLimited(Exception):
    status_code = 429
    response = None
    body = {"error": {"status": "RESOURCE_EXHAUSTED", "details": [{"retryDelay": "27s"}]}}


def _client(outcomes):
    """An LLMClient whose provider answers with ``outcomes`` in turn (an Exception is raised)."""
    class Completions:
        def create(self, **kw):
            out = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
            if isinstance(out, Exception):
                raise out

            class R:
                choices = [type("C", (), {"message": type("M", (), {"content": out})()})()]
            return R()

    c = llm_mod.LLMClient.__new__(llm_mod.LLMClient)
    c.available, c.provider, c.model, c.last_error = True, "gemini", "gemini-2.5-flash", ""
    c._client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    return c


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(llm_mod.time, "sleep", slept.append)
    monkeypatch.setattr(llm_mod, "LLM_CACHE", False)
    return slept


def test_a_rate_limited_call_waits_as_long_as_the_provider_asks_then_succeeds(no_sleep):
    client = _client([_RateLimited("Resource has been exhausted"), "ok"])
    assert client.complete("p") == "ok"
    assert len(no_sleep) == 1 and 27 <= no_sleep[0] <= 28     # retryDelay + up to 1s jitter


def test_a_call_that_fails_for_good_is_charged_to_its_stage(no_sleep):
    token, failures = llm_mod.collect_failures()
    stage = llm_mod.set_stage("fit")
    try:
        assert _client([_RateLimited("quota")]).complete("p") == ""
    finally:
        llm_mod.reset_stage(stage)
        llm_mod.stop_collecting(token)
    assert failures == [{"stage": "fit", "reason": "rate_limited"}]


def test_a_timeout_is_not_mistaken_for_a_rate_limit(no_sleep):
    token, failures = llm_mod.collect_failures()
    try:
        _client([TimeoutError("Request timed out.")]).complete("p")
    finally:
        llm_mod.stop_collecting(token)
    assert failures == [{"stage": "input", "reason": "timeout"}]
    assert no_sleep == [2, 4]                                   # the ordinary backoff, unchanged


def test_an_evaluation_names_every_stage_that_ran_without_the_model(offline, no_sleep, monkeypatch):
    df, tools = offline
    monkeypatch.setattr(pipeline, "LLMClient", lambda *a, **kw: _client([_RateLimited("quota")]))
    result = _run(df, tools)
    stages = {d["stage"] for d in result["degraded"]}
    assert {"summary", "fit"} <= stages
    assert all(d["reason"] == "rate_limited" and d["calls"] >= 1 for d in result["degraded"])


def test_a_clean_run_carries_no_degraded_field(offline):
    df, tools = offline                      # offline fixture: no model configured, nothing failed
    assert "degraded" not in _run(df, tools)


@pytest.mark.parametrize("backend", ["memory", "redis"])
def test_the_shared_gate_holds_requests_over_the_minute_budget(backend, monkeypatch):
    monkeypatch.setattr(flight, "_local_minutes", {})
    if backend == "redis":
        fakeredis = pytest.importorskip("fakeredis")
        client = fakeredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(flight, "_redis", lambda: client)
    else:
        monkeypatch.setattr(flight, "_redis", lambda: None)
    now = [30.0]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    gate = flight.llm_gate(2, clock=lambda: now[0], sleep=sleep)
    gate(); gate()
    assert slept == []                       # within budget: no waiting at all
    gate()
    assert slept == [30.0]                   # the third waits for the next minute's window
