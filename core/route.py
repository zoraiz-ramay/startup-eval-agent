"""Routing to the Siemens-for-Startups pillar (Connect / Collaborate / Empower / Pass)."""
from __future__ import annotations

import pandas as pd

from .config import FIT_ALIGN_THRESHOLD
from .llm import LLMClient
from .programs import assess_all_pillars, assess_sfs


def route(score: dict, fit: dict, row: pd.Series, llm: LLMClient, profile: dict = None) -> dict:
    """Eligibility-based routing: a startup can qualify for MORE than one pillar
    (e.g. Collaborate + Empower). `pillar` is the primary; `secondary` lists the rest.
    Also surfaces which Siemens Financial Services line, if any, is a real avenue.

    Two gates, deliberately kept separate:

    * the **scorecard** gates below, which ask how strong the startup is on each route's own
      weighting. These are mirrored in the browser (``ui/src/scoring/routing.js``) so a reviewer
      can re-weight the portfolio, and pinned behaviourally by tests/test_whatif_route_parity.py.
    * the **criteria** gates in ``core.programs``, which ask whether Siemens' published programme
      would actually take this company. These read evidence, not weights, so no reviewer
      weighting can move them and they are deliberately NOT mirrored in the browser.

    A pillar has to clear both. The criteria layer can only ever remove a pillar the scorecards
    admitted — which is why the browser's what-if stays a sound answer to the question it asks
    ("would my weighting re-route this"), and why it says nothing about the criteria.
    """
    profile = profile or {}
    final = score["final_score"]
    aligned = fit.get("aligned", False)
    traction = score["dimensions"]["traction"]

    # Route-aware eligibility: each pillar qualifies on ITS OWN scorecard (falling back
    # to the universal final score for results produced before scorecards existed).
    cards = score.get("route_scorecards", {}) or {}
    r_connect = cards.get("Connect", final)
    r_collab = cards.get("Collaborate", final)
    score_eligible = []
    if aligned and score["dimensions"]["siemens_fit"] >= FIT_ALIGN_THRESHOLD:
        if r_connect >= 70 and traction >= 60:
            score_eligible.append("Connect")      # market-ready, fits portfolio
        if r_collab >= 55 and traction >= 35:
            score_eligible.append("Collaborate")  # strong fit, real traction
        score_eligible.append("Empower")          # tech fit; Siemens tools accelerate the startup

    # Siemens' own criteria, per pillar. `blocked` means something about the company makes this
    # the wrong programme and no further evidence changes it; `unproven` means nothing
    # disqualifies it but a requirement is unevidenced. Only `blocked` removes a route — the app
    # routes a scout's attention, it does not make the admission decision — but an `eligible`
    # pillar always outranks an `unproven` one, so the headline never prefers a guess to a
    # substantiated match.
    assessments = assess_all_pillars(row, profile, fit, score)
    eligible = [p for p in score_eligible if assessments[p]["status"] != "blocked"]
    # Primary = the best-substantiated route, then the highest-scoring one, so the headline
    # pillar always matches what the criteria and the route scorecards actually say.
    eligible.sort(key=lambda r: (assessments[r]["status"] == "eligible", cards.get(r, final)),
                  reverse=True)
    pillar = eligible[0] if eligible else "Pass"
    secondary = eligible[1:]                # ALL other qualifying pillars

    sfs = assess_sfs(row, profile, fit)
    reasons, risks = _route_reasons(pillar, score, fit, row, llm)
    confidence = round(min(0.95, 0.4 + 0.5 * score["data_confidence"] *
                           (1 if pillar != "Pass" else 0.6)), 2)
    # An unproven primary is a weaker answer than a substantiated one and says so, rather than
    # borrowing the confidence of the data-completeness figure alone.
    if pillar != "Pass" and assessments[pillar]["status"] != "eligible":
        confidence = round(confidence * 0.8, 2)
    return {"pillar": pillar, "secondary": secondary, "confidence": confidence,
            "reasons": reasons, "risks": risks,
            "route_recommendations": _route_recommendations(eligible, score, fit, assessments),
            # What the scorecards alone admitted, before the criteria were applied. Kept so the
            # browser mirror stays checkable and so a reviewer can see that a pillar was dropped
            # on evidence rather than on score.
            "score_eligible": score_eligible,
            "portfolio_stance": _portfolio_stance(fit),
            "pillar_status": assessments[pillar]["status"] if pillar != "Pass" else "blocked",
            "pillar_assessments": assessments,
            "sfs_relevant": bool(sfs.get("relevant")),
            # relevant | conditional | not_relevant | unassessed. The boolean above collapses the
            # last three, which is right for a chip and wrong for anything reasoning about the
            # answer — a benchmark must not score "we never looked" as a wrong negative.
            "sfs_status": str(sfs.get("status", "")),
            "sfs_line": str(sfs.get("line", "")),
            "sfs_lines": sfs.get("lines", []),
            "sfs_blockers": sfs.get("blockers", []),
            "sfs_rationale": str(sfs.get("rationale", ""))}


# How the startup sits against the Siemens portfolio, as an outcome in its own right.
#
# `substitute` used to be visible only as a 0.55 multiplier on siemens_fit, which usually pushed
# the company under the alignment gate — so a scout read "Pass" and never learned that the reason
# was a product Siemens already sells. That is the single most strategically interesting thing an
# evaluation can find, and it was being expressed as a slightly lower number. The pillar answers
# "what should we offer them"; this answers "what are they to us", and the two are independent.
_STANCE = {
    "complement":  ("Complementary", "Adds capability the closest Siemens tool lacks."),
    "integration": ("Integrates",    "Plugs into or extends the closest Siemens tool."),
    "adjacent":    ("Adjacent",      "Same domain as the closest Siemens tool, different function."),
    "substitute":  ("Competes",      "Does what the closest Siemens tool already does."),
}


def _portfolio_stance(fit: dict) -> dict:
    """Where this startup stands relative to the portfolio, named rather than discounted."""
    matches = fit.get("matches") or []
    if not matches:
        return {"stance": "", "label": "", "note": "", "tool": "", "competes": False}
    top = matches[0]
    relation = str(top.get("relation", "")).strip().lower()
    label, note = _STANCE.get(relation, ("Unclassified",
                                         "The portfolio relation was not established."))
    tool = str(top.get("tool", ""))
    return {"stance": relation, "label": label,
            "note": f"{note} Closest match: {tool}." if tool else note,
            "tool": tool, "division": str(top.get("division", "")),
            # A competitor is not a bad startup — it is a different conversation, and frequently
            # a more urgent one (competitive watch, partnership-instead-of-build, acquisition).
            "competes": relation == "substitute"}


_ROUTE_TEMPLATES = {
    "Connect": "Introduce to the relevant Siemens business unit for a deployment/vendor "
               "conversation — route score {rs}, traction {tr}.",
    "Collaborate": "Set up a co-development or pilot engagement around {tool} — route score {rs}.",
    "Empower": "Offer Siemens tools/credits to accelerate the startup's build "
               "(closest tool: {tool}) — route score {rs}.",
}


def _route_recommendations(eligible: list, score: dict, fit: dict,
                           assessments: dict = None) -> list[dict]:
    """One recommendation object per qualifying route, driven by that route's scorecard.

    Carries the criteria verdict alongside the number, because "Empower, 71.9" and "Empower,
    71.9 — but nothing evidences that this is still an early-stage company" are different
    recommendations and the score cannot tell them apart."""
    cards = score.get("route_scorecards", {}) or {}
    assessments = assessments or {}
    tool = fit["matches"][0]["tool"] if fit.get("matches") else "n/a"
    out = []
    for r in eligible:
        assessment = assessments.get(r) or {}
        out.append({"route": r, "score": cards.get(r, score.get("final_score", 0)),
                    "status": assessment.get("status", "unproven"),
                    "next_steps": assessment.get("next_steps", []),
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
