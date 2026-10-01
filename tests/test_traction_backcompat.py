"""The traction rubric reaches stored runs on read, and every surface agrees on it.

Runs saved before the rubric existed carry only the model's holistic traction number. They are
scored on read rather than migrated, so the profile, the Explore grid and a fresh department
assessment must all see the same rubric value — a grid that says 90 beside a profile that says 52
would be two answers for one company.
"""
import copy
from unittest.mock import Mock

from core.judgment import DIMENSIONS, score_research
from core.traction import VERSION

# A pre-rubric run: model score only, no `traction`, no `traction_inputs`.
OLD_RUN = {
    "company": "Alpha",
    "summary": "Industrial inspection software.",
    "profile": {"funding": "€2.8M", "employees_count": "8"},
    "deep_profile": {"reference_customers": ["Bosch", "Acme Tools"]},
    "verification": {"claims": []},
}


def _model_score(value=90.0):
    entry = {"score": value, "rationale": "Model view.", "citations": ["E1"]}
    model = Mock(available=True)
    model.parse_json.return_value = {"dimensions": {k: copy.deepcopy(entry) for k in DIMENSIONS},
                                     "overall": {**entry, "score": 57.3}, "confidence": 61}
    return score_research(OLD_RUN, model)


def test_old_run_is_scored_by_the_rubric_on_read_and_the_grid_agrees():
    from api import store
    run_id = store.save_run({**OLD_RUN, "score": _model_score()})
    saved = store.get_run(run_id)
    row = next(r for r in store.list_runs() if r["id"] == run_id)
    assert saved["traction"]["version"] == VERSION
    # funding 25 + customers (Bosch big 7.5 + Acme SME 3.5) + employees 6, over 70 available
    assert saved["traction"]["score_0_100"] == round(100 * 42 / 70, 1)
    assert saved["score"]["dimensions"]["traction"] == saved["traction"]["score_0_100"]
    assert saved["score"]["traction_llm"] == 90.0
    assert row["traction"] == row["dimensions"]["traction"] == saved["traction"]["score_0_100"]


def test_a_stale_rubric_version_is_recomputed_and_a_current_one_is_kept():
    from core.traction import with_traction
    stale = with_traction({**OLD_RUN, "traction": {"version": "traction-rubric-v0", "status": "scored"}})
    assert stale["traction"]["version"] == VERSION
    current = {"version": VERSION, "status": "no_evidence", "score_0_100": None, "divisions": []}
    assert with_traction({**OLD_RUN, "traction": current})["traction"] is current


def test_a_failed_model_score_still_carries_the_rubric():
    from core.traction import with_traction
    out = with_traction({**OLD_RUN, "score": {"status": "unavailable", "dimensions": {}}})
    assert out["traction"]["status"] == "scored"
    assert out["score"] == {"status": "unavailable", "dimensions": {}}


def test_private_runs_read_through_the_same_path():
    from api import workspace
    run = workspace.private_save("traction-owner", "Alpha", {**OLD_RUN, "score": _model_score()})
    saved = workspace.private_get("traction-owner", run["run_id"])
    assert saved["traction"]["version"] == VERSION
    listed = workspace.private_list("traction-owner")[0]
    assert listed["dimensions"]["traction"] == saved["traction"]["score_0_100"]
