"""Market: size and growth banded from cited figures, strategic relevance judged, 0–15 in all.

The rule under test is the traction one: a cited figure decides its band in Python and nothing
the model says can move it; without a figure the model may judge, but never above 2.
"""
import json

import pytest

from core import market as M
from core.assessment import hydrate

EV = {"E1": {"id": "E1", "source": "trend.summary", "quote": "chemical recycling for plastics", "url": ""}}
AREAS = ["Chemicals", "Plastics", "Sustainability"]
URL = "https://reports.example/market"


@pytest.mark.parametrize("value, level", [
    ("€99M", 0), ("€100M", 1), ("€999M", 1), ("€1B", 2), ("€4.9B", 2), ("€5B", 3),
    ("€19.9B", 3), ("€20B", 4), ("€99B", 4), ("€100B", 5), ("€2.1 trillion", 5), ("USD 1.2 tn", 5),
])
def test_every_size_boundary_in_euros(value, level):
    out = M.size_level(value)
    assert (out[0] if out else None) == level


def test_size_in_dollars_is_converted_before_banding():
    assert M.size_level("$1.1 billion")[0] == 1          # ≈ €0.95B at the reference rate
    assert M.size_level("USD 26.88 billion")[0] == 4


@pytest.mark.parametrize("value, level", [
    ("-0.1%", 0), ("0%", 1), ("1.99%", 1), ("2%", 2), ("4.9%", 2), ("5%", 3), ("9.99%", 3),
    ("10%", 4), ("24.9%", 4), ("25%", 5), ("31.7% year-over-year growth rate", 5),
    ("9.4% CAGR", 3), ("None", None), ("", None),
])
def test_every_growth_boundary(value, level):
    out = M.growth_level(value)
    assert (out[0] if out else None) == level


@pytest.mark.parametrize("value, eur_billions", [
    ("US$15.2 bln", 13.07), ("$15.2-billion", 13.07), ("USD 15.2 billion", 13.07), ("15.2 Mrd. US-Dollar", 13.07),
    # The base comes first and the forecast after; the largest amount put forecasts in the size band.
    ("USD 15.2B (2024) to USD 25B (2030)", 13.07),
    ("15.2 USD Billion", 13.07),                         # the currency between number and magnitude
])
def test_market_sizes_in_the_notations_reports_use(value, eur_billions):
    assert round(M.size_level(value)[1] / 1e9, 2) == eur_billions


def test_an_amount_too_small_to_be_a_market_is_unparsed_not_a_niche():
    # "US$15.2 bln" once parsed as fifteen dollars and scored "niche/local" instead of letting the
    # model judge it.
    assert M.size_level("15.2 USD") is None and M.size_level("$500") is None


@pytest.mark.parametrize("value, pct", [("7,8 %", 7.8), ("7.8 percent", 7.8), ("8.1 per cent", 8.1), ("12.5%-15%", 12.5)])
def test_growth_in_the_notations_reports_use(value, pct):
    assert M.growth_level(value)[1] == pct


@pytest.mark.parametrize("points, label", [(0, "Limited Market"), (6, "Limited Market"), (7, "Moderate Market"),
                                           (9, "Moderate Market"), (10, "Attractive Market"),
                                           (12, "Attractive Market"), (13, "Highly Attractive Market"),
                                           (15, "Highly Attractive Market")])
def test_band_boundaries(points, label):
    assert M.band(points) == label


def figs(size=None, growth=None):
    return {"niche": "chemical recycling",
            "size": {"level": size, "eur": 23e9, "value": "USD 26.88 billion", "as_of": "2030", "source_url": URL} if size is not None else None,
            "growth": {"level": growth, "pct": 9.4, "value": "9.4%", "as_of": "2030", "source_url": URL} if growth is not None else None}


def judged(**levels):
    return {k: {"score": v[0], "rationale": "r", "citations": ["E1"] if v[0] else [], "areas": v[1] if len(v) > 1 else []}
            for k, v in levels.items()}


def test_cited_figures_decide_size_and_growth_whatever_the_model_says():
    raw = judged(market_size=(0,), market_growth=(5,), strategic_relevance=(4, ["Chemicals"]))
    out = M.validate(raw, figs(size=4, growth=3), EV, AREAS)
    rows = {r["id"]: r for r in out["criteria"]}
    assert rows["market_size"]["score"] == 4 and rows["market_size"]["basis"] == "cited_figure"
    assert rows["market_size"]["source_url"] == URL
    assert rows["market_growth"]["score"] == 3
    assert out["points"] == 11 and out["score_0_100"] == 73.3 and out["band"] == "Attractive Market"


def test_without_a_figure_the_model_judges_but_never_above_2():
    raw = judged(market_size=(5,), market_growth=(4,), strategic_relevance=(3,))
    out = M.validate(raw, figs(), EV, AREAS)
    rows = {r["id"]: r for r in out["criteria"]}
    assert rows["market_size"]["score"] == 2 and rows["market_growth"]["score"] == 2
    assert rows["market_size"]["basis"] == "model_judgment"
    assert sum("capped at 2" in n for n in out["notes"]) == 2


def test_a_core_strategic_rating_must_name_a_siemens_area():
    unnamed = M.validate(judged(strategic_relevance=(5, ["Space tourism"])), figs(4, 3), EV, AREAS)
    assert unnamed["criteria"][2]["score"] == 3 and unnamed["criteria"][2]["areas"] == []
    named = M.validate(judged(strategic_relevance=(5, ["plastics"])), figs(4, 3), EV, AREAS)
    assert named["criteria"][2]["score"] == 5 and named["criteria"][2]["areas"] == ["Plastics"]


@pytest.mark.parametrize("bad", [
    {"strategic_relevance": {"score": 6, "citations": ["E1"]}},
    {"strategic_relevance": {"score": True, "citations": ["E1"]}},
    {"strategic_relevance": {"score": 3, "citations": []}},
    {"strategic_relevance": {"score": 3, "citations": ["E9"]}},
    {},
    None,
])
def test_malformed_judgments_are_rejected(bad):
    with pytest.raises(ValueError):
        M.validate(bad, figs(4, 3), EV, AREAS)


def test_a_figure_without_a_source_is_not_a_figure():
    res = {"trend": {"niche": "x", "landscape": {"market_size": {"value": "USD 50 billion", "cagr": "30%", "source_url": ""}}}}
    assert M._figures(res)["size"] is None and M._figures(res)["growth"] is None


class FakeLLM:
    available = True

    def __init__(self, reply):
        self.reply = reply

    def complete(self, prompt, **_):
        self.prompt = prompt
        return json.dumps(self.reply)


RUN = {"company": "Radical Dot", "summary": "Chemical recycling of plastic waste.",
       "trend": {"niche": "Plastic chemical recycling", "landscape": {"market_size": {
           "value": "USD 26.88 billion", "cagr": "9.4%", "as_of": "2030", "source_url": URL}}}}


def test_assess_market_asks_the_model_only_for_what_no_figure_answers():
    llm = FakeLLM({"industry": "Chemicals", "market": "Chemical recycling",
                   "strategic_relevance": {"score": 4, "rationale": "Plastics circularity", "citations": ["E1"],
                                           "areas": ["Plastics"]}})
    out = M.assess_market(RUN, llm)
    assert out["status"] == "assessed" and out["points"] == 4 + 3 + 4 and out["band"] == "Attractive Market"
    assert '"market_size"' not in llm.prompt.split("Return ONLY JSON")[1].split("Research records")[0]
    assert out["industry"] == "Chemicals" and out["figures"]["size"]["level"] == 4


def test_no_model_leaves_market_unassessed_not_zero():
    class Off:
        available = False
    out = M.assess_market(RUN, Off())
    assert out["status"] == "unassessed" and out["points"] is None
    assert out["figures"]["size"]["level"] == 4                 # what was cited is still shown


def test_invalid_model_output_leaves_market_unassessed():
    out = M.assess_market(RUN, FakeLLM({"strategic_relevance": {"score": 9, "citations": ["E1"]}}))
    assert out["status"] == "unassessed" and out["reason"] == "invalid_model_output"


def _dept_run(market):
    return {"found": True, "company": "Acme", "department": {"id": "di", "label": "DI"},
            "traction": {"version": "traction-rubric-v2", "status": "scored", "score_0_100": 80.0,
                         "earned": 56, "available_max": 70, "divisions_known": 3, "divisions": []},
            "score": {"version": "llm-judgment-v1", "status": "assessed", "final_score": 60,
                      "dimensions": {"traction": 80.0, "market": 90}},
            "market": market,
            "assessment": {"siemens_fit": {"score": 78, "status": "assessed"},
                           "team_ecosystem": {"status": "assessed", "score_0_100": 60}}}


def test_the_total_uses_the_market_rubric_and_keeps_the_models_number_as_a_diagnostic():
    out = hydrate(_dept_run({"version": M.VERSION, "status": "assessed", "score_0_100": 73.3}))
    assert out["assessment"]["components"]["market"] == 73.3
    assert out["assessment"]["total"] == round(0.3 * 80 + 0.35 * 78 + 0.2 * 60 + 0.15 * 73.3, 1)
    assert out["score"]["dimensions"]["market"] == 73.3 and out["score"]["llm_market"] == 90
    assert out["assessment"]["market_method"] == "rubric"


def test_an_unassessed_market_leaves_the_total_pending():
    out = hydrate(_dept_run({"version": M.VERSION, "status": "unassessed", "points": None}))
    assert out["assessment"]["components"]["market"] is None and out["assessment"]["total"] is None


def test_a_run_from_before_the_rubric_keeps_the_models_market_and_says_so():
    run = _dept_run(None)
    run.pop("market")
    out = hydrate(run)
    assert out["assessment"]["components"]["market"] == 90 and out["assessment"]["market_method"] == "llm_judgment"
