"""core/market_signals.py: understand the market, then search each domain for signals that matter.

Everything is faked. What is pinned: the brief is built from the run's own research (a competitor
the research never names cannot seed a search), each domain is searched on its own, and only
quality survives — core or adjacent, dated, cited, carried by the search's own words, no forecasts,
no one-word labels, no event counted twice, and no quota to fill.
"""
import json
from unittest.mock import Mock

import pytest

from core import market_signals as M
from core.llm import LLMClient

RUN = {"company": "Radical Dot", "summary": "Radical Dot converts mixed plastic waste into acetic acid.",
       "trend": {"niche": "Mixed plastic chemical upcycling", "landscape": {"competitors": [{"name": "Aduro Clean Technologies"}]}}}
BRIEF = {"market": "Chemical upcycling of mixed plastic waste into platform chemicals", "terms": ["plastic upcycling"],
         "competitors": ["Aduro Clean Technologies", "Plastic Energy"], "buyers": ["chemical producers"], "exclude": ["mechanical recycling"]}
TEXT = {
    "funding": "June 2025: Novoloop closed a $50 million Series B led by Taranis [1]. 2025: AI startups raised $200 billion [1].",
    "competition": "June 2026: Braven Environmental cancelled plans for a $145 million pyrolysis plant in Texas [1]. Gong: Acquisition [1].",
    "adoption": "Nothing specific to this market happened.",
    "policy": "August 2026: HMRC set new rules for chemically recycled plastic under the plastic packaging tax [1].",
}
ROWS = {
    "funding": [{"date": "June 2025", "who": "Novoloop", "what": "closed a $50 million Series B led by Taranis", "figure": "$50 million",
                 "direction": "up", "relevance": "core", "citations": [1]},
                {"date": "2025", "who": "AI startups", "what": "AI startups raised $200 billion across the sector", "figure": "$200 billion",
                 "direction": "up", "relevance": "general", "citations": [1]}],
    "competition": [{"date": "June 2026", "who": "Braven Environmental", "what": "cancelled plans for a $145 million pyrolysis plant in Texas",
                     "figure": "$145 million", "direction": "down", "relevance": "core", "citations": [1]},
                    {"date": "", "who": "Gong", "what": "Acquisition", "relevance": "core", "citations": [1]},
                    {"date": "June 2025", "who": "Novoloop", "what": "raised $50 million in a Series B round", "figure": "$50 million",
                     "direction": "up", "relevance": "core", "citations": [1]}],
    "adoption": [],
    "policy": [{"date": "August 2026", "who": "HMRC", "what": "set new rules for chemically recycled plastic under the plastic packaging tax",
                "direction": "new", "relevance": "adjacent", "citations": [1]}],
}


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(M.web, "_cached", lambda *a, **k: None)
    monkeypatch.setattr(M.web, "_store", lambda *a, **k: None)


def fake_llm():
    llm = Mock(available=True, last_error="")
    llm.parse_json = LLMClient.parse_json
    domain_of = lambda prompt: next(d for d in M.DOMAINS if M.DOMAINS[d] in prompt)  # noqa: E731
    llm.web_answer.side_effect = lambda prompt, **k: {"text": TEXT[domain_of(prompt)], "queries": [],
                                                      "sources": [{"title": "news.test", "url": f"https://news.test/{domain_of(prompt)}"}]}

    def complete(prompt, **k):
        if prompt.startswith("You are preparing web searches"):
            return json.dumps(BRIEF)
        domain = next(d for d in M.DOMAINS if TEXT[d][:40] in prompt)
        return json.dumps({"signals": ROWS[domain]})
    llm.complete.side_effect = complete
    return llm


def test_the_brief_keeps_only_competitors_the_research_names():
    brief = M.market_brief(RUN, fake_llm())
    assert brief["competitors"] == ["Aduro Clean Technologies"]            # "Plastic Energy" is not in the research
    assert brief["market"].startswith("Chemical upcycling")


def test_each_domain_is_searched_with_the_brief_and_only_quality_signals_survive():
    llm = fake_llm()
    out = M.market_signals("Radical Dot", run=RUN, llm=llm)
    assert llm.web_answer.call_count == 4
    assert all("Chemical upcycling of mixed plastic waste" in c.args[0] for c in llm.web_answer.call_args_list)
    got = [(s["category"], s["who"], s["relevance"]) for s in out["signals"]]
    # The $200B sector total is "general", "Acquisition" is a label, the second Novoloop line repeats
    # the first, and adoption found nothing — so it has nothing, rather than filler.
    assert got == [("funding", "Novoloop", "core"), ("competition", "Braven Environmental", "core"), ("policy", "HMRC", "adjacent")]
    assert out["market"] == BRIEF["market"] and out["provider"] == "web"


def test_a_failed_domain_is_retried_reported_as_failed_and_not_cached(monkeypatch):
    stored = []
    monkeypatch.setattr(M.web, "_store", lambda *a, **k: stored.append(a))
    llm = fake_llm()
    ok = llm.web_answer.side_effect
    llm.web_answer.side_effect = lambda prompt, **k: None if M.DOMAINS["adoption"] in prompt else ok(prompt, **k)
    out = M.market_signals("Radical Dot", run=RUN, llm=llm)
    assert out["domains"] == {"funding": "searched", "competition": "searched", "adoption": "failed", "policy": "searched"}
    assert sum(M.DOMAINS["adoption"] in c.args[0] for c in llm.web_answer.call_args_list) == 2      # one retry
    assert stored == []                                                                              # tried again next time


def test_a_funding_round_filed_under_adoption_counts_as_funding():
    rows = M._clean("adoption", {"signals": [{"date": "March 2025", "who": "Radical Dot", "relevance": "core", "citations": [1],
                                              "what": "raised €2.7 million in a pre-seed round led by UVC Partners"}]},
                    "march 2025 radical dot raised €2.7 million in a pre-seed round led by uvc partners", M._citer([{"title": "t", "url": "https://t"}], "web"))
    assert rows and rows[0]["category"] == "adoption"
    for r in rows:
        if r["category"] in ("adoption", "policy") and M._ROUND.search(r["what"]):
            r["category"] = "funding"
    assert rows[0]["category"] == "funding"


def test_no_web_search_means_no_signals_from_memory():
    llm = fake_llm()
    llm.web_answer.side_effect = lambda *a, **k: None
    out = M.market_signals("Radical Dot", run=RUN, llm=llm)
    assert out["provider"] == "none" and out["signals"] == []
