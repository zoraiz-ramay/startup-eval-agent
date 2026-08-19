"""Weighted six-dimension scoring with data-confidence capping."""
from __future__ import annotations

import re

import pandas as pd

from .config import (WEIGHTS, THIN_PROFILE_CAP, PROGRAM_PRESTIGE_WEIGHTS, PROGRAM_PRESTIGE_CAP,
                     PROGRAM_SELF_ASSERTED_FACTOR, PROGRAM_SELF_ASSERTED_CAP)
from .text import has_funding_signal, parse_funding_amount

# Per-route weight profiles (each sums to 1.0). The universal WEIGHTS remain the
# backwards-compatible headline score; these drive route-specific recommendations.
ROUTE_WEIGHTS = {
    "Connect":     {"traction": 0.35, "siemens_fit": 0.30, "product": 0.15,
                    "market": 0.10, "founder": 0.05, "ecosystem": 0.05},
    "Collaborate": {"siemens_fit": 0.35, "product": 0.20, "traction": 0.15,
                    "founder": 0.15, "market": 0.10, "ecosystem": 0.05},
    "Empower":     {"product": 0.25, "founder": 0.25, "siemens_fit": 0.20,
                    "ecosystem": 0.15, "market": 0.10, "traction": 0.05},
}


STAGE_GROWTH_COL = ("Stage: Growth market stage (your solution is mature, and you are selling it "
                    "to your main target market)")
STAGE_EARLY_COL = ("Stage: Early market stage (you are selling an early version of your solution, "
                   "early adopters are your main clients)")
STAGE_PROTO_COL = "Stage: Prototype stage (a working prototype of your solution does exist)"

# Read in order; the first match wins, so the strongest wording present decides.
_STAGE_WORDS = (
    (90.0, r"\bgrowth\b|\bscal(?:e|ing)\b|\bcommercialis(?:ed|ing)\b|\bcommercializ(?:ed|ing)\b"
           r"|\bmature\b|\bmass[- ]market\b|\bexpansion\b"),
    (75.0, r"\bearly market\b|\bearly adopter|\bgo[- ]to[- ]market\b|\bpaying customer"
           r"|\blaunched\b|\brevenue\b|\bin production\b|\bdeployed\b|\bgenerally available\b"),
    (55.0, r"\bprototype\b|\bmvp\b|\bpilot|\bbeta\b|\bproof[- ]of[- ]concept\b|\bpoc\b|\bdemo\b"),
    (35.0, r"\bidea\b|\bideation\b|\bconcept\b|\bresearch stage\b|\bpre[- ]product\b"),
)

# Application columns that answer the same question as a `key_fields` entry, tried in order.
_ROW_EQUIVALENTS = {
    "customers": ("customers", "Reference customers"),
    "linkedin_url": ("linkedin_url", "crunchbase_url", "website", "domain"),
    "Your pitch": ("Your pitch", "short_description"),
}
# Researched `deep_profile` keys that answer it instead, when no column does.
_PROFILE_EQUIVALENTS = {
    "founded_year": ("founded_year",),
    "employees_count": ("employees",),
    "funding": ("funding",),
    "customers": ("reference_customers", "customer_segment"),
}


def _txt(value) -> str:
    """A cell as text, with pandas' and JSON's two spellings of "no value" treated as blank.

    `str(None)` is "None" and `str(float('nan'))` is "nan", both of which are truthy and both
    of which would count as a known field below.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _has(row, *cols) -> bool:
    return any(_txt(row.get(c, "")) for c in cols)


def _flag(row, col) -> bool:
    """A pitch-form checkbox, read as a checkbox.

    The three Stage columns hold 0/1 flags, and the old test was non-emptiness: "0" is a
    non-empty string, so *every* application row registered as growth stage. Phena — founded
    2026, two to ten staff, Early=1 and Growth=0 — scored 85 for a "mature solution being sold
    to its main target market". The float64 spelling "1.0" is accepted for the same reason
    `_cell` exists: a column containing one blank types the whole column as float.
    """
    return _txt(row.get(col, "")).lower() in ("1", "1.0", "true", "yes", "y", "x", "checked")


def _headcount(row: pd.Series, profile: dict) -> int:
    """Lower bound of the stated headcount — "11-50" counts as 11, "8.0" as 8, else 0."""
    text = _txt(row.get("employees_count", "")) or _txt(row.get("employee_band", "")) \
        or _txt(profile.get("employees", ""))
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    return int(min(nums)) if nums else 0


def _known(row: pd.Series, profile: dict, field: str) -> bool:
    """Whether the RUN knows this field, from the application row or from research.

    Completeness used to read the application row alone, so it measured how much of the pitch
    form an applicant had filled in rather than how much the evaluation established. Two
    consequences, both wrong: a web-sourced company has no form at all, and the researched
    values that the profile header displays are merged in by `backfill_profile` *after* this
    point in the pipeline. A company whose HQ, founding year, headcount, funding and customers
    had all been found and cited could still be scored as a thin profile and lose a third of
    its score to the confidence multiplier. Line 43 below already applies this row-then-profile
    fallback to funding; completeness never got the same fix.
    """
    if any(_txt(row.get(c, "")) for c in _ROW_EQUIVALENTS.get(field, (field,))):
        return True
    for key in _PROFILE_EQUIVALENTS.get(field, ()):
        value = profile.get(key)
        if isinstance(value, (list, tuple)):
            if any(value):
                return True
        elif _txt(value):
            return True
    return False


def score_startup(row: pd.Series, enrichment: dict, verification: dict, fit: dict,
                  profile: dict = None, trend: dict = None) -> dict:
    profile = profile or {}
    trend = trend or {}
    facts = enrichment["facts"]
    _W = {"verified": 1.0, "partial": 0.5, "unverified": 0.25, "contradicted": 0.0}
    cust = [c for c in verification.get("claims", []) if c.get("field") == "reference_customer"]
    verified_custs = sum(1 for c in cust if c.get("status") == "verified")
    unverified_custs = sum(1 for c in cust if c.get("status") in ("unverified", "partial"))
    contradicted = sum(1 for c in verification.get("claims", []) if c.get("status") == "contradicted")
    # anti-gaming: verified beats partial/unverified; contradicted counts zero
    effective_traction = sum(_W.get(c.get("status", "unverified"), 0.25) for c in cust)

    # The application row is authoritative, but it is blank for most startups — and for a
    # web-sourced company it does not exist at all. Reading only the row meant a round the
    # research had actually established (and which the profile header already displayed) was
    # invisible to scoring, despite being worth 20 traction points and market 70 vs 50.
    funding_txt = _txt(row.get("funding", "")) or _txt(profile.get("funding", ""))
    funding_amount = parse_funding_amount(funding_txt)
    has_funding = has_funding_signal(funding_txt) or funding_amount > 0

    dims = {}

    # traction: evidence that someone outside the company has committed something to it —
    # named accounts, investor money, payroll. Reference customers used to be the only route
    # (35 points each, so three verified accounts for full marks) plus a flat 20 for having
    # raised anything at all. That put a hard ceiling of 20 on every company that does not
    # sell to nameable accounts, so a consumer business with a billion-dollar raise and ten
    # thousand staff scored the same as a company with no traction whatsoever.
    traction = min(45.0, 15.0 * effective_traction)
    if has_funding:
        traction += (30.0 if funding_amount >= 25_000_000 else
                     22.0 if funding_amount >= 3_000_000 else 15.0)
    headcount = _headcount(row, profile)
    traction += (20.0 if headcount >= 50 else
                 12.0 if headcount >= 10 else
                 5.0 if headcount >= 3 else 0.0)
    if not cust and _txt(profile.get("customer_segment", "")):
        # A described customer base, for the companies whose accounts are not nameable.
        # Weaker than a corroborated logo, but it is not the absence of customers.
        traction += 10.0
    dims["traction"] = min(100.0, traction)

    # siemens_fit: supply-side tool match, relation-aware (a substitute/competitor is a much
    # weaker partnership signal than a complement), blended with the demand-side challenge
    # match when the challenge library has entries.
    _REL = {"complement": 1.0, "integration": 0.95, "adjacent": 0.75, "substitute": 0.55}
    if fit.get("matches"):
        m0 = fit["matches"][0]
        tool_fit = float(m0.get("confidence", 0)) * _REL.get(str(m0.get("relation", "")).lower(), 1.0)
    else:
        tool_fit = 0.0
    ch = fit.get("challenge_match", {}) or {}
    if ch.get("library_size"):
        dims["siemens_fit"] = min(100.0, 0.7 * tool_fit + 0.3 * float(ch.get("score", 0)))
    else:
        dims["siemens_fit"] = min(100.0, tool_fit)
    # product: how far the solution has actually got. The pitch form's three Stage checkboxes
    # first; failing those, the free-text stage description, which is the only stage answer a
    # web-sourced company has and which used to score every one of them 40.
    #
    # An unknown stage lands mid-scale rather than at the bottom. Not knowing is already
    # priced in — by the data-confidence multiplier, which scales the whole score — and
    # charging for it a second time here is what made a researched company score below an
    # applicant who ticked a box.
    if _flag(row, STAGE_GROWTH_COL):
        product = 90.0
    elif _flag(row, STAGE_EARLY_COL):
        product = 75.0
    elif _flag(row, STAGE_PROTO_COL):
        product = 55.0
    else:
        stage_txt = " ".join((_txt(row.get("Development stage of your solution", "")),
                              _txt(row.get("Business model", ""))))
        product = next((pts for pts, pat in _STAGE_WORDS if re.search(pat, stage_txt, re.I)), 55.0)
    if verified_custs and product < 75.0:
        product = 75.0        # a corroborated deployment outranks whatever the form claimed
    dims["product"] = product

    # market: the size and heat of the space. This was binary — 70 with funding, 50 without —
    # which made it a second, coarser reading of traction and could not tell a booming niche
    # from a flat one. `analyze_trend` already researches exactly that on every run and scores
    # it 0-100; its verdict simply was never passed to the scorer.
    market = 50.0
    if has_funding:
        market += 15.0 if funding_amount >= 25_000_000 else 10.0
    if str(trend.get("method", "")) in ("web+llm", "llm-knowledge"):
        # Centred on 50: a neutral niche moves nothing, and an unanalysed one cannot move it
        # at all, so a failed trend step never reads as a bad market.
        market += 0.5 * (float(trend.get("momentum", 50) or 50) - 50.0)
    dims["market"] = max(0.0, min(100.0, market))

    # founder: real researched signal (identified founders, backgrounds, advisors),
    # falling back to the old contact-presence heuristic when research found nothing.
    founders = [f for f in profile.get("founders", []) if isinstance(f, dict) and f.get("name")]
    advisors = [a for a in profile.get("advisors", []) if isinstance(a, dict) and a.get("name")]
    if founders or advisors:
        founder_score = 45.0
        founder_score += 20 if founders else 0
        founder_score += 10 if any(str(f.get("background", "")).strip() for f in founders) else 0
        founder_score += 15 if advisors else 0
        founder_score += 5 if _has(row, "linkedin_url", "contact_name") else 0
        dims["founder"] = min(100, founder_score)
    else:
        dims["founder"] = 70 if _has(row, "linkedin_url", "contact_name") else 45

    # ecosystem: verified web presence + program membership (Xcelerator, incubators,
    # corporate programs like Nvidia Inception / Microsoft for Startups) + corporate parent.
    # Programs are SUPPORTING signals: only evidence-backed memberships (with a source URL)
    # earn points, and each is weighted by a PRESTIGE TIER (a Y Combinator / Siemens-run spot
    # is worth more than a generic local incubator), so a self-claimed membership cannot inflate
    # the score and one prestigious program outweighs several obscure ones.
    # "Evidenced" means INDEPENDENTLY corroborated: the membership and the company co-occur in
    # a third-party result. A source_url alone is no longer sufficient evidence, because a
    # membership grounded only in the company's own fetched site pages also carries a URL (its
    # website) — counting that as evidence would let any startup inflate this dimension just by
    # listing a program on its /partners page. Older cached profiles predate the `confidence`
    # field, so they fall back to the original URL heuristic.
    programs = [p for p in profile.get("programs", []) if isinstance(p, dict) and p.get("name")]

    def _corroborated(p: dict) -> bool:
        conf = str(p.get("confidence", "")).strip().lower()
        if conf:
            return conf == "corroborated"
        return str(p.get("source_url", "")).startswith("http")

    def _tier_pts(p: dict) -> float:
        return PROGRAM_PRESTIGE_WEIGHTS.get(str(p.get("prestige", "tier3")).lower(),
                                            PROGRAM_PRESTIGE_WEIGHTS["tier3"])

    # Both groups are weighted by prestige tier, so one top-tier membership still outweighs
    # several obscure ones; the self-asserted side is discounted and capped separately, so a
    # logo wall can never reach what independent corroboration earns.
    evidenced_programs = [p for p in programs if _corroborated(p)]
    claimed_programs = [p for p in programs if not _corroborated(p)]
    prestige_pts = min(sum(_tier_pts(p) for p in evidenced_programs), PROGRAM_PRESTIGE_CAP)
    claimed_pts = min(PROGRAM_SELF_ASSERTED_FACTOR * sum(_tier_pts(p) for p in claimed_programs),
                      PROGRAM_SELF_ASSERTED_CAP)
    # Web presence is a THRESHOLD, not a ladder: that the open web corroborates a company at
    # all says it is real, and the fifth corroborated search result says nothing the fourth
    # did not. At 30 + 20 per verified fact, four of them — which a normal enrichment wave
    # produces for almost anyone — already reached 110, so this dimension scored exactly 100
    # in every one of fifteen real runs and the prestige tiers, the self-asserted discount and
    # the corporate parent below decided nothing at all.
    corroborated = len([f for f in facts if f.method == "ddg_search" and f.verified])
    eco = 15.0 + min(25.0, 5.0 * corroborated)
    eco += prestige_pts + claimed_pts
    eco += 10 if _txt(profile.get("parent_group", "")) else 0
    dims["ecosystem"] = min(100.0, eco)

    raw = sum(dims[k] * WEIGHTS[k] for k in WEIGHTS)

    key_fields = ["company_name", "hq", "founded_year", "employees_count", "funding",
                  "customers", "linkedin_url", "Your pitch"]
    known = {c: _known(row, profile, c) for c in key_fields}
    completeness = sum(1 for c in key_fields if known[c]) / len(key_fields)
    data_confidence = 0.5 + 0.5 * completeness
    final = raw * data_confidence
    if completeness < 0.5:               # confidence caps thin profiles
        final = min(final, THIN_PROFILE_CAP)

    # ---- route-aware scorecards: the same dimensions re-weighted per pillar, because
    # what makes a great Connect candidate (deployable traction) differs from a great
    # Empower candidate (technical promise Siemens tools can accelerate).
    scorecards = {
        route: round(sum(dims[k] * w[k] for k in w) * data_confidence, 1)
        for route, w in ROUTE_WEIGHTS.items()
    }

    # ---- missing evidence (absence of data) — kept strictly separate from red flags
    # (negative evidence). "We don't know" must never read as "it's bad".
    # Same test as completeness, so the list the UI shows and the number that caps the score
    # cannot disagree about what the run knows.
    missing = [c for c in key_fields if not known[c]]

    # ---- red flags: only genuinely negative signals
    red_flags = [str(f) for f in verification.get("red_flags", []) if str(f).strip()]
    if contradicted:
        red_flags.append(f"{contradicted} self-reported claim(s) contradicted by web evidence.")
    if cust and verified_custs == 0 and len(cust) >= 2:
        red_flags.append("None of the claimed reference customers could be corroborated online.")

    return {"dimensions": {k: round(v, 1) for k, v in dims.items()},
            "raw_score": round(raw, 1), "data_completeness": round(completeness, 2),
            "data_confidence": round(data_confidence, 2), "final_score": round(final, 1),
            "route_scorecards": scorecards,
            "missing_evidence": missing, "red_flags": red_flags,
            "effective_traction": round(effective_traction, 2),
            "verified_customers": verified_custs, "unverified_customers": unverified_custs,
            "contradicted": contradicted}
