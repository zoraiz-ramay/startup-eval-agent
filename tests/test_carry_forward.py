"""A refresh adds evidence and never quietly drops what an earlier run found (core/carry_forward.py).

Radical Dot's investors went 8 → 8 → 3 → 0 → 2 → 2 → 2 → 4 → 2 → 6 across its stored runs, because
each run was a fresh sample of the web and the newest replaced the rest. Folding its real history
through carry_forward ends at 15 grounded investors, with no list shorter than any run ever found.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import carry_forward as cf, pipeline  # noqa: E402
from core.provenance import Fact  # noqa: E402
from tests.test_evaluate_stream import offline, _run  # noqa: E402,F401  (fixture reuse)

NOW, TODAY = "2026-10-03T12:00:00+00:00", dt.date(2026, 10, 3)
UVC = {"name": "UVC Partners", "source_url": "https://press.example/round"}
HTGF = {"name": "HTGF", "source_url": "https://news.example/htgf"}


def prior(created, *, investors=(), hq=None, facts=(), website="https://acme.example", trend=None, **dp):
    return {"company": "Acme Vision", "run_created_at": created,
            "profile": {"website": website},
            "deep_profile": {"commercial": {"investors": list(investors)}, **({"hq": hq} if hq else {}), **dp},
            "facts": list(facts), "trend": trend or {}}


def merge(fresh_dp, priors, facts=()):
    report = {}
    usable = cf.usable_priors(priors, cf.identity("Acme Vision", "https://acme.example"))
    out = cf.merge_profile({"profile": fresh_dp, "facts": list(facts)}, usable, NOW, report)
    return out, report


# ----------------------------------------------------------------------------------- lists

def test_an_investor_only_an_earlier_run_found_is_kept_and_says_when_it_was_last_found():
    out, report = merge({"commercial": {"investors": [HTGF]}},
                        [prior("2026-08-22T03:00:00+00:00", investors=[UVC, HTGF])])
    investors = out["profile"]["commercial"]["investors"]
    assert [i["name"] for i in investors] == ["HTGF", "UVC Partners"]
    assert "last_confirmed_at" not in investors[0]                    # found again: current
    assert investors[1]["last_confirmed_at"] == "2026-08-22T03:00:00+00:00"
    assert investors[1]["source_url"] == UVC["source_url"]            # still traceable
    assert report["commercial.investors"] == {"new": 0, "reconfirmed": 1, "carried": 1}


def test_a_carried_item_keeps_the_date_it_was_actually_last_found():
    older = prior("2026-08-01T00:00:00+00:00", investors=[UVC])
    newer = prior("2026-09-01T00:00:00+00:00",
                  investors=[{**UVC, "last_confirmed_at": "2026-08-01T00:00:00+00:00"}])
    out, _ = merge({"commercial": {"investors": []}}, [older, newer])
    assert out["profile"]["commercial"]["investors"][0]["last_confirmed_at"] == "2026-08-01T00:00:00+00:00"


def test_an_ungrounded_item_from_an_older_run_is_not_resurrected():
    out, _ = merge({"commercial": {"investors": []}},
                   [prior("2026-08-01T00:00:00+00:00", investors=[{"name": "Recalled VC", "source_url": ""}])])
    assert out["profile"]["commercial"]["investors"] == []


def test_a_founder_spelled_with_a_title_or_accent_is_one_founder_not_two():
    # Radical Dot's stored runs held "Andreas Wagner" and "Dr. Andreas Wagner" side by side.
    src = "https://acme.example/team"
    fresh = {"founders": [{"name": "Andreas Wagner", "role": "", "source_url": src},
                          {"name": "Alexandre Kremer", "source_url": src}]}
    older = prior("2026-08-01T00:00:00+00:00", founders=[
        {"name": "Dr. Andreas Wagner", "role": "CEO", "source_url": src},
        {"name": "Alexandre Krémer (CTO)", "source_url": src}])
    out, report = merge(fresh, [older])
    assert [f["name"] for f in out["profile"]["founders"]] == ["Andreas Wagner", "Alexandre Kremer"]
    assert report["founders"]["reconfirmed"] == 2


def test_duplicates_within_one_run_collapse_and_fill_each_others_blanks():
    src = "https://acme.example/team"
    out, _ = merge({"founders": [{"name": "Andreas Wagner", "role": "", "source_url": src},
                                 {"name": "Dr. Andreas Wagner", "role": "CEO", "source_url": src}]},
                   [prior("2026-08-01T00:00:00+00:00")])
    assert out["profile"]["founders"] == [{"name": "Andreas Wagner", "role": "CEO", "source_url": src}]


def test_a_founder_stored_with_and_without_initials_is_one_founder():
    # Phena's latest run listed "KD Kutadgu Gokalp Demirci" (this run) and "Kutadgu Gokalp Demirci"
    # (carried from August) — one co-founder, shown twice, because the initials defeated the name key.
    fresh = {"founders": [{"name": "KD Kutadgu Gokalp Demirci", "role": "Co-Founder",
                           "linkedin": "kutadgu@phena.tech", "source_url": "https://phena.example/en/about"}]}
    older = prior("2026-08-19T00:00:00+00:00", founders=[
        {"name": "Kutadgu Gokalp Demirci", "role": "Co-Founder", "linkedin": "kutadgu@phena.tech",
         "source_url": "https://phena.example"}])
    out, report = merge(fresh, [older])
    assert [f["name"] for f in out["profile"]["founders"]] == ["KD Kutadgu Gokalp Demirci"]
    assert report["founders"]["carried"] == 0


def test_a_founder_also_listed_as_an_advisor_is_shown_as_a_founder_only():
    src = "https://acme.example/team"
    out, _ = merge({"founders": [{"name": "Trevor Amanya", "source_url": src}],
                    "advisors": [{"name": "Trevor Amanya", "source_url": src},
                                 {"name": "Jane Roe", "source_url": src}]},
                   [prior("2026-08-01T00:00:00+00:00")])
    assert [a["name"] for a in out["profile"]["advisors"]] == ["Jane Roe"]


def test_a_namesake_with_another_domain_contributes_nothing():
    other = prior("2026-08-01T00:00:00+00:00", investors=[UVC], website="https://acme-other.example")
    out, _ = merge({"commercial": {"investors": []}}, [other])
    assert out["profile"]["commercial"]["investors"] == []


def test_a_directory_page_recorded_as_the_website_does_not_split_one_company_in_two():
    # Makkook AI's latest run recorded clutch.co/profile/makkook-ai as its website.
    listed = prior("2026-08-01T00:00:00+00:00", investors=[UVC], website="https://clutch.co/profile/acme-vision")
    out, _ = merge({"commercial": {"investors": []}}, [listed])
    assert [i["name"] for i in out["profile"]["commercial"]["investors"]] == ["UVC Partners"]


def test_the_facts_behind_a_carried_item_come_with_it():
    fact = Fact("investor", "UVC Partners", UVC["source_url"], "profile_research", 0.65, True,
                "2026-08-22T03:00:00+00:00").as_dict()
    out, _ = merge({"commercial": {"investors": []}},
                   [prior("2026-08-22T03:00:00+00:00", investors=[UVC], facts=[fact])])
    (carried,) = [f.as_dict() for f in out["facts"]]
    assert (carried["key"], carried["value"], carried["source_url"]) == ("investor", "UVC Partners",
                                                                        UVC["source_url"])
    # The original retrieval time, not this run's: the evidence is as old as the search that found it.
    assert carried["retrieved_at"] == "2026-08-22T03:00:00+00:00"


# --------------------------------------------------------------------------------- single values

def test_a_blank_on_refresh_never_replaces_a_sourced_value():
    founded = {"key": "founded_year_research", "value": "2019", "source_url": "https://about.example"}
    out, report = merge({"founded_year": ""}, [prior("2026-08-01T00:00:00+00:00", founded_year="2019",
                                                     facts=[founded])])
    assert out["profile"]["founded_year"] == "2019"
    assert out["profile"]["carried_fields"]["founded_year"] == "2026-08-01T00:00:00+00:00"
    assert report["fields_carried"] == ["founded_year"]


def test_a_newer_sourced_value_wins_and_the_older_one_is_kept_as_history():
    old = {"key": "funding_research", "value": "€2.7M", "source_url": "https://old.example"}
    new = {"key": "funding_research", "value": "€4.1M", "source_url": "https://new.example"}
    out, _ = merge({"funding": "€4.1M"}, [prior("2026-08-01T00:00:00+00:00", funding="€2.7M", facts=[old])],
                   facts=[new])
    assert out["profile"]["funding"] == "€4.1M"
    assert out["profile"]["history"]["funding"][0]["value"] == "€2.7M"


def test_a_model_recalled_headquarters_never_replaces_a_web_sourced_one():
    out, _ = merge({"hq": "Berlin, DE", "hq_origin": "llm"},
                   [prior("2026-08-01T00:00:00+00:00", hq="Munich, DE", hq_origin="web")])
    assert (out["profile"]["hq"], out["profile"]["hq_origin"]) == ("Munich, DE", "web")
    assert out["profile"]["history"]["hq"][0]["value"] == "Berlin, DE"


def test_the_database_value_on_this_run_wins_over_an_older_web_value():
    gd = {"key": "hq", "value": "Hamburg, DE", "source_url": "GlassDollar", "method": "glassdollar_api",
          "source_type": "private"}
    out, _ = merge({"hq": "Hamburg, DE"}, [prior("2026-08-01T00:00:00+00:00", hq="Munich, DE", hq_origin="web")],
                   facts=[gd])
    assert out["profile"]["hq"] == "Hamburg, DE"


# ------------------------------------------------------------------------------------- market

def _size(as_of, url="https://reports.example/m"):
    return {"value": "USD 3B", "cagr": "12%", "as_of": as_of, "source_url": url}


def test_a_market_figure_older_than_two_years_is_dropped_even_on_a_first_run():
    report = {}
    out = cf.merge_trend({"landscape": {"market_size": _size("2023")}}, [], NOW, TODAY, report)
    assert out["landscape"]["market_size"] is None
    assert report["market_size_dropped"]["as_of"] == "2023"


def test_a_base_year_within_two_years_is_current_and_a_forecast_year_is_not():
    # Reports published in 2026 state the 2024 or 2025 market. The 18-month line dropped those and
    # kept "2030" figures, because a forecast is always dated ahead.
    assert cf.market_size_current(_size("2025"), TODAY)
    assert cf.market_size_current(_size("2025-03"), TODAY)
    assert cf.market_size_current(_size("2024"), TODAY)
    assert not cf.market_size_current(_size("2023"), TODAY)
    assert not cf.market_size_current(_size("2030"), TODAY)        # a forecast, not the size


def test_an_undated_figure_is_current_only_when_it_was_found_recently():
    assert cf.market_size_current(_size(""), TODAY, found=TODAY)
    assert cf.market_size_current(_size(""), TODAY, found=dt.date(2025, 6, 1))
    assert not cf.market_size_current(_size(""), TODAY, found=dt.date(2025, 1, 1))
    assert not cf.market_size_current(_size(""), TODAY)            # no date at all


def test_a_current_market_figure_from_an_earlier_run_fills_a_gap_and_a_stale_one_does_not():
    fresh = {"landscape": {"market_size": None, "competitors": []}}
    usable = cf.usable_priors([prior("2026-08-01T00:00:00+00:00",
                                     trend={"landscape": {"market_size": _size("2025")}})],
                              cf.identity("Acme Vision", "https://acme.example"))
    out = cf.merge_trend(fresh, usable, NOW, TODAY, {})
    assert out["landscape"]["market_size"]["value"] == "USD 3B"
    stale = cf.usable_priors([prior("2026-08-01T00:00:00+00:00",
                                    trend={"landscape": {"market_size": _size("2023")}})],
                             cf.identity("Acme Vision", "https://acme.example"))
    assert cf.merge_trend(fresh, stale, NOW, TODAY, {})["landscape"]["market_size"] is None


# ----------------------------------------------------------------------------------- pipeline

def test_an_evaluation_carries_an_earlier_runs_investor_into_its_result(offline):
    df, tools = offline
    earlier = {"company": "Acme Vision", "run_created_at": "2026-08-22T03:00:00+00:00",
               "profile": {"website": "https://acme.example"},
               "deep_profile": {"commercial": {"investors": [UVC]}}, "facts": []}
    result = _run(df, tools, prior_runs=[earlier])
    investors = result["deep_profile"]["commercial"]["investors"]
    assert [i["name"] for i in investors] == ["UVC Partners"]
    assert investors[0]["last_confirmed_at"] == "2026-08-22T03:00:00+00:00"
    assert result["carry_forward"]["prior_runs"] == 1


def test_a_first_evaluation_is_unchanged(offline):
    df, tools = offline
    assert "carry_forward" not in _run(df, tools)


# ---------------------------------------------------------------------------------- customers

GRADE = {"level": 1, "quote": "serves chemical manufacturers", "source_url": "https://preqin.example/radical-dot"}


def test_a_sourced_customer_base_statement_is_kept_when_a_refresh_misses_it():
    """Radical Dot's Customers division went evidenced → unknown → evidenced across three runs
    because this one statement was found, missed, then found again."""
    out, report = merge({"customer_segment_grade": {}},
                        [prior("2026-10-01T00:00:00+00:00", customer_segment_grade=GRADE)])
    assert out["profile"]["customer_segment_grade"] == GRADE
    assert "customer_segment_grade" in report["fields_carried"]


def test_a_quoted_revenue_figure_and_a_certification_are_kept():
    revenue = {"status": "amount", "quote": "EUR 2M revenue", "source_url": "https://news.example/rev"}
    cert = {"name": "ISO 27001", "source_url": "https://trust.example"}
    out, _ = merge({"commercial": {"investors": [], "revenue": {}, "certifications": []}},
                   [prior("2026-08-01T00:00:00+00:00", commercial={"investors": [], "revenue": revenue,
                                                                   "certifications": [cert]})])
    assert out["profile"]["commercial"]["revenue"] == revenue
    assert [c["name"] for c in out["profile"]["commercial"]["certifications"]] == ["ISO 27001"]


def _customer_run(created, name, status="verified", url="https://lanxess.example/case"):
    run = prior(created, reference_customers=[name],
                customer_classes=[{"name": name, "relation": "customer", "size": "large_enterprise"}])
    run["verification"] = {"claims": [{"field": "reference_customer", "value": name, "status": status,
                                       "evidence_url": url}]}
    return run


def test_a_named_customer_an_earlier_fact_check_sourced_is_carried_with_that_source_and_label():
    out, report = merge({"reference_customers": []}, [_customer_run("2026-09-01T00:00:00+00:00", "LANXESS")])
    dp = out["profile"]
    assert dp["reference_customers"] == ["LANXESS"]
    assert dp["customer_evidence"]["LANXESS"] == {"source_url": "https://lanxess.example/case",
                                                  "last_confirmed_at": "2026-09-01T00:00:00+00:00"}
    assert dp["customer_classes"][0]["relation"] == "customer"        # so the rubric can count it
    assert report["reference_customers"]["carried"] == 1


def test_an_unsourced_or_contradicted_customer_is_not_carried():
    for run in (_customer_run("2026-09-01T00:00:00+00:00", "LANXESS", url=""),
                _customer_run("2026-09-01T00:00:00+00:00", "LANXESS", status="contradicted")):
        out, _ = merge({"reference_customers": []}, [run])
        assert out["profile"].get("reference_customers") == []


def test_traction_scores_a_carried_customer_with_its_earlier_source():
    from core.traction import gather_traction_inputs
    out, _ = merge({"reference_customers": []}, [_customer_run("2026-09-01T00:00:00+00:00", "LANXESS")])
    inputs = gather_traction_inputs({"company": "Acme Vision", "deep_profile": out["profile"], "verification": {}})
    (customer,) = inputs["customers"]
    assert (customer["name"], customer["source_url"], customer["origin"]) == \
        ("LANXESS", "https://lanxess.example/case", "carried")
