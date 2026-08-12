"""Per-reviewer lists, the shared evaluation cache, and the admin gate.

Two properties are being defended here and they pull in opposite directions: an evaluation
is shared (so a second reviewer asking about the same company costs nothing), while the
*record* of who asked is private (so one reviewer's shortlist is not visible to another).
A change that satisfies only one of those is a regression, not a trade-off.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

import pytest
from fastapi.testclient import TestClient

from api import store
from api.main import app


@pytest.fixture()
def db(monkeypatch):
    """A DB per test. store.DB_PATH is read at call time by _conn, so patching it works."""
    path = pathlib.Path(tempfile.mkdtemp()) / "runs.db"
    monkeypatch.setattr(store, "DB_PATH", str(path))
    # _restore_from_s3 is a no-op without credentials, but pin it so a developer with the
    # real AWS vars exported does not silently test against the production database.
    monkeypatch.setattr(store, "_restore_from_s3", lambda: None)
    monkeypatch.setattr(store, "_upload_to_s3", lambda: None)
    return path


def _result(name: str, domain: str = "") -> dict:
    return {"company": name, "found": True,
            "routing": {"pillar": "Connect", "secondary": []},
            "score": {"final_score": 71.2, "dimensions": {"traction": 60.0},
                      "data_completeness": 0.75},
            "profile": {"domain": domain}, "facts": [], "fit": {"aligned": True}}


# ------------------------------------------------------------- the shared cache

def test_a_differently_typed_query_still_hits_the_stored_run(db):
    """The bug this table exists for: /api/evaluate looked up the name the reviewer typed
    while save_run filed the run under the name the pipeline resolved, so "phena" re-ran the
    entire external pipeline for a company already sitting in the database."""
    run_id = store.save_run(_result("Phena Technologies", "phena.ai"), aliases=["phena"])

    for typed in ("phena", "PHENA", "Phena Technologies", "phena.ai", "https://www.phena.ai/about"):
        hit = store.latest_run_for_alias(typed)
        assert hit is not None, f"{typed!r} should have resolved to the stored run"
        assert hit["run_id"] == run_id


def test_an_unknown_name_is_not_resolved_to_something_else(db):
    store.save_run(_result("Phena Technologies", "phena.ai"))
    assert store.latest_run_for_alias("Some Other Company") is None


def test_an_alias_is_not_stolen_by_a_later_company(db):
    """Two startups can share a typed prefix. Repointing the alias would serve the wrong
    company's evaluation from cache, which is worse than a cache miss."""
    first = store.save_run(_result("Nordwind Robotics"), aliases=["nord"])
    store.save_run(_result("Nordsee Analytics"), aliases=["nord"])
    assert store.latest_run_for_alias("nord")["run_id"] == first


def test_runs_saved_before_aliases_existed_are_still_served(db):
    """The exact-name fallback. Simulated by writing a run and then emptying the alias
    table, which is the state every pre-existing row is in."""
    run_id = store.save_run(_result("Kilnstack"))
    with store._conn() as con:
        con.execute("DELETE FROM company_aliases")
    assert store.latest_run_for_alias("Kilnstack")["run_id"] == run_id


# ------------------------------------------------------------- private lists

def test_a_reviewer_sees_only_the_companies_they_searched(db):
    run_a = store.save_run(_result("Aeroview"))
    store.save_run(_result("Nordwind"))
    alice = {"oid": "oid-alice", "upn": "alice@siemens.com"}
    bob = {"oid": "oid-bob", "upn": "bob@siemens.com"}
    store.record_search(alice, "aeroview", company_name="Aeroview", run_id=run_a)
    store.record_search(bob, "nordwind", company_name="Nordwind")

    assert [r["company"] for r in store.list_user_runs("oid-alice")] == ["Aeroview"]
    assert [r["company"] for r in store.list_user_runs("oid-bob")] == ["Nordwind"]
    assert store.list_user_runs("oid-nobody") == []


def test_a_cached_hit_still_lands_on_the_second_reviewers_list(db):
    """The whole point of the split: Bob pays nothing for the evaluation but still gets the
    company on his own list."""
    run_id = store.save_run(_result("Aeroview"), aliases=["aero"])
    store.record_search({"oid": "oid-alice", "upn": "a@x"}, "aero",
                        company_name="Aeroview", run_id=run_id, served_from="fresh")
    store.record_search({"oid": "oid-bob", "upn": "b@x"}, "aero",
                        company_name="Aeroview", run_id=run_id, served_from="cache")

    assert [r["company"] for r in store.list_user_runs("oid-bob")] == ["Aeroview"]
    assert store.admin_overview()["cache_hit_rate"] == 0.5


def test_a_re_evaluated_company_appears_once(db):
    """The list is per-company, not per-run: list_runs holds every historical run and a
    company that has been re-evaluated three times must still be one row in the grid."""
    for _ in range(3):
        store.save_run(_result("Aeroview"))
    store.record_search({"oid": "oid-alice", "upn": "a@x"}, "aeroview", company_name="Aeroview")
    assert [r["company"] for r in store.list_user_runs("oid-alice")] == ["Aeroview"]


def test_the_grid_payload_carries_what_the_browser_needs_to_re_score(db):
    """Explore's portfolio weighting re-scores rows client-side; without these it silently
    falls back to the engine's numbers and the control looks broken rather than absent."""
    store.save_run(_result("Aeroview"))
    store.record_search({"oid": "oid-alice", "upn": "a@x"}, "aeroview", company_name="Aeroview")
    row = store.list_user_runs("oid-alice")[0]
    assert row["dimensions"] == {"traction": 60.0}
    assert row["data_completeness"] == 0.75
    assert row["fit_aligned"] is True


def test_searches_without_a_principal_are_not_recorded(db):
    """Defensive: an oid-less caller must not create rows attributable to nobody."""
    store.record_search({}, "ghost", company_name="Ghost")
    assert store.list_searches() == []


# ------------------------------------------------------------- admin metrics

def test_admin_overview_counts_users_sessions_and_searches(db):
    store.record_session({"oid": "oid-alice", "upn": "alice@siemens.com"})
    store.record_session({"oid": "oid-bob", "upn": "bob@siemens.com"})
    store.record_session({"oid": "oid-alice", "upn": "alice@siemens.com"})
    store.save_run(_result("Aeroview"))
    store.record_search({"oid": "oid-alice", "upn": "alice@siemens.com"}, "aeroview",
                        company_name="Aeroview")
    store.record_search({"oid": "oid-bob", "upn": "bob@siemens.com"}, "aeroview",
                        company_name="Aeroview")

    ov = store.admin_overview()
    assert ov["sessions"]["total"] == 3
    assert ov["users"]["total"] == 2            # distinct principals, not sign-ins
    assert ov["searches"]["total"] == 2
    assert ov["companies"]["searched"] == 1     # both searched the same company
    assert ov["top_companies"][0] == {"company": "Aeroview", "searches": 2}


# ------------------------------------------------------------- the admin gate

@pytest.fixture()
def signed_in() -> TestClient:
    client = TestClient(app)
    client.get("/api/auth/login", follow_redirects=False)
    return client


STUB_UPN = "e2e.reviewer@siemens.com"


def test_admin_routes_are_closed_when_admin_upns_is_unset(signed_in, monkeypatch):
    """Fail-closed. An unset allowlist means nobody is an admin — never everybody."""
    monkeypatch.delenv("ADMIN_UPNS", raising=False)
    for path in ("/api/runs", "/api/admin/overview", "/api/admin/searches"):
        assert signed_in.get(path).status_code == 403, path


def test_admin_routes_are_closed_to_a_non_listed_reviewer(signed_in, monkeypatch):
    monkeypatch.setenv("ADMIN_UPNS", "someone.else@siemens.com")
    assert signed_in.get("/api/admin/overview").status_code == 403


def test_a_listed_reviewer_gets_the_dashboard(signed_in, monkeypatch):
    monkeypatch.setenv("ADMIN_UPNS", f"  {STUB_UPN.upper()} , other@siemens.com ")
    assert signed_in.get("/api/admin/overview").status_code == 200
    assert signed_in.get("/api/admin/searches").status_code == 200
    assert signed_in.get("/api/runs").status_code == 200
    assert signed_in.get("/api/auth/me").json()["user"]["is_admin"] is True


def test_me_reports_non_admin_by_default(signed_in, monkeypatch):
    monkeypatch.delenv("ADMIN_UPNS", raising=False)
    assert signed_in.get("/api/auth/me").json()["user"]["is_admin"] is False


def test_my_searches_is_open_to_any_signed_in_reviewer(signed_in, monkeypatch):
    monkeypatch.delenv("ADMIN_UPNS", raising=False)
    res = signed_in.get("/api/my/searches")
    assert res.status_code == 200
    assert "runs" in res.json()


# ------------------------------------------------------------- saved views

def test_saved_views_are_scoped_to_their_owner(db):
    store.save_view("oid-alice", "Munich passes", ["company", "pillar"], {"q": "munich"})
    assert store.list_views("oid-bob") == []
    mine = store.list_views("oid-alice")
    assert len(mine) == 1
    assert mine[0]["columns"] == ["company", "pillar"]
    assert mine[0]["filters"] == {"q": "munich"}


def test_saving_over_a_name_replaces_that_view(db):
    store.save_view("oid-alice", "My view", ["a"], {"q": "x"})
    store.save_view("oid-alice", "My view", ["b"], {"q": "y"})
    views = store.list_views("oid-alice")
    assert len(views) == 1
    assert views[0]["columns"] == ["b"]


def test_deleting_someone_elses_view_does_nothing(db):
    store.save_view("oid-alice", "My view", ["a"], {})
    assert store.delete_view("oid-bob", "My view") is False
    assert len(store.list_views("oid-alice")) == 1
