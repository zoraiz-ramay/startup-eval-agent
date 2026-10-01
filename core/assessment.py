"""One department's assessment of one startup: pillars, Siemens Fit, route, and the weighted total.

    total = 0.30 × traction + 0.35 × Siemens Fit + 0.20 × (Team & Ecosystem points × 5) + 0.15 × market

Every input is a 0–100 number or it is missing, and a missing input leaves the total *pending*
(null), never treats itself as 0: a startup whose market was not scored has not scored zero on
market. Product and the older founder/ecosystem dimensions stay visible as diagnostics and are
deliberately not added in again.

The total and its components are recomputed whenever a run is read (`hydrate`), from the stored
pillar and team results, so a traction-rubric change cannot leave a stale total behind it.
"""
from __future__ import annotations

from . import pillars as P
from .market import VERSION as MARKET_VERSION
from .team_ecosystem import CRITERIA as TEAM_CRITERIA, VERSION as TEAM_VERSION
from .text import is_named_org
from .traction import VERSION as TRACTION_VERSION, with_traction

VERSION = "department-assessment-v1"
WEIGHTS = {"traction": 0.30, "siemens_fit": 0.35, "team_ecosystem": 0.20, "market": 0.15}
LABELS = {"traction": "Traction", "siemens_fit": "Siemens Fit",
          "team_ecosystem": "Team & Ecosystem", "market": "Market"}


def rubric_version() -> str:
    return f"{VERSION}+{P.VERSION}+{TEAM_VERSION}+{TRACTION_VERSION}+{MARKET_VERSION}"


def rubric_scales() -> dict:
    """Every level's anchor, per criterion, so a reader can see the whole scale a score sits on.

    A stored criterion carries only the anchor it reached; attaching the scale on read keeps the
    UI from holding a second copy of the rubric that could drift from this one.
    """
    return {"pillars": {name: {k: list(v) for k, v in spec["anchors"].items()} for name, spec in P.PILLARS.items()},
            "team_ecosystem": {k: list(levels) for k, _, levels in TEAM_CRITERIA}}


def assessment_key(catalogs: dict) -> str:
    """What a cached run must match to be served as current: rubric and every catalog's bytes."""
    sums = ":".join((catalogs.get(k) or {}).get("checksum", "")[:16]
                    for k in ("siemens_tools", "xcelerator", "department_needs"))
    return f"{rubric_version()}|{sums}"


def components(result: dict) -> dict:
    traction = result.get("traction") or {}
    dims = (result.get("score") or {}).get("dimensions") or {}
    a = result.get("assessment") or {}
    team = a.get("team_ecosystem") or {}
    market = result.get("market") or {}
    fit = a.get("siemens_fit") or {}

    def num(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return {
        "traction": num(traction.get("score_0_100")) if traction.get("status") == "scored" else num(dims.get("traction")),
        "siemens_fit": num(fit.get("score")),
        "team_ecosystem": num(team.get("score_0_100")) if team.get("status") == "assessed" else None,
        # The market rubric when the run has one; a department run from before it existed keeps
        # the model's market number, which the UI labels as such (`market_method`).
        "market": (num(market.get("score_0_100")) if market.get("status") == "assessed"
                   else None if market else num(dims.get("llm_market", dims.get("market")))),
    }


def total(parts: dict) -> float | None:
    if any(parts.get(k) is None for k in WEIGHTS):
        return None
    return round(sum(WEIGHTS[k] * parts[k] for k in WEIGHTS), 1)


def route(assessment: dict, prior: dict | None = None) -> dict:
    """The routing block the UI reads, from the recommendation core/pillars.py decided.

    Portfolio stance and the SFS fields are kept from the prior routing: they answer other
    questions and nothing here re-derives them.
    """
    rec = assessment["recommendation"]
    keep = {k: v for k, v in (prior or {}).items() if k == "portfolio_stance" or k.startswith("sfs_")}
    return {**keep, "version": "pillar-route-v1", "status": "assessed", "pillar": rec["pillar"],
            "secondary": [], "reasons": rec["reasons"], "next_steps": rec["next_steps"],
            "evidence": rec["evidence"], "method": "pillar_rubric"}


def build(result: dict, department: dict, pillar_result: dict, team: dict, market: dict | None = None) -> dict:
    """A new result dict carrying this department's assessment, route and total."""
    snapshot = ((pillar_result.get("catalogs") or {}).get("department_needs") or {})
    out = dict(result)
    if market is not None:
        out["market"] = market
    out["department"] = {"id": department["id"], "label": department.get("label", department["id"]),
                         "interests": list(department.get("interests") or []),
                         "demo": bool(department.get("demo", True)),
                         "checksum": snapshot.get("checksum", "")}
    out["assessment"] = {**pillar_result, "team_ecosystem": team, "weights": WEIGHTS,
                         "rubric_version": rubric_version(),
                         "assessment_key": assessment_key(pillar_result.get("catalogs") or {})}
    out["routing"] = route(out["assessment"], result.get("routing"))
    return hydrate(out)


def _named_customers(result: dict) -> dict:
    """Reference customers that read as named organisations, for runs stored before the check.

    Only ever removes: a fragment of a prose customer box ("In parallel", "For scale-up") is
    dropped from what the profile shows and the rubric counts; no name is added or rewritten.
    """
    dp = result.get("deep_profile") if isinstance(result, dict) else None
    names = (dp or {}).get("reference_customers") if isinstance(dp, dict) else None
    if not isinstance(names, list):
        return result
    kept = [n for n in names if is_named_org(n)]
    return result if kept == names else {**result, "deep_profile": {**dp, "reference_customers": kept}}


def hydrate(result: dict) -> dict:
    """A result whose traction, components, total and headline score agree — live or stored.

    Legacy runs (no department) only get the traction rubric; there is nothing to total.
    """
    result = with_traction(_named_customers(result))
    if not isinstance(result, dict) or not isinstance(result.get("assessment"), dict) \
            or not result.get("department"):
        return result
    parts = components(result)
    grand = total(parts)
    a = {**result["assessment"], "components": parts, "total": grand,
         "market_method": "rubric" if (result.get("market") or {}).get("status") == "assessed"
         else "unassessed" if result.get("market") else "llm_judgment",
         "total_status": "complete" if grand is not None else "pending", "scales": rubric_scales()}
    score = dict(result.get("score") or {})
    dims = dict(score.get("dimensions") or {})
    # The model's holistic numbers are kept once, under their own names, the first time a run is
    # hydrated. After that `siemens_fit` is this department's pillar result or absent — never the
    # model's guess, and never the value another department's run carried in.
    score.setdefault("llm_final_score", score.get("final_score"))
    score.setdefault("llm_siemens_fit", dims.get("siemens_fit"))
    market = result.get("market") or {}
    if market.get("status") == "assessed":
        score.setdefault("llm_market", dims.get("market"))
        dims["market"] = market["score_0_100"]
    if parts["siemens_fit"] is not None:
        dims["siemens_fit"] = parts["siemens_fit"]
    else:
        dims.pop("siemens_fit", None)
    score.update(dimensions=dims, final_score=grand, total_method="weighted_components")
    return {**result, "assessment": a, "score": score}
