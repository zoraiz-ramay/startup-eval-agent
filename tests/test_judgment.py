import copy
from unittest.mock import Mock
import pytest
from core.judgment import score_research, department_fit, evidence_for, DIMENSIONS

RUN = {"company": "Alpha", "summary": "Industrial inspection software with two customer pilots.",
       "deep_profile": {"founders": [{"name": "Jane", "background": "Machine vision engineering"}]}}


def answer():
    citation = {"evidence_id": "E1", "quote": RUN["summary"]}
    entry = {"score": 63.7, "rationale": "Customer pilots support early traction; no measured revenue is evidenced.", "citations": [citation]}
    return {"dimensions": {k: copy.deepcopy(entry) for k in DIMENSIONS},
            "overall": {**entry, "score": 57.3}, "confidence": 61}


def llm(data):
    model = Mock(available=True); model.parse_json.return_value = data
    return model


def test_scores_are_model_judgments_not_weighted_arithmetic():
    result = score_research(RUN, llm(answer()))
    assert result["status"] == "assessed"
    assert set(result["dimensions"].values()) == {63.7}
    assert result["final_score"] == 57.3  # Not the mean or any weighted sum of identical dimensions.
    assert result["judgments"]["traction"]["evidence"][0]["quote"] == RUN["summary"]


@pytest.mark.parametrize("bad", [float("nan"), 101, -1, True, "80"])
def test_invalid_model_scores_never_become_fallback_points(bad):
    data = answer(); data["dimensions"]["traction"]["score"] = bad
    assert score_research(RUN, llm(data))["final_score"] is None


def test_fabricated_quotes_and_incomplete_dimensions_are_rejected():
    data = answer(); data["dimensions"]["traction"]["citations"][0]["quote"] = "Revenue of one billion"
    assert score_research(RUN, llm(data))["status"] == "unavailable"
    data = answer(); del data["dimensions"]["founder"]
    assert score_research(RUN, llm(data))["status"] == "unavailable"
    assert score_research(RUN, Mock(available=False))["dimensions"] == {}


def test_department_needs_and_all_research_reach_the_model():
    department = {"id":"mobility", "label":"Siemens Mobility", "interests":["rail", "fleet"]}
    data = {"criteria":{k:{"rationale":"No directly evidenced rail use case.","citations":[]} for k in ["strategic","complement","impact"]}}
    data["overall"] = {"score": 31, "rationale": "Limited evidenced rail relevance", "citations": ["E1"]}
    model = llm(data); result = department_fit(RUN, department, model)
    assert [c["id"] for c in result["criteria"]] == ["strategic","complement","impact"]
    prompt = model.complete.call_args.args[0]
    assert "rail" in prompt and "Machine vision engineering" in prompt
    assert not any("score" in e["source"] for e in evidence_for({**RUN,"score":{"final_score":99}}))


def test_assessment_endpoint_scopes_private_results_and_caches_by_needs(monkeypatch):
    from api import assessments as a
    from api.auth import Principal
    user = Principal(oid="department-judgment-test",tid="tenant",name="Reviewer",upn="reviewer@example.com",email="reviewer@example.com")
    monkeypatch.setattr(a.workspace,"private_get",lambda oid,rid: RUN if oid==user.oid else None)
    profile={"id":"di","interests":["automation"]}
    monkeypatch.setattr(a,"profiles",lambda u:{"departments":[profile]})
    score=Mock(return_value={"status":"assessed","version":a.VERSION,"dimensions":{}})
    fit=Mock(return_value={"status":"assessed", "department":profile, "score":45})
    monkeypatch.setattr(a,"score_research",score);monkeypatch.setattr(a,"department_fit",fit)
    a.assess(-123,"di",user);a.assess(-123,"di",user)
    assert score.call_count == fit.call_count == 1
    profile["interests"]=["energy"]
    a.assess(-123,"di",user)
    assert score.call_count == 1 and fit.call_count == 2


def test_judgment_calls_have_a_single_attempt_budget(monkeypatch):
    import core.llm as module
    model = module.LLMClient.__new__(module.LLMClient)
    model.available=True; model.provider="openai"; model.model="test"; model.last_error=""
    model._client=Mock()
    model._client.chat.completions.create.side_effect=TimeoutError("unreachable")
    monkeypatch.setattr(module,"LLM_CACHE",False)
    assert model.complete("scoring retry test",max_attempts=1) == ""
    assert model._client.chat.completions.create.call_count == 1


def test_evidence_id_citations_are_hydrated_from_original_research():
    data = answer()
    for entry in [*data["dimensions"].values(), data["overall"]]:
        entry["citations"] = ["E1"]
    result = score_research(RUN, llm(data))
    assert result["status"] == "assessed"
    assert result["judgments"]["traction"]["evidence"][0]["quote"] == RUN["summary"]
    data["dimensions"]["traction"]["citations"] = ["E99999"]
    assert score_research(RUN, llm(data))["status"] == "unavailable"


def test_prompt_does_not_repeat_inherited_source_urls():
    source = "https://example.com/long-research-source"
    run = {"facts":[{"value":"Customer pilot", "method":"research", "verified":True, "source_url":source}]}
    model = llm(answer())
    score_research(run, model)
    prompt = model.complete.call_args.args[0]
    assert prompt.count(source) == 1
    assert model.complete.call_args.kwargs["reasoning"] == "none"


def test_timeout_message_distinguishes_loaded_interests_from_model_failure():
    model=Mock(available=True,last_error="Request timed out.")
    model.parse_json.return_value=None
    result=department_fit(RUN,{"interests":["automation"]},model)
    assert result["reason"] == "model_timeout"
    assert "department interests are available" in result["message"]


def test_department_profile_is_valid_evidence_for_its_stated_needs():
    department={"id":"di","label":"Digital Industries","interests":["automation"],"demo":True}
    data={"criteria":{k:{"rationale":"Potential relevance to the department's automation needs.","citations":["E1","di"]} for k in ["strategic","complement","impact"]}}
    data["overall"] = {"score": 47, "rationale": "Potential automation fit", "citations": ["E1", "di"]}
    result=department_fit(RUN,department,llm(data))
    assert result["status"] == "assessed"
    cited=result["criteria"][0]["evidence"][1]
    assert cited["source"] == "Mock department interests"
    assert cited["quote"] == "Digital Industries: automation"


def test_saved_assessments_match_database_and_keep_each_department():
    from api import store
    original={**RUN,"score":{"dimensions":{"siemens_fit":10},"final_score":20}}
    run_id=store.save_run(original)
    score=score_research(RUN,llm(answer()))
    for key,points in [("di",78),("si",32)]:
        fit={"status":"assessed","department":{"id":key,"interests":[key]},"score":points}
        store.save_assessment(run_id,score,fit)
    saved=store.get_run(run_id)
    row=next(r for r in store.list_runs() if r["id"]==run_id)
    assert saved["score"]["final_score"] == row["final_score"] == 57.3
    assert saved["score"]["dimensions"]["siemens_fit"] == row["siemens_fit"] == 63.7
    assert row["department_assessments"]["di"]["score"] == 78
    assert row["department_assessments"]["si"]["score"] == 32
    assert saved["original_score"] == original["score"]
    store.save_assessment(run_id,{"status":"unavailable"},{"status":"unavailable"})
    assert store.get_run(run_id)["score"] == score


def test_private_assessment_never_changes_public_database():
    from api import workspace,store
    run=workspace.private_save("private-score-owner","Alpha",{**RUN,"score":{}})
    score=score_research(RUN,llm(answer()))
    fit={"status":"assessed","department":{"id":"di"},"score":75}
    assert workspace.private_assessment("another-user",run["run_id"],score,fit) is None
    workspace.private_assessment("private-score-owner",run["run_id"],score,fit)
    saved=workspace.private_get("private-score-owner",run["run_id"])
    assert saved["score"]==score
    row=workspace.private_list("private-score-owner")[0]
    assert row["siemens_fit"] == 63.7 and row["department_assessments"]["di"]["score"] == 75
    assert store.get_run(run["run_id"]) is None


def test_decision_uses_model_choice_and_requires_supported_next_steps():
    from core.judgment import decision_research
    data = {"pillar":"Collaborate", "recommendation":{"rationale":"Customer pilots support a joint trial; services or distribution are less useful yet.","citations":["E1"]}, "next_steps":["Identify an inspection owner.","Validate pilot outcomes."], "confidence":73}
    result = decision_research({**RUN,"score":{"final_score":1}}, llm(data))
    assert result["pillar"] == "Collaborate"  # No numeric score gates.
    assert result["evidence"][0]["quote"] == RUN["summary"]
    assert result["next_steps"] == data["next_steps"]
    data["recommendation"]["citations"] = ["invented"]
    assert decision_research(RUN, llm(data))["status"] == "unavailable"


def test_decision_persistence_preserves_scores_and_updates_database_route(tmp_path, monkeypatch):
    from api import store
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "decisions.db")
    run={**RUN,"score":{"final_score":58},"routing":{"pillar":"Empower","secondary":["Connect"],"sfs_relevant":True}}
    rid=store.save_run(run)
    saved=store.save_assessment(rid, {}, {}, {"status":"assessed","pillar":"Collaborate","secondary":[],"next_steps":["Validate pilots.","Identify owner."]})
    assert saved["score"]["final_score"] == 58
    assert saved["routing"]["sfs_relevant"] is True
    row=next(r for r in store.list_runs() if r["id"] == rid)
    assert row["pillar"] == "Collaborate" and row["secondary"] == []


def test_pass_is_a_supported_model_choice_and_not_a_missing_data_fallback():
    from core.judgment import decision_research, DECISION_VERSION
    data = {"pillar":"Pass", "recommendation":{"rationale":"The evidenced offering does not meet the identified Siemens needs.","citations":["E1"]}, "next_steps":["Close the scouting review without pursuing a pilot.","Reconsider if an industrial use case is evidenced."], "confidence":78}
    model=llm(data)
    result=decision_research(RUN, model)
    assert result["status"] == "assessed" and result["pillar"] == "Pass"
    assert result["version"] == DECISION_VERSION
    assert result["next_steps"] == data["next_steps"]
    data["recommendation"]["citations"] = []
    assert decision_research(RUN, llm(data))["status"] == "unavailable"
    data["pillar"] = "Defer"
    assert decision_research(RUN, llm(data))["pillar"] == "Defer"


def test_the_same_evidence_retrieved_at_another_time_reads_identically():
    """retrieved_at changes every run. In the records it made every prompt unique, so the LLM cache
    never hit on a re-evaluation and the model re-answered identical evidence differently — two
    replays of one company scored Siemens Fit 89 and 100."""
    from core.judgment import evidence_for
    fact = {"key": "investor", "value": "UVC Partners", "source_url": "https://press.example/round"}
    monday = {"company": "Acme", "facts": [{**fact, "retrieved_at": "2026-10-05T09:00:00+00:00"}]}
    friday = {"company": "Acme", "facts": [{**fact, "retrieved_at": "2026-10-09T17:30:00+00:00",
                                            "last_confirmed_at": "2026-10-05T09:00:00+00:00"}]}
    assert evidence_for(monday) == evidence_for(friday)
    assert any(r["text"] == "UVC Partners" for r in evidence_for(monday))
