"""Every model call of an evaluation is logged with its tokens, stored per run, and shown to admins.

The log answers what a run cost and where: which stage, which model, how many input, output and
reasoning tokens, how long, how many attempts, and how much of the run the cache answered.
"""
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import store  # noqa: E402
from core import llm as llm_mod, pipeline  # noqa: E402
from tests.test_evaluate_stream import offline, _run  # noqa: E402,F401  (fixture reuse)


class _Usage:
    def __init__(self, prompt, completion, total, reasoning=None):
        self.prompt_tokens, self.completion_tokens, self.total_tokens = prompt, completion, total
        self.completion_tokens_details = type("D", (), {"reasoning_tokens": reasoning})()


def _client(answers):
    """An LLMClient whose provider returns (text, usage) pairs in turn, or raises an Exception."""
    class Completions:
        def create(self, **kw):
            out = answers.pop(0) if len(answers) > 1 else answers[0]
            if isinstance(out, Exception):
                raise out
            text, usage = out

            class R:
                choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]
            R.usage = usage
            return R()

    c = llm_mod.LLMClient.__new__(llm_mod.LLMClient)
    c.available, c.provider, c.model, c.last_error = True, "gemini", "gemini-2.5-flash", ""
    c._client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    return c


@pytest.fixture
def calls(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_CACHE", False)
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    token, log = llm_mod.collect_usage()
    yield log
    llm_mod.stop_collecting_usage(token)


def test_a_call_is_logged_with_its_stage_model_and_tokens(calls):
    stage = llm_mod.set_stage("fit")
    try:
        _client([("ok", _Usage(1200, 300, 1500, reasoning=0))]).complete("p")
    finally:
        llm_mod.reset_stage(stage)
    (c,) = calls
    assert (c["stage"], c["model"], c["kind"], c["ok"], c["cached"]) == ("fit", "gemini-2.5-flash", "completion", True, False)
    assert (c["input_tokens"], c["output_tokens"], c["total_tokens"]) == (1200, 300, 1500)


def test_thinking_tokens_gemini_reports_only_in_the_total_are_counted(calls):
    _client([("ok", _Usage(1000, 200, 4200))]).complete("p")       # 3000 tokens of thinking
    assert calls[0]["reasoning_tokens"] == 3000 and calls[0]["total_tokens"] == 4200


def test_a_failed_call_is_logged_with_its_attempts_and_no_tokens(calls):
    _client([TimeoutError("Request timed out.")]).complete("p")
    (c,) = calls
    assert (c["ok"], c["reason"], c["attempts"], c["total_tokens"]) == (False, "timeout", 3, 0)


def test_a_cache_hit_is_logged_at_zero_tokens(calls, monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_CACHE", True)
    monkeypatch.setattr(llm_mod._web, "_cached", lambda kind, key, meta=None: "cached answer")
    assert _client([("unused", _Usage(1, 1, 2))]).complete("p") == "cached answer"
    assert calls[0]["cached"] is True and calls[0]["total_tokens"] == 0


def test_an_evaluation_carries_its_token_log_and_saving_it_shows_it_to_admins(offline, monkeypatch):
    df, tools = offline
    monkeypatch.setattr(llm_mod, "LLM_CACHE", False)
    monkeypatch.setattr(pipeline, "LLMClient", lambda *a, **kw: _client([("", _Usage(500, 50, 550))]))
    result = _run(df, tools)
    usage = result["token_usage"]
    completions = [c for c in usage["log"] if c["kind"] == "completion"]
    assert len(completions) >= 2 and usage["input_tokens"] == 500 * len(completions)
    # Semantic tool search tries one embedding call too; this fake client cannot embed, so it is
    # logged as failed and the run falls back to word matching.
    assert [c["ok"] for c in usage["log"] if c["kind"] == "embedding"] == [False] *         sum(c["kind"] == "embedding" for c in usage["log"])
    assert {"summary", "fit"} <= {s["stage"] for s in usage["by_stage"]}
    run_id = store.save_run({**result, "company": f"Tokens-{uuid.uuid4().hex[:6]}"})
    listed = next(r for r in store.token_usage_runs(500)["runs"] if r["run_id"] == run_id)
    assert (listed["calls"], listed["total_tokens"]) == (usage["calls"], usage["total_tokens"])
    log = store.token_usage_log(run_id)
    assert [c["stage"] for c in log] == [c["stage"] for c in usage["log"]]


def test_an_offline_evaluation_has_no_token_log(offline):
    df, tools = offline
    assert "token_usage" not in _run(df, tools)


def test_the_token_log_is_not_public():
    from api.main import app
    client = TestClient(app)
    assert client.get("/api/admin/token-usage").status_code == 401
    assert client.get("/api/admin/token-usage/1").status_code == 401
