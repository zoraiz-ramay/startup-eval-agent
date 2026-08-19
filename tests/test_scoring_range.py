"""The score has to be able to reach the top of its own scale.

Across fifteen real stored runs the highest final score was 54.4 and only two cleared 50 —
including runs for companies whose evidence is not in doubt. Four separate defects held the
number down, and each one is pinned here:

* the three Stage checkboxes were tested for non-emptiness, and they hold `0`/`1`, so every
  application row read as "growth stage" while every web-sourced row read as no stage at all;
* `completeness` counted filled cells of the application form, not facts the run established,
  and the researched values are merged into the profile *after* scoring;
* `traction` could only be earned through nameable reference customers, capping every consumer
  business at the 20 points a funding round was worth;
* `market` was a yes/no on funding, so the researched market momentum — computed on every run —
  never reached the score at all.

These are range and discrimination tests. They assert relations between scores, not constants,
so re-weighting a component does not break them but flattening one does.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.provenance import Fact  # noqa: E402
from core.score import (STAGE_EARLY_COL, STAGE_GROWTH_COL, STAGE_PROTO_COL,  # noqa: E402
                        score_startup)
from core.text import parse_funding_amount  # noqa: E402

_EMPTY_VER = {"claims": [], "red_flags": []}
_NO_FIT = {"matches": [], "challenge_match": {}}


def _score(row, *, profile=None, verification=None, fit=None, facts=(), trend=None):
    return score_startup(pd.Series(row), {"facts": list(facts)},
                         verification or _EMPTY_VER, fit or _NO_FIT, profile or {}, trend)


def _customer_claims(*statuses):
    return {"claims": [{"field": "reference_customer", "value": f"Acct {i}", "status": s}
                       for i, s in enumerate(statuses)], "red_flags": []}


# --------------------------------------------------------------- stage flags are flags

def test_an_unticked_growth_box_is_not_a_growth_stage_company():
    """`str("0").strip()` is truthy, so the old test passed for every applicant. Phena —
    founded 2026, two to ten staff, Early ticked and Growth not — was scored as a mature
    company selling to its main target market."""
    early = _score({"company_name": "Phena", STAGE_GROWTH_COL: "0",
                    STAGE_EARLY_COL: "1", STAGE_PROTO_COL: "0"})
    growth = _score({"company_name": "Phena", STAGE_GROWTH_COL: "1",
                     STAGE_EARLY_COL: "0", STAGE_PROTO_COL: "0"})
    assert early["dimensions"]["product"] < growth["dimensions"]["product"]


def test_the_three_stages_are_ordered():
    def product(**flags):
        row = {"company_name": "Acme", STAGE_GROWTH_COL: "0",
               STAGE_EARLY_COL: "0", STAGE_PROTO_COL: "0"}
        row.update(flags)
        return _score(row)["dimensions"]["product"]

    assert (product(**{STAGE_PROTO_COL: "1"})
            < product(**{STAGE_EARLY_COL: "1"})
            < product(**{STAGE_GROWTH_COL: "1"}))


@pytest.mark.parametrize("value", ["1", "1.0", "TRUE", "yes", "x"])
def test_a_ticked_box_is_recognised_however_the_sheet_spells_it(value):
    """A column containing one blank is read as float64, so a tick arrives as "1.0"."""
    assert _score({"company_name": "Acme", STAGE_GROWTH_COL: value})["dimensions"]["product"] == 90


# --------------------------------------------------------- stage without a pitch form

def test_a_web_sourced_company_is_staged_from_its_description():
    """The Stage columns exist only on the application form. Web-sourced rows have none, and
    used to score the same 40 whether the company was an idea or a public one."""
    mature = _score({"company_name": "Uber",
                     "Development stage of your solution": "Growth stage, scaling globally"})
    early = _score({"company_name": "Seedco",
                    "Development stage of your solution": "Working prototype in beta"})
    assert mature["dimensions"]["product"] > early["dimensions"]["product"]


def test_an_unknown_stage_lands_mid_scale_rather_than_at_the_bottom():
    """Not knowing is already priced in by the confidence multiplier, which scales the whole
    score. Charging for it again in the dimension made a researched company score below an
    applicant who ticked a box."""
    unknown = _score({"company_name": "Acme"})["dimensions"]["product"]
    idea = _score({"company_name": "Acme",
                   "Development stage of your solution": "Concept stage"})["dimensions"]["product"]
    growth = _score({"company_name": "Acme",
                     STAGE_GROWTH_COL: "1"})["dimensions"]["product"]
    assert idea < unknown < growth


def test_a_corroborated_customer_outranks_the_stage_the_form_claimed():
    proto = {"company_name": "Acme", STAGE_PROTO_COL: "1"}
    assert (_score(proto, verification=_customer_claims("verified"))["dimensions"]["product"]
            > _score(proto)["dimensions"]["product"])


# ------------------------------------------------------------------ traction is earnable

def test_a_company_without_nameable_accounts_can_still_show_traction():
    """35 points per verified reference customer was the only route to traction, so a consumer
    business — no accounts to name, by construction — could never pass the 20 points a funding
    round was worth, however large the round or the payroll."""
    nothing = _score({"company_name": "Startup"})["dimensions"]["traction"]
    consumer = _score({"company_name": "Uber", "funding": "$25.2 billion over 33 rounds",
                       "employees_count": "31100"},
                      profile={"customer_segment": "riders and drivers in 70 countries"})
    assert consumer["dimensions"]["traction"] > nothing + 20


def test_headcount_and_round_size_both_move_traction():
    base = {"company_name": "Acme", "funding": "$1M seed", "employees_count": "4"}
    bigger_round = dict(base, funding="$120M Series C")
    bigger_team = dict(base, employees_count="400")
    assert _score(bigger_round)["dimensions"]["traction"] > _score(base)["dimensions"]["traction"]
    assert _score(bigger_team)["dimensions"]["traction"] > _score(base)["dimensions"]["traction"]


def test_verified_accounts_still_beat_unverified_ones():
    """The anti-gaming property the old formula had, kept intact by the rebalance."""
    verified = _score({"company_name": "Acme"}, verification=_customer_claims("verified",
                                                                             "verified"))
    claimed = _score({"company_name": "Acme"}, verification=_customer_claims("unverified",
                                                                            "unverified"))
    assert verified["dimensions"]["traction"] > claimed["dimensions"]["traction"]


# ------------------------------------------------------------------- market reads the niche

def test_researched_market_momentum_reaches_the_score():
    """`analyze_trend` scores the niche 0-100 on every run. It was computed, stored, displayed
    — and never passed to `score_startup`."""
    row = {"company_name": "Acme", "funding": "$5M seed"}
    hot = _score(row, trend={"method": "web+llm", "momentum": 90})
    cold = _score(row, trend={"method": "web+llm", "momentum": 15})
    assert hot["dimensions"]["market"] > cold["dimensions"]["market"]


def test_a_trend_step_that_did_not_run_is_neutral_not_negative():
    """"We could not analyse the market" must never read as "the market is bad" — the same
    rule the profile follows for missing evidence."""
    row = {"company_name": "Acme", "funding": "$5M seed"}
    neutral = _score(row, trend={"method": "web+llm", "momentum": 50})["dimensions"]["market"]
    assert _score(row)["dimensions"]["market"] == neutral
    assert _score(row, trend={"method": "offline", "momentum": 0})["dimensions"]["market"] \
        == neutral


# ----------------------------------------------------- completeness measures the evaluation

def test_completeness_counts_researched_facts_not_filled_form_cells():
    """The lever that held every score down. `score_startup` runs before `backfill_profile`,
    so a company whose founding year, headcount, funding and customers had all been found and
    cited was still scored as a thin profile and lost a third of its score."""
    thin = {"company_name": "Acme", "Your pitch": "We do things"}
    researched = {"founded_year": "2019", "employees": "45", "funding": "$12M Series A",
                  "reference_customers": ["Bosch"]}
    before = _score(thin)
    after = _score(thin, profile=researched)
    assert after["data_completeness"] > before["data_completeness"]
    assert after["data_confidence"] > before["data_confidence"]
    assert after["final_score"] > before["final_score"]


def test_missing_evidence_agrees_with_the_completeness_number():
    """The list the reviewer reads and the number that caps the score answer the same
    question, so they must not be computed two different ways."""
    out = _score({"company_name": "Acme", "hq": "Munich, DE"},
                 profile={"founded_year": "2019", "funding": "$3M seed"})
    assert "founded_year" not in out["missing_evidence"]
    assert "funding" not in out["missing_evidence"]
    assert len(out["missing_evidence"]) == round((1 - out["data_completeness"]) * 8)


def test_a_public_identity_counts_however_the_source_spells_it():
    """`web_profile_row` hardcodes an empty `linkedin_url`, so every web-sourced company was
    permanently one eighth short of a complete profile for a field research never fills."""
    assert _score({"company_name": "Acme", "website": "acme.io"})["data_completeness"] > \
        _score({"company_name": "Acme"})["data_completeness"]


@pytest.mark.parametrize("blank", [None, float("nan"), "nan", "None", "  "])
def test_pandas_and_json_spellings_of_no_value_do_not_count_as_knowledge(blank):
    """`str(None)` is "None" and `str(nan)` is "nan"; both are truthy, and a truthy blank is a
    field the run would claim to know."""
    assert _score({"company_name": "Acme", "hq": blank})["missing_evidence"].count("hq") == 1


# ------------------------------------------------------------------------ the range itself

def test_a_well_evidenced_company_reaches_the_upper_half_of_the_scale():
    """The complaint this file exists for: nothing could score above about 54, so the top half
    of a 0-100 scale was decorative."""
    row = {"company_name": "Acme Robotics", "hq": "Munich, DE", "founded_year": "2018",
           "employees_count": "180", "funding": "$45M Series B", "customers": "Bosch, BMW",
           "linkedin_url": "https://linkedin.com/company/acme",
           "Your pitch": "Autonomous inspection robots for process plants",
           STAGE_GROWTH_COL: "1"}
    facts = [Fact(key=f"f{i}", value="v", method="ddg_search", source_url=f"https://x/{i}",
                  confidence=0.7, verified=True) for i in range(4)]
    out = _score(row, facts=facts,
                 verification=_customer_claims("verified", "verified", "verified"),
                 fit={"matches": [{"confidence": 80, "relation": "complement"}],
                      "challenge_match": {}},
                 profile={"founders": [{"name": "R Vogel", "background": "ex-KUKA"}],
                          "advisors": [{"name": "A Weber"}], "programs": [],
                          "parent_group": ""},
                 trend={"method": "web+llm", "momentum": 80})
    assert out["final_score"] > 75


def test_a_thin_unevidenced_application_still_scores_low():
    """The fix must widen the range, not shift everything upwards — a blank application has to
    stay clearly separated from an evidenced company."""
    out = _score({"company_name": "Anon", "Your pitch": "An AI platform"})
    assert out["final_score"] < 45


# --------------------------------------------------------------------------- funding size

@pytest.mark.parametrize("value, expected", [
    ("$5M seed", 5_000_000),
    ("Series C, $200 million", 200_000_000),
    ("€2.8M", 2_800_000),
    ("1.4B", 1_400_000_000),
    ("2831100.0", 2_831_100),          # the xlsx cell and the API bigint
    ("€250K pre-seed", 250_000),
    ("Pre-Seed, amount undisclosed", 0.0),
    ("Seed round, 2023", 0.0),         # a bare year is not an amount
    ("", 0.0),
    (None, 0.0),
])
def test_funding_amounts_are_read_at_their_magnitude(value, expected):
    assert parse_funding_amount(value) == expected
