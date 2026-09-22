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
    # No exact name/domain match, but Tracxn still returned a candidate for the query — a
    # connected account's own data outranks falling through to another provider.
    assert client.company_row("Alph")["company_name"] == "Alpha"
    monkeypatch.setattr(client,"search",lambda q:[])
    assert client.company_row("Alpha") is None
    monkeypatch.setattr(client,"search",lambda q:[row,{**row,"website":"alpha.de"}])
    # Two exact-name matches: still seed from Tracxn rather than bailing out, using the first.
    assert client.company_row("Alpha")["website"] == "alpha.ai"


def test_tracxn_parses_real_nested_provider_schema(monkeypatch):
    # Shape captured live from platform.tracxn.com/mcp for a real company: website is a list of
    # {url, isPrimary}, HQ lives under locations[].city/country, employee count is nested under
    # latestEmployeeCount.value, funding under totalEquityFunding.amount.{currency}.value, and
    # LinkedIn under socialMediaProfiles.linkedin — none of them the flat field names the client
    # used to look for, which is why every one of these came back blank despite source="tracxn".
    provider_record = {
        "id": "65578d1af973523eb3280078", "name": "Radical Dot",
        "shortDescription": "Technology solution for plastic recycling",
        "website": [{"url": "https://radicaldot.com", "isPrimary": "Yes"}],
        "foundedYear": 2024,
        "locations": [{"city": {"name": "Munich"}, "state": {"name": "Bavaria"}, "country": {"name": "Germany"}}],
        "latestEmployeeCount": {"value": 17, "asOnDate": {"day": 31, "month": 7, "year": 2026}},
        "socialMediaProfiles": {"linkedin": "https://linkedin.com/company/radicaldot"},
        "totalEquityFunding": {"baseCurrency": "USD", "amount": {
            "USD": {"value": 2843478}, "EUR": {"value": 2676139}}},
    }
    row = {"name": "Radical Dot", "description": provider_record["shortDescription"], "website": "",
           "tracxn_id": provider_record["id"], "provider_record": provider_record}
    client = TracxnClient("test")
    monkeypatch.setattr(client, "search", lambda q: [row])
    result = client.company_row("Radical Dot")
    assert result["website"] == "https://radicaldot.com"
    assert result["hq"] == "Munich, Germany"
    assert result["employees_count"] == "17"
    assert result["linkedin_url"] == "https://linkedin.com/company/radicaldot"
    assert result["funding"] == "USD 2843478"
    assert result["founded_year"] == "2024"


def test_tracxn_retries_with_word_boundaries_restored(monkeypatch):
    # Tracxn's own search tools match tokenized words, not an arbitrary string: a name typed
    # without the separators its brand uses ("Radical.Dot", "RadicalDot") finds nothing even
    # though the company is indexed as "Radical Dot". The client retries once with word breaks
    # restored at unambiguous boundaries (case changes, punctuation) before giving up.
    client = TracxnClient("test")
    row = {"name": "Radical Dot", "description": "Plastic recycling", "website": "radicaldot.com",
           "tracxn_id": "9", "provider_record": {}}
    calls = []
    def fake_search(q):
        calls.append(q)
        return [row] if q == "Radical Dot" else []
    monkeypatch.setattr(client, "search", fake_search)
    assert client.company_row("Radical.Dot")["company_name"] == "Radical Dot"
    assert calls == ["Radical.Dot", "Radical Dot"]
    calls.clear()
    assert client.company_row("RadicalDot")["company_name"] == "Radical Dot"
    assert calls == ["RadicalDot", "Radical Dot"]
    # A single case/character run has no unambiguous word break to restore — retrying with
    # the same string again would just repeat the same miss, so it is not attempted.
    calls.clear()
    assert client.company_row("radicaldot") is None
    assert calls == ["radicaldot"]
    # Already-successful literal query never triggers the fallback search.
    calls.clear()
    assert client.company_row("Radical Dot")["company_name"] == "Radical Dot"
    assert calls == ["Radical Dot"]


def test_private_runs_cannot_be_read_by_another_reviewer():
    result = workspace.private_save("alice","Alpha",{"company":"Alpha","source":"tracxn"})
    assert result["run_id"] < 0
    assert workspace.private_get("bob",result["run_id"]) is None
    assert workspace.private_latest("alice","alpha")["company"] == "Alpha"
    assert workspace.private_latest("bob","Alpha") is None


def test_job_submission_is_idempotent_and_isolated(monkeypatch):
    pool = Mock(); monkeypatch.setattr(jobs,"_pool",pool)
    body = jobs.JobBody(names=["Alpha","Beta"],request_id="test-request-unique")
    a,b = user("job-a"),user("job-b")
    first = jobs.start(body,a)
    assert jobs.start(body,a) == first
    assert pool.submit.call_count == 2
    with pytest.raises(Exception) as exc:
        jobs.get_job(first["jobs"][0]["id"],b)
    assert exc.value.status_code == 404
    for _ in first["jobs"]: jobs._slots.release()


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
