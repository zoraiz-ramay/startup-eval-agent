"""core/business_flow.py: five plain sentences about how a startup's business works.

The model only rephrases the run's own research. What is pinned is the gate every sentence has to
pass before it is shown: real citations, words carried by what it cites, no number the research
does not state — and a story too thin to tell is reported as such, not padded.
"""
import json
from unittest.mock import Mock

import pytest

from core import business_flow as B
from core.llm import LLMClient

RUN = {"company": "Radical Dot", "found": True,
       "summary": "Radical Dot converts mixed, unrecyclable plastic waste into acetic acid through its Oxolysis process.",
       "profile": {"Business model": "Today, revenue comes from R&D partnerships with chemical companies."}}


def model(reply: dict):
    llm = Mock(available=True)
    llm.complete.return_value = json.dumps(reply)
    return llm


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(B.web, "_cached", lambda *a, **k: None)
    monkeypatch.setattr(B.web, "_store", lambda *a, **k: None)


def ids():
    by_source = {r["source"]: r["id"] for r in B._evidence(RUN)}
    return by_source["summary"], by_source["profile.Business model"]


def test_sentences_carried_by_their_sources_are_kept_in_story_order():
    s, m = ids()
    out = B.business_flow(RUN, model({
        "problem": {"text": "Mixed plastic waste cannot be recycled today.", "citations": [s]},
        "how": {"text": "Its Oxolysis process converts plastic waste into acetic acid.", "citations": [s]},
        "money": {"text": "It earns from R&D partnerships with chemical companies.", "citations": [m]}}))
    assert out["status"] == "ok"
    assert [x["id"] for x in out["steps"]] == ["problem", "how", "money"]
    assert out["steps"][2]["label"] == "How it makes money"
    assert out["steps"][1]["sources"][0]["quote"].startswith("Radical Dot converts")


def test_a_sentence_its_sources_do_not_carry_or_with_an_invented_number_is_dropped():
    s, m = ids()
    out = B.business_flow(RUN, model({
        "problem": {"text": "Mixed plastic waste cannot be recycled today.", "citations": [s]},
        "offer": {"text": "Satellite imaging for insurance underwriters.", "citations": [s]},           # not in the record
        "how": {"text": "Oxolysis converts 90% of plastic waste into acetic acid.", "citations": [s]},   # 90 is invented
        "customers": {"text": "Chemical companies partner with it.", "citations": ["E999"]},           # cites nothing real
        "money": {"text": "It earns from R&D partnerships with chemical companies.", "citations": [m]}}))
    assert [x["id"] for x in out["steps"]] == ["problem", "money"]


def test_a_story_of_fewer_than_two_steps_is_reported_as_too_thin():
    s, _ = ids()
    out = B.business_flow(RUN, model({"problem": {"text": "Mixed plastic waste cannot be recycled today.", "citations": [s]}}))
    assert out["status"] == "insufficient" and out["steps"] == []


def test_no_model_means_no_story():
    assert B.business_flow(RUN, Mock(available=False))["status"] == "unavailable"


def test_a_reply_with_a_stray_trailing_brace_still_parses():
    assert LLMClient.parse_json('```json\n{"a":{"b":1}}}\n```') == {"a": {"b": 1}}
