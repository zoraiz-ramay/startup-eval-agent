"""Data loading: GlassDollar export, startup lookup, live web-profile fallback,
Siemens tool catalogue, and pitch-PDF text extraction."""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from .config import PDF_DIR, GLASSDOLLAR_API_KEY
from .text import _norm
from .web import _ddg_many
from .llm import LLMClient
from . import s3 as _s3


def load_glassdollar(path: str = None) -> pd.DataFrame:
    """Load the GlassDollar company set.

    Primary source is the live GlassDollar REST API (requires GLASSDOLLAR_API_KEY, or a key
    passed via load_glassdollar_api). The legacy Excel path is only used when an explicit
    file path is given AND no API key is configured, so existing offline exports still work.
    """
    from . import glassdollar_api

    api_key = GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")
    if api_key or (path is None):
        # API mode (the default now). Raises a clear GlassDollarError if the key/endpoint fail.
        return glassdollar_api.load_all_as_df()
    # Legacy Excel fallback: only when a path is supplied and no API key is set.
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df.fillna("")


def load_glassdollar_api(api_key: str = "") -> pd.DataFrame:
    """Explicitly load the company set from the GlassDollar API with a given key."""
    from . import glassdollar_api
    return glassdollar_api.load_all_as_df(api_key=api_key)


def search_glassdollar(query: str, limit: int = 10, api_key: str = "") -> pd.DataFrame:
    """Search the GlassDollar API for companies matching `query` (interactive picker use)."""
    from . import glassdollar_api
    return glassdollar_api.search_as_df(query, limit=limit, api_key=api_key)



def find_startup(df: pd.DataFrame, name: str) -> Optional[pd.Series]:
    """Confidently locate a startup row by company_name / submission_title.

    Uses a high similarity threshold so a query that is NOT in the database (e.g. "RIIICO")
    is reported as a miss rather than snapping to a loosely-similar name (e.g. "vidio").
    Returns None when no row clears the confidence bar so callers can fall back to the web.
    """
    target = _norm(name)
    if not target:
        return None
    cand_cols = [c for c in ("company_name", "submission_title", "domain") if c in df.columns]
    try:
        from rapidfuzz import fuzz
        scorer = lambda a, b: fuzz.token_set_ratio(a, b) / 100.0
    except Exception:  # pragma: no cover - fallback if rapidfuzz missing
        from difflib import SequenceMatcher
        scorer = lambda a, b: SequenceMatcher(None, a, b).ratio()

    best, best_score = None, 0.0
    for _, row in df.iterrows():
        for c in cand_cols:
            cand = _norm(row[c])
            if not cand:
                continue
            if cand == target:                      # exact (normalized) match wins outright
                return row
            score = scorer(target, cand)
            # prefix/substring boost only for sufficiently long queries, so short non-matches
            # (e.g. "riiico" vs "vidio") cannot be promoted on a few shared characters.
            if len(target) >= 4 and (cand.startswith(target) or target.startswith(cand)):
                score = max(score, 0.92)
            if score > best_score:
                best, best_score = row, score
    return best if best_score >= 0.82 else None


def web_profile_row(name: str, llm: "LLMClient" = None, max_results: int = 4) -> Optional[pd.Series]:
    """Assemble a GlassDollar-like row for a startup that is NOT in the database, live from
    the web (DuckDuckGo) plus optional LLM extraction. Returns None if the web yields nothing.

    The synthetic row uses the same column names as the GlassDollar export so the rest of the
    pipeline (enrich / verify / summarize / fit / score / route) works unchanged.
    """
    queries = [
        f"{name} startup company overview what they do",
        f"{name} funding raised investors valuation",
        f"{name} headquarters location founded year",
        f"{name} customers clients case study",
        f"{name} crunchbase founded funding stage",
    ]
    results = _ddg_many({str(i): q for i, q in enumerate(queries)}, max_results=max_results)
    hits: list[dict] = []
    for i in range(len(queries)):
        hits.extend(results.get(str(i), []))
    if not hits:
        # DDG gave nothing (throttled / obscure name): last resort, ONE LLM call builds a
        # minimal profile from model knowledge, clearly marked unverified.
        return _knowledge_profile_row(name, llm)

    # Existence guard: DDG returns *something* for almost any string, so require the queried
    # name to actually appear in at least 2 result titles/snippets before assembling a profile.
    # Otherwise a typo or a made-up name would produce a fabricated company.
    _name_l = _norm(name)
    mentions = sum(1 for h in hits
                   if _name_l and _name_l in _norm(f"{h.get('title','')} {h.get('body','')} {h.get('href','')}"))
    # 2+ mentions when offline; 1 is enough when the LLM exists-check below can adjudicate
    if mentions < (1 if (llm and llm.available) else 2):
        return None

    # first non-social result is a reasonable website guess
    _SOCIAL = ("linkedin.", "crunchbase.", "wikipedia.", "facebook.", "twitter.", "x.com",
               "youtube.", "instagram.", "bloomberg.", "pitchbook.")
    website = ""
    for h in hits:
        href = h.get("href", "")
        if href and not any(s in href for s in _SOCIAL):
            website = href
            break

    text = "\n".join(f"{h.get('title','')} :: {h.get('body','')} :: {h.get('href','')}"
                     for h in hits)[:4500]
    fields: dict = {}
    if llm and llm.available:
        prompt = (
            f"From the web search results below about the company '{name}', extract a factual "
            "profile. Use ONLY what the results support; leave a field empty if unknown. Never invent. "
            "Set exists=false if the results do NOT clearly describe a real company with this name.\n\n"
            f"RESULTS:\n{text}\n\n"
            'Return ONLY JSON: {"exists":true,"company_name":"","website":"","hq":"","founded_year":"",'
            '"funding":"","employees":"","customers":"","business_model":"","stage":"","description":""}'
        )
        fields = LLMClient.parse_json(
            llm.complete(prompt, system="You extract structured company facts strictly from the "
                         "supplied web text. JSON only.", max_tokens=600)) or {}
        if fields and fields.get("exists") is False:
            return None            # LLM judged the results do not describe a real company

    desc = str(fields.get("description") or "").strip()
    if not desc:
        desc = " ".join(h.get("body", "") for h in hits[:3])[:500]

    def _flat(v) -> str:
        """LLM extraction may return a dict/list for a field (e.g. a structured hq); flatten
        it to a readable comma-joined string."""
        if isinstance(v, dict):
            return ", ".join(_flat(x) for x in v.values() if x)
        if isinstance(v, (list, tuple, set)):
            return ", ".join(_flat(x) for x in v if x)
        return str(v or "").strip()

    # Gap-fill: any column the web results left empty gets ONE more LLM call against
    # model knowledge (marked unverified) so profiles never ship with blank fields.
    if llm and llm.available:
        _GAP_KEYS = ("hq", "founded_year", "funding", "employees", "customers",
                     "business_model", "stage", "website")
        missing = [k for k in _GAP_KEYS if not str(fields.get(k) or "").strip()]
        if missing:
            gap = LLMClient.parse_json(llm.complete(
                f"From your own knowledge of the startup '{name}', fill ONLY these fields "
                f"(empty string if unknown, never guess): {', '.join(missing)}.\n"
                'Return ONLY JSON with exactly those keys.',
                system="Factual recall only. JSON only.", max_tokens=300)) or {}
            for k in missing:
                if str(gap.get(k) or "").strip():
                    fields[k] = gap[k]
            fields["_knowledge_filled"] = missing

    row = {
        "company_name": (_flat(fields.get("company_name")) or name),
        "website": (_flat(fields.get("website")) or website),
        "hq": _flat(fields.get("hq")),
        "founded_year": _flat(fields.get("founded_year")),
        "funding": _flat(fields.get("funding")),
        "employees_count": _flat(fields.get("employees")),
        "customers": _flat(fields.get("customers")),
        "short_description": desc,
        "Your pitch": desc,
        "Business model": _flat(fields.get("business_model")),
        "Development stage of your solution": _flat(fields.get("stage")),
        "domain": "", "has_pdf": "", "linkedin_url": "", "crunchbase_url": "",
    }
    return pd.Series(row)


def _knowledge_profile_row(name: str, llm: "LLMClient" = None) -> Optional[pd.Series]:
    """Zero-web-results fallback: one LLM call, model knowledge only, marked unverified."""
    if not (llm and llm.available):
        return None
    fields = LLMClient.parse_json(llm.complete(
        f"Do you know the startup/company '{name}'? If NOT, return exists=false. If yes, "
        "fill from your own knowledge (empty string where unsure, never invent).\n"
        'Return ONLY JSON: {"exists":true,"company_name":"","website":"","hq":"","founded_year":"",'
        '"funding":"","employees":"","customers":"","business_model":"","stage":"","description":""}',
        system="Factual recall only. JSON only.", max_tokens=500)) or {}
    if not fields or fields.get("exists") is False:
        return None
    g = lambda k: str(fields.get(k) or "").strip()
    desc = g("description")
    return pd.Series({
        "company_name": g("company_name") or name, "website": g("website"), "hq": g("hq"),
        "founded_year": g("founded_year"), "funding": g("funding"),
        "employees_count": g("employees"), "customers": g("customers"),
        "short_description": desc, "Your pitch": desc,
        "Business model": g("business_model"),
        "Development stage of your solution": g("stage"),
        "domain": "", "has_pdf": "", "linkedin_url": "", "crunchbase_url": "",
        "_source": "llm_knowledge",     # surfaces as unverified; web enrichment still runs
    })


def load_siemens_tools(path: str) -> list[dict]:
    df = pd.read_csv(path).fillna("")
    # Normalize the tool-name column: accept 'name' (new) or 'product' (legacy).
    if "product" not in df.columns and "name" in df.columns:
        df = df.rename(columns={"name": "product"})
    # Normalize the tool-type column: accept 'type' -> 'category' if 'category' missing.
    if "category" not in df.columns and "type" in df.columns:
        df = df.rename(columns={"type": "category"})
    return df.to_dict("records")


# ----------------------------------------------------------------------------- pdf
def _resolve_pdf(path_field: str, pdf_dir: str = PDF_DIR) -> str:
    """Resolve a row's pdf_local_path (which may list several "; "-joined paths) to a
    real file inside the pdfs folder. Tries the stored path first, falls back to the
    basename inside pdf_dir, and finally fetches from S3 if still not found."""
    for raw in str(path_field).split(";"):
        raw = raw.strip().strip('"')
        if not raw:
            continue
        basename = os.path.basename(raw.replace("\\", "/"))
        for cand in (raw, os.path.join(pdf_dir, basename)):
            if cand and os.path.exists(cand):
                return cand
        # Fall back to S3
        if basename:
            local = _s3.fetch_pdf(basename)
            if local:
                return local
    return ""


def extract_pdf_text(path: str, max_chars: int = 6000) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return text[:max_chars]
    except Exception:
        return ""
