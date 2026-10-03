"""Pipeline orchestration: INPUT -> ENRICH -> VERIFY -> STRUCTURE -> SCORE -> REVIEW (+ ROUTE)."""
from __future__ import annotations

import concurrent.futures
import contextvars
import functools
import logging

import pandas as pd
from opentelemetry import trace

from . import web
from . import llm as llm_mod
from .llm import LLMClient
from .data import load_glassdollar, find_startup, web_profile_row, load_siemens_tools
from .enrich import enrich
from .verify import verify_facts
from .summarize import summarize_offering
from .fit import match_siemens_tools
from .trend import analyze_trend
from .text import format_funding
from .profile import research_profile

log = logging.getLogger(__name__)

# Spans are no-ops until api/telemetry.py installs an SDK, so scripts and tests are unaffected.
# Each branch runs inside its own current span so the searches and completions it makes nest
# under it: the question a trace answers is which branch the 118 seconds went to.
_tracer = trace.get_tracer(__name__)


def _traced(span_name: str, fn):
    # The span name doubles as the stage a failed model call is charged to (result["degraded"]).
    stage = span_name.removeprefix("pipeline.")

    @functools.wraps(fn)
    def run(*a, **kw):
        token = llm_mod.set_stage(stage)
        try:
            with _tracer.start_as_current_span(span_name):
                return fn(*a, **kw)
        finally:
            llm_mod.reset_stage(token)
    return run


def _submit(ex, span_name: str, fn, *a):
    # copy_context(): pool threads start with an EMPTY context, which would drop both the
    # cache-bypass ContextVar and the current span.
    return ex.submit(contextvars.copy_context().run, _traced(span_name, fn), *a)

# Headline fields the DB leaves blank but web research can establish, mapped to their key in
# the researched deep profile.
#
# The three URL rows are not cosmetic. A web-sourced row carries linkedin_url="" by construction
# (core/data.py never fills it), the non-empty filter below then drops the key entirely, and the
# profile header rendered a blank LinkedIn line for every company outside GlassDollar even though
# the URL was sitting in the search results the run had already fetched.
_BACKFILL_FIELDS = (("founded_year", "founded_year"), ("funding", "funding"),
                    ("employees_count", "employees"), ("website", "website"),
                    ("hq", "hq"),
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
            # hq and the two profile URLs fall back to model knowledge when neither the database
            # nor the web had them, and the UI must not label that "web-sourced"
            # (profile.py's _recall_hq_offline / _recall_links_offline).
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


@_tracer.start_as_current_span("evaluate")
def evaluate(name: str, glassdollar_path: str, tools_path: str, do_web: bool = True,
             df: "pd.DataFrame" = None, on_step=None, use_web_cache: bool = True,
             on_partial=None, tracxn=None, department: dict | None = None) -> dict:
    """Run the full pipeline for one startup.

    ``department`` ({id, label, interests, demo}) scores Siemens Fit as the three pillar
    assessments for that department and routes from them (core/assessment.py). Without one the
    run is the engine's department-less evaluation, as scripts and older tests use it.

    ``use_web_cache=False`` forces every search and site fetch to hit the network. A forced
    re-evaluation must not replay cached results, or "Re-evaluate" would hand back the same
    week-old evidence it was asked to refresh.

    ``on_partial(section, data)`` is called as each part of the result becomes available, so a
    caller can show the profile while scoring is still running. The return value is unchanged and
    still complete — the callback is an addition, never a replacement.
    """
    span = trace.get_current_span()
    span.set_attribute("startup.query", name)
    span.set_attribute("startup.department", str((department or {}).get("id", "")))
    span.set_attribute("web_cache.enabled", use_web_cache)
    token = web.set_cache_enabled(use_web_cache)
    collecting, failures = llm_mod.collect_failures()
    try:
        return _with_degraded(_evaluate(name, glassdollar_path, tools_path, do_web, df, on_step,
                                        on_partial, tracxn, department), failures)
    finally:
        llm_mod.stop_collecting(collecting)
        web.reset_cache_enabled(token)


def _with_degraded(result: dict, failures: list) -> dict:
    """Name every stage whose model call failed for good, so a fallback is never silent.

    Absent when nothing failed. A run with no model configured at all is not "degraded" — it never
    calls the model, records nothing here, and its engine already reads offline-fallback.
    """
    if failures and result.get("found", True):
        result["degraded"] = llm_mod.summarize_failures(failures)
    return result


def _evaluate(name: str, glassdollar_path: str, tools_path: str, do_web: bool = True,
              df: "pd.DataFrame" = None, on_step=None, on_partial=None, tracxn=None,
              department: dict | None = None) -> dict:
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
    provider_row = None
    provider_status = "not_connected"
    if tracxn is not None:
        try:
            provider_row = tracxn.company_row(name)
            provider_status = "used" if provider_row is not None else "no_exact_match"
        except Exception:
            provider_status = "unavailable"
    if provider_row is not None:
        df = pd.DataFrame([provider_row])
    if df is None:
        # API mode: the database is huge, so search for just this name instead of loading all.
        from . import glassdollar_api
        try:
            df = glassdollar_api.search_as_df(name)
        except glassdollar_api.GlassDollarError:
            df = pd.DataFrame()   # search unavailable -> treat as a DB miss and fall back to web
    llm = LLMClient()
    row = provider_row if provider_row is not None else find_startup(df, name)
    source = "tracxn" if provider_row is not None else "glassdollar"
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
    trace.get_current_span().set_attribute("startup.source", source)
    # The company is resolved and nothing else is known yet. Emitting here is what lets the page
    # put up a header with the real name instead of whatever the reviewer typed.
    _emit("identity", {"company": str(row.get("company_name", "")) or name, "source": source})

    tools = load_siemens_tools(tools_path)
    _step("ENRICH", "running")
    enrichment = _traced("pipeline.enrich", enrich)(row, do_web=do_web)
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
        def _spawn(section, fn, *a):
            return _submit(ex, f"pipeline.{section}", fn, *a)

        jobs = {
            "verification": _spawn("verification", verify_facts, row, enrichment, llm),
            "summary": _spawn("summary", summarize_offering, row, enrichment["pitch_pdf"], llm),
            "fit": _spawn("fit", match_siemens_tools, row, enrichment["pitch_pdf"], tools, llm),
            # deep structured profile: founders / advisors / programs / parent group / commercial
            "profile": _spawn("profile", research_profile, row, llm, do_web, enrichment.get("site"),
                              enrichment.get("web")),
            # trend uses niche keywords derived inside analyze_trend (stage 1); we pass an empty
            # list here and it derives its own terms. Kicked off early so it runs in parallel.
            "trend": _spawn("trend", analyze_trend, row, "", [], llm, do_web),
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
    # The traction rubric needs no model, so it is ready the moment the branches join — well
    # before the scoring completion returns — and goes to the page on its own. The raw database
    # values ride along in the result: the header profile only keeps funding after
    # format_funding has rounded it, and "€2.0M" can be €1.96M, one band lower.
    from .traction import score_traction, gather_traction_inputs, apply_traction
    traction_inputs = {"origin": {"glassdollar": "GlassDollar", "tracxn": "Tracxn"}.get(source, "application"),
                       **{k: _cell(row.get(k, "")) for k in
                          ("funding", "employees_count", "employee_band", "customers")}}
    traction = score_traction(gather_traction_inputs({
        "company": str(row.get("company_name", "")) or name, "traction_inputs": traction_inputs,
        "profile": profile, "profile_sources": profile_sources, "deep_profile": deep_profile,
        "verification": verification}))
    _emit("traction", traction)
    _step("SCORE", "running")
    from .judgment import score_research, decision_research
    research = {"company": name, "application": row.to_dict(), "profile": profile,
                         "deep_profile": deep_profile, "summary": summary, "fit": fit,
                         "facts": [f.as_dict() for f in enrichment["facts"]],
                         "verification": verification, "trend": trend}
    # The model score, Team & Ecosystem and the three pillars read the same finished research and
    # nothing else, so they run side by side; each is emitted as it lands, which is what lets the
    # page show the component scores while Siemens Fit and the total are still pending.
    team = pillar_result = market = None
    if department:
        from .team_ecosystem import assess_team
        from .pillar_match import assess_pillars
        from .market import assess_market
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            f_score = _submit(ex, "pipeline.score", score_research, research, llm)
            f_team = _submit(ex, "pipeline.team_ecosystem", assess_team, research, llm)
            f_market = _submit(ex, "pipeline.market", assess_market, research, llm)
            f_pill = _submit(ex, "pipeline.pillars", assess_pillars,
                             {**research, "company": str(row.get("company_name", "")) or name},
                             department, llm, do_web)
            sc = apply_traction(f_score.result(), traction)
            _step("SCORE", "done")
            _emit("score", sc)
            team = f_team.result()
            _emit("team_ecosystem", team)
            market = f_market.result()
            _emit("market", market)
            pillar_result = f_pill.result()
    else:
        sc = apply_traction(score_research(research, llm), traction)
        _step("SCORE", "done")
        _emit("score", sc)
    _step("ROUTE", "running")
    from .route import _portfolio_stance
    from .programs import assess_sfs
    sfs = assess_sfs(row, deep_profile, fit)
    rt = {"portfolio_stance": _portfolio_stance(fit), "sfs_relevant": bool(sfs.get("relevant")),
          **{f"sfs_{k}": sfs.get(k) for k in ("status", "line", "lines", "blockers", "rationale")}}
    if not department:
        rt.update(decision_research(research, llm))
    _step("ROUTE", "done")

    # The provider and model that actually ran. This used to be "openai:" + LLM_MODEL whichever
    # key was set, so every Gemini run was recorded as openai:gpt-5.4.
    engine = f"{llm.provider}:{llm.model}" if llm.available else "offline-fallback"
    if source == "web":
        engine += " · web-sourced"
    stats = enrichment.get("search_stats") or {}
    if stats.get("timed_out"):
        # Surface partial coverage instead of letting it look like a complete run.
        engine += f" · {stats['timed_out']}/{stats.get('requested', 0)} web queries timed out"

    result = {
        "found": True,
        "source": source,
        "engine": engine,
        "provider_status": {"tracxn": provider_status},
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
        "traction": traction,
        "traction_inputs": traction_inputs,
    }
    if department:
        from .assessment import build
        result = build(result, department, pillar_result, team, market)
        _emit("assessment", result["assessment"])
        # Again, because the headline now carries the weighted total: a partial that later
        # disagrees with the stored result is worse than no partial.
        _emit("score", result["score"])
    _emit("routing", result["routing"])
    return result


@_tracer.start_as_current_span("assess_department")
def assess_department(result: dict, department: dict, llm: "LLMClient | None" = None,
                      do_web: bool = True) -> dict:
    """A new department run from an existing one's research — no enrichment, no profile search.

    Siemens Fit is the only department-specific part of an evaluation. Team & Ecosystem is reused
    when the source run already holds a current one; the startup research itself is not redone.
    """
    llm = llm or LLMClient()
    collecting, failures = llm_mod.collect_failures()
    try:
        return _with_degraded(_assess_department(result, department, llm, do_web), failures)
    finally:
        llm_mod.stop_collecting(collecting)


def _assess_department(result: dict, department: dict, llm, do_web: bool) -> dict:
    from .assessment import build
    from .pillar_match import assess_pillars
    from .team_ecosystem import assess_team, VERSION as TEAM_VERSION
    from .market import assess_market, VERSION as MARKET_VERSION
    base = {k: v for k, v in result.items()
            if k not in ("assessment", "department", "run_id", "run_created_at", "cached",
                         "freshness", "private", "department_assessments", "original_score")}
    from .judgment import score_research, VERSION as JUDGMENT_VERSION
    from .traction import apply_traction, with_traction
    base = with_traction(base)
    prior = (result.get("assessment") or {}).get("team_ecosystem") or {}
    old_score = base.get("score") or {}
    # The market component comes from the model score. A source run stored before that score
    # existed (or whose scoring failed) has no market number, and reusing it would leave this
    # department's total pending for a reason that has nothing to do with the department.
    rescore = not (old_score.get("version") == JUDGMENT_VERSION and old_score.get("status") == "assessed")
    reuse_team = prior.get("status") == "assessed" and prior.get("version") == TEAM_VERSION
    prior_market = result.get("market") or {}
    reuse_market = prior_market.get("status") == "assessed" and prior_market.get("version") == MARKET_VERSION
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_pill = _submit(ex, "pipeline.pillars", assess_pillars, base, department, llm, do_web)
        f_team = None if reuse_team else _submit(ex, "pipeline.team_ecosystem", assess_team, base, llm)
        f_score = _submit(ex, "pipeline.score", score_research, base, llm) if rescore else None
        f_market = None if reuse_market else _submit(ex, "pipeline.market", assess_market, base, llm)
        market = f_market.result() if f_market else prior_market
        team = f_team.result() if f_team else prior
        if f_score:
            base["score"] = apply_traction(f_score.result(), base.get("traction"))
        pillars = f_pill.result()
    return build(base, department, pillars, team, market)
