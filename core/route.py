"""Routing to the Siemens-for-Startups pillar (Connect / Collaborate / Empower / Pass)."""
from __future__ import annotations

import pandas as pd

from .config import FIT_ALIGN_THRESHOLD
from .llm import LLMClient


def route(score: dict, fit: dict, row: pd.Series, llm: LLMClient, profile: dict = None) -> dict:
    """Eligibility-based routing: a startup can qualify for MORE than one pillar
    (e.g. Collaborate + Empower). `pillar` is the primary; `secondary` lists the rest.
    Also surfaces whether Siemens Financial Services is a relevant avenue."""
    profile = profile or {}
    final = score["final_score"]
    aligned = fit.get("aligned", False)
    traction = score["dimensions"]["traction"]

    # Route-aware eligibility: each pillar qualifies on ITS OWN scorecard (falling back
    # to the universal final score for results produced before scorecards existed).
    cards = score.get("route_scorecards", {}) or {}
    r_connect = cards.get("Connect", final)
    r_collab = cards.get("Collaborate", final)
    eligible = []
    if aligned and score["dimensions"]["siemens_fit"] >= FIT_ALIGN_THRESHOLD:
        if r_connect >= 70 and traction >= 60:
            eligible.append("Connect")      # market-ready, fits portfolio
        if r_collab >= 55 and traction >= 35:
            eligible.append("Collaborate")  # strong fit, real traction
        eligible.append("Empower")          # tech fit; Siemens tools accelerate the startup
    # Primary = HIGHEST-SCORING eligible route (not a fixed order), so the headline
    # pillar always matches what the route scorecards actually say.
    eligible.sort(key=lambda r: cards.get(r, final), reverse=True)
    pillar = eligible[0] if eligible else "Pass"
    secondary = eligible[1:]                # ALL other qualifying pillars

    sfs = profile.get("sfs", {}) or {}
    reasons, risks = _route_reasons(pillar, score, fit, row, llm)
    confidence = round(min(0.95, 0.4 + 0.5 * score["data_confidence"] *
                           (1 if pillar != "Pass" else 0.6)), 2)
    return {"pillar": pillar, "secondary": secondary, "confidence": confidence,
            "reasons": reasons, "risks": risks,
            "route_recommendations": _route_recommendations(eligible, score, fit),
            "sfs_relevant": bool(sfs.get("relevant")),
            "sfs_rationale": str(sfs.get("rationale", ""))}


_ROUTE_TEMPLATES = {
    "Connect": "Introduce to the relevant Siemens business unit for a deployment/vendor "
               "conversation — route score {rs}, traction {tr}.",
    "Collaborate": "Set up a co-development or pilot engagement around {tool} — route score {rs}.",
    "Empower": "Offer Siemens tools/credits to accelerate the startup's build "
               "(closest tool: {tool}) — route score {rs}.",
}


def _route_recommendations(eligible: list, score: dict, fit: dict) -> list[dict]:
    """One recommendation object per qualifying route, driven by that route's scorecard."""
    cards = score.get("route_scorecards", {}) or {}
    tool = fit["matches"][0]["tool"] if fit.get("matches") else "n/a"
    out = []
    for r in eligible:
        out.append({"route": r, "score": cards.get(r, score.get("final_score", 0)),
                    "recommendation": _ROUTE_TEMPLATES[r].format(
                        rs=cards.get(r, "—"), tr=score["dimensions"].get("traction", "—"),
                        tool=tool)})
    return out


def _route_reasons(pillar, score, fit, row, llm: LLMClient):
    if llm.available:
        prompt = (f"A startup was routed to the Siemens-for-Startups pillar '{pillar}'. "
                  f"Final score {score['final_score']}, Siemens-fit {score['dimensions']['siemens_fit']}, "
                  f"traction {score['dimensions']['traction']}, top tool matches "
                  f"{[m['tool'] for m in fit.get('matches', [])]}.\n"
                  "Give 2 short bullet reasons and 2 short risk bullets. "
                  'Return ONLY JSON: {"reasons": ["..."], "risks": ["..."]}.')
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=400))
        if data and "reasons" in data:
            return data.get("reasons", []), data.get("risks", [])
    # offline templated
    pill_reason = {
        "Connect": "Market-ready and aligned with deployable Siemens tools.",
        "Collaborate": "Strong portfolio fit with early but real traction to co-develop.",
        "Empower": "Clear technical fit; Siemens tools could accelerate the startup.",
        "Pass": "No credible fit to the current Siemens software portfolio.",
    }[pillar]
    reasons = [pill_reason]
    if fit.get("matches"):
        reasons.append("Closest tool: " + fit["matches"][0]["tool"] + ".")
    risks = []
    if score["data_completeness"] < 0.5:
        risks.append("Sparse/unverifiable profile — score capped.")
    if score["unverified_customers"]:
        risks.append("Some reference customers not yet corroborated online.")
    if not risks:
        risks.append("Standard diligence on traction and references recommended.")
    return reasons, risks
