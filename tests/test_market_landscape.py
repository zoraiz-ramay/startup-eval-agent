"""The market landscape extracted by core/trend.py.

The trend stage has always ASKED for competitor and funding queries in stage 1 and then thrown
everything except the prose away, so "who else is in this space, and who is funding them" — the
question a reviewer asks right after "is it growing" — was searched for and discarded on every run.

What these pin is the grounding, because that is the part that fails silently. Asked to name
competitors in a niche, a model will list the three companies it remembers from training rather
than the ones in the results, and once a fabricated competitor is on screen beside a link a reader
cannot tell it from a real one. Two gates: the name has to appear in the evidence text, and the
citation has to be a real link.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.trend import _grounded_rows, _landscape_queries, _market_landscape  # noqa: E402


EVIDENCE = [
    {"title": "Fireflies.ai raises $19M Series A", "url": "https://techcrunch.example/fireflies",
     "snippet": "Fireflies.ai has raised a $19M Series A led by Khosla Ventures."},
    {"title": "Meeting intelligence market to reach $3.4B",
     "url": "https://research.example/report",
     "snippet": "The meeting intelligence market is forecast to grow at 21% CAGR through 2030."},
    {"title": "tl;dv secures seed round", "url": "https://eu-startups.example/tldv",
     "snippet": "tl;dv closed a EUR 5.5M seed round."},
]


class _FakeLLM:
    """Returns a scripted extraction. The point under test is what survives the gates, not the
    model — so the payload deliberately mixes grounded entries with the two failure modes."""

    available = True

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def complete(self, *a, **kw):
        self.calls += 1
        return self.payload


import json  # noqa: E402


def _run(payload, evidence=EVIDENCE):
    text = "\n".join(f"[{e['url']}] {e['title']}: {e['snippet']}" for e in evidence)
    return _market_landscape("meeting intelligence", evidence, text, _FakeLLM(json.dumps(payload)))


# --------------------------------------------------------------------------- grounding

def test_it_keeps_a_competitor_the_evidence_actually_names():
    out = _run({"competitors": [{"name": "Fireflies.ai", "note": "meeting transcription",
                                 "source_url": "https://techcrunch.example/fireflies"}]})
    assert [c["name"] for c in out["competitors"]] == ["Fireflies.ai"]
    assert out["competitors"][0]["note"] == "meeting transcription"


def test_it_drops_a_competitor_the_evidence_never_mentions():
    # The failure this exists for: a plausible name recalled from training, cited to a link that
    # says nothing about it.
    out = _run({"competitors": [{"name": "Otter.ai", "note": "recalled, not found",
                                 "source_url": "https://techcrunch.example/fireflies"}]})
    assert out["competitors"] == []


def test_it_drops_an_entry_with_no_real_link():
    out = _run({"competitors": [{"name": "Fireflies.ai", "source_url": "the first result"}]})
    assert out["competitors"] == []


def test_it_does_not_repeat_the_same_company():
    out = _run({"competitors": [
        {"name": "Fireflies.ai", "source_url": "https://techcrunch.example/fireflies"},
        {"name": "fireflies.ai", "source_url": "https://techcrunch.example/fireflies"},
    ]})
    assert len(out["competitors"]) == 1


# --------------------------------------------------------------------------- funded peers

def test_a_funded_peer_keeps_only_the_fields_the_results_state():
    out = _run({"funded_peers": [{"company": "tl;dv", "round": "Seed", "amount": "EUR 5.5M",
                                  "date": "", "investors": "",
                                  "source_url": "https://eu-startups.example/tldv"}]})
    peer = out["funded_peers"][0]
    assert peer["company"] == "tl;dv" and peer["round"] == "Seed"
    # Empty fields are omitted rather than rendered as blanks the reader has to interpret.
    assert "date" not in peer and "investors" not in peer


# --------------------------------------------------------------------------- market size

def test_a_cited_market_size_survives():
    out = _run({"market_size": {"value": "$3.4B", "cagr": "21%", "as_of": "2030",
                                "source_url": "https://research.example/report"}})
    assert out["market_size"]["value"] == "$3.4B"
    assert out["market_size"]["cagr"] == "21%"


def test_an_uncited_market_size_is_dropped_entirely():
    out = _run({"market_size": {"value": "$3.4B", "cagr": "21%", "source_url": ""}})
    assert out["market_size"] is None


def test_an_empty_market_size_is_not_reported_as_a_figure():
    out = _run({"market_size": {"value": "", "cagr": "",
                                "source_url": "https://research.example/report"}})
    assert out["market_size"] is None


# --------------------------------------------------------------------------- shape contract

def test_it_returns_a_landscape_even_when_nothing_survives():
    # "We looked and found nothing" and "this run never looked" are different statements, and the
    # UI renders them differently. An empty landscape must still BE a landscape.
    out = _run({"competitors": [], "funded_peers": [], "active_investors": []})
    assert out is not None
    assert out["competitors"] == [] and out["funded_peers"] == []


def test_it_returns_nothing_at_all_without_a_model_or_evidence():
    class Off:
        available = False

        def complete(self, *a, **kw):
            raise AssertionError("must not be called")

    assert _market_landscape("niche", EVIDENCE, "text", Off()) is None
    assert _market_landscape("niche", [], "", _FakeLLM("{}")) is None


def test_the_landscape_queries_are_named_so_their_results_can_be_told_apart():
    # The landscape rides in the same DuckDuckGo wave as the trend queries, which are keyed by
    # index. Distinct keys are what lets the two sets of results be separated afterwards.
    keys = set(_landscape_queries("x"))
    assert keys.isdisjoint({str(i) for i in range(10)})
    assert all(k.startswith("lc_") for k in keys)


def test_a_malformed_entry_costs_that_entry_and_nothing_else():
    rows = _grounded_rows(["not a dict", {"name": "Fireflies.ai",
                                          "source_url": "https://techcrunch.example/fireflies"}],
                          "fireflies ai", "name", ("note",))
    assert len(rows) == 1


def test_the_startup_is_not_listed_as_its_own_competitor():
    """Celonis came back at the top of its own process-mining landscape. The prompt forbids it and
    the model does it anyway, because in results about a company's own niche that company IS the
    most prominent name — so the rule is enforced in code rather than argued about in the prompt."""
    payload = {"competitors": [
        {"name": "Celonis", "source_url": "https://research.example/report"},
        {"name": "Fireflies.ai", "source_url": "https://techcrunch.example/fireflies"},
    ]}
    evidence = EVIDENCE + [{"title": "Celonis leads process mining",
                            "url": "https://research.example/report",
                            "snippet": "Celonis is the leading vendor."}]
    text = "\n".join(f"[{e['url']}] {e['title']}: {e['snippet']}" for e in evidence)
    out = _market_landscape("process mining", evidence, text,
                            _FakeLLM(json.dumps(payload)), "Celonis")
    assert [c["name"] for c in out["competitors"]] == ["Fireflies.ai"]


def test_the_startup_is_not_listed_as_its_own_funded_peer():
    payload = {"funded_peers": [{"company": "tl;dv", "round": "Seed",
                                 "source_url": "https://eu-startups.example/tldv"}]}
    text = "\n".join(f"[{e['url']}] {e['title']}: {e['snippet']}" for e in EVIDENCE)
    out = _market_landscape("meeting intelligence", EVIDENCE, text,
                            _FakeLLM(json.dumps(payload)), "tl;dv")
    assert out["funded_peers"] == []


def test_without_a_company_name_nothing_is_filtered():
    # The parameter is optional; an empty name must not silently drop every row.
    out = _run({"competitors": [{"name": "Fireflies.ai",
                                 "source_url": "https://techcrunch.example/fireflies"}]})
    assert len(out["competitors"]) == 1
