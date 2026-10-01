"""Siemens Fit as three pillar assessments — Empower, Collaborate, Connect — and the route.

Each pillar scores three criteria 0–3 against the anchors in the product owner's Siemens Fit
diagram, over a catalog (core/catalogs.py): Empower against the Siemens tools list, Collaborate
against the selected department's needs, Connect against the Xcelerator ecosystem workbook.

This module is the pure half — definitions, validation of what a model returned, bands, the
Siemens Fit number and the recommended route. The model half (concept extraction, shortlisting,
the deep match) is core/pillar_match.py. Keeping them apart is what lets every boundary here be
tested without a model: the model *proposes* scores; Python decides whether each one stands.

Two states are never conflated. A pillar is `unassessed` when it could not be judged — no grounded
evidence, no catalog, no model, output that failed validation — and `assessed` when it was, even
if the answer is 0. Only an assessed pillar can contribute to Siemens Fit or support a Pass.
"""
from __future__ import annotations

VERSION = "siemens-fit-pillars-v1"
ORDER = ("Empower", "Collaborate", "Connect")          # the stable tie-break, per the spec

PILLARS = {
    "Empower": {
        "catalog": "siemens_tools",
        "concepts": ("technologies", "needs_gaps", "use_cases"),
        "criteria": (("tool_fit", "Tool fit"), ("benefit_fit", "Benefit fit"),
                     ("actionability", "Actionability")),
        "anchors": {
            "tool_fit": ("No relevant capability", "Broad/indirect relevance",
                         "Clearly relevant tool capability",
                         "Tool directly supports a core startup activity/capability"),
            "benefit_fit": ("No identifiable benefit", "Minor/speculative benefit", "Clear benefit",
                            "Material benefit to product development, operations, scaling, etc."),
            "actionability": ("No realistic route identified", "Theoretical possibility only",
                              "Realistic empowerment opportunity",
                              "Clear tool + startup application + concrete next step"),
        },
        "statement": "[Siemens tool] could help the startup [specific benefit] by [specific application].",
        # The sentence shape the PDF asks for, as the fragments it must contain, in order.
        "statement_marker": ("could help the startup", " by "),
    },
    "Collaborate": {
        "catalog": "department_needs",
        "concepts": ("technologies", "capabilities", "use_cases"),
        "criteria": (("capability_fit", "Capability fit"), ("need_fit", "Need fit"),
                     ("actionability", "Actionability")),
        "anchors": {
            "capability_fit": ("Startup does not provide the capability",
                               "Broad/indirect capability overlap",
                               "Startup clearly provides a relevant capability",
                               "Startup's core offering directly provides the capability"),
            "need_fit": ("Startup does not address the stated need", "Indirectly related to the need",
                         "Startup clearly contributes to solving the need",
                         "Startup directly addresses the stated need/problem"),
            "actionability": ("No plausible collaboration can be identified",
                              "Possible connection, but vague or speculative",
                              "A concrete collaboration/use case can be described",
                              "Clear department + startup use case with an obvious next step"),
        },
        "statement": "[Department] could pilot the startup's [capability] to address [stated need] by [use case].",
        "statement_marker": (),
    },
    "Connect": {
        "catalog": "xcelerator",
        "concepts": ("industries", "topics", "use_cases"),
        "criteria": (("industry_fit", "Industry fit"), ("topic_fit", "Topic fit"),
                     ("ecosystem_value", "Ecosystem value")),
        "anchors": {
            "industry_fit": ("No industry relationship", "Indirect/adjacent industry",
                             "Clearly relevant industry", "Startup directly targets that industry"),
            "topic_fit": ("No match", "Broad thematic similarity", "Clear relevance",
                          "Core startup offering directly matches the topic"),
            "ecosystem_value": ("No identifiable ecosystem value", "Possible but generic relevance",
                                "Clear potential value for ecosystem participants",
                                "Clear target/use case for an ecosystem connection"),
        },
        "statement": ("The startup could be relevant to the Xcelerator ecosystem because [offering] "
                      "addresses [topic/use case] for [industry/ecosystem audience]."),
        "statement_marker": ("relevant to the xcelerator ecosystem because", " for "),
    },
}


def third_criterion(pillar: str) -> str:
    """Actionability for Empower and Collaborate, ecosystem value for Connect — the criterion that
    decides whether a high total is Strong or only worth a review."""
    return PILLARS[pillar]["criteria"][2][0]


def band(total: int, third: int) -> str:
    """0–3 no match · 4–6 review · 7–9 strong, but only with the third criterion at 2 or more.

    The cap is the whole point of the third criterion: a startup can resemble a Siemens tool in
    every respect and still have no route to working with it, and that is a review, not a match.
    """
    if total <= 3:
        return "no_match"
    if total >= 7 and third >= 2:
        return "strong"
    return "review"


BAND_LABELS = {"no_match": "No match", "review": "Moderate / Review", "strong": "Strong"}


def _follows(text: str, fragments: tuple) -> bool:
    """True when every fragment appears, each after the one before it.

    A statement that merely mentions the Xcelerator ecosystem is thematic similarity; the anchors
    ask for the sentence that names who it is for and why, and a live run showed the model writing
    the first while scoring as if it had written the second.
    """
    at = 0
    for frag in fragments:
        at = text.find(frag, at)
        if at < 0:
            return False
        at += len(frag)
    return True


def unassessed(pillar: str, reason: str, message: str, **extra) -> dict:
    return {"pillar": pillar, "status": "unassessed", "reason": reason, "message": message,
            "total": None, "band": None, "criteria": [], **extra}


def validate_match(pillar: str, raw, evidence: dict, catalog_ids: dict) -> dict:
    """Turn a model's proposed pillar judgment into an assessed pillar, or raise ValueError.

    `evidence` maps evidence id → record; `catalog_ids` maps shortlisted catalog id → entry. The
    rules, each of which closes a way a fluent answer can outrun its evidence:

    - exactly the three criteria, each an integer 0–3 (a bool, a float or a string is malformed);
    - every citation an existing evidence id and every catalog id one we actually shortlisted;
    - a score above 0 needs both — startup evidence *and* the catalog entry it fits;
    - the third criterion at 2+ needs the pillar's statement naming a cited catalog entry, and a
      concrete next step. Without them it is capped at 1: thematic similarity alone cannot earn
      a route.
    """
    spec = PILLARS[pillar]
    if not isinstance(raw, dict) or not isinstance(raw.get("criteria"), dict):
        raise ValueError("missing criteria")
    keys = [k for k, _ in spec["criteria"]]
    if set(raw["criteria"]) != set(keys):
        raise ValueError("criteria keys do not match the pillar")
    rows, notes = [], []
    for key, label in spec["criteria"]:
        item = raw["criteria"][key]
        if not isinstance(item, dict):
            raise ValueError(f"{key}: not an object")
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 3:
            raise ValueError(f"{key}: score must be an integer 0-3")
        cites = item.get("citations") or []
        cats = item.get("catalog_ids") or []
        if not isinstance(cites, list) or not isinstance(cats, list):
            raise ValueError(f"{key}: citations and catalog_ids must be lists")
        if any(c not in evidence for c in cites):
            raise ValueError(f"{key}: cites evidence that does not exist")
        if any(c not in catalog_ids for c in cats):
            raise ValueError(f"{key}: names a catalog entry that was not shortlisted")
        rationale = str(item.get("rationale") or "").strip()
        if score > 0 and not (cites and cats):
            score = 0
            notes.append(f"{label}: no startup evidence and catalog entry cited together; scored 0.")
        rows.append({"id": key, "label": label, "score": score, "rationale": rationale[:600],
                     "anchor": spec["anchors"][key][score],
                     "evidence": [evidence[c] for c in dict.fromkeys(cites)],
                     "catalog": [catalog_ids[c] for c in dict.fromkeys(cats)]})
    statement = str(raw.get("statement") or "").strip()
    next_step = str(raw.get("next_step") or "").strip()
    third = rows[2]
    cited_names = {e["name"].casefold() for r in rows for e in r["catalog"]}
    concrete = (len(statement) >= 30 and len(next_step) >= 10
                and any(n in statement.casefold() for n in cited_names)
                and _follows(statement.casefold(), spec["statement_marker"]))
    if third["score"] >= 2 and not concrete:
        third["score"] = 1
        third["anchor"] = spec["anchors"][third["id"]][1]
        notes.append(f"{third['label']} capped at 1: no concrete statement naming a matched "
                     "catalog entry, with a next step.")
    total = sum(r["score"] for r in rows)
    covered = sum(1 for r in rows if r["evidence"])
    return {"pillar": pillar, "status": "assessed", "total": total,
            "band": band(total, third["score"]), "criteria": rows,
            "statement": statement if concrete else "", "next_step": next_step if concrete else "",
            "evidence_coverage": round(covered / 3, 2), "notes": notes}


def _rank_key(p: dict):
    return (p["total"], p["criteria"][2]["score"], p.get("evidence_coverage", 0),
            -ORDER.index(p["pillar"]))


def siemens_fit(pillars: dict) -> dict:
    """`round(100 × best assessed total / 9)`, with the pillar that earned it.

    Null when nothing was assessable — never 0, which would read as "assessed and unfit". A run
    missing a pillar still gets a number from the ones it has, flagged partial, because the
    number is a maximum and a maximum over fewer pillars is a floor, not a guess.
    """
    assessed = [p for p in pillars.values() if p.get("status") == "assessed"]
    if not assessed:
        return {"score": None, "winner": None, "partial": False, "status": "unassessed"}
    best = max(assessed, key=_rank_key)
    return {"score": round(100 * best["total"] / 9), "winner": best["pillar"],
            "raw": best["total"], "partial": len(assessed) < len(ORDER), "status": "assessed"}


def recommend(pillars: dict) -> dict:
    """The route, decided from the pillar outcomes alone — no model can override it.

    Strong pillar → that pillar (highest ranked). Every pillar assessed and every one a no-match
    → Pass. Anything else → Defer: a best result of Review is a question for a person, and a
    pillar that could not be assessed means a negative conclusion would be a guess.
    """
    assessed = {k: p for k, p in pillars.items() if p.get("status") == "assessed"}
    strong = [p for p in assessed.values() if p["band"] == "strong"]
    if strong:
        best = max(strong, key=_rank_key)
        reasons = [f"{best['pillar']} is a strong match ({best['total']}/9)."]
        reasons += [f"{r['label']} {r['score']}/3: {r['rationale']}" for r in best["criteria"] if r.get("rationale")]
        steps = [best["next_step"]] if best.get("next_step") else []
        steps += [f"Review {p['pillar']} as a secondary route ({p['total']}/9)."
                  for p in sorted(assessed.values(), key=_rank_key, reverse=True)
                  if p is not best and p["band"] in ("strong", "review")]
        return {"pillar": best["pillar"], "reasons": reasons, "next_steps": steps[:4],
                "evidence": [e for r in best["criteria"] for e in r.get("evidence", [])][:6]}
    missing = [k for k in ORDER if k not in assessed]
    if not missing and all(p["band"] == "no_match" for p in assessed.values()):
        reasons = [f"{p['pillar']} scored {p['total']}/9: no match." for p in assessed.values()]
        return {"pillar": "Pass", "reasons": reasons,
                "next_steps": ["Reconsider if the startup's offering or target industry changes."],
                "evidence": [e for p in assessed.values() for r in p["criteria"] for e in r["evidence"]][:6]}
    reasons, steps = [], []
    for p in sorted(assessed.values(), key=_rank_key, reverse=True):
        if p["band"] == "review":
            reasons.append(f"{p['pillar']} needs review ({p['total']}/9).")
            weak = [r["label"] for r in p["criteria"] if r["score"] < 2]
            steps.append(f"Verify {p['pillar']}: " + (", ".join(weak) or "confirm the match") + ".")
    for k in missing:
        reasons.append(f"{k} could not be assessed: {pillars.get(k, {}).get('message', 'no result')}")
        steps.append(f"Supply the missing input for {k} and reassess.")
    return {"pillar": "Defer", "reasons": reasons or ["No pillar reached a strong match."],
            "next_steps": steps[:4] or ["Gather more evidence before deciding."], "evidence": []}
