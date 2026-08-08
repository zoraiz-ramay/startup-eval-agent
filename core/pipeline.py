"""Pipeline orchestration: INPUT -> ENRICH -> VERIFY -> STRUCTURE -> SCORE -> REVIEW (+ ROUTE)."""
from __future__ import annotations

import concurrent.futures

import pandas as pd

from .config import LLM_MODEL
from .llm import LLMClient
from .data import load_glassdollar, find_startup, web_profile_row, load_siemens_tools
from .enrich import enrich
from .verify import verify_facts
from .summarize import summarize_offering
from .fit import match_siemens_tools
from .trend import analyze_trend
from .score import score_startup
from .route import route
from .profile import research_profile


# Headline fields the DB leaves blank but web research can establish, mapped to their key in
# the researched deep profile.
_BACKFILL_FIELDS = (("founded_year", "founded_year"), ("funding", "funding"),
                    ("employees_count", "employees"))


def backfill_profile(profile: dict, deep_profile: dict) -> dict:
    """Fill BLANK profile fields from web research, in place; return the provenance map.

    GlassDollar's export frequently omits founded_year, funding and headcount, and the
    researched values otherwise exist only as evidence Facts — visible in the Evidence tab but
    never in the profile header, so the UI showed "—" for facts the run had actually
    established. Only blank fields are filled: wherever the DB has a value it stays
    authoritative. Every filled field is recorded in the returned ``profile_sources`` so the UI
    can mark it web-sourced rather than passing it off as application data.
    """
    sources: dict = {}
    for col, pkey in _BACKFILL_FIELDS:
        if str(profile.get(col, "")).strip():
            continue
        val = str(deep_profile.get(pkey, "")).strip()
        if val:
            profile[col] = val
            # Not every researched field carries a source URL (headcount has no *_source key),
            # so the origin is recorded even when the URL is unknown.
            sources[col] = {"origin": "web",
                            "url": str(deep_profile.get(f"{pkey}_source", "")).strip()}
    return sources


def evaluate(name: str, glassdollar_path: str, tools_path: str, do_web: bool = True,
             df: "pd.DataFrame" = None, on_step=None) -> dict:
    # Optional progress callback: on_step(step_label, status) where status is one of
    # "running" | "done" | "error". Reporting must never break the evaluation itself.
    def _step(label: str, status: str = "running") -> None:
        if on_step is None:
            return
        try:
            on_step(label, status)
        except Exception:
            pass

    _step("INPUT", "running")
    if df is None:
        # API mode: the database is huge, so search for just this name instead of loading all.
        from . import glassdollar_api
        try:
            df = glassdollar_api.search_as_df(name)
        except glassdollar_api.GlassDollarError:
            df = pd.DataFrame()   # search unavailable -> treat as a DB miss and fall back to web
    llm = LLMClient()
    row = find_startup(df, name)
    source = "glassdollar"
    if row is None:
        # Not confidently in the GlassDollar database -> research it live on the web.
        row = web_profile_row(name, llm=llm)
        source = "web"
        if row is None:
            _step("INPUT", "error")
            return {"found": False, "query": name, "source": "none",
                    "available": sorted(df.get("company_name", pd.Series(dtype=str)).astype(str).tolist())}
        do_web = True            # web-sourced startup must be enriched/verified online
    else:
        # The paginated /v1/companies list can return lighter objects than /v1/companies/{id}.
        # If this row came from the API, hydrate the full profile (referenced_customers,
        # long_description, ...) once so downstream steps see complete data. Best-effort only.
        gd_id = str(row.get("glassdollar_id", "")).strip()
        if gd_id and gd_id.lower() != "nan":
            try:
                from . import glassdollar_api
                full = glassdollar_api.get_company_row(int(float(gd_id)))
                if full is not None:
                    # keep any existing non-empty values, fill the rest from the detailed row
                    merged = full.to_dict()
                    for k, v in row.to_dict().items():
                        if str(v).strip() and not str(merged.get(k, "")).strip():
                            merged[k] = v
                    row = pd.Series(merged)
            except Exception:
                pass
    _step("INPUT", "done")

    tools = load_siemens_tools(tools_path)
    _step("ENRICH", "running")
    enrichment = enrich(row, do_web=do_web)
    _step("ENRICH", "done")

    # verify / summarize / fit / trend are independent LLM steps — run them concurrently.
    _step("VERIFY", "running")
    _step("STRUCTURE", "running")
    _step("REVIEW", "running")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        f_ver   = ex.submit(verify_facts, row, enrichment, llm)
        f_sum   = ex.submit(summarize_offering, row, enrichment["pitch_pdf"], llm)
        f_fit   = ex.submit(match_siemens_tools, row, enrichment["pitch_pdf"], tools, llm)
        # deep structured profile: founders / advisors / programs / parent group / SFS relevance
        f_prof  = ex.submit(research_profile, row, llm, do_web, enrichment.get("site"))
        # trend uses niche keywords derived inside analyze_trend (stage 1); we pass an empty
        # list here and it derives its own terms. We kick it off early so it runs in parallel.
        f_trend = ex.submit(analyze_trend, row, "", [], llm, do_web)
        verification = f_ver.result()
        _step("VERIFY", "done")
        summary      = f_sum.result()
        fit          = f_fit.result()
        _step("STRUCTURE", "done")
        prof_res     = f_prof.result()
        trend        = f_trend.result()
        _step("REVIEW", "done")
    deep_profile = prof_res["profile"]
    enrichment["facts"].extend(prof_res["facts"])
    _step("SCORE", "running")
    sc = score_startup(row, enrichment, verification, fit, deep_profile)
    _step("SCORE", "done")
    _step("ROUTE", "running")
    rt = route(sc, fit, row, llm, deep_profile)
    _step("ROUTE", "done")

    profile_cols = ("company_name", "website", "hq", "founded_year", "employee_band",
                    "employees_count", "funding", "linkedin_url", "crunchbase_url",
                    "customers", "Reference customers",
                    "Business model", "Development stage of your solution")
    if source == "glassdollar":
        profile = {c: str(row.get(c, "")) for c in profile_cols if c in df.columns}
    else:                       # web row: keep only the fields we actually populated
        profile = {c: str(row.get(c, "")) for c in profile_cols if str(row.get(c, "")).strip()}

    profile_sources = backfill_profile(profile, deep_profile)

    engine = "openai:" + LLM_MODEL if llm.available else "offline-fallback"
    if source == "web":
        engine += " · web-sourced"
    stats = enrichment.get("search_stats") or {}
    if stats.get("timed_out"):
        # Surface partial coverage instead of letting it look like a complete run.
        engine += f" · {stats['timed_out']}/{stats.get('requested', 0)} web queries timed out"

    return {
        "found": True,
        "source": source,
        "engine": engine,
        "company": str(row.get("company_name", "")) or name,
        "profile": profile,
        "profile_sources": profile_sources,
        "summary": summary,
        "facts": [f.as_dict() for f in enrichment["facts"]],
        "verification": verification,
        "fit": fit,
        "score": sc,
        "routing": rt,
        "trend": trend,
        "deep_profile": deep_profile,
    }
