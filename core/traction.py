"""Traction as a points rubric: Funding 30 · Customers 30 · Revenue 30 · Employees 10.

Deterministic on purpose. Every number here is a band lookup over a fact the run already holds, so
the score costs nothing per run, cannot drift between two reads of the same evidence, and can be
recomputed for every stored run whenever the table changes. The model's part is upstream and
narrow — it labels grounded customers and quotes a revenue line (core/profile.py) — and nothing
here takes a number from it.

A division with no evidence is *dropped*, not scored zero, and the rest are normalised over what
remains. That is the product owner's rule and it is the same distinction `employees_history_status`
and the SFS `unassessed` state exist for: "we found nothing" and "we found it was nothing" are
different statements. Confidence is the share of the 100 points the evidence covers, so a score
normalised from employees alone reads as 10% confident rather than as a strong company.
"""
from __future__ import annotations

import datetime
import re

from . import config
from .text import find_money, is_named_org, parse_funding_stage, parse_headcount, _clean_source_url

# v2: customers must read as named organisations (text.is_named_org). Bumping the version is what
# makes every stored run rescore on read instead of keeping a breakdown that counted fragments.
VERSION = "traction-rubric-v2"
DIVISIONS = ("funding", "customers", "revenue", "employees")
# Relations that make a named organisation a customer. A pilot is not yet a paying account, and a
# partner, investor or supplier is not one at all — the grounding window accepts "partner" as a
# relationship phrase, so this is where that distinction has to be drawn.
_COUNTED_RELATIONS = ("customer", "")
_REVENUE_METRICS = ("revenue", "arr", "turnover", "run_rate", "mrr")
_LEGAL = re.compile(r"\b(?:ag|se|gmbh|kgaa|kg|co|inc|corp|corporation|llc|ltd|limited|plc|sa|sas|"
                    r"bv|nv|oy|ab|as|spa|srl|group|holding|holdings)\b\.?", re.I)


def _norm_org(name) -> str:
    """'Siemens AG', 'SIEMENS' and 'Siemens Aktiengesellschaft' are one customer."""
    s = str(name or "").lower().replace("aktiengesellschaft", "")
    s = _LEGAL.sub(" ", s)
    return re.sub(r"[^a-z0-9&]+", " ", s).strip()


_NOTABLE = {_norm_org(n) for n in config.NOTABLE_COMPANIES}


def _band(value: float, bands) -> tuple[float, str]:
    for lower, points, label in bands:
        if value >= lower:
            return points, label
    return 0.0, ""


def _to_eur(money: dict) -> tuple[float | None, bool]:
    """(amount in EUR, currency_assumed). None when the currency is one we hold no rate for."""
    currency = money.get("currency") or "EUR"    # a bare number is GlassDollar's € convention
    rate = config.FX_TO_EUR.get(currency)
    if rate is None:
        return None, False
    return money["low"] * rate, bool(money.get("currency_assumed"))


def _fmt_eur(v: float) -> str:
    if v >= 1e6:
        return f"€{v / 1e6:.2f}M".replace(".00M", "M")
    if v >= 1e3:
        return f"€{v / 1e3:.0f}k"
    return f"€{v:.0f}"


def _division(key: str, **kw) -> dict:
    spec = config.TRACTION_RUBRIC[key]
    out = {"id": key, "label": spec["label"], "max": spec["max"], "status": "unknown",
           "points": None, "value": "", "band": "", "source_url": "", "origin": "", "basis": "",
           "conflict": False, "currency_assumed": False, "stale": False, "rationale": "",
           "candidates": []}
    out.update(kw)
    return out


# ----------------------------------------------------------------------------- divisions

# Researched lines carry other money in the same sentence — "Total raised: $724M. Current valuation:
# $8.5B", "Revenue €3M in a €10B market" — and the largest amount is then the wrong one. Within a
# clause that names other money, an amount counts only if the words just before it say it is the
# thing asked about and nothing between says otherwise. Dropping the whole clause instead lost the
# real round in "Raised $5M at a $50M valuation".
_NOT_RAISED = re.compile(r"valuation|valued|market|revenue|\barr\b|turnover|sales|\btam\b|worth",
                         re.I)
_RAISED = re.compile(r"rais|round|funding|secured|closed|invest|seed|series|grant", re.I)
_NOT_REVENUE = re.compile(r"valuation|valued|market|\btam\b|worth|rais|round|funding|gmv|"
                          r"bookings|forecast|target|by 20\d\d", re.I)
_REVENUE = re.compile(r"revenue|\barr\b|\bmrr\b|turnover|sales|run[- ]rate|umsatz|income", re.I)


def _amounts_about(text: str, want: re.Pattern, avoid: re.Pattern) -> list[dict]:
    out = []
    for clause in re.split(r"(?<!\d)[.;](?!\d)|\n", str(text or "")):
        found = find_money(clause)
        if not avoid.search(clause):
            out.extend(found)
            continue
        for m in found:
            before = clause[max(0, m["start"] - 30):m["start"]]
            # Only a word directly qualifying the amount ("$50M valuation", "€10B market"); a
            # comma ends it, so "Raised €3M, valued at €30M" keeps the €3M.
            after = re.match(r"\s*(?:[\w-]+\s+)?(\S+)", clause[m["end"]:m["end"] + 30])
            if (want.search(before) and not avoid.search(before[-15:])
                    and not (after and avoid.match(after.group(1)))):
                out.append(m)
    return out


def _raised_amounts(text: str) -> list[dict]:
    return _amounts_about(text, _RAISED, _NOT_RAISED)


def _funding(inputs: dict) -> dict:
    rubric = config.TRACTION_RUBRIC["funding"]
    candidates = []
    for c in inputs["funding"]:
        money = max(_raised_amounts(c["value"]), key=lambda m: m["low"], default=None)
        eur, assumed = _to_eur(money) if money else (None, False)
        reason = ("no amount stated" if not money else
                  f"currency {money['currency']} has no reference rate" if eur is None else "")
        candidates.append({**c, "eur": eur, "currency_assumed": assumed, "reason": reason})
    priced = [c for c in candidates if c["eur"]]
    stage = inputs.get("funding_stage") or next(
        (s for s in (parse_funding_stage(c["value"]) for c in candidates) if s), "")
    if priced:
        # Any single round is a floor on the total raised, so the larger figure is the truer one.
        best = max(priced, key=lambda c: c["eur"])
        points, band = _band(best["eur"], rubric["bands"])
        basis = "amount"
        if stage == "series_b_plus" and best["eur"] >= 2_000_000:
            points, band, basis = rubric["max"], "Series B+ at ≥ €2M", "amount_and_stage"
        bands = {_band(c["eur"], rubric["bands"])[1] for c in priced}
        for c in candidates:
            c["used"] = c is best
        return _division(
            "funding", status="evidenced", points=float(points), band=band, basis=basis,
            value=best["value"], value_eur=round(best["eur"]), source_url=best["source_url"],
            origin=best["origin"], currency_assumed=best["currency_assumed"],
            conflict=len(bands) > 1, candidates=candidates,
            rationale=f"{best['value']} ≈ {_fmt_eur(best['eur'])} → {band}: {points:g} of "
                      f"{rubric['max']}.")
    if stage in config.FUNDING_STAGE_POINTS:
        points = config.FUNDING_STAGE_POINTS[stage]
        src = next((c for c in candidates if parse_funding_stage(c["value"]) == stage),
                   candidates[0] if candidates else {})
        label = stage.replace("_plus", "+").replace("_", " ").title().replace("B+", "B+")
        return _division(
            "funding", status="evidenced", points=float(points), band=f"Stage: {label}",
            basis="stage_only", value=src.get("value", label), source_url=src.get("source_url", ""),
            origin=src.get("origin", ""), candidates=candidates,
            rationale=f"Amount undisclosed; {label} scores {points} of {rubric['max']} by stage.")
    return _division("funding", candidates=candidates,
                     rationale="No funding amount or stage was evidenced.")


def _customers(inputs: dict) -> dict:
    rubric = config.TRACTION_RUBRIC["customers"]
    company, parent = _norm_org(inputs.get("company")), _norm_org(inputs.get("parent_group"))
    investors = {_norm_org(i) for i in inputs.get("investors", [])}
    contradicted = {_norm_org(n) for n in inputs.get("contradicted", [])}
    classes = {_norm_org(c.get("name")): c for c in inputs.get("customer_classes", [])
               if isinstance(c, dict)}
    items, seen, big, sme = [], set(), 0, 0
    for c in inputs.get("customers", []):
        name, key = c["name"], _norm_org(c["name"])
        cls = classes.get(key, {})
        relation = str(cls.get("relation") or "").lower()
        reason = ("" if key and key not in seen else "duplicate")
        if not reason and key in (company, parent):
            reason = "the startup itself or its parent"
        elif not reason and key in investors:
            reason = "listed as an investor"
        elif not reason and key in contradicted:
            reason = "contradicted by the web evidence"
        elif not reason and relation not in _COUNTED_RELATIONS:
            reason = f"relationship is '{relation}', not customer"
        size = ("large_enterprise" if key in _NOTABLE or cls.get("size") == "large_enterprise"
                else "sme")
        counted = not reason
        if counted:
            seen.add(key)
            big += size == "large_enterprise"
            sme += size == "sme"
        items.append({"name": name, "size": size, "relation": relation or "customer",
                      "source_url": c.get("source_url", ""), "origin": c.get("origin", ""),
                      "classified_by": "list" if key in _NOTABLE else cls.get("by", "default"),
                      "counted": counted, "reason": reason})
    big_pts, _ = _band(big, [(n, p, "") for n, p in config.CUSTOMER_BIG_POINTS])
    sme_pts, _ = _band(sme, [(n, p, "") for n, p in config.CUSTOMER_SME_POINTS])
    named = min(float(rubric["max"]), big_pts + sme_pts)
    grade = inputs.get("segment_grade") or {}
    generic = config.CUSTOMER_GENERIC_POINTS.get(grade.get("level")) if grade.get("source_url") else None
    if not (big or sme) and generic is None:
        return _division("customers", items=items,
                         rationale="No named customer or sourced customer-base statement.")
    if generic is not None and generic > named:
        return _division(
            "customers", status="evidenced", points=float(generic), items=items,
            band=f"Generic customer base, level {grade['level']}", basis="generic",
            value=inputs.get("segment", "") or grade.get("quote", ""),
            source_url=grade["source_url"], origin="web",
            rationale=f"Customers described, not named ('{grade.get('quote', '')[:80]}'): "
                      f"{generic:g} of {rubric['max']}.")
    parts = [f"{big} big-name ({big_pts:g})" if big else "", f"{sme} SME ({sme_pts:g})" if sme else ""]
    return _division(
        "customers", status="evidenced", points=named, items=items, basis="named",
        band=" + ".join(p for p in parts if p), value=f"{big + sme} named customer(s)",
        source_url=next((i["source_url"] for i in items if i["counted"] and i["source_url"]), ""),
        rationale=f"{' + '.join(p for p in parts if p)} = {named:g} of {rubric['max']}"
                  f"{' (capped)' if big_pts + sme_pts > rubric['max'] else ''}.")


def _revenue(inputs: dict) -> dict:
    rubric = config.TRACTION_RUBRIC["revenue"]
    rev = inputs.get("revenue") or {}
    url = _clean_source_url(rev.get("source_url"))
    if not url:
        return _division("revenue", rationale="No sourced revenue statement.")
    year = rev.get("fiscal_year")
    stale = bool(year) and str(year).isdigit() and datetime.date.today().year - int(year) > 3
    if rev.get("status") == "pre_revenue":
        return _division("revenue", status="zero_evidenced", points=0.0, band="Pre-revenue",
                         value=rev.get("quote", "pre-revenue"), source_url=url, origin="web",
                         stale=stale, basis="pre_revenue",
                         rationale=f"Evidenced as pre-revenue: 0 of {rubric['max']}.")
    metric = str(rev.get("metric") or "revenue").lower()
    money = max(_amounts_about(rev.get("quote"), _REVENUE, _NOT_REVENUE),
                key=lambda m: m["low"], default=None)
    if rev.get("status") != "amount" or metric not in _REVENUE_METRICS or not money:
        return _division("revenue", value=rev.get("quote", ""), source_url=url,
                         rationale=f"Stated figure is not revenue ({metric})." if money else
                         "Revenue mentioned without an amount.")
    eur, assumed = _to_eur(money)
    if eur is None:
        return _division("revenue", value=rev.get("quote", ""), source_url=url,
                         rationale=f"Currency {money['currency']} has no reference rate.")
    if metric == "mrr":
        eur *= 12
    points, band = _band(eur, rubric["bands"])
    growth = rev.get("growth_pct")
    if (inputs.get("revenue_signal") == "recurring" and isinstance(growth, (int, float))
            and growth >= config.GROWTH_STRONG_PCT and eur >= config.GROWTH_STRONG_MIN_EUR):
        points, band = rubric["max"], f"Recurring, +{growth:g}% growth"
    return _division(
        "revenue", status="evidenced", points=float(points), band=band, value=rev.get("quote", ""),
        value_eur=round(eur), source_url=url, origin="web", currency_assumed=assumed, stale=stale,
        basis=metric, rationale=f"{metric.upper() if metric != 'revenue' else 'Revenue'} "
        f"{_fmt_eur(eur)}{' (MRR × 12)' if metric == 'mrr' else ''} → {band}: {points:g} of "
        f"{rubric['max']}.")


def _employees(inputs: dict) -> dict:
    rubric = config.TRACTION_RUBRIC["employees"]
    candidates = []
    for c in inputs["employees"]:
        hc = parse_headcount(c["value"])
        ok = hc and 1 <= hc["low"] <= config.HEADCOUNT_MAX_PLAUSIBLE
        candidates.append({**c, "low": hc["low"] if ok else None,
                           "reason": "" if ok else "not a plausible headcount"})
    usable = [c for c in candidates if c["low"] is not None]
    if not usable:
        return _division("employees", candidates=candidates,
                         rationale="No usable headcount was evidenced.")
    best = usable[0]                      # candidates arrive in precedence order
    points, band = _band(best["low"], rubric["bands"])
    for c in candidates:
        c["used"] = c is best
    return _division(
        "employees", status="evidenced", points=float(points), band=band, value=best["value"],
        source_url=best["source_url"], origin=best["origin"], candidates=candidates,
        basis="band_lower_bound" if "-" in str(best["value"]) else "count",
        conflict=len({_band(c["low"], rubric["bands"])[1] for c in usable}) > 1,
        rationale=f"{best['value']} → {band}: {points:g} of {rubric['max']}.")


# ----------------------------------------------------------------------------- assembly

def gather_traction_inputs(result: dict) -> dict:
    """Everything the rubric reads, from a pipeline result — live or stored.

    One function for both, so a stored run scored on read and a fresh run scored in the pipeline
    cannot disagree. `traction_inputs` carries the raw database values: the header profile only
    keeps funding after `format_funding` has rounded it, and "€2.0M" can be €1.96M, a band lower.
    """
    raw = result.get("traction_inputs") or {}
    profile = result.get("profile") or {}
    sources = result.get("profile_sources") or {}
    deep = result.get("deep_profile") or {}
    commercial = deep.get("commercial") or {}
    db_origin = raw.get("origin") or "database"

    def cand(value, url, origin):
        v = str(value or "").strip()
        return {"value": v, "source_url": _clean_source_url(url), "origin": origin} if v and v.lower() != "nan" else None

    funding = [cand(raw.get("funding"), "", db_origin) if raw else
               cand(profile.get("funding"), sources.get("funding") if isinstance(sources.get("funding"), str) else "", "profile"),
               cand(deep.get("funding"), deep.get("funding_source"), "web")
               if _clean_source_url(deep.get("funding_source")) else None]
    series = sorted((p for p in deep.get("employees_over_time") or [] if isinstance(p, dict)),
                    key=lambda p: str(p.get("year", "")))
    employees = [cand(raw.get("employees_count") or raw.get("employee_band"), "", db_origin) if raw else
                 cand(profile.get("employees_count") or profile.get("employee_band"), "", "profile"),
                 cand(deep.get("employees"), "", "web"),
                 cand(series[-1].get("count"), series[-1].get("source_url"), "web") if series else None,
                 cand(deep.get("linkedin_size_band"), deep.get("linkedin_size_source"), "linkedin")]
    claims = (result.get("verification") or {}).get("claims") or []
    by_value = {_norm_org(c.get("value")): c for c in claims if c.get("field") == "reference_customer"}
    # Stored runs predate the named-organisation check, so it is applied again here: a fragment
    # of a prose "Reference customers" box ("In parallel") must not score as a named account.
    names = [n for n in (deep.get("reference_customers") or [
        n.strip() for n in re.split(r"[,\n;·|]+", str(raw.get("customers") or "")) if n.strip()]) if is_named_org(n)]
    customers = []
    for n in names:
        claim = by_value.get(_norm_org(n), {})
        customers.append({"name": str(n), "source_url": _clean_source_url(claim.get("evidence_url")),
                          "origin": "verified" if claim.get("status") == "verified" else "research"})
    return {
        "company": result.get("company", ""),
        "parent_group": deep.get("parent_group", ""),
        "funding": [c for c in funding if c],
        "funding_stage": commercial.get("funding_stage", ""),
        "employees": [c for c in employees if c],
        "customers": customers,
        "customer_classes": deep.get("customer_classes") or [],
        "investors": [i.get("name", "") for i in commercial.get("investors") or [] if isinstance(i, dict)],
        "contradicted": [c.get("value") for c in claims
                         if c.get("field") == "reference_customer" and c.get("status") == "contradicted"],
        "segment": deep.get("customer_segment", ""),
        "segment_grade": deep.get("customer_segment_grade") or {},
        "revenue": commercial.get("revenue") or {},
        "revenue_signal": commercial.get("revenue_signal", ""),
    }


def score_traction(inputs: dict) -> dict:
    divisions = [_funding(inputs), _customers(inputs), _revenue(inputs), _employees(inputs)]
    known = [d for d in divisions if d["status"] != "unknown"]
    earned = sum(d["points"] for d in known)
    available = sum(d["max"] for d in known)
    return {
        "version": VERSION,
        "status": "scored" if known else "no_evidence",
        "score_0_100": round(100 * earned / available, 1) if available else None,
        "earned": earned, "available_max": available, "total_max": 100,
        # Points-weighted, per the product owner: evidencing funding (30) is worth more certainty
        # than evidencing headcount (10), so they cannot count the same.
        "confidence": available / 100,
        "divisions_known": len(known), "fx_as_of": config.FX_AS_OF,
        "divisions": divisions,
    }


def apply_traction(score: dict, traction: dict) -> dict:
    """The model's score with its traction replaced by the rubric's, as a new dict.

    The model's own number is kept as `traction_llm`, both for audit and because the gap between
    the two across the corpus is the calibration signal. Idempotent: re-applying never overwrites
    `traction_llm` with the rubric's value.
    """
    # With nothing evidenced the model's number stands, untouched: the six-key contract the what-if
    # re-weighting relies on needs a traction value, and an absent `traction_method` is how the UI
    # knows the number is the model's.
    if (not isinstance(score, dict) or score.get("status") != "assessed"
            or not traction or traction.get("status") != "scored"):
        return score
    out = {**score, "dimensions": dict(score.get("dimensions") or {}),
           "judgments": dict(score.get("judgments") or {})}
    prior = score.get("traction_llm") if score.get("traction_method") == "rubric" \
        else (score.get("dimensions") or {}).get("traction")
    evidence = [{"id": f"T-{d['id']}", "source": f"traction.{d['id']}", "text": d["value"],
                 "url": d["source_url"], "quote": d["value"]}
                for d in traction["divisions"] if d["status"] != "unknown" and d["value"]]
    out["dimensions"]["traction"] = traction["score_0_100"]
    out["judgments"]["traction"] = {
        "score": traction["score_0_100"], "evidence": evidence,
        "rationale": (f"Rubric: {traction['earned']:g} of {traction['available_max']} available points "
                      f"({traction['divisions_known']} of 4 divisions evidenced). "
                      + " ".join(d["rationale"] for d in traction["divisions"] if d["status"] != "unknown"))}
    out["traction_llm"] = prior
    out["traction_method"] = "rubric"
    return out


def ladders() -> dict:
    """Every rung of each division's rubric, best first, for a reader to see where a score sits.

    Built from config on read rather than stored, so the page never holds a second copy of the
    rubric that could drift. A rung names the `band` string its division reports (`match`, or a
    `prefix` for bands carrying a figure); customer rungs are counts (`kind`, `min`), because the
    customer band is a sum of the named big-name and SME tiers.
    """
    rub = config.TRACTION_RUBRIC
    stage_label = {"pre_seed": "Pre Seed", "seed": "Seed", "series_a": "Series A", "series_b_plus": "Series B+"}
    amount, stage = "By amount raised", "By stage, amount undisclosed"
    big, sme, generic = "Named big-name customers", "Named SME customers", "Customer base described, not named"
    return {
        "funding": [{"group": amount, "label": "Series B+ with ≥ €2M raised", "points": rub["funding"]["max"], "match": "Series B+ at ≥ €2M"}]
        + [{"group": amount, "label": f"Raised {label}", "points": p, "match": label} for _, p, label in rub["funding"]["bands"]]
        + [{"group": stage, "label": stage_label[s], "points": p, "match": f"Stage: {stage_label[s]}"}
           for s, p in sorted(config.FUNDING_STAGE_POINTS.items(), key=lambda kv: -kv[1])],
        "customers": [{"group": big, "label": f"{n}+ big-name customer{'s' if n > 1 else ''}", "points": p, "kind": "big", "min": n}
                      for n, p in config.CUSTOMER_BIG_POINTS]
        + [{"group": sme, "label": f"{n}+ SME customer{'s' if n > 1 else ''}", "points": p, "kind": "sme", "min": n}
           for n, p in config.CUSTOMER_SME_POINTS]
        + [{"group": generic, "label": f"Level {lvl}", "points": p, "match": f"Generic customer base, level {lvl}"}
           for lvl, p in sorted(config.CUSTOMER_GENERIC_POINTS.items(), reverse=True)],
        "revenue": [{"group": "", "label": f"Recurring, ≥ {config.GROWTH_STRONG_PCT:g}% growth on ≥ €1M",
                     "points": rub["revenue"]["max"], "prefix": "Recurring, +"}]
        + [{"group": "", "label": label, "points": p, "match": label} for _, p, label in rub["revenue"]["bands"]]
        + [{"group": "", "label": "Pre-revenue (sourced)", "points": 0, "match": "Pre-revenue"}],
        "employees": [{"group": "", "label": f"{label} employees", "points": p, "match": label}
                      for _, p, label in rub["employees"]["bands"]],
    }


def with_traction(result: dict) -> dict:
    """A result carrying a current traction breakdown, with its score agreeing with it.

    Called on the live pipeline result and on every stored run as it is read, so a rubric change
    reaches old runs without a migration and the Explore grid can never disagree with the profile.
    """
    if not isinstance(result, dict) or not result.get("found", True):
        return result
    traction = result.get("traction")
    if not isinstance(traction, dict) or traction.get("version") != VERSION:
        traction = score_traction(gather_traction_inputs(result))
    # The rubric's rungs ride beside the breakdown, not inside it: a current breakdown is returned
    # as the very object that was stored, so nothing read from a run is silently rebuilt.
    return {**result, "traction": traction, "traction_ladders": ladders(),
            "score": apply_traction(result.get("score") or {}, traction)}
