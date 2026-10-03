"""Every evaluation is assessed for every department and recommends one for Collaborate.

The reviewer used to choose a department before searching, which asks them to guess the answer to
one of the questions the evaluation exists to answer. Research, Empower and Connect do not depend on
the department; only Collaborate does (it matches the startup against that department's stated
needs), so a run scores Collaborate per department and is headed by the one it answers best.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import assessment, pillar_match  # noqa: E402
from tests.test_evaluate_stream import offline, _run  # noqa: E402,F401  (fixture reuse)

DEPS = [{"id": "di", "label": "Digital Industries", "interests": ["automation"], "demo": True},
        {"id": "si", "label": "Smart Infrastructure", "interests": ["buildings"], "demo": True},
        {"id": "mobility", "label": "Siemens Mobility", "interests": ["rail"], "demo": True}]


def _pillar(name, total, needs=()):
    band = "strong" if total >= 7 else "review" if total >= 4 else "no_match"
    scores = [min(3, max(0, total - 3 * i)) for i in range(3)]            # three criteria, as validated
    return {"pillar": name, "status": "assessed", "total": total, "band": band, "next_step": "",
            "evidence_coverage": 1.0,
            "criteria": [{"id": f"c{i}", "label": f"C{i}", "score": sc, "rationale": "", "evidence": [],
                          "catalog": [{"id": f"need:{n}"} for n in needs] if i == 0 else []}
                         for i, sc in enumerate(scores)]}


def _results(collab: dict):
    """Packaged pillar results per department: shared Empower/Connect, that department's Collaborate."""
    out = {}
    for d in DEPS:
        state = pillar_match.prepare_pillars({}, d, llm=None, do_web=False)
        c = collab.get(d["id"])
        out[d["id"]] = pillar_match.package_pillars(state, {
            "Empower": _pillar("Empower", 5), "Connect": _pillar("Connect", 3),
            "Collaborate": c if c is not None else {"pillar": "Collaborate", "status": "unassessed",
                                                    "total": None, "band": None, "criteria": []}})
    return out


BASE = {"found": True, "company": "Acme", "score": {"dimensions": {}}, "routing": {},
        # Traction is recomputed from its inputs on every read, so the fixture carries inputs.
        "traction_inputs": {"origin": "GlassDollar", "funding": "5000000", "employees_count": "40"}}
TEAM = {"status": "assessed", "score_0_100": 70, "points": 14}
MARKET = {"status": "assessed", "score_0_100": 50}


def test_the_department_whose_needs_it_answers_best_heads_the_run():
    out = assessment.build_all(BASE, DEPS, _results({"di": _pillar("Collaborate", 4, ["a"]),
                                                     "mobility": _pillar("Collaborate", 8, ["x", "y"])}), TEAM)
    block = out["departments"]
    assert block["recommended"] == "mobility" and block["basis"] == "collaborate"
    assert [e["department"]["id"] for e in block["ranked"]] == ["mobility", "di", "si"]
    assert out["department"]["id"] == "mobility"                       # the headline is the recommendation
    assert out["assessment"]["pillars"]["Collaborate"]["total"] == 8


def test_a_tie_goes_to_the_department_with_more_of_its_needs_answered():
    out = assessment.build_all(BASE, DEPS, _results({"di": _pillar("Collaborate", 6, ["a"]),
                                                     "si": _pillar("Collaborate", 6, ["a", "b", "c"])}), TEAM)
    assert out["departments"]["recommended"] == "si"


def test_no_collaborate_assessment_recommends_nothing_rather_than_the_first_department():
    out = assessment.build_all(BASE, DEPS, _results({}), TEAM)
    assert out["departments"]["recommended"] is None
    assert out["departments"]["basis"] == "no_collaborate_assessment"


def test_every_department_carries_its_own_total_and_they_differ_only_by_collaborate():
    out = assessment.build_all(BASE, DEPS, _results({"di": _pillar("Collaborate", 9, ["a"])}), TEAM, MARKET)
    by_id = {e["department"]["id"]: e for e in out["departments"]["ranked"]}
    # DI's Collaborate (9/9) beats the shared Empower (5/9), so its Siemens Fit is higher.
    assert by_id["di"]["assessment"]["siemens_fit"]["score"] == 100
    assert by_id["si"]["assessment"]["siemens_fit"]["score"] == round(100 * 5 / 9)
    assert by_id["di"]["score"]["final_score"] != by_id["si"]["score"]["final_score"]


def test_reading_a_stored_run_recomputes_every_departments_total():
    out = assessment.build_all(BASE, DEPS, _results({"di": _pillar("Collaborate", 9, ["a"])}), TEAM, MARKET)
    stale = {**out, "departments": {**out["departments"], "ranked": [
        {**e, "score": {"final_score": -1}} for e in out["departments"]["ranked"]]}}
    fresh = assessment.hydrate(stale)
    assert all(e["score"]["final_score"] != -1 for e in fresh["departments"]["ranked"])


def test_the_cache_key_covers_every_departments_needs():
    cats = {"siemens_tools": {"checksum": "t"}, "xcelerator": {"checksum": "x"}}
    a = assessment.all_departments_key(cats, {"di": {"checksum": "1"}, "si": {"checksum": "2"}})
    b = assessment.all_departments_key(cats, {"di": {"checksum": "1"}, "si": {"checksum": "3"}})
    assert a != b


def test_an_evaluation_for_all_departments_runs_collaborate_once_per_department(offline, monkeypatch):
    from core import pipeline
    df, tools = offline
    calls = []
    real = pipeline._pillar_after

    def spy(prep, pillar, run, llm, department=None):
        calls.append((pillar, (department or {}).get("id")))
        return real(prep, pillar, run, llm, department)

    monkeypatch.setattr(pipeline, "_pillar_after", spy)
    result = _run(df, tools, departments=DEPS)
    # The first department reuses the prepared state as is (None); the others switch catalogs.
    assert sorted(str(d) for p, d in calls if p == "Collaborate") == ["None", "mobility", "si"]
    assert sorted(p for p, _ in calls if p != "Collaborate") == ["Connect", "Empower"]   # once each
    assert [e["department"]["id"] for e in result["departments"]["ranked"]] == ["di", "si", "mobility"]
