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

Connect asks whether the offering is already in the Xcelerator ecosystem (Ecosystem gap), whether
it belongs there (Industry & topic fit), and whether connecting it would be worth something
(Ecosystem value). Gap and value are derived here, never scored by the model: the model labels the
nearest sellers and names who would use, integrate or resell the offering, and Python turns those
words — with the fit and the market signals — into numbers. `connect_case` then states, in plain
sentences built from the same facts, whether connecting makes sense.
"""
from __future__ import annotations

from . import config

VERSION = "siemens-fit-pillars-v3"
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
        # Ecosystem gap first: it answers "is this already in the ecosystem?", which decides how much
        # the other two can matter. Ecosystem value stays third, because band() gates Strong on it.
        "criteria": (("ecosystem_gap", "Ecosystem gap"), ("industry_topic_fit", "Industry & topic fit"),
                     ("ecosystem_value", "Ecosystem value")),
        # Computed in Python from the model's labels, the fit and the market signals; the model
        # scores only Industry & topic fit.
        "derived": ("ecosystem_gap", "ecosystem_value"),
        "anchors": {
            "ecosystem_gap": ("Already well represented: several sellers offer it and nothing evidenced sets it apart",
                              "Partially represented, or absent only because it sits outside the ecosystem's industries and topics",
                              "Related offerings exist, but none is an undifferentiated equivalent",
                              "Not yet in the ecosystem: no seller offers it"),
            "industry_topic_fit": ("No Xcelerator industry or topic relationship",
                                   "Adjacent industry or broad thematic similarity",
                                   "Clearly relevant Xcelerator industry and topic",
                                   "Directly targets a listed industry and the core offering matches a listed topic"),
            # Two paths. With an ecosystem audience (a seller that would use, integrate or resell
            # it): 1 audience only, 2 plus fit or market, 3 plus both. Without one — open space —
            # the case rests on fit and market alone: 0 neither, 1 one of them, 2 both.
            "ecosystem_value": ("No ecosystem audience, a loose industry and topic fit, and no good market signal",
                                "An audience with little else, or no audience but a clear fit or a good market",
                                "An audience with a clear fit or a good market, or open space with both",
                                "An audience, a clear industry and topic fit, and good market signals"),
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
OVERLAPS = ("equivalent", "overlapping", "distinct")


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


def gap_level(equivalents: int, undifferentiated: int, overlapping: int) -> int:
    """Ecosystem gap from counts. Only an equivalent with nothing evidenced to set the startup apart
    counts against it: a crowded area is no penalty for a startup that shows its difference."""
    if not equivalents and overlapping <= config.CONNECT_GAP_ABSENT_MAX_OVERLAP:
        return 3
    if not undifferentiated:
        return 2
    return 1 if undifferentiated <= config.CONNECT_GAP_PARTIAL_MAX else 0


def _neighbour(seller: dict, overlap: str, differentiator: str = "", evidence=(), **extra) -> dict:
    return {"id": seller["id"], "name": seller["name"], "url": seller.get("url", ""), "overlap": overlap,
            "differentiator": differentiator, "evidence": list(evidence), **extra}


def value_level(audience: bool, fit: bool, market: bool) -> int:
    """Ecosystem value from its three signals, on the two paths the rubric describes.

    With an audience the value starts at 1 and each of fit and market adds one (max 3). Without
    one the offering is in open space and only fit and market count (max 2): new to the ecosystem,
    in an industry and topic it serves and a market worth entering, is a reason to connect; new,
    loosely related and in a weak market is not.
    """
    return 1 + (fit or market) + (fit and market) if audience else int(fit) + int(market)


AUDIENCE_ROLES = ("use", "integrate", "resell", "partner")
MAX_AUDIENCE = 5


def ecosystem_audience(raw: dict, evidence: dict, catalog_ids: dict, exclude: set) -> list[dict]:
    """The sellers the model names as an audience, held to the same bar as a recommended tool:
    shortlisted, a known role, a reason and a real citation. A seller that already sells the same
    thing (``exclude``) is a competitor, never an audience. An unusable entry is dropped, not fatal:
    no audience is a finding the rubric scores, not a malformed answer."""
    out, seen = [], set()
    items = raw.get("audience") if isinstance(raw.get("audience"), list) else []
    for item in items:
        if not isinstance(item, dict) or len(out) >= MAX_AUDIENCE:
            continue
        cid = str(item.get("catalog_id") or "")
        role = str(item.get("role") or "").strip().lower()
        reason = str(item.get("reason") or "").strip()
        cites = [c for c in item.get("citations") or [] if isinstance(c, str) and c in evidence]
        if (not cid.startswith("seller:") or cid not in catalog_ids or cid in exclude or cid in seen
                or role not in AUDIENCE_ROLES or not reason or not cites):
            continue
        seen.add(cid)
        out.append({**catalog_ids[cid], "role": role, "reason": reason[:300],
                    "evidence": [evidence[c] for c in dict.fromkeys(cites)]})
    return out


def ecosystem_value(raw: dict, evidence: dict, catalog_ids: dict, fit: dict, gap: dict) -> dict:
    """The Ecosystem value row: audience, fit (Industry & topic fit at 2+) and a good market signal
    (a `market:` record core/pillar_match.market_records built in Python)."""
    audience = ecosystem_audience(raw, evidence, catalog_ids, {e["id"] for e in gap["catalog"]})
    market = [e for e in evidence.values() if str(e.get("source", "")).startswith("market:")]
    fit_ok = fit["score"] >= 2
    level = value_level(bool(audience), fit_ok, bool(market))
    found = (f"Ecosystem audience: {', '.join(a['name'] for a in audience)}." if audience
             else "No Xcelerator seller was found who would use, integrate or resell it, so it is in open space.")
    why = " ".join([found, "Industry & topic fit is clear." if fit_ok else "Industry & topic fit is loose.",
                    "A good market signal is cited." if market else "No good market signal is cited."])
    return {"id": "ecosystem_value", "label": "Ecosystem value", "score": level, "rationale": why,
            "anchor": PILLARS["Connect"]["anchors"]["ecosystem_value"][level], "basis": "derived",
            "path": "audience" if audience else "open_space",
            "signals": {"audience": bool(audience), "industry_topic": fit_ok, "market": bool(market)},
            "evidence": list({e["id"]: e for e in [x for a in audience for x in a["evidence"]] + market}.values()),
            "catalog": [{k: v for k, v in a.items() if k not in ("role", "reason", "evidence")} for a in audience],
            "audience": audience}


_ROLE_WORDS = {"use": "would use it", "integrate": "would integrate it", "resell": "would resell it",
               "partner": "would partner on it"}
_VERDICTS = {"strong": ("makes_sense", "Connecting makes sense"),
             "review": ("worth_exploring", "Worth exploring, with open questions"),
             "no_match": ("not_yet", "Connecting does not make sense on current evidence")}


def connect_case(rows: list[dict], band_name: str) -> dict:
    """Whether connecting this startup to the ecosystem makes sense, as sentences built from the
    criteria — templated, never generated, so every point is a fact the rows already hold."""
    gap, fit, value = rows
    points = []

    def point(tone, text, sources=()):
        points.append({"tone": tone, "text": text, "sources": [u for u in dict.fromkeys(sources) if u]})

    undiff = [n["name"] for n in gap.get("neighbours") or [] if n["overlap"] == "equivalent" and not n["differentiator"]]
    if gap.get("outside"):
        point("minus", "No Xcelerator seller offers this, but because it sits outside the ecosystem's "
                       "industries and topics rather than filling a gap in them.")
    elif gap["score"] == 3:
        point("plus", "No Xcelerator seller offers this yet: it would add something new to the ecosystem.")
    elif gap["score"] == 2:
        point("plus", "Related offerings exist in the ecosystem, but the startup is evidenced as different.")
    else:
        point("minus", f"Already offered by {len(undiff)} seller(s) with nothing evidenced to set it apart: "
                       + ", ".join(undiff[:5]) + ".")
    audience = value.get("audience") or []
    if audience:
        point("plus", "Who in the ecosystem would benefit: "
              + "; ".join(f"{a['name']} {_ROLE_WORDS.get(a['role'], '')} ({a['reason'].rstrip('.')})" for a in audience) + ".",
              [e.get("url", "") for a in audience for e in a["evidence"]])
    else:
        point("minus", "No Xcelerator seller was found who would use, integrate or resell it.")
    named = [e["name"] for e in fit["catalog"] if str(e.get("id", "")).startswith(("industry:", "topic:"))]
    if fit["score"] >= 2:
        point("plus", "Serves Xcelerator industries and topics: " + ", ".join(named) + ".")
    else:
        point("minus", "Only a loose link to Xcelerator's industries and topics"
              + (f" ({', '.join(named)})" if named else "") + ".")
    market = [e for e in value["evidence"] if str(e.get("source", "")).startswith("market:")]
    if market:
        point("plus", "Good market signals: " + "; ".join(e["quote"] for e in market) + ".", [e.get("url", "") for e in market])
    else:
        point("minus", "No good market signal was cited.")
    verdict, title = _VERDICTS[band_name]
    if value.get("path") == "audience":
        summary = "Part of the ecosystem would use, integrate or resell it; the case below is what that rests on."
    elif value["score"] >= 2:
        summary = "Nobody in the ecosystem was found to use it yet, but it fits the industries and topics Xcelerator serves, in a market with good signals."
    else:
        summary = "Nobody in the ecosystem was found to use it, and its industry fit or market does not make up for that yet."
    return {"verdict": verdict, "title": title, "summary": summary, "points": points}


def ecosystem_gap(raw: dict, evidence: dict, catalog_ids: dict) -> dict:
    """The Ecosystem gap row, from the model's label for each shortlisted seller.

    The model says, per seller, whether it offers the same thing (equivalent), part of it
    (overlapping) or something else (distinct), and names a differentiator only with a citation.
    It never gives the number. A seller it skipped counts as overlapping: silence must not read as
    "nobody offers this".
    """
    # Only the nearest sellers are labelled; the audience candidates are a different question.
    sellers = {i: e for i, e in catalog_ids.items()
               if str(i).startswith("seller:") and e.get("slot", "neighbour") == "neighbour"}
    labels = raw.get("neighbours")
    if not isinstance(labels, list):
        raise ValueError("neighbours: missing")
    found: dict = {}
    for item in labels:
        if not isinstance(item, dict):
            raise ValueError("neighbours: not an object")
        cid = str(item.get("catalog_id") or "")
        if cid not in catalog_ids:
            raise ValueError("neighbours: names a seller that was not shortlisted")
        if cid not in sellers:
            continue                                   # an audience candidate, labelled by mistake
        overlap = str(item.get("overlap") or "").strip().lower()
        if overlap not in OVERLAPS:
            raise ValueError("neighbours: overlap must be equivalent, overlapping or distinct")
        cites = item.get("citations") or []
        if not isinstance(cites, list) or any(c not in evidence for c in cites):
            raise ValueError("neighbours: cites evidence that does not exist")
        # A differentiator the model cannot cite is its opinion, not the startup's evidence.
        diff = str(item.get("differentiator") or "").strip()[:300] if cites else ""
        found.setdefault(cid, _neighbour(sellers[cid], overlap, diff, [evidence[c] for c in dict.fromkeys(cites)]))
    unlabelled = [cid for cid in sellers if cid not in found]
    for cid in unlabelled:
        found[cid] = _neighbour(sellers[cid], "overlapping", unlabelled=True)
    neighbours = list(found.values())
    equivalents = [n for n in neighbours if n["overlap"] == "equivalent"]
    undiff = [n for n in equivalents if not n["differentiator"]]
    overlapping = sum(1 for n in neighbours if n["overlap"] == "overlapping")
    level = gap_level(len(equivalents), len(undiff), overlapping)
    if not sellers:
        why = "No Xcelerator seller is close to this offering."
    elif undiff:
        why = (f"{len(undiff)} seller(s) already offer this and nothing evidenced sets the startup apart: "
               + ", ".join(n["name"] for n in undiff[:5]) + ".")
    elif equivalents:
        why = f"{len(equivalents)} seller(s) offer something equivalent; each has an evidenced difference."
    else:
        why = f"No seller offers the same thing; {overlapping} of the {len(sellers)} nearest overlap in part."
    if unlabelled:
        why += f" {len(unlabelled)} seller(s) were not labelled and count as overlapping."
    cited = [e for n in neighbours if n["overlap"] != "distinct" for e in n["evidence"]]
    return {"id": "ecosystem_gap", "label": "Ecosystem gap", "score": level, "rationale": why,
            "anchor": PILLARS["Connect"]["anchors"]["ecosystem_gap"][level], "basis": "derived",
            "evidence": list({e["id"]: e for e in cited}.values()),
            "catalog": [sellers[n["id"]] for n in equivalents], "neighbours": neighbours}


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

    Connect adds: Ecosystem gap and Ecosystem value are derived (`ecosystem_gap`,
    `ecosystem_value`), and Industry & topic fit at 2+ must cite both an Xcelerator industry and a
    topic, else 1.
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
        if score > 0 and not (cites and cats):
            score = 0
            notes.append(f"{label}: no startup evidence and catalog entry cited together; scored 0.")
        rows.append({"id": key, "label": label, "score": score, "rationale": rationale[:600],
                     "anchor": spec["anchors"][key][score],
                     "evidence": [evidence[c] for c in dict.fromkeys(cites)],
                     "catalog": [catalog_ids[c] for c in dict.fromkeys(cats)]})
    if pillar == "Connect":
        fit = rows[1]
        kinds = {str(e.get("id", "")).split(":")[0] for e in fit["catalog"]}
        if fit["score"] >= 2 and not {"industry", "topic"} <= kinds:
            fit["score"], fit["anchor"] = 1, spec["anchors"][fit["id"]][1]
            notes.append(f"{fit['label']} capped at 1: it must cite both an Xcelerator industry and a topic.")
        rows[0] = gap = ecosystem_gap(raw, evidence, catalog_ids)
        # Absence is a gap only where the ecosystem is: an offering no seller sells because it is
        # unrelated to Xcelerator's industries and topics is distant, not new. Without this, a weak,
        # unrelated startup collected 3/3 for being absent and read as worth a review.
        if gap["score"] >= 2 and fit["score"] < 2:
            gap.update(score=1, anchor=spec["anchors"]["ecosystem_gap"][1], outside=True,
                       rationale=gap["rationale"] + " It is absent because it sits outside the ecosystem's "
                       "industries and topics, not because it fills a gap in them.")
            notes.append("Ecosystem gap capped at 1: Industry & topic fit is loose, so absence is distance, not a gap.")
        rows[2] = ecosystem_value(raw, evidence, catalog_ids, fit, gap)
    statement = str(raw.get("statement") or "").strip()
    next_step = str(raw.get("next_step") or "").strip()
    third = rows[2]
    # A seller the startup duplicates is not an entry to recommend connecting to.
    cited_names = {e["name"].casefold() for r in rows if r["id"] != "ecosystem_gap" for e in r["catalog"]}
    concrete = (len(statement) >= 30 and len(next_step) >= 10
                and any(n in statement.casefold() for n in cited_names)
                and _follows(statement.casefold(), spec["statement_marker"]))
    if third["score"] >= 2 and not concrete:
        third["score"] = 1
        third["anchor"] = spec["anchors"][third["id"]][1]
        notes.append(f"{third['label']} capped at 1: no concrete statement naming a matched "
                     "catalog entry, with a next step.")
    tools = _recommended_tools(raw, evidence, catalog_ids) if pillar == "Empower" else None
    total = sum(r["score"] for r in rows)
    covered = sum(1 for r in rows if r["evidence"])
    banded = band(total, third["score"])
    return {"pillar": pillar, "status": "assessed", "total": total,
            "band": banded, "criteria": rows,
            "statement": statement if concrete else "", "next_step": next_step if concrete else "",
            "evidence_coverage": round(covered / 3, 2), "notes": notes,
            **({"recommended_tools": tools} if tools is not None else {}),
            **({"case": connect_case(rows, banded)} if pillar == "Connect" else {})}


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
