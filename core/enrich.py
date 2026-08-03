"""Fact collection (with provenance) from the DB row and, optionally, the web."""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from .provenance import Fact
from .web import ddg_search, _ddg_many
from .data import extract_pdf_text, _resolve_pdf
from .text import _split_list

log = logging.getLogger(__name__)


def _verify_claim(claim: str, company: str) -> Optional[Fact]:
    """Light verification: corroborate a claim via a DDG query."""
    if not claim.strip():
        return None
    hits = ddg_search(f"{company} {claim}", max_results=3)
    if hits:
        top = hits[0]
        return Fact(key=f"verify:{claim}", value=top.get("title", ""),
                    source_url=top.get("href", ""), method="ddg_search",
                    confidence=0.7, verified=True)
    return Fact(key=f"verify:{claim}", value="no corroboration found",
                method="ddg_search", confidence=0.3, verified=False)


def enrich(row: pd.Series, do_web: bool = True) -> dict:
    """Collect facts (with provenance) from the DB row and, optionally, the web."""
    facts: list[Fact] = []
    company = str(row.get("company_name", "")).strip()

    def db_fact(col, key=None, conf=0.5):
        val = str(row.get(col, "")).strip()
        if val:
            facts.append(Fact(key=key or col, value=val, method="glassdollar_db",
                              source_url="GlassDollar", confidence=conf, verified=False))

    for col, key in [("hq", "hq"), ("founded_year", "founded_year"),
                     ("employees_count", "employees"), ("funding", "funding"),
                     ("customers", "customers"), ("website", "website"),
                     ("linkedin_url", "linkedin"), ("crunchbase_url", "crunchbase")]:
        db_fact(col, key, conf=0.55)

    pitch_pdf = ""
    if str(row.get("has_pdf", "")).lower() in ("true", "1", "yes"):
        pdf_path_raw = str(row.get("pdf_local_path", ""))
        resolved = _resolve_pdf(pdf_path_raw)
        log.info("[enrich] PDF for %s: raw=%r resolved=%r", company, pdf_path_raw[:60], resolved[:60] if resolved else "")
        pitch_pdf = extract_pdf_text(resolved)
        if pitch_pdf:
            facts.append(Fact(key="pitch_deck", value=f"{len(pitch_pdf)} chars extracted",
                              method="pitch_pdf", source_url=str(row.get("pdf_filename", "")),
                              confidence=0.6, verified=True))

    web = {}
    if do_web and company:
        domain = str(row.get("domain", "")).strip()
        hq = str(row.get("hq", "")).strip()
        country = hq.split(",")[-1].strip() if hq else ""
        queries = {
            "funding_web": f"{company} funding round amount raised investors",
            "founders_web": f"{company} founders team background",
            "location_web": f"{company} headquarters location {country}".strip(),
            "employees_web": f"{company} number of employees headcount",
            "customers_web": f"{company} customers clients case study",
            "competitors_web": f"{company} competitors alternatives",
            "news_web": f"{company} {domain} news".strip(),
        }
        if country:
            queries["country_vc_web"] = f"venture capital funding {country} startups 2025"
        # Build the per-customer verification queries and run EVERYTHING in one concurrent wave
        # (single bounded deadline) so enrichment + verification finish together, fast.
        custs = _split_list(str(row.get("customers", "")) or str(row.get("Reference customers", "")))
        all_q = dict(queries)
        for i, c in enumerate(custs):
            all_q[f"__cust__{i}"] = f"{company} {c}"
        results = _ddg_many(all_q, max_results=4)
        web = {k: results.get(k, []) for k in queries}
        for key in queries:
            hits = web.get(key, [])
            if hits:
                facts.append(Fact(key=key, value=hits[0].get("title", ""),
                                  source_url=hits[0].get("href", ""), method="ddg_search",
                                  confidence=0.65, verified=True))
        # reference-customer verification (anti-gaming feeds traction)
        for i, c in enumerate(custs):
            hits = results.get(f"__cust__{i}", [])
            if hits:
                top = hits[0]
                facts.append(Fact(key=f"verify:{c}", value=top.get("title", ""),
                                  source_url=top.get("href", ""), method="ddg_search",
                                  confidence=0.7, verified=True))
            else:
                facts.append(Fact(key=f"verify:{c}", value="no corroboration found",
                                  method="ddg_search", confidence=0.3, verified=False))

    return {"company": company, "facts": facts, "pitch_pdf": pitch_pdf, "web": web}
