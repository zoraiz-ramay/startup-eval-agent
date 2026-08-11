"""Characterisation tests for profile-headcount-trend (PROF-12).

The engine already computes `deep_profile.employees_over_time` and threads it, source URLs
included, all the way to the API response and through persistence — see
`contract/feature-proposals.md` for the evidence trail (core/profile.py:814-920,
core/pipeline.py:154,196, api/store.py:354,462,479). Nothing in `ui/src` reads it yet; that is
a UI gap, not a backend one.

These tests lock down the two things a UI integrator depends on and a future refactor could
silently break:

1. `_employee_history` (core/profile.py) never fabricates a point — no LLM, no search hits, and
   an uncited LLM answer all collapse to the same honest `[]`, exactly like a missing field
   everywhere else in this codebase.
2. The series and its per-point `source_url` survive a full save_run/get_run round trip through
   api/store.py untouched — the persistence layer must not be the place that quietly drops
   provenance.

Requires pandas; run in the app environment.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.profile import _employee_history  # noqa: E402
import core.profile as profile_mod  # noqa: E402
from api import store as store_mod  # noqa: E402


class _Unavailable:
    """An LLM client with no key configured — the offline-degradation path."""
    available = False

    def complete(self, *a, **k):  # pragma: no cover - must never be called
        raise AssertionError("complete() must not be called when the LLM is unavailable")


class _FakeLLM:
    """Available LLM whose .complete() answer is scripted per test."""
    available = True

    def __init__(self, reply: str):
        self._reply = reply
        self.calls = 0

    def complete(self, *a, **k):
        self.calls += 1
        return self._reply


def _no_search(*a, **k):
    return {}


def _row():
    return pd.Series({"company_name": "Acme Robotics", "domain": "acme.example"})


# ---------------------------------------------------------------- honest-failure paths

def test_llm_unavailable_returns_empty_series_without_searching(monkeypatch):
    """No API key configured -> [] immediately, and it must not even attempt the search wave
    (a search that then goes unused would just be wasted latency for a result already known)."""
    def _boom(*a, **k):
        raise AssertionError("_ddg_many must not be called when the LLM is unavailable")
    monkeypatch.setattr(profile_mod, "_ddg_many", _boom)
    out = _employee_history("Acme Robotics", _row(), {}, _Unavailable())
    assert out == []


def test_no_search_results_returns_empty_series_without_calling_the_llm(monkeypatch):
    """Search returns nothing, existing results are empty too -> the corpus is empty, so the
    function must decline before spending an LLM call on evidence that doesn't exist."""
    monkeypatch.setattr(profile_mod, "_ddg_many", _no_search)
    llm = _FakeLLM('{"employees_over_time": [{"year": 2024, "count": 99, "source_url": ""}]}')

    def _no_calls(*a, **k):
        raise AssertionError("llm.complete must not be called with an empty corpus")
    llm.complete = _no_calls
    out = _employee_history("Acme Robotics", _row(), {}, llm)
    assert out == []


def test_search_wave_failure_is_absorbed_not_raised(monkeypatch):
    """The dedicated historical-headcount search wave can time out or error; that must degrade
    to 'use whatever evidence was already gathered', never raise out of research."""
    def _boom(*a, **k):
        raise TimeoutError("ddg timed out")
    monkeypatch.setattr(profile_mod, "_ddg_many", _boom)
    llm = _FakeLLM('{"employees_over_time": []}')
    out = _employee_history("Acme Robotics", _row(), {}, llm)
    assert out == []
    assert llm.calls == 0        # no evidence survived the failed search -> no point asking


def test_llm_answer_without_a_source_is_dropped_not_shown(monkeypatch):
    """Evidence exists (so the LLM is asked), but its answer cites no URL for either point —
    the function must not pass an uncited guess through; _clean_employee_series enforces this
    and _employee_history must not route around it."""
    monkeypatch.setattr(profile_mod, "_ddg_many", _no_search)
    existing = {"h0": [{"title": "Acme grows", "body": "acme now employs many people",
                        "href": "https://news.example/acme"}]}
    llm = _FakeLLM(
        '{"employees_over_time": ['
        '{"year": 2023, "count": 10, "source_url": ""}, '
        '{"year": 2024, "count": 40, "source_url": ""}]}')
    out = _employee_history("Acme Robotics", _row(), existing, llm)
    assert out == []


def test_llm_unavailability_and_missing_evidence_are_indistinguishable_to_the_ui(monkeypatch):
    """Both honest-failure modes above must converge on exactly the same shape ([]), so the UI
    needs only one empty-state branch rather than guessing at a reason."""
    monkeypatch.setattr(profile_mod, "_ddg_many", _no_search)
    a = _employee_history("Acme Robotics", _row(), {}, _Unavailable())
    b = _employee_history("Acme Robotics", _row(), {}, _FakeLLM('{"employees_over_time": []}'))
    assert a == b == []


# ---------------------------------------------------------------------- honest-success path

def test_cited_points_survive_with_their_source_urls(monkeypatch):
    """The one path that must actually produce data: >=2 distinct cited years come back intact,
    sorted, each still carrying the URL that supports it."""
    monkeypatch.setattr(profile_mod, "_ddg_many", _no_search)
    existing = {"h0": [{"title": "Acme headcount", "body": "acme employee history",
                        "href": "https://linkedin.example/acme"}]}
    llm = _FakeLLM(
        '{"employees_over_time": ['
        '{"year": 2024, "count": 60, "source_url": "https://linkedin.example/acme"}, '
        '{"year": 2022, "count": 3, "source_url": "https://crunchbase.example/acme"}]}')
    out = _employee_history("Acme Robotics", _row(), existing, llm)
    assert out == [
        {"year": 2022, "count": 3, "source_url": "https://crunchbase.example/acme"},
        {"year": 2024, "count": 60, "source_url": "https://linkedin.example/acme"},
    ]
    assert all(p["source_url"].startswith("http") for p in out)


# --------------------------------------------------------- persistence round trip (api/store.py)
# `deep_profile.employees_over_time` reaches the API today purely because save_run/get_run
# serialise the WHOLE result dict rather than a hand-picked subset of fields. That is easy to
# break by accident (a future column-by-column rewrite of runs, a response model that lists
# fields explicitly) so it is pinned down here against the real functions, not a re-description
# of json.dumps/json.loads.

def _make_result(employees_over_time):
    return {
        "found": True,
        "company": "Acme Robotics",
        "engine": "test",
        "profile": {"company_name": "Acme Robotics", "website": "https://acme.example"},
        "profile_sources": {},
        "summary": "",
        "facts": [],
        "verification": {"claims": []},
        "fit": {},
        "score": {"final_score": 42.0, "dimensions": {}},
        "routing": {"pillar": "Empower", "secondary": []},
        "trend": {},
        "deep_profile": {
            "founders": [], "key_team": [], "advisors": [], "employees": "60",
            "employees_over_time": employees_over_time,
            "parent_group": "", "founded_year": "", "founded_year_source": "",
            "funding": "", "funding_source": "", "programs": [],
            "reference_customers": [], "customer_segment": "",
            "sfs": {"relevant": False, "rationale": ""}, "method": "llm",
        },
    }


def _isolated_db(monkeypatch, tmp_path):
    """Point api.store at a throwaway SQLite file so these tests never touch data/runs.db,
    and short-circuit S3 sync (unavailable in this environment anyway, but pinned so the test
    doesn't depend on ambient credentials)."""
    monkeypatch.setattr(store_mod, "DB_PATH", str(tmp_path / "test_runs.db"))
    monkeypatch.setattr(store_mod, "_restored", True)
    monkeypatch.setattr(store_mod, "_s3_available", lambda: False)


def test_save_and_get_run_round_trips_the_series_and_its_sources(monkeypatch, tmp_path):
    _isolated_db(monkeypatch, tmp_path)
    points = [
        {"year": 2022, "count": 3, "source_url": "https://crunchbase.example/acme"},
        {"year": 2024, "count": 60, "source_url": "https://linkedin.example/acme"},
    ]
    run_id = store_mod.save_run(_make_result(points))
    fetched = store_mod.get_run(run_id)
    assert fetched["deep_profile"]["employees_over_time"] == points
    assert all(p["source_url"].startswith("http")
               for p in fetched["deep_profile"]["employees_over_time"])


def test_latest_run_for_company_also_round_trips_the_series(monkeypatch, tmp_path):
    """The cache-first /api/evaluate path (api/main.py) serves this function's return value
    directly — a re-read run must carry the series too, not just a freshly computed one."""
    _isolated_db(monkeypatch, tmp_path)
    points = [
        {"year": 2021, "count": 5, "source_url": "https://a.example/x"},
        {"year": 2023, "count": 25, "source_url": "https://b.example/y"},
    ]
    store_mod.save_run(_make_result(points))
    fetched = store_mod.latest_run_for_company("Acme Robotics")
    assert fetched is not None
    assert fetched["deep_profile"]["employees_over_time"] == points


def test_insufficient_series_persists_as_the_same_honest_empty_list(monkeypatch, tmp_path):
    """A company with fewer than two cited points is stored and rehydrated as [] — persistence
    must not turn 'insufficient evidence' into either a dropped key or a fabricated point."""
    _isolated_db(monkeypatch, tmp_path)
    run_id = store_mod.save_run(_make_result([]))
    fetched = store_mod.get_run(run_id)
    assert fetched["deep_profile"]["employees_over_time"] == []
