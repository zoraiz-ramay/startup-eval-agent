"""Department runs — the storage and API contract.

A new evaluation is assessed for EVERY department and filed under department "*"; a cache hit must
match company, rubric and every department's catalog. Older one-department runs stay readable, are
never overwritten, and their research may seed a new all-departments run — always a new run.
"""
import uuid

import pytest
from fastapi import HTTPException

from api import main, store, workspace
from api.auth import Principal


def user(oid="dept-reviewer"):
    return Principal(oid=oid, name=oid, email=oid + "@test", upn=oid + "@test", tid="test")


def dept_run(company, dep_id, key="k1", total=None, label=None):
    return {"found": True, "company": company, "summary": f"{company} does inspection",
            "department": {"id": dep_id, "label": label or dep_id.upper(), "interests": ["automation"], "demo": True},
            "assessment": {"assessment_key": key, "siemens_fit": {"score": 60, "status": "assessed"},
                           "team_ecosystem": {"status": "unassessed"}},
            "routing": {"pillar": "Defer"}, "score": {"final_score": total, "dimensions": {}}}


def test_two_departments_are_two_runs_and_neither_overwrites_the_other():
    name = f"Acme-{uuid.uuid4().hex[:6]}"
    di = store.save_run(dept_run(name, "di"))
    si = store.save_run(dept_run(name, "si"))
    assert store.latest_department_run(name, "di")["run_id"] == di
    assert store.latest_department_run(name, "si")["run_id"] == si
    assert store.latest_department_run(name, "mobility") is None
    by_dep = {r["department_id"]: r["run_id"] for r in store.company_department_runs(name)}
    assert by_dep == {"di": di, "si": si}


def test_a_cache_hit_must_match_the_assessment_key():
    name = f"Keyed-{uuid.uuid4().hex[:6]}"
    store.save_run(dept_run(name, "di", key="rubric-v1|old"))
    assert store.latest_department_run(name, "di", "rubric-v1|old") is not None
    assert store.latest_department_run(name, "di", "rubric-v1|new") is None


def test_the_database_list_has_one_row_per_company_and_department_and_labels_legacy_runs():
    name = f"Grid-{uuid.uuid4().hex[:6]}"
    legacy_id = store.save_run({"found": True, "company": name, "score": {"final_score": 50, "dimensions": {}},
                                "routing": {"pillar": "Empower"}})
    store.save_run(dept_run(name, "di", label="Digital Industries"))
    store.save_run(dept_run(name, "si"))
    rows = [r for r in store.list_runs(limit=500) if r["company"] == name]
    assert {(r["department_id"], r["legacy"]) for r in rows} == {("", True), ("di", False), ("si", False)}
    legacy = next(r for r in rows if r["id"] == legacy_id)
    assert legacy["total_status"] == "" and legacy["department_label"] == ""
    di = next(r for r in rows if r["department_id"] == "di")
    assert di["department_label"] == "Digital Industries" and di["total_status"] == "pending"
    reviewer = user(f"grid-{uuid.uuid4().hex[:6]}")
    store.record_search(reviewer.as_reviewer(), name, company_name=name, run_id=legacy_id)
    mine = [r for r in store.list_user_runs(reviewer.oid) if r["company"] == name]
    assert sorted(r["department_id"] for r in mine) == ["", "di", "si"]


def all_run(company, key):
    """An all-departments run as core.assessment.build_all shapes it, headed by DI."""
    return {**dept_run(company, "di"), "departments": {"scope": "all", "recommended": "di",
                                                        "assessment_key": key, "ranked": []}}


def test_an_evaluation_needs_no_department_and_an_old_clients_id_is_ignored():
    body = main.EvaluateBody(name=f"Nobody-{uuid.uuid4().hex[:6]}", department_id="not-a-department")
    assert main._evaluation_cached(body.name, body, user()) is None        # a miss, not a 422
    with pytest.raises(HTTPException) as exc:                              # legacy per-department routes
        main._department("not-a-department", user())
    assert exc.value.status_code == 422


def test_the_cached_evaluation_is_an_all_departments_run_at_the_current_key():
    name = f"Cache-{uuid.uuid4().hex[:6]}"
    key = main._all_key(main._all_departments(user()))
    store.save_run(dept_run(name, "di", key=main._current_key(main._department("di", user()))), aliases=[name])
    assert main._evaluation_cached(name, main.EvaluateBody(name=name), user()) is None   # one department only
    run_id = store.save_run(all_run(name, key), aliases=[name])
    hit = main._evaluation_cached(name, main.EvaluateBody(name=name), user())
    assert hit["run_id"] == run_id and hit["cached"] is True
    assert main._evaluation_cached(name, main.EvaluateBody(name=name, refresh=True), user()) is None


def test_a_change_to_any_departments_needs_makes_the_cached_run_stale(monkeypatch):
    name = f"Stale-{uuid.uuid4().hex[:6]}"
    store.save_run(all_run(name, main._all_key(main._all_departments(user()))), aliases=[name])
    from core import catalogs
    real = catalogs.department_catalog
    monkeypatch.setattr(catalogs, "department_catalog",
                        lambda d: {**real(d), "checksum": "changed"} if d["id"] == "mobility" else real(d))
    assert main._evaluation_cached(name, main.EvaluateBody(name=name), user()) is None


def test_fresh_research_is_reassessed_for_every_department_as_a_new_run(monkeypatch):
    name = f"Reuse-{uuid.uuid4().hex[:6]}"
    source = store.save_run(dept_run(name, "di"), aliases=[name])
    seen = {}

    def fake_assess(result, departments, llm=None, do_web=True):
        seen.update(source=result.get("run_id"), departments=[d["id"] for d in departments])
        return all_run(name, "k-all")
    import core.pipeline
    monkeypatch.setattr(core.pipeline, "assess_departments", fake_assess)
    monkeypatch.setattr(main, "tracxn_client_for", lambda *a, **k: None)
    res = main._run_evaluation(name, main.EvaluateBody(name=name), user().as_reviewer(), user=user())
    assert seen["source"] == source and res["run_id"] != source
    assert seen["departments"] == [d["id"] for d in main._all_departments(user())]
    assert store.get_run(source)["department"]["id"] == "di"          # the source is untouched
    assert store.latest_department_run(name, "*", "k-all")["run_id"] == res["run_id"]


def test_switching_department_offers_a_run_or_creates_one_and_never_rewrites(monkeypatch):
    name = f"Switch-{uuid.uuid4().hex[:6]}"
    dep = main._department("di", user())
    di = store.save_run(dept_run(name, "di", key=main._current_key(dep)), aliases=[name])
    listing = main.run_departments(di, user())
    rows = {d["id"]: d for d in listing["departments"]}
    assert rows["di"]["run_id"] == di and rows["di"]["current"] is True
    assert rows["si"]["run_id"] is None and listing["legacy"] is False
    import core.pipeline
    monkeypatch.setattr(core.pipeline, "assess_department",
                        lambda result, department, llm=None, do_web=True: dept_run(name, department["id"], key="new"))
    created = main.run_assess_department(di, "si", user())
    assert created["run_id"] not in (None, di) and created["department"]["id"] == "si"
    assert store.get_run(di)["department"]["id"] == "di"


def test_private_runs_are_kept_per_department_too():
    oid = f"private-{uuid.uuid4().hex[:6]}"
    a = workspace.private_save(oid, "Acme", dept_run("Acme", "di", key="k"))
    assert workspace.private_latest(oid, "Acme", "di")["run_id"] == a["run_id"]
    assert workspace.private_latest(oid, "Acme", "si") is None
    assert workspace.private_latest(oid, "Acme", "di", assessment_key="other") is None
    assert workspace.private_list(oid)[0]["department_id"] == "di"


def test_the_old_department_fit_endpoint_refuses_a_department_run():
    from api import assessments
    run_id = store.save_run(dept_run(f"Guard-{uuid.uuid4().hex[:6]}", "di"))
    with pytest.raises(HTTPException) as exc:
        assessments.assess(run_id, "di", user())
    assert exc.value.status_code == 409


def _pillars_stub(result, department, llm, do_web=True):
    from core.pillars import ORDER, unassessed
    ps = {p: unassessed(p, "x", "x") for p in ORDER}
    ps["Empower"] = {"pillar": "Empower", "status": "assessed", "total": 7, "band": "strong",
                     "criteria": [{"id": k, "label": k, "score": s, "evidence": [], "catalog": []}
                                  for k, s in (("tool_fit", 3), ("benefit_fit", 2), ("actionability", 2))],
                     "evidence_coverage": 0, "next_step": "x", "statement": "x"}
    from core.pillars import siemens_fit, recommend
    return {"version": "v", "pillars": ps, "catalogs": {}, "siemens_fit": siemens_fit(ps), "recommendation": recommend(ps)}


@pytest.mark.parametrize("source_score, rescored", [
    ({"status": "unavailable", "dimensions": {}}, True),                                   # no market to reuse
    ({"version": "llm-judgment-v1", "status": "assessed", "final_score": 60,
      "dimensions": {"market": 70, "traction": 50}}, False),                              # current: reused
])
def test_reusing_research_rescores_the_model_only_when_the_source_has_no_current_score(monkeypatch, source_score, rescored):
    import core.judgment, core.pillar_match, core.team_ecosystem, core.market
    from core.pipeline import assess_department
    calls = []
    monkeypatch.setattr(core.judgment, "score_research", lambda run, llm: calls.append(1) or
                        {"version": "llm-judgment-v1", "status": "assessed", "final_score": 61,
                         "dimensions": {"market": 72, "traction": 40}})
    monkeypatch.setattr(core.pillar_match, "assess_pillars", _pillars_stub)
    monkeypatch.setattr(core.team_ecosystem, "assess_team",
                        lambda run, llm: {"version": core.team_ecosystem.VERSION, "status": "assessed", "score_0_100": 60})
    monkeypatch.setattr(core.market, "assess_market",
                        lambda run, llm: {"version": core.market.VERSION, "status": "assessed", "score_0_100": 66.7})
    source = {"found": True, "company": "Acme", "score": source_score,
              "traction": {"version": "traction-rubric-v2", "status": "scored", "score_0_100": 80.0,
                           "earned": 56, "available_max": 70, "divisions_known": 3, "divisions": []}}
    out = assess_department(source, {"id": "si", "label": "SI", "interests": ["grid"], "demo": True}, llm=object())
    assert bool(calls) is rescored
    # Market in the total is the market rubric; the model's own market number is a diagnostic.
    assert out["assessment"]["components"] == {"traction": 80.0, "siemens_fit": 78.0, "team_ecosystem": 60.0, "market": 66.7}
    assert out["assessment"]["total"] == round(0.3 * 80 + 0.35 * 78 + 0.2 * 60 + 0.15 * 66.7, 1)
    assert out["score"]["llm_market"] == (72 if rescored else 70)
    assert out["assessment"]["market_method"] == "rubric"
