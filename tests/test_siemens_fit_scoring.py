"""Unit tests for the siemens_fit dimension in core/score.py.

Two regressions are pinned here, both found by re-scoring the 18 runs stored in data/runs.db.

1. The challenge library used to be blended in as a fixed 0.7/0.3 average whenever it held
   anything at all. With one approved, unrelated challenge recorded, the best match scored
   0-5.6 against every company in the corpus, so every startup silently lost ~30% of its tool
   fit. That single blend accounted for ALL EIGHT Pass verdicts in the corpus: Phena's fit of
   52.2 became 36.6 and Makkook AI's became 38.3, both under FIT_ALIGN_THRESHOLD. A demand-side
   match must only ever raise the fit.

2. A match whose `relation` the model declined to state used to take the multiplier reserved
   for `complement` (1.0) — the most generous of the four — so not committing scored exactly as
   well as the best case. 15 of the 54 stored matches carry no relation at all.

Requires the application dependencies (pandas), so run these in the app / Docker environment.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.score import score_startup  # noqa: E402


def _row():
    return pd.Series({
        "company_name": "Acme Vision",
        "hq": "Munich, DE",
        "founded_year": "2021",
        "employees_count": "40",
        "funding": "$5M seed",
        "customers": "Bosch",
        "linkedin_url": "https://linkedin.com/company/acme",
        "Your pitch": "Machine vision for production lines",
    })


def _fit(confidence=90, relation="complement", challenge=None):
    match = {"tool": "Industrial Edge", "division": "DI", "confidence": confidence}
    if relation is not None:
        match["relation"] = relation
    return {"aligned": True, "matches": [match],
            "challenge_match": challenge if challenge is not None else {}}


def _siemens_fit(fit):
    out = score_startup(_row(), {"facts": []}, {"claims": [], "red_flags": []}, fit, {})
    return out["dimensions"]["siemens_fit"]


# --------------------------------------------------------------- the challenge blend

def test_empty_challenge_library_leaves_fit_untouched():
    assert _siemens_fit(_fit(challenge={"score": 0.0, "library_size": 0})) == 90.0


def test_irrelevant_challenge_cannot_lower_fit():
    """The corpus case: library_size=1 and a best match of 0.0 against every company.

    Under the old 0.7/0.3 blend this returned 63.0 — a 27-point tax for the library merely
    existing. The library is a small opt-in list of problems Siemens people happened to type
    in; its silence about a startup is not evidence against that startup.
    """
    assert _siemens_fit(_fit(challenge={"score": 0.0, "library_size": 1})) == 90.0


def test_weak_challenge_match_cannot_lower_fit():
    assert _siemens_fit(_fit(challenge={"score": 5.6, "library_size": 1})) == 90.0


def test_strong_challenge_match_raises_fit():
    """A recorded Siemens need the startup answers well is real demand-side evidence."""
    weak = _siemens_fit(_fit(confidence=60, challenge={"score": 0.0, "library_size": 3}))
    strong = _siemens_fit(_fit(confidence=60, challenge={"score": 100.0, "library_size": 3}))
    assert strong > weak


def test_challenge_bonus_is_bounded_by_the_scale():
    assert _siemens_fit(_fit(confidence=100, challenge={"score": 100.0, "library_size": 3})) <= 100.0


def test_phena_clears_the_alignment_gate_again():
    """The exact stored numbers: confidence 95, relation substitute, one empty challenge.

    tool_fit is 95 * 0.55 = 52.25, which clears FIT_ALIGN_THRESHOLD. The old blend turned it
    into 36.6 and routed a genuinely aligned startup to Pass.
    """
    from core.config import FIT_ALIGN_THRESHOLD
    fit = _fit(confidence=95, relation="substitute", challenge={"score": 0.0, "library_size": 1})
    assert _siemens_fit(fit) >= FIT_ALIGN_THRESHOLD


# --------------------------------------------------------------- the relation multiplier

def test_relation_ranks_partnership_value():
    """A complement is the best partnership signal; a competitor the weakest."""
    fits = [_siemens_fit(_fit(relation=r))
            for r in ("complement", "integration", "adjacent", "substitute")]
    assert fits == sorted(fits, reverse=True)


def test_unstated_relation_is_not_treated_as_a_complement():
    """Declining to classify the relation must not earn the best-case multiplier."""
    assert _siemens_fit(_fit(relation=None)) < _siemens_fit(_fit(relation="complement"))


def test_unstated_relation_is_not_treated_as_a_competitor_either():
    """It is an absence of judgement, not a negative one — the cautious middle, not the floor."""
    assert _siemens_fit(_fit(relation=None)) > _siemens_fit(_fit(relation="substitute"))


def test_no_matches_scores_zero():
    assert _siemens_fit({"aligned": False, "matches": [], "challenge_match": {}}) == 0.0
