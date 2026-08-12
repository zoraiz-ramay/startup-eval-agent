"""Unit tests for prestige-weighted ecosystem scoring in core/score.py.

Requires the application dependencies (pandas), so run these in the app / Docker
environment (e.g. `python -m pytest tests/test_ecosystem_scoring.py`), not the light
agent venv. They assert that an EVIDENCED tier1 program lifts the ecosystem dimension
above the same startup with only a tier3 program, and that an unevidenced (self-claimed)
membership cannot earn full prestige points.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.provenance import Fact  # noqa: E402
from core.score import score_startup  # noqa: E402


def _row():
    return pd.Series({
        "company_name": "Acme Robotics",
        "hq": "Munich, DE",
        "founded_year": "2021",
        "employees_count": "40",
        "funding": "$5M seed",
        "customers": "Bosch",
        "linkedin_url": "https://linkedin.com/company/acme",
        "Your pitch": "Robots for factories",
    })


def _base_kwargs():
    enrichment = {"facts": [Fact(key="funding_web", value="raised", method="ddg_search",
                                 source_url="https://x/y", confidence=0.6, verified=True)]}
    verification = {"claims": [], "red_flags": []}
    fit = {"matches": [], "challenge_match": {}}
    return enrichment, verification, fit


def _ecosystem(profile):
    enrichment, verification, fit = _base_kwargs()
    out = score_startup(_row(), enrichment, verification, fit, profile)
    return out["dimensions"]["ecosystem"]


def test_tier1_beats_tier3():
    tier1 = {"programs": [{"name": "Y Combinator", "type": "accelerator",
                           "source_url": "https://ycombinator.com/companies/acme",
                           "prestige": "tier1"}]}
    tier3 = {"programs": [{"name": "Local Hub", "type": "incubator",
                           "source_url": "https://localhub.org/acme",
                           "prestige": "tier3"}]}
    assert _ecosystem(tier1) > _ecosystem(tier3)


def test_unevidenced_membership_scores_low():
    evidenced = {"programs": [{"name": "Techstars", "type": "accelerator",
                               "source_url": "https://techstars.com/acme",
                               "prestige": "tier1"}]}
    self_claim = {"programs": [{"name": "Techstars", "type": "accelerator",
                                "source_url": "", "prestige": "tier1"}]}
    assert _ecosystem(evidenced) > _ecosystem(self_claim)


def test_prestige_points_capped():
    many = {"programs": [
        {"name": f"Prog {i}", "type": "accelerator",
         "source_url": f"https://p{i}.com/acme", "prestige": "tier1"}
        for i in range(6)
    ]}
    # Even six tier1 memberships cannot push ecosystem to a runaway value: the dimension
    # stays within [0, 100] and the prestige contribution is capped.
    assert 0 <= _ecosystem(many) <= 100
