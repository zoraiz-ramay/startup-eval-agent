"""Tests for the corroborated / self-asserted split on program memberships.

A membership found only on the company's OWN site is evidence that the company CLAIMS it,
not that it holds it — and programs like NVIDIA Inception and Microsoft for Startups publish
no searchable public member directory, so such a claim is often uncheckable. These tests pin
down the three behaviours that follow: the label is assigned correctly, third-party evidence
outranks a site claim, and a self-asserted membership cannot earn full prestige points even
though it now carries a source URL (the company website).

Requires pandas; run in the app environment.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.profile import _program_grounded, _detect_programs, _ground_programs  # noqa: E402
from core.score import score_startup  # noqa: E402

_THIRD_PARTY = {"q": [{"title": "Acme joins NVIDIA Inception",
                       "body": "acme was accepted into nvidia inception",
                       "href": "https://news.example/acme"}]}
# _merge_site_results keys the company's own pages as __site__N and prepends the company name.
_OWN_SITE = {"__site__0": [{"title": "Acme — /partners",
                            "body": "acme part of the nvidia inception program",
                            "href": "https://acme.com"}]}


def test_third_party_result_is_corroborated():
    assert _program_grounded("nvidia inception", "acme", "", _THIRD_PARTY) == (
        "https://news.example/acme", "corroborated")


def test_company_own_site_is_self_asserted():
    assert _program_grounded("nvidia inception", "acme", "", _OWN_SITE) == (
        "https://acme.com", "self_asserted")


def test_application_text_only_is_self_asserted():
    src, conf = _program_grounded("nvidia inception", "acme", "we joined nvidia inception", {})
    assert (src, conf) == ("", "self_asserted")


def test_third_party_evidence_outranks_a_site_claim():
    """Both present -> the independent source wins, so the badge reads corroborated."""
    combined = {**_OWN_SITE, **_THIRD_PARTY}
    assert _program_grounded("nvidia inception", "acme", "", combined)[1] == "corroborated"


def test_ungrounded_membership_is_still_dropped():
    """The split must not weaken the co-occurrence gate that prevents false memberships."""
    directory = {"q": [{"title": "Top 100 startups in NVIDIA Inception",
                        "body": "beta corp, gamma gmbh and others", "href": "https://dir/x"}]}
    assert _program_grounded("nvidia inception", "acme", "", directory) is None
    assert _program_grounded("nvidia inception", "acme", "", {}) is None


def test_detect_and_ground_programs_carry_the_confidence_label():
    row = pd.Series({"company_name": "Acme"})
    detected = _detect_programs(row, _OWN_SITE)
    nvidia = [p for p in detected if p["name"].lower() == "nvidia inception"]
    assert nvidia and nvidia[0]["confidence"] == "self_asserted"

    grounded = _ground_programs(
        [{"name": "NVIDIA Inception", "type": "corporate_program"}], row, _THIRD_PARTY)
    assert grounded and grounded[0]["confidence"] == "corroborated"


def _eco(programs):
    row = pd.Series({"company_name": "Acme"})
    profile = {"founders": [], "key_team": [], "advisors": [], "employees": "",
               "parent_group": "", "reference_customers": [], "customer_segment": "",
               "sfs": {"relevant": False, "rationale": ""}, "programs": programs}
    return score_startup(row, {"facts": []}, {}, {}, profile)["dimensions"]["ecosystem"]


def test_self_asserted_program_cannot_earn_full_prestige_points():
    """The site URL must not be mistaken for independent evidence.

    Before the confidence label, `source_url.startswith('http')` decided this — and a
    site-grounded membership carries the company's own website as its URL, so it would have
    scored as fully evidenced.
    """
    claimed = _eco([{"name": "NVIDIA Inception", "prestige": "tier1",
                     "source_url": "https://acme.com", "confidence": "self_asserted"}])
    corroborated = _eco([{"name": "NVIDIA Inception", "prestige": "tier1",
                          "source_url": "https://news.example/acme",
                          "confidence": "corroborated"}])
    assert claimed < corroborated
    assert claimed > _eco([])          # still worth something; it is a real signal


def test_spelling_variants_collapse_to_one_membership():
    """The LLM and the keyword scan name the same program differently.

    'NVIDIA Inception Program' vs 'Nvidia Inception' survived an exact-string dedup, so the
    profile listed one membership twice and the ecosystem score counted it twice.
    """
    from core.profile import _dedupe_programs

    out = _dedupe_programs([
        {"name": "NVIDIA Inception Program", "source_url": "", "confidence": "self_asserted"},
        {"name": "Nvidia Inception", "source_url": "https://acme.com",
         "confidence": "self_asserted"},
    ])
    assert len(out) == 1
    assert out[0]["source_url"] == "https://acme.com"      # the entry with evidence wins


def test_dedupe_prefers_corroborated_and_keeps_distinct_programs():
    from core.profile import _dedupe_programs

    out = _dedupe_programs([
        {"name": "Techstars", "source_url": "https://acme.com", "confidence": "self_asserted"},
        {"name": "Techstars", "source_url": "https://news/x", "confidence": "corroborated"},
        {"name": "Y Combinator", "source_url": "https://news/y", "confidence": "corroborated"},
    ])
    assert len(out) == 2
    tech = [p for p in out if p["name"] == "Techstars"][0]
    assert tech["confidence"] == "corroborated"


def _claimed(name, tier):
    return {"name": name, "prestige": tier, "source_url": "https://acme.com",
            "confidence": "self_asserted"}


def test_self_asserted_points_follow_the_prestige_tier():
    """A claimed NVIDIA Inception must outweigh a claimed generic local incubator.

    Self-asserted memberships used to earn a flat 4 points each, so a logo wall of obscure
    programs scored the same as a top-tier one.
    """
    assert _eco([_claimed("NVIDIA Inception", "tier1")]) > _eco([_claimed("Local Hub", "tier3")])


def test_self_asserted_points_are_capped():
    """A long list of self-claimed logos cannot run away with the ecosystem dimension."""
    from core.config import PROGRAM_SELF_ASSERTED_CAP

    many = _eco([_claimed(f"Program {i}", "tier1") for i in range(10)])
    baseline = _eco([])
    assert many - baseline <= PROGRAM_SELF_ASSERTED_CAP
    # ...and a genuinely corroborated set of the same size still scores higher.
    corroborated = _eco([{"name": f"Program {i}", "prestige": "tier1",
                          "source_url": "https://news.example/acme",
                          "confidence": "corroborated"} for i in range(10)])
    assert corroborated > many


def test_legacy_profiles_without_confidence_keep_the_url_heuristic():
    """Cached profiles predate the field and must not silently lose their score."""
    legacy = _eco([{"name": "NVIDIA Inception", "prestige": "tier1",
                    "source_url": "https://news.example/acme"}])
    assert legacy == _eco([{"name": "NVIDIA Inception", "prestige": "tier1",
                            "source_url": "https://news.example/acme",
                            "confidence": "corroborated"}])
