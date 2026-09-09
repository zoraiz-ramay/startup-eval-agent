"""Who gets credited for a pillar override.

This is the reason the app has sign-in at all. Overrides change a partnership routing
decision, and before Entra ID the reviewer was a string the client chose — so the audit
trail recorded assertions, not facts.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api import store
from api.auth import STUB_PRINCIPAL
from api.main import app


@pytest.fixture()
def client() -> TestClient:
    c = TestClient(app)
    c.get("/api/auth/login", follow_redirects=False)
    return c


@pytest.fixture()
def run_id() -> int:
    return store.save_run({
        "company": "Attribution Test GmbH",
        "engine": "test",
        "routing": {"pillar": "Collaborate", "secondary": []},
        "score": {"final_score": 50.0},
    })


def _post_override(client: TestClient, run_id: int, body: dict):
    return client.post(f"/api/runs/{run_id}/override", json=body,
                       headers={"X-CSRF-Token": client.cookies.get("sea_csrf")})


def test_retired_override_endpoint_does_not_write(client, run_id):
    before = store.list_overrides(run_id)
    res = _post_override(client, run_id, {"new_pillar": "Connect", "reason": "retired control"})
    assert res.status_code == 410
    assert store.list_overrides(run_id) == before


def test_legacy_rows_keep_their_text_and_stay_unverified(run_id):
    """Rows written before sign-in existed carry a free-text reviewer and NULL identity
    columns. Reading them must not quietly promote them to verified."""
    with store._conn() as con:
        con.execute(
            "INSERT INTO overrides (run_id, prev_pillar, new_pillar, reason, evidence_note, "
            "reviewer, created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, "Connect", "Pass", "recorded before SSO", "", "Legacy Name",
             "2025-01-01T00:00:00+00:00"))

    legacy = [o for o in store.list_overrides(run_id) if o["reason"] == "recorded before SSO"]
    assert len(legacy) == 1
    assert legacy[0]["reviewer"] == "Legacy Name"
    assert legacy[0]["verified"] is False
    assert legacy[0]["reviewer_oid"] == ""


def test_overrides_are_refused_without_a_session(run_id):
    anon = TestClient(app)
    res = anon.post(f"/api/runs/{run_id}/override",
                    json={"new_pillar": "Pass", "reason": "should never be recorded"})
    assert res.status_code == 401
    assert all(o["reason"] != "should never be recorded" for o in store.list_overrides(run_id))
