"""The deterministic Traction rubric: Funding 30 · Customers 30 · Revenue 30 · Employees 10.

Every boundary below is a product-owner decision. The inputs are built directly in the shape
`gather_traction_inputs` returns, except where the point is the gathering itself, which goes
through `with_traction` on a small fake pipeline result.
"""
import datetime
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import config  # noqa: E402
from core import traction as T  # noqa: E402
from core.profile import (_clean_customer_classes, _clean_revenue,  # noqa: E402
                          _clean_segment_grade, _verbatim)

URL = "https://example.com/news"


def inputs(**kw):
    base = {"company": "Acme", "parent_group": "", "funding": [], "funding_stage": "",
            "employees": [], "customers": [], "customer_classes": [], "investors": [],
            "contradicted": [], "segment": "", "segment_grade": {}, "revenue": {},
            "revenue_signal": ""}
    base.update(kw)
    return base


def fund(value, url="", origin="database"):
    return {"value": value, "source_url": url, "origin": origin}


def cust(*names):
    return [{"name": n, "source_url": URL, "origin": "research"} for n in names]


def rev(quote, metric="revenue", status="amount", url=URL, **kw):
    return {"status": status, "quote": quote, "metric": metric, "source_url": url, **kw}


def div(result, key):
    return next(d for d in result["divisions"] if d["id"] == key)


def points(key, **kw):
    return div(T.score_traction(inputs(**kw)), key)["points"]


# ================================================================================== funding

@pytest.mark.parametrize("amount, expected", [
    (1, 2.5), (499_999, 2.5),
    (500_000, 5), (999_999, 5),
    (1_000_000, 10), (1_499_999, 10),
    (1_500_000, 15), (1_999_999, 15),
    (2_000_000, 25), (50_000_000, 25),
])
def test_funding_bands_inclusive_lower_edges(amount, expected):
    assert points("funding", funding=[fund(f"€{amount}")]) == expected


def test_bare_database_number_is_euros_and_says_so():
    d = div(T.score_traction(inputs(funding=[fund("2831100.0")])), "funding")
    assert (d["points"], d["currency_assumed"], d["value_eur"]) == (25, True, 2_831_100)


@pytest.mark.parametrize("stage, expected", [
    ("pre_seed", 5), ("seed", 10), ("series_a", 25), ("series_b_plus", 30)])
def test_stage_only_scores_by_stage(stage, expected):
    d = div(T.score_traction(inputs(funding_stage=stage)), "funding")
    assert (d["status"], d["points"], d["basis"]) == ("evidenced", expected, "stage_only")


@pytest.mark.parametrize("text, expected", [
    ("Pre-Seed, amount undisclosed", 5), ("Seed round", 10), ("Series A", 25),
    ("Series C, undisclosed", 30)])
def test_stage_read_from_the_funding_string_when_no_amount(text, expected):
    assert points("funding", funding=[fund(text)]) == expected


def test_a_grant_is_not_on_the_stage_ladder():
    d = div(T.score_traction(inputs(funding=[fund("EU grant, undisclosed")])), "funding")
    assert d["status"] == "unknown" and d["points"] is None


def test_series_b_plus_at_two_million_lifts_to_the_maximum():
    d = div(T.score_traction(inputs(funding=[fund("Series B, €2M")])), "funding")
    assert (d["points"], d["basis"]) == (30, "amount_and_stage")


def test_series_b_plus_below_two_million_scores_by_amount():
    assert points("funding", funding=[fund("Series B, €1.2M")]) == 10


def test_series_b_lift_is_measured_in_euros_after_fx():
    # $2M ≈ €1.72M: under the edge, so neither the top band nor the lift applies.
    assert points("funding", funding=[fund("Series B, $2M")]) == 15


def test_series_a_with_amount_scores_by_amount_not_stage():
    assert points("funding", funding=[fund("Series A, €600k")]) == 5


@pytest.mark.parametrize("text, expected", [
    ("$2M", 15),                 # 1.72M
    ("$2.4M", 25),               # 2.064M
    ("CHF 1M", 10),              # 1.07M
    ("£1.3M", 15),               # 1.508M
    ("SAR 3.75 million", 5),     # 862.5k
    ("₹15 crore", 10),           # 1.47M
    ("¥100M", 5),                # 580k
])
def test_other_currencies_are_converted(text, expected):
    assert points("funding", funding=[fund(text)]) == expected


def test_a_currency_without_a_rate_is_not_priced(monkeypatch):
    # Every ISO code the parser knows has a rate today, so this path is only reachable by
    # removing one; it must fall back to "not priced", never to 1:1.
    monkeypatch.setattr(config, "FX_TO_EUR", {k: v for k, v in config.FX_TO_EUR.items()
                                              if k != "TRY"})
    d = div(T.score_traction(inputs(funding=[fund("TRY 90M")])), "funding")
    assert d["status"] == "unknown"
    assert "no reference rate" in d["candidates"][0]["reason"]


def test_valuation_is_not_money_raised():
    d = div(T.score_traction(inputs(funding=[fund(
        "Total raised: $724M. Current valuation: $8.5B")])), "funding")
    assert d["value_eur"] == round(724e6 * config.FX_TO_EUR["USD"])


@pytest.mark.parametrize("text", ["Valued at €50M", "Market size €4B", "Revenue €3M",
                                  "ARR of $2M", "TAM $10B"])
def test_non_raised_money_alone_is_no_funding_evidence(text):
    d = div(T.score_traction(inputs(funding=[fund(text)])), "funding")
    assert d["status"] == "unknown"


def test_a_valuation_beside_a_raise_keeps_the_raise_and_drops_the_valuation():
    assert [m["low"] for m in T._raised_amounts("Raised $5M at a $50M valuation")] == [5e6]
    assert [m["low"] for m in T._raised_amounts("Raised €3M, valued at €30M")] == [3e6]


def test_raised_amounts_splits_on_sentences_but_not_decimals():
    assert [m["low"] for m in T._raised_amounts("Raised $3.5M. Valued at $40M")] == [3.5e6]


def test_largest_priced_candidate_wins_and_conflict_is_flagged():
    d = div(T.score_traction(inputs(funding=[fund("€300k"), fund("€2.2M", URL, "web")])),
            "funding")
    assert (d["points"], d["source_url"], d["conflict"]) == (25, URL, True)
    assert [c["used"] for c in d["candidates"]] == [False, True]


def test_year_before_amount_does_not_change_its_currency():
    assert points("funding", funding=[fund("Seed 2023 $2.3M")]) == 15


# ================================================================================ customers

@pytest.mark.parametrize("n, expected", [(1, 7.5), (2, 15), (3, 20), (5, 20)])
def test_big_name_bands(n, expected):
    names = ["Siemens", "Bosch", "BASF", "BMW", "SAP"][:n]
    assert points("customers", customers=cust(*names)) == expected


@pytest.mark.parametrize("n, expected", [(1, 3.5), (2, 7), (3, 15), (5, 15), (6, 20), (9, 20)])
def test_sme_bands(n, expected):
    names = [f"Small Firm {i}" for i in range(n)]
    assert points("customers", customers=cust(*names)) == expected


def test_big_and_sme_are_summed():
    assert points("customers", customers=cust("Siemens", "Tiny One", "Tiny Two")) == 7.5 + 7


def test_customer_points_are_capped_at_thirty():
    d = div(T.score_traction(inputs(customers=cust(
        "Siemens", "Bosch", "BASF", *[f"Small {i}" for i in range(6)]))), "customers")
    assert d["points"] == 30 and "capped" in d["rationale"]


@pytest.mark.parametrize("names", [("Siemens AG", "Siemens"), ("SIEMENS", "Siemens Aktiengesellschaft"),
                                   ("Robert Bosch GmbH", "robert bosch")])
def test_duplicates_after_legal_suffix_normalisation_count_once(names):
    d = div(T.score_traction(inputs(customers=cust(*names))), "customers")
    assert [i["reason"] for i in d["items"]] == ["", "duplicate"]


@pytest.mark.parametrize("name, norm", [
    ("Siemens AG", "siemens"), ("Siemens Aktiengesellschaft", "siemens"),
    ("Mercedes-Benz Group AG", "mercedes benz"), ("E.ON SE", "e on"), ("BMW Group", "bmw")])
def test_norm_org(name, norm):
    assert T._norm_org(name) == norm


@pytest.mark.parametrize("field, value", [("company", "Acme GmbH"), ("parent_group", "Holdco AG")])
def test_the_company_itself_or_its_parent_is_not_a_customer(field, value):
    d = div(T.score_traction(inputs(**{field: value}, customers=cust("Acme", "Holdco"))),
            "customers")
    excluded = {i["name"]: i["reason"] for i in d["items"]}
    target = "Acme" if field == "company" else "Holdco"
    assert excluded[target] == "the startup itself or its parent"


def test_an_investor_is_not_a_customer():
    d = div(T.score_traction(inputs(customers=cust("Siemens", "Bosch"),
                                    investors=["Siemens AG"])), "customers")
    assert d["points"] == 7.5
    assert d["items"][0]["reason"] == "listed as an investor"


def test_a_contradicted_customer_is_not_counted():
    d = div(T.score_traction(inputs(customers=cust("Bosch"), contradicted=["Bosch GmbH"])),
            "customers")
    assert d["status"] == "unknown"
    assert d["items"][0]["reason"] == "contradicted by the web evidence"


@pytest.mark.parametrize("relation", ["pilot", "partner", "investor", "supplier"])
def test_non_customer_relations_are_excluded(relation):
    d = div(T.score_traction(inputs(customers=cust("Bosch"), customer_classes=[
        {"name": "Bosch", "relation": relation, "size": "large_enterprise", "by": "llm"}])),
        "customers")
    assert d["status"] == "unknown" and not d["items"][0]["counted"]


def test_notable_list_is_big_name_even_if_the_model_says_sme():
    d = div(T.score_traction(inputs(customers=cust("Bosch"), customer_classes=[
        {"name": "Bosch", "relation": "customer", "size": "sme", "by": "llm"}])), "customers")
    assert (d["points"], d["items"][0]["classified_by"]) == (7.5, "list")


def test_model_may_upgrade_an_unlisted_customer_to_large_enterprise():
    classes = [{"name": "Regional Utility", "relation": "customer", "size": "large_enterprise",
                "by": "llm"}]
    assert points("customers", customers=cust("Regional Utility"),
                  customer_classes=classes) == 7.5
    assert points("customers", customers=cust("Regional Utility")) == 3.5


GRADE = {1: 7.5, 2: 11.25, 3: 15}


@pytest.mark.parametrize("level", [1, 2, 3])
def test_generic_segment_grade_scores_when_nothing_is_named(level):
    d = div(T.score_traction(inputs(segment_grade={"level": level, "quote": "chemical producers",
                                                   "source_url": URL})), "customers")
    assert (d["points"], d["basis"]) == (GRADE[level], "generic")


def test_generic_grade_needs_a_source():
    d = div(T.score_traction(inputs(segment_grade={"level": 3, "quote": "x"})), "customers")
    assert d["status"] == "unknown"


def test_generic_grade_counts_only_if_it_beats_the_named_total():
    grade = {"level": 3, "quote": "q", "source_url": URL}
    assert div(T.score_traction(inputs(customers=cust("Bosch"), segment_grade=grade)),
               "customers")["basis"] == "generic"                     # 15 > 7.5
    assert div(T.score_traction(inputs(customers=cust("Bosch", "BASF", "BMW"),
                                       segment_grade=grade)), "customers")["points"] == 20


def test_generic_grade_tie_keeps_the_named_basis():
    d = div(T.score_traction(inputs(customers=cust("Bosch"), segment_grade={
        "level": 1, "quote": "q", "source_url": URL})), "customers")
    assert (d["points"], d["basis"]) == (7.5, "named")


# ================================================================================== revenue

@pytest.mark.parametrize("amount, expected", [
    (1, 5), (99_999, 5), (100_000, 10), (499_999, 10), (500_000, 15), (999_999, 15),
    (1_000_000, 20), (4_999_999, 20), (5_000_000, 25), (9_999_999, 25), (10_000_000, 30)])
def test_revenue_bands(amount, expected):
    assert points("revenue", revenue=rev(f"Revenue of €{amount}")) == expected


def test_pre_revenue_is_an_evidenced_zero_that_stays_in_the_denominator():
    r = T.score_traction(inputs(funding=[fund("€2M")],
                                revenue=rev("pre-revenue", status="pre_revenue")))
    d = div(r, "revenue")
    assert (d["status"], d["points"]) == ("zero_evidenced", 0.0)
    assert (r["available_max"], r["earned"], r["score_0_100"]) == (60, 25, round(2500 / 60, 1))


def test_revenue_without_a_source_url_is_unknown():
    assert div(T.score_traction(inputs(revenue=rev("Revenue €2M", url=""))),
               "revenue")["status"] == "unknown"
    assert div(T.score_traction(inputs(revenue=rev("pre-revenue", status="pre_revenue",
                                                   url="f1"))), "revenue")["status"] == "unknown"


def test_mrr_is_annualised():
    d = div(T.score_traction(inputs(revenue=rev("MRR of €10k", metric="mrr"))), "revenue")
    assert (d["value_eur"], d["points"]) == (120_000, 10)


@pytest.mark.parametrize("metric", ["arr", "turnover", "run_rate"])
def test_other_revenue_metrics_score(metric):
    assert points("revenue", revenue=rev("ARR of €1.2M", metric=metric)) == 20


@pytest.mark.parametrize("metric", ["gmv", "bookings", "estimate", "projection"])
def test_non_revenue_metrics_are_not_scored(metric):
    assert div(T.score_traction(inputs(revenue=rev("GMV of €50M", metric=metric))),
               "revenue")["status"] == "unknown"


def test_revenue_mentioned_without_an_amount_is_unknown():
    assert div(T.score_traction(inputs(revenue=rev("Revenue grew strongly"))),
               "revenue")["status"] == "unknown"


def test_revenue_in_dollars_is_converted():
    assert points("revenue", revenue=rev("Revenue of $1.1M")) == 15     # €946k


@pytest.mark.parametrize("growth, amount, signal, expected", [
    (100, 1_000_000, "recurring", 30),
    (250, 3_000_000, "recurring", 30),
    (99.9, 1_000_000, "recurring", 20),
    (100, 999_999, "recurring", 15),
    (100, 1_000_000, "one_off", 20),
    (None, 1_000_000, "recurring", 20),
])
def test_strong_recurring_growth_lift(growth, amount, signal, expected):
    assert points("revenue", revenue_signal=signal,
                  revenue=rev(f"ARR €{amount}", metric="arr", growth_pct=growth)) == expected


def test_old_fiscal_year_is_flagged_stale():
    this_year = datetime.date.today().year
    assert div(T.score_traction(inputs(revenue=rev("Revenue €2M", fiscal_year=str(this_year - 4)))),
               "revenue")["stale"] is True
    assert div(T.score_traction(inputs(revenue=rev("Revenue €2M", fiscal_year=str(this_year - 3)))),
               "revenue")["stale"] is False


def test_market_size_in_the_revenue_quote_is_not_revenue():
    assert points("revenue", revenue=rev("Revenue €3M in a €10B market")) == 20


# ================================================================================ employees

@pytest.mark.parametrize("value, expected", [
    ("1", 2), ("3", 2), ("4", 4), ("6", 4), ("7", 6), ("10", 6), ("11", 8), ("20", 8),
    ("21", 10), ("5000", 10), ("11-50", 8), ("2-10", 2), ("51-200", 10)])
def test_employee_bands(value, expected):
    assert points("employees", employees=[fund(value)]) == expected


@pytest.mark.parametrize("value", ["0", "<10", "600000", "unknown"])
def test_implausible_headcount_is_unknown(value):
    assert div(T.score_traction(inputs(employees=[fund(value)])), "employees")["status"] == "unknown"


def test_first_usable_candidate_wins_in_precedence_order():
    d = div(T.score_traction(inputs(employees=[fund("0"), fund("<10"), fund("25"), fund("5")])),
            "employees")
    assert (d["points"], d["value"], d["conflict"]) == (10, "25", True)


def test_band_basis_is_reported():
    assert div(T.score_traction(inputs(employees=[fund("11-50")])),
               "employees")["basis"] == "band_lower_bound"


# ============================================================================ normalisation

def test_nothing_evidenced_is_no_evidence_not_zero():
    r = T.score_traction(inputs())
    assert (r["status"], r["score_0_100"], r["confidence"]) == ("no_evidence", None, 0.0)


@pytest.mark.parametrize("kw, confidence", [
    ({"employees": [fund("5")]}, 0.10),
    ({"funding": [fund("€1M")]}, 0.30),
    ({"funding": [fund("€1M")], "customers": cust("Bosch")}, 0.60),
    ({"funding": [fund("€1M")], "customers": cust("Bosch"), "revenue": rev("Revenue €1M"),
      "employees": [fund("5")]}, 1.0),
])
def test_confidence_is_the_share_of_points_evidenced(kw, confidence):
    assert T.score_traction(inputs(**kw))["confidence"] == pytest.approx(confidence)


def test_score_normalises_over_evidenced_divisions_only():
    r = T.score_traction(inputs(employees=[fund("5")]))          # 4 of 10, no minimum
    assert (r["score_0_100"], r["divisions_known"]) == (40.0, 1)
    r = T.score_traction(inputs(funding=[fund("€2M")], customers=cust("Bosch")))
    assert r["score_0_100"] == round(100 * 32.5 / 60, 1)


def test_full_marks():
    r = T.score_traction(inputs(
        funding=[fund("Series C, €40M")], customers=cust("Siemens", "Bosch", "BASF",
                                                           *[f"S{i}" for i in range(6)]),
        revenue=rev("Revenue €12M"), employees=[fund("250")]))
    assert (r["score_0_100"], r["earned"], r["available_max"]) == (100.0, 100, 100)


# ============================================================================ apply_traction

def _score(traction=40.0, **kw):
    return {"status": "assessed", "dimensions": {"traction": traction, "product": 60},
            "judgments": {"product": {"score": 60}}, **kw}


SCORED = T.score_traction(inputs(employees=[fund("5")]))            # 40.0


def test_apply_overrides_and_keeps_the_model_value():
    out = T.apply_traction(_score(traction=77.0), SCORED)
    assert out["dimensions"]["traction"] == 40.0
    assert (out["traction_llm"], out["traction_method"]) == (77.0, "rubric")
    assert out["dimensions"]["product"] == 60 and out["judgments"]["traction"]["score"] == 40.0


def test_apply_does_not_mutate_its_input():
    s = _score(traction=77.0)
    T.apply_traction(s, SCORED)
    assert s == _score(traction=77.0)


def test_apply_is_idempotent_and_keeps_the_original_model_value():
    once = T.apply_traction(_score(traction=77.0), SCORED)
    other = T.score_traction(inputs(funding=[fund("€2M")]))
    twice = T.apply_traction(T.apply_traction(once, SCORED), other)
    assert twice["traction_llm"] == 77.0
    assert twice["dimensions"]["traction"] == other["score_0_100"]


@pytest.mark.parametrize("score, traction", [
    (_score(), T.score_traction(inputs())),                          # no evidence
    (_score(), None),
    (_score(), {}),
    ({**_score(), "status": "unassessed"}, SCORED),
    ({}, SCORED),
])
def test_apply_leaves_the_score_unchanged_when_not_applicable(score, traction):
    assert T.apply_traction(score, traction) is score


# ============================================================================= with_traction

def _result(**kw):
    base = {"company": "Acme", "found": True, "score": _score(traction=50.0),
            "traction_inputs": {"funding": "2831100.0", "employees_count": "12", "origin": "glassdollar"}}
    base.update(kw)
    return base


def test_with_traction_computes_from_the_raw_database_values():
    out = T.with_traction(_result())
    tr = out["traction"]
    assert (tr["version"], div(tr, "funding")["points"], div(tr, "employees")["points"]) == \
        (T.VERSION, 25, 8)
    assert div(tr, "funding")["origin"] == "glassdollar"
    assert out["score"]["dimensions"]["traction"] == tr["score_0_100"]
    assert out["score"]["traction_llm"] == 50.0


def test_with_traction_keeps_a_current_version_as_is():
    current = {**SCORED, "score_0_100": 12.3}
    out = T.with_traction(_result(traction=current))
    assert out["traction"] is current and out["score"]["dimensions"]["traction"] == 12.3


def test_every_division_carries_its_rubric_ladder_best_rung_first():
    ladders = T.with_traction(_result(traction={**SCORED}))["traction_ladders"]
    assert set(ladders) == {"funding", "customers", "revenue", "employees"}
    for rungs in ladders.values():
        for group in {r["group"] for r in rungs}:
            points = [r["points"] for r in rungs if r["group"] == group]
            assert points == sorted(points, reverse=True), group
    # Each band a division can report is a rung the page can highlight.
    bands = {r.get("match") for rungs in ladders.values() for r in rungs}
    assert {"≥ €2M", "Stage: Seed", "Series B+ at ≥ €2M", "Pre-revenue", "7 – 10",
            "Generic customer base, level 2"} <= bands


def test_with_traction_recomputes_an_old_version():
    out = T.with_traction(_result(traction={**SCORED, "version": "traction-rubric-v0",
                                            "score_0_100": 12.3}))
    assert out["traction"]["version"] == T.VERSION and out["traction"]["score_0_100"] != 12.3


def test_with_traction_passes_not_found_through():
    r = {"found": False, "company": "Nope"}
    assert T.with_traction(r) is r


def test_with_traction_reads_the_deep_profile():
    this_year = datetime.date.today().year
    out = T.with_traction({
        "company": "Acme", "score": _score(), "profile": {"funding": "€1.2M"},
        "verification": {"claims": [
            {"field": "reference_customer", "value": "Bosch", "status": "verified",
             "evidence_url": URL},
            {"field": "reference_customer", "value": "BASF SE", "status": "contradicted"}]},
        "deep_profile": {
            "reference_customers": ["Bosch", "BASF", "Acme GmbH"],
            "employees_over_time": [{"year": 2023, "count": 5, "source_url": URL},
                                    {"year": 2025, "count": 22, "source_url": URL}],
            "commercial": {"funding_stage": "seed", "revenue_signal": "recurring",
                           "investors": [{"name": "Seed Fund"}],
                           "revenue": rev("ARR €1.5M", metric="arr", growth_pct=120.0,
                                          fiscal_year=str(this_year))}}})
    tr = out["traction"]
    assert div(tr, "funding")["points"] == 10                         # €1.2M from the profile
    cust_div = div(tr, "customers")
    assert cust_div["points"] == 7.5                                  # Bosch only
    assert {i["name"]: i["reason"] for i in cust_div["items"]} == {
        "Bosch": "", "BASF": "contradicted by the web evidence",
        "Acme GmbH": "the startup itself or its parent"}
    assert cust_div["items"][0]["origin"] == "verified"
    assert div(tr, "revenue")["points"] == 30                         # recurring + 120% + ≥ €1M
    # headcount without a source-less profile value falls through to the latest series point
    assert div(tr, "employees")["value"] == "22"


def test_gather_ignores_nan_and_uncited_web_funding():
    got = T.gather_traction_inputs({"traction_inputs": {"funding": "nan"},
                                    "deep_profile": {"funding": "$9M", "funding_source": "f1"}})
    assert got["funding"] == []


# ========================================================================= profile cleaners

CORPUS = ("Acme reported revenue of €2.4 million in 2024. Revenue doubled year over year. "
          "The company is pre-revenue. Customers include chemical producers across Europe.")


def test_verbatim_requires_the_quote_in_the_evidence():
    assert _verbatim("revenue of  €2.4 MILLION", CORPUS) == "revenue of €2.4 MILLION"
    assert _verbatim("revenue of €2.5 million", CORPUS) == ""
    assert _verbatim("pre-revenue", CORPUS) == ""                     # shorter than 12


def test_clean_revenue_keeps_a_verbatim_quote():
    out = _clean_revenue({"status": "amount", "quote": "revenue of €2.4 million", "metric": "Run-Rate",
                          "fiscal_year": "FY2024", "growth_quote": "Revenue doubled",
                          "source_url": URL}, CORPUS)
    assert out == {"status": "amount", "quote": "revenue of €2.4 million", "metric": "run_rate",
                   "fiscal_year": "2024", "growth_pct": 100.0, "source_url": URL}


@pytest.mark.parametrize("raw", [
    {"status": "amount", "quote": "revenue of €3.0 million", "source_url": URL},   # not in corpus
    {"status": "amount", "quote": "revenue of €2.4 million", "source_url": "f1"},  # not a URL
    {"status": "maybe", "quote": "revenue of €2.4 million", "source_url": URL},
    "revenue of €2.4 million",
    None,
])
def test_clean_revenue_rejects(raw):
    assert _clean_revenue(raw, CORPUS) == {}


def test_clean_revenue_pre_revenue_short_quote_and_unknown_metric():
    assert _clean_revenue({"status": "pre_revenue", "quote": "pre-revenue", "source_url": URL},
                          CORPUS)["status"] == "pre_revenue"
    assert _clean_revenue({"status": "amount", "quote": "revenue of €2.4 million",
                           "metric": "sales pipeline", "source_url": URL}, CORPUS)["metric"] == "estimate"


def test_clean_revenue_growth_not_in_evidence_is_dropped():
    out = _clean_revenue({"status": "amount", "quote": "revenue of €2.4 million",
                          "growth_quote": "grew 300%", "source_url": URL}, CORPUS)
    assert out["growth_pct"] is None


def test_clean_customer_classes_cannot_add_or_rename_customers():
    out = _clean_customer_classes([
        {"name": "bosch", "relation": "Customer", "size": "large_enterprise"},
        {"name": "Bosch", "relation": "pilot", "size": "sme"},            # duplicate
        {"name": "Robert Bosch GmbH", "relation": "customer", "size": "sme"},  # renamed
        {"name": "Tesla", "relation": "customer", "size": "large_enterprise"},  # invented
        {"name": "Tiny", "relation": "reseller", "size": "sme"},          # bad relation
        {"name": "Tiny", "relation": "customer", "size": "huge"},         # bad size → sme
        "BASF"], ["Bosch", "Tiny"])
    assert out == [
        {"name": "Bosch", "relation": "customer", "size": "large_enterprise", "by": "llm"},
        {"name": "Tiny", "relation": "customer", "size": "sme", "by": "llm"}]


@pytest.mark.parametrize("level, ok", [(1, True), (2, True), (3, True), (0, False), (4, False),
                                       (2.5, False), ("2", False), (True, False), (None, False)])
def test_clean_segment_grade_level_must_be_discrete(level, ok):
    out = _clean_segment_grade({"level": level, "quote": "chemical producers", "source_url": URL},
                               CORPUS)
    assert bool(out) is ok
    if ok:
        assert out == {"level": level, "quote": "chemical producers", "source_url": URL}


@pytest.mark.parametrize("raw", [
    {"level": 2, "quote": "automotive OEMs", "source_url": URL},        # not in evidence
    {"level": 2, "quote": "chemical producers", "source_url": ""},
    None])
def test_clean_segment_grade_needs_quote_and_source(raw):
    assert _clean_segment_grade(raw, CORPUS) == {}
