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

Connect is Siemens partnering with the startup itself — not introducing it to Xcelerator sellers.
It asks two questions in order. First, how many Xcelerator sellers already sell the same kind of
solution: two or more is the crowded case, and the pillar scores from that count alone, lower the
more there are (`crowded_level`). Otherwise — the open case — it scores the startup: Industry &
topic fit and Offering by the model, Market signals in Python from cited figures. The model only
labels sellers same / different; Python counts them. `connect_case` then states, in plain
sentences built from the same facts, whether partnering makes sense.
"""
from __future__ import annotations

from . import config

VERSION = "siemens-fit-pillars-v5"
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
        "concepts": ("industries", "topics", "use_cases", "capabilities"),
        # Rubric v5. Whether the sellers already sell this is not a criterion but a gate, decided
        # before any of these count (validate_match). Offering is third because band() gates
        # Strong on the third criterion: a fitting startup in a good market with no clear offering
        # is a review, not a partnership.
        "criteria": (("industry_topic_fit", "Industry & topic fit"), ("market_signals", "Market signals"),
                     ("offering", "Offering")),
        # Computed in Python from the trend stage's cited figures; never the model's call.
        "derived": ("market_signals",),
        # What the startup sells is a fact about the startup, not a match to the catalog: requiring
        # a catalog id zeroed Celonis's process-mining offering because no Xcelerator entry is one.
        # Research citations are still required, and Industry & topic fit carries the catalog side.
        "evidence_only": ("offering",),
        "anchors": {
            "industry_topic_fit": ("No Xcelerator industry or topic relationship",
                                   "Adjacent industry or broad thematic similarity",
                                   "Clearly relevant Xcelerator industry and topic",
                                   "Directly targets a listed industry and the core offering matches a listed topic"),
            "market_signals": ("No good market signal is cited",
                               "One good market signal: a large market, strong growth or funded peers",
                               "Two good market signals",
                               "A large, fast-growing market with funded peers"),
            "offering": ("No clear offering in the research",
                         "An offering is described, but it is generic or unproven",
                         "A clear product or service with an evidenced use case",
                         "A clear, evidenced and differentiated offering"),
        },
        "statement": ("Siemens could partner with the startup because [offering] addresses "
                      "[topic/use case] for [Xcelerator industry]."),
        "statement_marker": ("could partner with the startup because", " for "),
    },
}


def third_criterion(pillar: str) -> str:
    """Actionability for Empower and Collaborate, Offering for Connect — the criterion that
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
SIMILARITY = ("same", "different")


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


_RELATIONS = ("complement", "integration", "substitute", "adjacent")
MAX_RECOMMENDED_TOOLS = 5


def _recommended_tools(raw: dict, evidence: dict, catalog_ids: dict) -> list[dict]:
    """Empower's ranked tool list, held to the criteria's own bar, at most five.

    A tool is kept only if it was shortlisted, has a known relation, a reason, and at least one
    citation of a real research record — the model cannot add a tool it was not shown, or one it
    cannot tie to the startup. Order is the model's ranking; it never affects the pillar's score.
    """
    out, seen = [], set()
    for item in raw.get("recommended_tools") or []:
        if not isinstance(item, dict) or len(out) >= MAX_RECOMMENDED_TOOLS:
            continue
        cid = str(item.get("catalog_id") or "")
        relation = str(item.get("relation") or "").strip().lower()
        reason = str(item.get("reason") or "").strip()
        cites = [c for c in item.get("citations") or [] if isinstance(c, str) and c in evidence]
        if cid not in catalog_ids or cid in seen or relation not in _RELATIONS or not reason or not cites:
            continue
        seen.add(cid)
        out.append({**catalog_ids[cid], "relation": relation, "reason": reason[:400],
                    "evidence": [evidence[c] for c in dict.fromkeys(cites)], "rank": len(out) + 1})
    return out


def crowded_level(count: int) -> int | None:
    """Connect's total in the crowded case, from how many sellers sell the same kind of solution;
    None below the first band, where the open case scores the startup instead."""
    level = None
    for at_least, score in config.CONNECT_CROWDED:
        if count >= at_least:
            level = score
    return level


def _seller(seller: dict, label: str, differentiator: str = "", evidence=()) -> dict:
    return {"id": seller["id"], "name": seller["name"], "url": seller.get("url", ""), "label": label,
            "differentiator": differentiator, "evidence": list(evidence)}


def similar_sellers(raw: dict, evidence: dict, catalog_ids: dict) -> dict:
    """The sellers that already sell the same kind of solution, nearest first.

    The model labels each shortlisted seller same / different and never gives the count. The
    shortlist's order is the search rank, so the first five shown are the most similar. A seller
    the model skipped counts as different: here a "same" pushes the startup into the crowded case,
    and silence is not evidence that someone already sells it.
    """
    sellers = {i: e for i, e in catalog_ids.items() if str(i).startswith("seller:")}
    labels = raw.get("neighbours")
    if not isinstance(labels, list):
        raise ValueError("neighbours: missing")
    found: dict = {}
    for item in labels:
        if not isinstance(item, dict):
            raise ValueError("neighbours: not an object")
        cid = str(item.get("catalog_id") or "")
        if cid not in sellers:
            raise ValueError("neighbours: names a seller that was not shortlisted")
        label = str(item.get("label") or "").strip().lower()
        if label not in SIMILARITY:
            raise ValueError("neighbours: label must be same or different")
        cites = item.get("citations") or []
        if not isinstance(cites, list) or any(c not in evidence for c in cites):
            raise ValueError("neighbours: cites evidence that does not exist")
        # A differentiator the model cannot cite is its opinion, not the startup's evidence.
        diff = str(item.get("differentiator") or "").strip()[:300] if cites else ""
        found.setdefault(cid, _seller(sellers[cid], label, diff, [evidence[c] for c in dict.fromkeys(cites)]))
    same = [found[cid] for cid in sellers if cid in found and found[cid]["label"] == "same"]
    shown = config.CONNECT_SIMILAR_SHOWN
    return {"count": len(same), "searched": len(sellers),
            # Every shortlisted seller sells it: the true count may be higher than the search reached.
            "at_least": bool(sellers) and len(same) == len(sellers),
            "shown": same[:shown], "more": max(0, len(same) - shown), "sellers": same,
            "skipped": sum(1 for cid in sellers if cid not in found),
            "case": "crowded" if crowded_level(len(same)) is not None else "open"}


_MARKET_SIGNALS = (("market:size", "market_size"), ("market:growth", "market_growth"),
                   ("market:funded_peers", "funded_peers"))


def market_signals(evidence: dict) -> dict:
    """The Market signals row: one point per good signal — a cited size or CAGR at or above
    config.CONNECT_GOOD_MARKET, or grounded funded peers — each a `market:` record
    core/pillar_match.market_records built in Python, so "good" is never the model's call."""
    market = [e for e in evidence.values() if str(e.get("source", "")).startswith("market:")]
    level = min(3, len(market))
    named = {e["source"] for e in market}
    return {"id": "market_signals", "label": "Market signals", "score": level,
            "rationale": (f"{len(market)} good market signal(s) cited." if market else "No good market signal is cited."),
            "anchor": PILLARS["Connect"]["anchors"]["market_signals"][level], "basis": "derived", "path": "market",
            "signals": {k: src in named for src, k in _MARKET_SIGNALS}, "evidence": market, "catalog": []}


def _names(similar: dict) -> str:
    names = ", ".join(s["name"] for s in similar["shown"])
    if similar["more"]:
        names += f" + {similar['more']} more"
    return names


_VERDICTS = {"strong": ("makes_sense", "Partnering makes sense"),
             "review": ("worth_exploring", "Worth exploring, with open questions"),
             "no_match": ("not_yet", "Partnering does not make sense on current evidence")}


def connect_case(rows: list[dict], band_name: str, similar: dict) -> dict:
    """Whether Siemens partnering with this startup makes sense, as sentences built from the
    criteria and the similar sellers — templated, never generated, so every point is a fact the
    assessment already holds."""
    fit, market_row, offering = rows
    points = []

    def point(tone, text, sources=()):
        points.append({"tone": tone, "text": text, "sources": [u for u in dict.fromkeys(sources) if u]})

    verdict, title = _VERDICTS[band_name]
    n = similar["count"]
    if similar["case"] == "crowded":
        point("minus", f"{n}{' or more' if similar['at_least'] else ''} Xcelerator sellers already sell the same "
                       f"kind of solution: {_names(similar)}.", [s["url"] for s in similar["shown"]])
        return {"verdict": verdict, "title": title, "points": points,
                "summary": "The ecosystem already has this, so Connect is scored from how many sell it; "
                           "the startup's own fit and market are shown but not counted."}
    if n == 1:
        one = similar["sellers"][0]
        if one["differentiator"]:
            point("plus", f"One Xcelerator seller sells something similar, {one['name']}, but the startup is "
                          f"evidenced as different: {one['differentiator'].rstrip('.')}.",
                  [e.get("url", "") for e in one["evidence"]])
        else:
            point("minus", f"One Xcelerator seller already sells something similar: {one['name']}.", [one["url"]])
    else:
        point("plus", "No Xcelerator seller sells the same kind of solution: a partnership would add something new.")
    named = [e["name"] for e in fit["catalog"] if str(e.get("id", "")).startswith(("industry:", "topic:"))]
    if fit["score"] >= 2:
        point("plus", "Serves Xcelerator industries and topics: " + ", ".join(named) + ".")
    else:
        point("minus", "Only a loose link to Xcelerator's industries and topics"
              + (f" ({', '.join(named)})" if named else "") + ".")
    if market_row["evidence"]:
        point("plus", "Good market signals: " + "; ".join(e["quote"] for e in market_row["evidence"]) + ".",
              [e.get("url", "") for e in market_row["evidence"]])
    else:
        point("minus", "No good market signal was cited.")
    if offering["score"] >= 2:
        point("plus", f"Offering: {offering['anchor']}.", [e.get("url", "") for e in offering["evidence"]])
    else:
        point("minus", f"Offering: {offering['anchor']}.")
    good = sum(1 for p in points if p["tone"] == "plus")
    summary = ("Few in the ecosystem sell this, and the startup's fit, market and offering make the case."
               if good == len(points) else
               "Few in the ecosystem sell this; the points against it are what stand between it and a partnership.")
    return {"verdict": verdict, "title": title, "summary": summary, "points": points}


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

    Connect adds: Industry & topic fit at 2+ must cite both an Xcelerator industry and a topic,
    else 1; Market signals is derived (`market_signals`); and the similar sellers decide the case —
    crowded scores from their count alone (`crowded_level`), open sums the rows, with Offering
    capped at 2 when one seller sells the same thing and nothing cited sets the startup apart.
    """
    spec = PILLARS[pillar]
    if not isinstance(raw, dict) or not isinstance(raw.get("criteria"), dict):
        raise ValueError("missing criteria")
    derived = spec.get("derived", ())
    keys = [k for k, _ in spec["criteria"] if k not in derived]
    if set(raw["criteria"]) != set(keys):
        raise ValueError("criteria keys do not match the pillar")
    rows, notes = [], []
    for key, label in spec["criteria"]:
        if key in derived:
            rows.append({"id": key})                 # filled below, once the scored rows exist
            continue
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
        if score > 0 and key in spec.get("evidence_only", ()) and not cites:
            score = 0
            notes.append(f"{label}: no startup evidence cited; scored 0.")
        elif score > 0 and key not in spec.get("evidence_only", ()) and not (cites and cats):
            score = 0
            notes.append(f"{label}: no startup evidence and catalog entry cited together; scored 0.")
        rows.append({"id": key, "label": label, "score": score, "rationale": rationale[:600],
                     "anchor": spec["anchors"][key][score],
                     "evidence": [evidence[c] for c in dict.fromkeys(cites)],
                     "catalog": [catalog_ids[c] for c in dict.fromkeys(cats)]})
    similar = None
    if pillar == "Connect":
        fit = rows[0]
        kinds = {str(e.get("id", "")).split(":")[0] for e in fit["catalog"]}
        if fit["score"] >= 2 and not {"industry", "topic"} <= kinds:
            fit["score"], fit["anchor"] = 1, spec["anchors"][fit["id"]][1]
            notes.append(f"{fit['label']} capped at 1: it must cite both an Xcelerator industry and a topic.")
        rows[1] = market_signals(evidence)
        similar = similar_sellers(raw, evidence, catalog_ids)
        if similar["skipped"]:
            notes.append(f"{similar['skipped']} seller(s) were not labelled and count as different.")
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
    if similar and similar["count"] == 1 and third["score"] == 3 and not similar["sellers"][0]["differentiator"]:
        third["score"], third["anchor"] = 2, spec["anchors"][third["id"]][2]
        notes.append(f"{third['label']} capped at 2: {similar['sellers'][0]['name']} already sells the same "
                     "kind of solution and nothing cited sets the startup apart.")
    tools = _recommended_tools(raw, evidence, catalog_ids) if pillar == "Empower" else None
    total = sum(r["score"] for r in rows)
    if similar and similar["case"] == "crowded":
        # The ecosystem already sells this: the count is the score, and the rows are shown for what
        # they say about the startup, not added up.
        total = crowded_level(similar["count"])
        for r in rows:
            r["counted"] = False
    covered = sum(1 for r in rows if r["evidence"])
    banded = band(total, third["score"])
    return {"pillar": pillar, "status": "assessed", "total": total,
            "band": banded, "criteria": rows,
            "statement": statement if concrete else "", "next_step": next_step if concrete else "",
            "evidence_coverage": round(covered / 3, 2), "notes": notes,
            **({"recommended_tools": tools} if tools is not None else {}),
            **({"similar": similar, "case": connect_case(rows, banded, similar)} if similar else {})}


def _rank_key(p: dict):
    return (p["total"], p["criteria"][2]["score"], p.get("evidence_coverage", 0),
            -ORDER.index(p["pillar"]))


def siemens_fit(pillars: dict) -> dict:
    """`round(100 × best assessed total / 9)`, with the pillar that earned it.

    Null when nothing was assessable — never 0, which would read as "assessed and unfit". A run
    missing a pillar still gets a number from the ones it has, flagged partial, because the
    number is a maximum and a maximum over fewer pillars is a floor, not a guess.

    A Collaborate at 0/9 is left out: no department's stated needs matched, so it is not a route
    and must not be the pillar the fit is credited to — on a tie at 0 it used to win the label on
    evidence coverage, and with Empower and Connect unassessed it turned "pending" into a 0.
    """
    assessed = [p for p in pillars.values() if p.get("status") == "assessed"]
    partial = len(assessed) < len(ORDER)
    eligible = [p for p in assessed if not (p.get("pillar") == "Collaborate" and not p.get("total"))]
    if not eligible:
        return {"score": None, "winner": None, "partial": partial, "status": "unassessed"}
    best = max(eligible, key=_rank_key)
    return {"score": round(100 * best["total"] / 9), "winner": best["pillar"],
            "raw": best["total"], "partial": partial, "status": "assessed"}


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
