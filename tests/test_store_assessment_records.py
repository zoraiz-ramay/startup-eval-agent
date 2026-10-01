"""What a run produces is stored row by row, not only inside `result_json`.

Every scored criterion (pillars, Team & Ecosystem, market) is per-run history; the investors the
evaluation evidenced and the Empower tool checks are current knowledge. Runs saved before those
tables existed are backfilled once — and only once, or history would double on every restart.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def store(monkeypatch, tmp_path):
    from api import store as s
    monkeypatch.setattr(s, "DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setattr(s, "_restore_from_s3", lambda: None)
    monkeypatch.setattr(s, "_upload_to_s3", lambda: None)
    return s


def run(**over):
    crit = lambda i, score: {"id": i, "label": i.title(), "score": score, "anchor": "a", "rationale": "r"}
    return {"company": "Acme Robotics", "profile": {"domain": "acme.test"},
            "deep_profile": {"commercial": {"investors": [{"name": "LEA Partners", "source_url": "https://lea.test"}]}},
            "assessment": {"pillars": {"Empower": {"criteria": [crit("tool", 2), crit("benefit", 1)], "tool_checks": [
                {"id": "tool:ghost", "name": "Ghost Suite", "status": "not_found", "note": "nothing found", "replaced": True}]}},
                "team_ecosystem": {"criteria": [crit("founders", 4)]}},
            "market": {"criteria": [crit("size", None)]}, **over}


def rows(s, sql):
    with s._conn() as con:
        return con.execute(sql).fetchall()


def test_a_saved_run_records_each_criterion_its_investors_and_its_tool_checks(store):
    run_id = store.save_run(run())
    crits = rows(store, "SELECT block, criterion, score, max FROM assessment_criteria ORDER BY block, criterion")
    assert crits == [("Empower", "benefit", 1.0, 3), ("Empower", "tool", 2.0, 3),
                     ("market", "size", None, 5), ("team_ecosystem", "founders", 4.0, 5)]
    assert rows(store, "SELECT name, provider FROM investors") == [("LEA Partners", "research")]
    assert store.list_tool_checks("not_found")[0] | {"checked_at": ""} == {
        "tool_id": "tool:ghost", "name": "Ghost Suite", "category": "", "division": "", "status": "not_found", "url": "",
        "note": "nothing found", "checked_at": "", "last_run_id": run_id, "times_recommended": 1}


def test_runs_saved_before_the_tables_existed_are_backfilled_once(store):
    run_id = store.save_run(run())
    with store._conn() as con:            # as an old database would look: the run, but none of its records
        for t in ("assessment_criteria", "investors", "tool_checks"):
            con.execute(f"DELETE FROM {t}")
    assert store.backfill_assessment_records() == 1
    assert store.backfill_assessment_records() == 0
    assert len(rows(store, f"SELECT 1 FROM assessment_criteria WHERE run_id={run_id}")) == 4
    assert rows(store, "SELECT name FROM investors") == [("LEA Partners",)]
    assert [t["times_recommended"] for t in store.list_tool_checks()] == [1]
    assert json.loads(rows(store, f"SELECT result_json FROM runs WHERE id={run_id}")[0][0])["company"] == "Acme Robotics"
