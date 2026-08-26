"""Empower: the investment signals, the relevance, and how to approach the startup.

Empower is the pillar a scout acts on most often — it is the one Siemens can offer immediately,
with no business unit to line up first — and until now the page said only that the company
qualified. "You qualify for Empower" is not something anyone can act on. What a scout needs is
which bundle to offer, what in the evidence says this is worth their week, and a concrete opening.

Everything here is DERIVED, not researched: it reads the evidence the run already gathered and
re-presents it as a decision. That is deliberate — no new searches, no new model calls, no new
latency — and every signal keeps the source URL of the fact it came from, so nothing on this panel
can say more than the evidence behind it. Pure functions over dicts; no I/O, no imports from api/.

The approach angles are the one place this composes sentences rather than reporting facts. They
are templated from named evidence (a bundle, a founder, a programme, an API) rather than
generated, so an angle cannot mention a product the company does not make or a programme it is not
in — which is exactly what a model asked for outreach ideas produces, fluently.
"""
from __future__ import annotations

import pandas as pd

from .config import KNOWN_PROGRAM_TIERS
from .programs import _commercial, _top_division, match_empower_bundles

# How strongly a signal argues for spending time on this company. Three levels, because two
# collapses "we found something" into "this is compelling", and a scout triaging twenty profiles
# needs those apart.
STRONG, MODERATE, WEAK = "strong", "moderate", "weak"

_STAGE_LABEL = {
    "pre_seed": "Pre-seed", "seed": "Seed", "series_a": "Series A",
    "series_b_plus": "Series B or later", "grant": "Grant-funded",
}
# Stage argues in both directions, and the direction is what matters to Empower: a pre-seed team
# has the most to gain from free tooling, a Series B company is past the programme entirely.
_STAGE_STRENGTH = {"seed": STRONG, "series_a": STRONG, "pre_seed": MODERATE,
                   "grant": MODERATE, "series_b_plus": WEAK}


def _signal(sid, label, detail, strength, source_url="") -> dict:
    return {"id": sid, "label": label, "detail": detail, "strength": strength,
            "source_url": str(source_url or "")}


def _growth(series) -> dict | None:
    """Headcount growth between the first and last CITED points, or None.

    Only ever computed from ``employees_over_time``, whose ``_clean_employee_series`` gate requires
    an http source per datapoint. A growth rate derived from an uncited number would be a new
    claim manufactured out of two old ones.
    """
    points = [p for p in (series or []) if isinstance(p, dict)
              and str(p.get("count", "")).strip() and p.get("source_url")]
    if len(points) < 2:
        return None
    first, last = points[0], points[-1]
    try:
        start, end = float(first["count"]), float(last["count"])
        years = int(last.get("year", 0)) - int(first.get("year", 0))
    except (TypeError, ValueError):
        return None
    if start <= 0 or years <= 0:
        return None
    return {"start": int(start), "end": int(end), "years": years,
            "multiple": round(end / start, 1), "source_url": last.get("source_url", "")}


def investment_signals(row: pd.Series, profile: dict, fit: dict, score: dict,
                       trend: dict = None) -> list[dict]:
    """What in this run argues the startup is worth Siemens' time, each with its evidence."""
    profile, fit, score, trend = profile or {}, fit or {}, score or {}, trend or {}
    commercial = _commercial(profile)
    out: list[dict] = []

    stage = str(commercial.get("funding_stage") or "")
    if stage:
        out.append(_signal("funding_stage", "Funding stage",
                           f"{_STAGE_LABEL.get(stage, stage)} — "
                           f"{profile.get('funding') or 'amount not evidenced'}",
                           _STAGE_STRENGTH.get(stage, MODERATE),
                           profile.get("funding_source", "")))

    investors = [i for i in (commercial.get("investors") or [])
                 if isinstance(i, dict) and i.get("name")]
    if investors:
        out.append(_signal("investors", "Institutional backing",
                           ", ".join(str(i["name"]) for i in investors[:4]),
                           STRONG if len(investors) > 1 else MODERATE,
                           investors[0].get("source_url", "")))

    growth = _growth(profile.get("employees_over_time"))
    if growth:
        plural = "s" if growth["years"] > 1 else ""
        out.append(_signal(
            "headcount_growth", "Headcount growth",
            f"{growth['start']} to {growth['end']} staff over {growth['years']} year{plural} "
            f"({growth['multiple']}x)",
            STRONG if growth["multiple"] >= 2 else MODERATE, growth["source_url"]))

    # A top-tier accelerator has already run a diligence pass this evaluation cannot reproduce,
    # which is why it belongs here as a signal and not only as an input to the ecosystem score.
    programs = [p for p in (profile.get("programs") or [])
                if isinstance(p, dict) and p.get("name")]
    tier1 = [p for p in programs
             if str(p.get("prestige", "")).lower() == "tier1"
             or KNOWN_PROGRAM_TIERS.get(str(p.get("name", "")).lower()) == "tier1"]
    if tier1:
        claimed = all(str(p.get("confidence", "")).lower() == "self_asserted" for p in tier1)
        suffix = " (company-claimed, not corroborated)" if claimed else ""
        out.append(_signal("accelerator", "Top-tier programme",
                           ", ".join(str(p["name"]) for p in tier1[:3]) + suffix,
                           MODERATE if claimed else STRONG, tier1[0].get("source_url", "")))

    verified = int(score.get("verified_customers") or 0)
    if verified:
        named = [str(c) for c in (profile.get("reference_customers") or []) if str(c).strip()][:3]
        detail = f"{verified} verified"
        if named:
            detail += " — " + ", ".join(named)
        out.append(_signal("customers", "Corroborated customers", detail,
                           STRONG if verified >= 3 else MODERATE))

    momentum = trend.get("momentum")
    if isinstance(momentum, (int, float)) and momentum:
        basis = trend.get("basis") or trend.get("niche") or "niche assessed"
        out.append(_signal("market", "Market momentum", f"{int(momentum)}/100 — {basis}",
                           STRONG if momentum >= 70 else MODERATE if momentum >= 40 else WEAK))
    return out


def relevance(row: pd.Series, profile: dict, fit: dict) -> dict:
    """Why Siemens is relevant to this startup: the bundles, the closest tool, the division."""
    matches = (fit or {}).get("matches") or []
    top = matches[0] if matches else {}
    return {
        "bundles": match_empower_bundles(row if row is not None else pd.Series(dtype=str),
                                         profile or {}, fit or {}),
        "tool": str(top.get("tool", "")),
        "division": _top_division(fit or {}),
        "relation": str(top.get("relation", "")),
        "rationale": str(top.get("rationale", "")),
    }


def _first_founder(profile: dict) -> str:
    for f in (profile or {}).get("founders") or []:
        name = str((f or {}).get("name", "")).strip()
        if name:
            return name
    return ""


def approach_angles(row: pd.Series, profile: dict, fit: dict, rel: dict) -> list[str]:
    """Concrete openings, composed ONLY from evidence this run actually found."""
    profile, rel = profile or {}, rel or {}
    series = row if row is not None else pd.Series(dtype=str)
    company = str(series.get("company_name", "")).strip() or "the company"
    angles: list[str] = []

    bundles = rel.get("bundles") or []
    if bundles:
        bundle = bundles[0]
        angles.append(f"Lead with {bundle['label']}: {bundle['offer']}. It is the bundle that "
                      f"maps to what {company} is actually building, so the offer lands as "
                      "specific rather than as a catalogue.")
    if rel.get("tool") and rel.get("division"):
        angles.append(f"Route the introduction through {rel['division']}, which owns "
                      f"{rel['tool']} — the closest portfolio match, and the team that would "
                      "recognise the use case fastest.")

    founder = _first_founder(profile)
    if founder:
        angles.append(f"Approach {founder} directly. Empower decisions sit with the founder at "
                      "this stage, and a tooling offer needs no procurement conversation.")

    programs = [str(p.get("name")) for p in (profile.get("programs") or [])
                if isinstance(p, dict) and p.get("name")]
    if programs:
        angles.append(f"There is a warm path via {programs[0]} — a shared programme is a better "
                      "introduction than a cold approach.")

    if _commercial(profile).get("has_public_api"):
        angles.append("Public API documentation exists, so a technical proof of concept against a "
                      "Siemens product can be scoped before any commercial conversation.")
    return angles


def empower_brief(row: pd.Series, profile: dict, fit: dict, score: dict,
                  trend: dict = None) -> dict:
    """Everything the Empower section shows, in one object. Never raises."""
    try:
        rel = relevance(row, profile, fit)
        return {"signals": investment_signals(row, profile, fit, score, trend),
                "relevance": rel,
                "approach": approach_angles(row, profile, fit, rel)}
    except Exception:                                  # pragma: no cover - defensive
        return {"signals": [], "relevance": {}, "approach": []}
