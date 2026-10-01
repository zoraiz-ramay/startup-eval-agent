import json
from unittest.mock import Mock
import pandas as pd
import pytest
from api.auth import Principal, sessions
from api import workspace, jobs, interests
from core.tracxn import TracxnClient
from core.siemens_fit import assess_fit


def user(oid):
    return Principal(oid=oid, name=oid, email=oid+"@test", upn=oid+"@test", tid="test")


def test_tracxn_exact_identity_and_currency_preserved(monkeypatch):
    client = TracxnClient("test")
    row = {"name":"Alpha", "description":"Industrial inspection", "website":"alpha.ai", "tracxn_id":"1",
           "provider_record":{"foundedYear":2020,"totalFunding":{"amount":100,"currency":"USD"}}}
    monkeypatch.setattr(client,"search",lambda q:[row])
    assert client.company_row("ALPHA")["funding"] == "USD 100"
    assert client.company_row("https://alpha.ai")["founded_year"] == "2020"
    assert client.company_row("Alph") is None
    monkeypatch.setattr(client,"search",lambda q:[row,{**row,"website":"alpha.de"}])
    assert client.company_row("Alpha") is None


def test_private_runs_cannot_be_read_by_another_reviewer():
    result = workspace.private_save("alice","Alpha",{"company":"Alpha","source":"tracxn"})
    assert result["run_id"] < 0
    assert workspace.private_get("bob",result["run_id"]) is None
    assert workspace.private_latest("alice","alpha")["company"] == "Alpha"
    assert workspace.private_latest("bob","Alpha") is None


def test_job_submission_is_idempotent_and_isolated(monkeypatch):
    pool = Mock(); monkeypatch.setattr(jobs,"_pool",pool)
    body = jobs.JobBody(names=["Alpha","Beta"],request_id="test-request-unique",department_id="di")
    a,b = user("job-a"),user("job-b")
    first = jobs.start(body,a)
    assert jobs.start(body,a) == first
    assert pool.submit.call_count == 2
    # The batch's department is applied to every startup in it.
    assert {j["department_id"] for j in first["jobs"]} == {"di"}
    with pytest.raises(Exception) as exc:
        jobs.get_job(first["jobs"][0]["id"],b)
    assert exc.value.status_code == 404
    for _ in first["jobs"]: jobs._slots.release()


def test_an_evaluation_batch_without_a_department_is_refused_before_anything_queues(monkeypatch):
    pool = Mock(); monkeypatch.setattr(jobs,"_pool",pool)
    for department in (None, "no-such-department"):
        body = jobs.JobBody(names=["Alpha"],request_id=f"no-dept-{department}",department_id=department)
        with pytest.raises(Exception) as exc:
            jobs.start(body,user("job-c"))
        assert exc.value.status_code == 422
    assert pool.submit.call_count == 0


def test_batch_limit_is_enforced_server_side():
    with pytest.raises(ValueError):
        jobs.JobBody(names=[str(i) for i in range(11)],request_id="batch-validation")


def test_rubric_rejects_fabricated_citations_and_caps_self_claims():
    text="We provide industrial inspection software for production lines."
    row=pd.Series({"short_description":text})
    llm=Mock(available=True)
    llm.parse_json.return_value={"criteria":[
        {"criterion":"strategic","level":4,"evidence_id":"E0","quote":text,"rationale":"Specific use case"},
        {"criterion":"impact","level":4,"evidence_id":"E0","quote":"Reduced costs by 40%"}]}
    result=assess_fit(row,{},[],llm)
    assert result["criteria"][0]["level"] == 3
    assert next(c for c in result["criteria"] if c["id"]=="impact")["points"] == 0
    assert result["score"] == sum(c["points"] for c in result["criteria"])


def test_unknown_rubric_does_not_invent_evidence():
    result=assess_fit(pd.Series(dtype=str),{},[],None)
    assert result["score"] == 0
    assert result["evidence_coverage"] == 0
    assert all(not c["evidence"] for c in result["criteria"])


def test_department_score_is_explicit_and_does_not_change_canonical_score():
    run={"summary":"Industrial inspection software", "fit":{"rubric":{"score":80}}}
    result=interests.interest_score(run,{"interests":["inspection","energy"]})
    assert result["score"] == 62
    assert result["matched"] == ["inspection"]
    assert run["fit"]["rubric"]["score"] == 80
    assert interests.interest_score(None,{"interests":["energy"]})["score"] is None


def test_provider_row_skips_glassdollar_resolution(monkeypatch):
    from core import pipeline, glassdollar_api
    client=Mock(); client.company_row.return_value=pd.Series({"company_name":"Alpha","tracxn_id":"1","website":"alpha.ai"})
    gd=Mock(side_effect=AssertionError("GlassDollar should be skipped")); monkeypatch.setattr(glassdollar_api,"search_as_df",gd)
    monkeypatch.setattr(pipeline,"load_siemens_tools",lambda _:[])
    # Stop at enrichment: identity resolution must already have emitted the Tracxn identity.
    monkeypatch.setattr(pipeline,"enrich",Mock(side_effect=RuntimeError("stop after identity")))
    events=[]
    with pytest.raises(RuntimeError,match="stop after identity"):
        pipeline.evaluate("Alpha",None,"",tracxn=client,on_partial=lambda s,d:events.append((s,d)))
    assert events[0] == ("identity",{"company":"Alpha","source":"tracxn"})
    gd.assert_not_called()


def test_background_job_publishes_partial_and_complete_without_browser(monkeypatch):
    from api import main
    principal=user("worker-test")
    record={"id":"worker-id","kind":"evaluate","query":"Alpha","status":"queued"}
    sessions().put(jobs._key(principal.oid,record["id"]),record,60)
    monkeypatch.setattr(main,"_evaluation_cached",lambda *args:None)
    def evaluate(name, body, reviewer, on_partial, user):
        on_partial("identity",{"company":"Alpha","source":"tracxn"})
        assert jobs.get_job("worker-id",principal)["partial"]["company"] == "Alpha"
        return {"company":"Alpha","run_id":-123}
    monkeypatch.setattr(main,"_run_evaluation",evaluate)
    jobs._slots.acquire()
    jobs._execute(principal.oid,"worker-id",jobs.JobBody(names=["Alpha"],request_id="worker-request"),principal)
    final=jobs.get_job("worker-id",principal)
    assert final["status"] == "complete" and final["result"]["run_id"] == -123


def test_applicants_rank_above_higher_scoring_external_candidates(monkeypatch):
    from core import solve
    monkeypatch.setattr(solve,"save_challenge",lambda *a:None)
    monkeypatch.setattr(solve,"_derive_keywords",lambda *a:["inspection"])
    base={"description":"Inspection", "website":"", "name":"Applicant", "source":"applications"}
    monkeypatch.setattr(solve,"_application_candidates",lambda *a:[base])
    monkeypatch.setattr(solve,"_rank",lambda p,cs,llm:[{**c,"relevance":40 if c["source"]=="applications" else 95} for c in cs])
    tracxn=Mock(); tracxn.search.return_value=[{**base,"name":"External","source":"tracxn"}]
    result=solve.solve_problem("inspection",tracxn=tracxn,do_web=False)
    assert [c["source"] for c in result["candidates"]] == ["applications","tracxn"]
