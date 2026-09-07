"""Pipeline orchestration: INPUT -> ENRICH -> VERIFY -> STRUCTURE -> SCORE -> REVIEW (+ ROUTE)."""
from __future__ import annotations

import concurrent.futures
import contextvars
import functools

import pandas as pd

from . import web
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
from .text import format_funding
from .profile import research_profile


# Headline fields the DB leaves blank but web research can establish, mapped to their key in
# the researched deep profile.
#
# The three URL rows are not cosmetic. A web-sourced row carries linkedin_url="" by construction
# (core/data.py never fills it), the non-empty filter below then drops the key entirely, and the
# profile header rendered a blank LinkedIn line for every company outside GlassDollar even though
# the URL was sitting in the search results the run had already fetched.
_BACKFILL_FIELDS = (("founded_year", "founded_year"), ("funding", "funding"),
                    ("employees_count", "employees"), ("website", "website"),
                    ("linkedin_url", "linkedin_url"), ("crunchbase_url", "crunchbase_url"))


def _cell(value) -> str:
    """Stringify a spreadsheet cell without pandas' float artefacts.

    A column holding any blank is read as float64, so every value in it stringifies with a
    trailing ".0": an 8-person company displayed "8.0", a year "2024.0", a funding amount
    "2831100.0". Only whole floats are narrowed — a genuine 2.5 keeps its fraction — and NaN
    becomes the empty string the rest of the pipeline already treats as "no value".
    """
    if value is None:
        return ""
    if isinstance(value, float):        # numpy.float64 subclasses float; numpy.int64 does not
        if value != value:              # NaN
            return ""
        if value.is_integer():
            return str(int(value))
    return str(value)


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
            # `{pkey}_origin` overrides "web" where the field can arrive by more than one route:
            # hq falls back to model knowledge when neither the database nor the web had it, and
            # the UI must not label that "web-sourced" (profile.py's _recall_hq_offline).
            origin = str(deep_profile.get(f"{pkey}_origin", "")).strip() or "web"
            sources[col] = {"origin": origin,
                            "url": str(deep_profile.get(f"{pkey}_source", "")).strip()}
    return sources


_PROFILE_COLS = ("company_name", "website", "hq", "founded_year", "employee_band",
                 "employees_count", "funding", "linkedin_url", "crunchbase_url",
                 "customers", "Reference customers",
                 "Business model", "Development stage of your solution")


def _header_profile(row: "pd.Series", deep_profile: dict, source: str) -> tuple[dict, dict]:
    """The profile shown at the top of the page, plus where each backfilled field came from.

    Pulled out of the end of the run so it can be built the moment the researched profile lands:
    it reads only the row and that profile, and nothing downstream touches it. That is what lets a
    reviewer start reading a company while its score is still being computed.
    """
    if source == "glassdollar":
        # row.index, not df.columns: a row resolved by domain never came out of `df` at all,
        # and reading the column list off the search frame would leave its profile empty.
        profile = {c: _cell(row.get(c, "")) for c in _PROFILE_COLS if c in row.index}
    else:                       # web row: keep only the fields we actually populated
        profile = {c: _cell(row.get(c, "")) for c in _PROFILE_COLS
                   if _cell(row.get(c, "")).strip()}
    profile_sources = backfill_profile(profile, deep_profile)
    # After the backfill, not before: a blank funding column gets filled from web research
    # here, and that value needs the same treatment. Free text passes through untouched.
    profile["funding"] = format_funding(profile.get("funding", ""))
    return profile, profile_sources


def _looks_like_domain(value: str) -> bool:
    """A single dotted token with no spaces — "phena.tech", "https://phena.tech/about"."""
    s = str(value or "").strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    s = s.split("/", 1)[0]
    return bool(s) and " " not in s and "." in s and not s.endswith(".")


def _by_domain(name: str):
    """GlassDollar's by-domain lookup, or None. Best-effort: no key, no network, no match and
    an unparseable input all mean "fall through to the next resolution step"."""
    if not _looks_like_domain(name):
        return None
    s = str(name).strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    s = s.split("/", 1)[0]
    if s.lower().startswith("www."):
        s = s[4:]
    try:
        from . import glassdollar_api
        company = glassdollar_api.get_client().get_company_by_domain(s)
        return glassdollar_api.company_to_row(company) if company else None
    except Exception:
        return None


def evaluate(name: str, glassdollar_path: str, tools_path: str, do_web: bool = True,
             df: "pd.DataFrame" = None, on_step=None, use_web_cache: bool = True,
             on_partial=None) -> dict:
    """Run the full pipeline for one startup.

    ``use_web_cache=False`` forces every search and site fetch to hit the network. A forced
    re-evaluation must not replay cached results, or "Re-evaluate" would hand back the same
    week-old evidence it was asked to refresh.

    ``on_partial(section, data)`` is called as each part of the result becomes available, so a
    caller can show the profile while scoring is still running. The return value is unchanged and
    still complete — the callback is an addition, never a replacement.
    """
    token = web.set_cache_enabled(use_web_cache)
    try:
        return _evaluate(name, glassdollar_path, tools_path, do_web, df, on_step, on_partial)
    finally:
        web.reset_cache_enabled(token)


def _evaluate(name: str, glassdollar_path: str, tools_path: str, do_web: bool = True,
              df: "pd.DataFrame" = None, on_step=None, on_partial=None) -> dict:
    # Optional progress callback: on_step(step_label, status) where status is one of
    # "running" | "done" | "error". Reporting must never break the evaluation itself.
    def _step(label: str, status: str = "running") -> None:
        if on_step is None:
            return
        try:
            on_step(label, status)
        except Exception:
            pass

    # Same contract for partial results: a consumer that throws, or a client that has hung up,
    # must not take the evaluation down with it. The run finishes and is still saved.
    def _emit(section: str, data) -> None:
        if on_partial is None:
            return
        try:
            on_partial(section, data)
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
    hydrated = False
    if row is None:
        # A domain is a stronger identity than a fuzzy name match at 0.82: "phena.tech"
        # resolves to exactly one company, while "Phena" competes with FENA Holdings and
        # Phenna Group. Tried before falling through to the web, so a reviewer who pastes a
        # URL still gets the database record rather than a scraped reconstruction of it.
        row = _by_domain(name)
        hydrated = row is not None     # by-domain returns the full company, not a search hit
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
        gd_id = "" if hydrated else str(row.get("glassdollar_id", "")).strip()
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
    # The company is resolved and nothing else is known yet. Emitting here is what lets the page
    # put up a header with the real name instead of whatever the reviewer typed.
    _emit("identity", {"company": str(row.get("company_name", "")) or name, "source": source})

    tools = load_siemens_tools(tools_path)
    _step("ENRICH", "running")
    enrichment = enrich(row, do_web=do_web)
    _step("ENRICH", "done")
    # The profile as the ROW already knows it — name, site, HQ, founded year, funding, stage —
    # before any research runs. Emitted because the deep-profile branch is the slowest thing in
    # the pipeline by a wide margin: measured on a real run it returned at 112s of 118s, so a page
    # that waits for it waits for essentially the whole evaluation and the progressive render buys
    # nothing. This is safe to show early precisely because `backfill_profile` only ever fills
    # BLANK fields — the richer version that replaces it adds values, it never changes one.
    _emit("profile", dict(zip(("profile", "profile_sources", "deep_profile"),
                              (*_header_profile(row, {}, source), {}))))

    # verify / summarize / fit / trend are independent LLM steps — run them concurrently.
    _step("VERIFY", "running")
    _step("STRUCTURE", "running")
    _step("REVIEW", "running")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        # Pool threads start with an EMPTY context, so anything submitted plainly here loses
        # the cache-bypass ContextVar set by evaluate() and falls back to its default (True):
        # a forced refresh would keep replaying cached searches and completions for the whole
        # of the profile / trend research, which is most of the run.
        def _spawn(fn, *a):
            return ex.submit(contextvars.copy_context().run, functools.partial(fn, *a))

        jobs = {
            "verification": _spawn(verify_facts, row, enrichment, llm),
            "summary": _spawn(summarize_offering, row, enrichment["pitch_pdf"], llm),
            "fit": _spawn(match_siemens_tools, row, enrichment["pitch_pdf"], tools, llm),
            # deep structured profile: founders / advisors / programs / parent group / commercial
            "profile": _spawn(research_profile, row, llm, do_web, enrichment.get("site"),
                              enrichment.get("web")),
            # trend uses niche keywords derived inside analyze_trend (stage 1); we pass an empty
            # list here and it derives its own terms. Kicked off early so it runs in parallel.
            "trend": _spawn(analyze_trend, row, "", [], llm, do_web),
        }
        # Collected as they land rather than in a fixed order. The five branches differ by tens of
        # seconds — the profile chain alone runs four recall nets — and awaiting them in a written
        # order meant a summary that finished in three seconds sat unread until the slowest branch
        # returned. `.result()` still raises here exactly as it did, so a failing branch fails the
        # run the same way.
        done: dict = {}
        pending = {fut: section for section, fut in jobs.items()}
        for fut in concurrent.futures.as_completed(pending):
            section = pending[fut]
            done[section] = fut.result()
            if section == "verification":
                _step("VERIFY", "done")
            elif section == "fit":
                _step("STRUCTURE", "done")
            if section == "profile":
                # The header profile depends only on the row and the researched profile — nothing
                # downstream mutates it — so it is assembled here rather than after routing, which
                # is what lets the page render a company while its score is still being computed.
                deep_profile = done["profile"]["profile"]
                profile, profile_sources = _header_profile(row, deep_profile, source)
                _emit("profile", {"profile": profile, "profile_sources": profile_sources,
                                  "deep_profile": deep_profile})
            else:
                _emit(section, done[section])
        _step("REVIEW", "done")

    verification, summary = done["verification"], done["summary"]
    fit, trend, prof_res = done["fit"], done["trend"], done["profile"]
    deep_profile = prof_res["profile"]
    enrichment["facts"].extend(prof_res["facts"])
    _emit("facts", [f.as_dict() for f in enrichment["facts"]])
    _step("SCORE", "running")
    sc = score_startup(row, enrichment, verification, fit, deep_profile, trend)
    _step("SCORE", "done")
    _emit("score", sc)
    _step("ROUTE", "running")
    rt = route(sc, fit, row, llm, deep_profile, trend)
    _step("ROUTE", "done")
    _emit("routing", rt)

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
