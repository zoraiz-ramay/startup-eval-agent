"""Weighted six-dimension scoring with data-confidence capping."""
from __future__ import annotations

import re

import pandas as pd

from .config import WEIGHTS, THIN_PROFILE_CAP, PROGRAM_PRESTIGE_WEIGHTS, PROGRAM_PRESTIGE_CAP

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


def _has(row, *cols) -> bool:
    return any(str(row.get(c, "")).strip() for c in cols)


def score_startup(row: pd.Series, enrichment: dict, verification: dict, fit: dict,
                  profile: dict = None) -> dict:
    profile = profile or {}
    facts = enrichment["facts"]
    _W = {"verified": 1.0, "partial": 0.5, "unverified": 0.25, "contradicted": 0.0}
    cust = [c for c in verification.get("claims", []) if c.get("field") == "reference_customer"]
    verified_custs = sum(1 for c in cust if c.get("status") == "verified")
    unverified_custs = sum(1 for c in cust if c.get("status") in ("unverified", "partial"))
    contradicted = sum(1 for c in verification.get("claims", []) if c.get("status") == "contradicted")
    # anti-gaming: verified beats partial/unverified; contradicted counts zero
    effective_traction = sum(_W.get(c.get("status", "unverified"), 0.25) for c in cust)

    funding_txt = str(row.get("funding", ""))
    has_funding = bool(re.search(r"[\$€£]|\bm\b|million|seed|series", funding_txt, re.I))

    stage_growth = str(row.get("Stage: Growth market stage (your solution is mature, and you are selling it to your main target market)", "")).strip()
    stage_proto = str(row.get("Stage: Prototype stage (a working prototype of your solution does exist)", "")).strip()
    stage_early = str(row.get("Stage: Early market stage (you are selling an early version of your solution, early adopters are your main clients)", "")).strip()

    dims = {}
    dims["traction"] = min(100, 35 * effective_traction + (20 if has_funding else 0))

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
    dims["product"] = 85 if stage_growth else 65 if stage_early else 50 if stage_proto else 40
    dims["market"] = 70 if has_funding else 50

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
    programs = [p for p in profile.get("programs", []) if isinstance(p, dict) and p.get("name")]
    evidenced_programs = [p for p in programs if str(p.get("source_url", "")).startswith("http")]
    prestige_pts = sum(
        PROGRAM_PRESTIGE_WEIGHTS.get(str(p.get("prestige", "tier3")).lower(),
                                     PROGRAM_PRESTIGE_WEIGHTS["tier3"])
        for p in evidenced_programs)
    prestige_pts = min(prestige_pts, PROGRAM_PRESTIGE_CAP)
    eco = 30 + 20 * len([f for f in facts if f.method == "ddg_search" and f.verified])
    eco += prestige_pts + 4 * min(2, len(programs) - len(evidenced_programs))
    eco += 10 if str(profile.get("parent_group", "")).strip() else 0
    dims["ecosystem"] = min(100, eco)

    raw = sum(dims[k] * WEIGHTS[k] for k in WEIGHTS)

    key_fields = ["company_name", "hq", "founded_year", "employees_count", "funding",
                  "customers", "linkedin_url", "Your pitch"]
    completeness = sum(1 for c in key_fields if str(row.get(c, "")).strip()) / len(key_fields)
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
    missing = [c for c in key_fields if not str(row.get(c, "")).strip()]

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
