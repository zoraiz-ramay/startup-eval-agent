"""The assistant's source order: Tracxn first, the model's own web search second, never DuckDuckGo.

Everything here is faked — Tracxn only resolves with a reviewer's own OAuth token, and a real web
search costs a model call — so what is pinned is the routing and the labelling: an answer says
where it came from, and a model answering from memory is never presented as a searched one.
"""
from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from core import chat, web
from core.llm import LLMClient, _cite
from core.tracxn import TracxnClient, TracxnError


@pytest.fixture(autouse=True)
def no_duckduckgo(monkeypatch):
    """Any DuckDuckGo call from the assistant path fails the test."""
    def refuse(*a, **k):
        raise AssertionError("the assistant must not use DuckDuckGo")
    monkeypatch.setattr(web, "ddg_search", refuse)
    monkeypatch.setattr(web, "_ddg_many", refuse)
    monkeypatch.setattr(chat, "ddg_search", refuse)


def model(web_result=None, text="From memory."):
    llm = Mock(available=True, last_error="")
    llm.complete.return_value = text
    llm.web_answer.return_value = web_result
    return llm


WEB = {"text": "Radical Dot raised a seed round [1].", "sources": [{"title": "eu-startups.com", "url": "https://eu-startups.com/x"}], "queries": ["Radical Dot funding"]}


def test_a_connected_tracxn_answers_first_and_the_web_is_not_searched():
    llm = model(WEB, text="Tracxn lists Radical Dot as a seed-stage chemical recycler.")
    tracxn = Mock()
    tracxn.research.return_value = [{"tool": "get_company", "text": '{"name": "Radical Dot"}',
                                     "companies": [{"name": "Radical Dot", "website": "radicaldot.com", "description": "Oxolysis"}]}]
    out = chat.chat_assistant("What does Radical Dot do?", llm=llm, tracxn=tracxn, context_company="Radical Dot")
    assert out["provider"] == "tracxn" and out["source"] == "Tracxn"
    assert out["evidence"][0]["title"] == "Radical Dot"
    llm.web_answer.assert_not_called()
    assert "Startup in focus: Radical Dot" in tracxn.research.call_args.args[0]


@pytest.mark.parametrize("tracxn_result, note", [
    (TracxnError("down"), "Tracxn could not be reached"),
    ([], "Tracxn had no data on this"),
])
def test_tracxn_failure_or_silence_falls_back_to_web_search_and_says_so(tracxn_result, note):
    tracxn = Mock()
    if isinstance(tracxn_result, Exception):
        tracxn.research.side_effect = tracxn_result
    else:
        tracxn.research.return_value = tracxn_result
    out = chat.chat_assistant("Radical Dot funding?", llm=model(WEB), tracxn=tracxn)
    assert out["provider"] == "web" and out["evidence"][0]["url"] == "https://eu-startups.com/x"
    assert out["note"].startswith(note)


def test_without_tracxn_the_models_web_search_answers_with_its_citations():
    llm = model(WEB)
    out = chat.chat_assistant("Who competes with Radical Dot?", llm=llm, history=[
        {"role": "user", "text": "Tell me about Radical Dot"}, {"role": "assistant", "text": "A chemical recycler."}])
    assert out["source"] == "Web search (AI)" and out["note"] == ""
    prompt = llm.web_answer.call_args.args[0]
    assert "Reviewer: Tell me about Radical Dot" in prompt and "Assistant: A chemical recycler." in prompt


def test_a_model_that_cannot_search_is_labelled_unverified_not_web():
    out = chat.chat_assistant("Market size of chemical recycling?", llm=model(None))
    assert out["provider"] == "model" and out["evidence"] == []
    assert "unverified" in out["source"] and "not available" in out["note"]


def test_no_model_says_so():
    out = chat.chat_assistant("Anything", llm=Mock(available=False))
    assert out["provider"] == "none"


# ------------------------------------------------------------------ the evaluation in focus

RUN = {"company": "Radical Dot", "summary": "Chemical recycling of mixed plastic waste.",
       "profile": {"hq": "Munich, DE", "funding": "€2.8M"},
       "profile_sources": {"hq": {"origin": "web", "url": "https://radicaldot.com/about"}},
       "deep_profile": {"commercial": {"investors": [{"name": "UVC Partners", "source_url": "https://uvc.test/news"},
                                                     {"name": "None", "source_url": "https://x.test"}]},
                        "founders": [{"name": "Andreas Wagner", "role": "CEO", "source_url": "https://radicaldot.com/team"}]},
       "trend": {"landscape": {"competitors": [{"name": "BlueAlp", "note": "Plastic upcycling", "source_url": "https://bluealp.test"}],
                               "market_size": {"value": "$15B", "cagr": "None", "as_of": "2030", "source_url": "https://m.test"}}}}


def test_the_brief_is_the_runs_sourced_facts_each_with_its_source_and_no_placeholder_values():
    text, facts = chat.run_brief(RUN)
    by_text = {f["text"]: f for f in facts}
    assert by_text["Investor: UVC Partners"]["url"] == "https://uvc.test/news"
    assert by_text["Headquarters: Munich, DE"]["url"] == "https://radicaldot.com/about"
    assert by_text["Market size $15B (as of 2030)"]["url"] == "https://m.test"     # "None" CAGR left out
    assert "Investor: None" not in by_text
    assert text.startswith("R1: Radical Dot: Chemical recycling") and all(f["id"] in text for f in facts)


def test_a_question_the_evaluation_answers_is_answered_from_it_without_any_search():
    _, facts = chat.run_brief(RUN)
    rid = next(f["id"] for f in facts if f["text"] == "Investor: UVC Partners")
    llm = model(WEB, text=f"Radical Dot is backed by UVC Partners [{rid}].\n- Its HQ is Munich [R2].")
    tracxn = Mock()
    out = chat.chat_assistant("Who funds it?", llm=llm, tracxn=tracxn, context_company="Radical Dot", run_facts=facts)
    assert out["provider"] == "run" and out["source"] == "This evaluation"
    assert out["answer"] == "Radical Dot is backed by UVC Partners [1].\n- Its HQ is Munich [2]."   # renumbered like a web answer
    assert [e["url"] for e in out["evidence"]] == ["https://uvc.test/news", "https://radicaldot.com/about"]
    llm.web_answer.assert_not_called()
    tracxn.research.assert_not_called()
    assert llm.complete.call_args.kwargs["reasoning"] == "none"


def test_grouped_citations_are_split_and_linked_like_single_ones():
    _, facts = chat.run_brief(RUN)
    llm = model(WEB, text="Backed by UVC Partners and led by Andreas Wagner [R7, R6].")
    out = chat.chat_assistant("Who funds and runs it?", llm=llm, run_facts=facts)
    assert out["answer"] == "Backed by UVC Partners and led by Andreas Wagner [1][2]."
    assert len(out["evidence"]) == 2


def test_when_the_facts_do_not_answer_the_model_names_a_better_search_and_it_is_used():
    _, facts = chat.run_brief(RUN)
    llm = model(WEB, text="SEARCH: Radical Dot Oxolysis pilot plant news 2026")
    out = chat.chat_assistant("Any news this month?", llm=llm, context_company="Radical Dot", run_facts=facts)
    assert out["provider"] == "web"
    prompt = llm.web_answer.call_args.args[0]
    assert "Suggested search: Radical Dot Oxolysis pilot plant news 2026" in prompt
    assert "Investor: UVC Partners" not in prompt               # only the headline facts travel to the search
    assert llm.web_answer.call_args.kwargs["thinking_budget"] == chat.CHAT_SEARCH_THINKING


def test_the_suggested_search_always_names_the_startup():
    _, facts = chat.run_brief(RUN)
    llm = model(WEB, text="SEARCH: top risks chemical recycling startups")
    chat.chat_assistant("What are the top risks?", llm=llm, context_company="Radical Dot", run_facts=facts)
    assert "Suggested search: Radical Dot top risks chemical recycling startups" in llm.web_answer.call_args.args[0]


def test_a_half_answer_searches_for_what_it_says_is_missing():
    _, facts = chat.run_brief(RUN)
    llm = model(WEB, text="The market is $15B [R4].\nNot covered: the market's growth rate.")
    out = chat.chat_assistant("How big is its market and how fast is it growing?", llm=llm,
                              context_company="Radical Dot", run_facts=facts)
    assert out["provider"] == "web"
    assert "Suggested search: Radical Dot the market's growth rate." in llm.web_answer.call_args.args[0]


def test_a_grounded_answer_written_twice_is_shown_once():
    from core.llm import _drop_repeat
    once = "No specific risks for Radical Dot were found in the results. General risks:\n- Feedstock [1]."
    assert _drop_repeat(once + "\n\nNot covered: x." + once) == once + "\n\nNot covered: x."
    assert _drop_repeat(once) == once


def test_an_answer_that_cites_no_fact_is_not_shown_as_the_evaluations():
    _, facts = chat.run_brief(RUN)
    out = chat.chat_assistant("Who funds it?", llm=model(WEB, text="Probably some VCs."), run_facts=facts)
    assert out["provider"] == "web"                                   # fell through to a sourced search


def test_the_history_resent_with_each_question_is_short():
    history = [{"role": "assistant" if i % 2 else "user", "text": "x" * 2000} for i in range(10)]
    ctx = chat._conversation(history)
    assert ctx.count("Reviewer:") + ctx.count("Assistant:") == 4
    assert len(ctx) < 2200


# ------------------------------------------------------------------ Tracxn research planning

def rpc_script(tools, results):
    """initialize, initialized, tools/list, then one reply per tools/call."""
    return Mock(side_effect=[{"protocolVersion": "2025-03-26"}, {}, {"tools": tools}, *results])


def test_research_runs_only_read_only_tools_with_schema_valid_arguments(monkeypatch):
    tools = [
        {"name": "get_company_profile", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "search_companies", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        {"name": "update_watchlist", "inputSchema": {"type": "object"}},
    ]
    llm = Mock(available=True)
    llm.complete.return_value = json.dumps({"calls": [
        {"name": "update_watchlist", "arguments": {}},                 # mutating: never listed, never called
        {"name": "get_company_profile", "arguments": {"name": 7}},     # fails its schema: dropped
        {"name": "search_companies", "arguments": {"query": "chemical recycling"}}]})
    llm.parse_json = LLMClient.parse_json
    client = TracxnClient("never-log-this", llm=llm)
    rpc = rpc_script(tools, [{"content": [{"type": "text", "text": json.dumps({"companies": [{"name": "Alpha", "description": "Pyrolysis"}]})}]}])
    monkeypatch.setattr(client, "_rpc", rpc)
    out = client.research("Who competes with Radical Dot?")
    calls = [c.args[1] for c in rpc.call_args_list if c.args[0] == "tools/call"]
    assert calls == [{"name": "search_companies", "arguments": {"query": "chemical recycling"}}]
    assert out[0]["tool"] == "search_companies" and out[0]["companies"][0]["name"] == "Alpha"
    assert "update_watchlist" not in llm.complete.call_args.args[0]


def test_research_without_a_model_refuses_rather_than_guessing():
    with pytest.raises(TracxnError):
        TracxnClient("never-log-this").research("anything")


# ------------------------------------------------------------------ Gemini citations

def test_citations_land_on_utf8_byte_offsets_and_number_sources_in_citation_order():
    text = "Radical Dot’s Oxolysis is low-temperature. It raised €2.8M."
    first = len("Radical Dot’s Oxolysis is low-temperature.".encode("utf-8"))
    chunks = [{"web": {"uri": "https://a.test", "title": "a.test"}}, {"web": {"uri": "https://b.test", "title": "b.test"}}]
    supports = [{"segment": {"endIndex": first}, "groundingChunkIndices": [1]},
                {"segment": {"endIndex": len(text.encode("utf-8"))}, "groundingChunkIndices": [0, 1]}]
    cited, sources = _cite(text, supports, chunks)
    assert cited == "Radical Dot’s Oxolysis is low-temperature.[1] It raised €2.8M.[1][2]"
    assert [s["url"] for s in sources] == ["https://b.test", "https://a.test"]


# ------------------------------------------------------------------ the endpoint

def test_the_endpoint_passes_history_and_the_reviewers_tracxn_connection(monkeypatch):
    from api import main
    seen = {}
    monkeypatch.setattr(main, "tracxn_client_for", lambda user, llm=None: "tracxn-client")
    def fake(question, **kw):
        seen.update(kw, question=question)
        return {"answer": "ok", "evidence": [], "source": "Tracxn", "provider": "tracxn", "note": ""}
    monkeypatch.setattr(main.core, "chat_assistant", fake)
    client = TestClient(main.app)
    client.get("/api/auth/login", follow_redirects=False)
    res = client.post("/api/ask", headers={"X-CSRF-Token": client.cookies.get("sea_csrf")},
                      json={"question": "And their competitors?", "history": [{"role": "user", "text": "Radical Dot?"}]})
    assert res.status_code == 200 and res.json()["provider"] == "tracxn"
    assert seen["tracxn"] == "tracxn-client" and seen["history"] == [{"role": "user", "text": "Radical Dot?"}]
