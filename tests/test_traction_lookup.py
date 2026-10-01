"""Funding rounds, investor profiles and headcounts looked up on request (core/traction_lookup.py).

Everything is faked — Tracxn needs a reviewer's own OAuth token and a web search costs a model
call. What is pinned is the order (Tracxn, then the model's web search, never memory) and the
grounding: a value survives only if the gathered research states it, and a web row only if it
cites a source the search used.
"""
from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from core import traction_lookup as L
from core.llm import LLMClient, _cite

WEB_TEXT = ("FUNDING ROUNDS: February 2025, Seed Round, €2.8 million, led by LEA Partners with 468 Capital [1].\n"
            "INVESTORS: LEA Partners is a private equity and venture capital firm in Karlsruhe, Germany [2].")
WEB = {"text": WEB_TEXT, "sources": [{"title": "tech.eu", "url": "https://tech.eu/a"},
                                     {"title": "pitchbook.com", "url": "https://pitchbook.com/b"}], "queries": []}
EXTRACTED = {"rounds": [
    {"date": "February 2025", "stage": "Seed Round", "amount": "€2.8 million", "lead_investors": ["LEA Partners"],
     "investors": ["468 Capital", "Sequoia"], "citations": [1]},                 # Sequoia is not in the text
    {"date": "2021", "stage": "Series A", "amount": "€40 million", "citations": [9]},   # cites nothing real
], "investors": [
    {"name": "LEA Partners", "type": "private equity and venture capital firm", "hq": "Karlsruhe, Germany",
     "focus": "B2B software", "portfolio": [], "citations": [2]},              # focus not in the text
    {"name": "Invented Ventures", "type": "venture capital firm", "citations": [2]}]}


def model(web=WEB, extracted=EXTRACTED):
    llm = Mock(available=True)
    llm.web_answer.return_value = web
    llm.complete.return_value = json.dumps(extracted)
    llm.parse_json = LLMClient.parse_json
    return llm


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(L.web, "_cached", lambda *a, **k: None)
    monkeypatch.setattr(L.web, "_store", lambda *a, **k: None)


def test_a_web_answer_keeps_only_what_the_research_states_and_cites():
    out = L.funding_details("Bliro", website="https://www.bliro.io", llm=model())
    assert out["provider"] == "web"
    [row] = out["rounds"]                                        # the uncited Series A is dropped
    assert row["amount"] == "€2.8 million" and row["lead_investors"] == ["LEA Partners"]
    assert row["investors"] == ["468 Capital"]                   # Sequoia never appeared in the research
    assert [s["url"] for s in row["sources"]] == ["https://tech.eu/a"]
    [lea] = out["investors"]                                     # an investor the research never named is dropped
    assert lea["type"] == "Private equity" and lea["type_detail"] == "private equity and venture capital firm"
    assert lea["hq"] == "Karlsruhe, Germany" and lea["focus"] == ""
    assert {s["url"] for s in out["sources"]} == {"https://tech.eu/a", "https://pitchbook.com/b"}


def test_tracxn_answers_first_and_the_web_is_not_searched():
    llm = model(extracted={"rounds": [{"date": "2025", "stage": "Seed", "amount": "USD 2.9M", "citations": []}], "investors": []})
    tracxn = Mock()
    tracxn.research.return_value = [{"tool": "company", "text": "Seed round 2025: USD 2.9M", "companies": []}]
    out = L.funding_details("Bliro", llm=llm, tracxn=tracxn)
    assert out["provider"] == "tracxn" and out["rounds"][0]["sources"] == [{"title": "Tracxn", "url": ""}]
    llm.web_answer.assert_not_called()


@pytest.mark.parametrize("tracxn_result, note", [(RuntimeError("down"), "Tracxn could not be reached"),
                                                 ([], "Tracxn had nothing on this")])
def test_tracxn_failure_or_silence_falls_back_to_web_search_and_says_so(tracxn_result, note):
    tracxn = Mock()
    if isinstance(tracxn_result, Exception):
        tracxn.research.side_effect = tracxn_result
    else:
        tracxn.research.return_value = tracxn_result
    out = L.funding_details("Bliro", llm=model(), tracxn=tracxn)
    assert out["provider"] == "web" and out["note"].startswith(note)


def test_without_web_search_nothing_is_filled_in_from_memory():
    llm = model(web=None)
    out = L.funding_details("Bliro", llm=llm)
    assert out["provider"] == "none" and out["rounds"] == [] and "never filled in from the model's memory" in out["note"]
    llm.complete.assert_not_called()


def test_a_headcount_needs_a_figure_the_research_states():
    text = "LinkedIn lists 11-50 employees as of 2025 [1]. The team is small and growing [1]."
    llm = model(web={"text": text, "sources": [{"title": "linkedin.com", "url": "https://linkedin.com/c"}], "queries": []},
                extracted={"figures": [{"count": "11-50", "as_of": "2025", "where": "LinkedIn", "citations": [1]},
                                       {"count": "small", "citations": [1]},
                                       {"count": "42", "where": "company site", "citations": [1]}]})
    out = L.headcount_details("Bliro", llm=llm)
    assert [f["count"] for f in out["figures"]] == ["11-50"]
    assert out["figures"][0]["where"] == "LinkedIn" and out["figures"][0]["sources"][0]["url"] == "https://linkedin.com/c"


def test_grounding_keeps_pages_and_drops_utility_chunks():
    text = "Rockstart is in Amsterdam."
    chunks = [{"web": {"uri": "https://x", "title": "Current time information in Munich, DE."}},
              {"web": {"uri": "https://y", "title": "rockstart.com"}}]
    cited, sources = _cite(text, [{"segment": {"endIndex": len(text)}, "groundingChunkIndices": [0, 1]}], chunks)
    assert cited == "Rockstart is in Amsterdam.[1]" and [s["url"] for s in sources] == ["https://y"]


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    """A database of the test's own: the endpoint now stores what it fetches."""
    from api import store
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setattr(store, "_restore_from_s3", lambda: None)
    monkeypatch.setattr(store, "_upload_to_s3", lambda: None)
    return store


def test_the_endpoint_uses_the_reviewers_tracxn_and_names_only_known_lookups(monkeypatch, temp_db):
    from api import main, store
    run_id = store.save_run({"company": "Lookup Test GmbH", "found": True, "profile": {"website": "https://lookup.test"}})
    seen = {}
    monkeypatch.setattr(main, "tracxn_client_for", lambda user, llm=None: "tracxn-client")
    monkeypatch.setattr(L, "lookup", lambda spec, company, **kw: seen.update(kw, spec=spec["name"], company=company) or {"provider": "tracxn"})
    client = TestClient(main.app)
    client.get("/api/auth/login", follow_redirects=False)
    headers = {"X-CSRF-Token": client.cookies.get("sea_csrf")}
    assert client.post(f"/api/runs/{run_id}/lookup/headcount", headers=headers).json() == {"provider": "tracxn"}
    assert seen == {"spec": "headcount", "company": "Lookup Test GmbH", "website": "https://lookup.test",
                    "llm": seen["llm"], "tracxn": "tracxn-client", "refresh": False}
    assert client.post(f"/api/runs/{run_id}/lookup/customers", headers=headers).status_code == 422


def test_a_fetched_lookup_is_stored_and_served_from_the_database_until_refresh(monkeypatch, temp_db):
    from api import main, store
    run_id = store.save_run({"company": "Stored Lookup GmbH", "found": True, "profile": {}})
    calls = []
    payload = {"provider": "web", "note": "", "sources": [], "rounds": [{"date": "2025", "stage": "Seed", "amount": "€2M",
               "lead_investors": ["Acme VC"], "investors": [], "sources": [{"title": "t", "url": "https://t"}]}],
               "investors": [{"name": "Acme VC", "type": "Venture capital", "hq": "Berlin", "focus": "", "portfolio": [],
                              "sources": [{"url": "https://acme.vc"}]}]}
    monkeypatch.setattr(main, "tracxn_client_for", lambda user, llm=None: None)
    monkeypatch.setattr(L, "lookup", lambda spec, company, **kw: calls.append(kw["refresh"]) or dict(payload))
    client = TestClient(main.app)
    client.get("/api/auth/login", follow_redirects=False)
    headers = {"X-CSRF-Token": client.cookies.get("sea_csrf")}
    first = client.post(f"/api/runs/{run_id}/lookup/funding", headers=headers).json()
    second = client.post(f"/api/runs/{run_id}/lookup/funding", headers=headers).json()
    assert calls == [False] and "from_store" not in first
    assert second["from_store"] is True and second["rounds"][0]["amount"] == "€2M"     # served, not searched
    client.post(f"/api/runs/{run_id}/lookup/funding?refresh=true", headers=headers)
    assert calls == [False, True]                                                     # Refresh searches again
    with store._conn() as con:
        assert con.execute("SELECT count(*) FROM enrichments WHERE kind='funding'").fetchone()[0] == 2   # history kept
        assert con.execute("SELECT amount FROM funding_rounds").fetchall() == [("€2M",)]
        assert con.execute("SELECT name, provider FROM investors").fetchall() == [("Acme VC", "web")]
