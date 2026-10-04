"""FastAPI backend for the Siemens Startup Evaluation Agent.

Wraps the existing core pipeline (evaluate / solve / search) behind a REST API so a
proper frontend (React, Tracxn-style) can drive it. Run history persists in SQLite.

Run locally:   uvicorn api.main:app --reload --port 8000
In Docker:     see docker-compose.yml (service `api`)
"""
from __future__ import annotations

import logging
import os
import sys
import pathlib

# Ensure the project root is importable when launched as `uvicorn api.main:app`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from typing import Literal

from pydantic import BaseModel, Field

import glob

import pandas as pd

import core
from core.solve import solve_problem, load_challenges, set_challenge_status
from core.chat import run_brief
from core import s3 as _s3
from api import store
from api.auth import Principal, current_user, require_admin, settings as auth_settings
from api.auth import admin_upns as auth_admin_upns, db_admin_upns as auth_db_admin_upns
from api.auth import router as auth_router
from api.security import SecurityMiddleware
from api.telemetry import setup_telemetry
from api import flight
from api.routes_evidence import router as evidence_router

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- local applications file
# The local Siemens applications Excel (pitch-form rows + pdfs/ of decks) is searched
# ONLY in problem mode (/api/solve) — "which of our applicants could solve this problem?".
# General name search and evaluation stay on the GlassDollar API.
# Set GLASSDOLLAR_XLSX or drop the file in DATA_DIR.
def _find_local_xlsx() -> str:
    cand = os.getenv("GLASSDOLLAR_XLSX", "").strip()
    if cand and os.path.exists(cand):
        return cand
    if os.path.exists(core.DEFAULT_GLASSDOLLAR):
        return core.DEFAULT_GLASSDOLLAR
    hits = sorted(glob.glob(os.path.join(str(core.BASE_DIR), "*.xlsx")))
    if hits:
        return hits[0]
    # Fall back to S3
    import tempfile
    local = os.path.join(tempfile.gettempdir(), "glassdollar_applications.xlsx")
    fetched = _s3.fetch_data_file("data/glassdollar_applications.xlsx", local)
    return fetched


_LOCAL_XLSX = _find_local_xlsx()
_local_df: "pd.DataFrame | None" = None

# One-time, idempotent: populate the normalized entity tables from any runs saved
# before the schema existed.
try:
    store.backfill_entities()
    store.backfill_assessment_records()
except Exception:
    pass

# Give the engine its result cache. Injected rather than imported by core/ so nothing in core/
# depends on api/ and the engine still runs (uncached) from tests, scripts.
# A shared per-minute budget for model requests, set to the provider's quota. Off unless LLM_RPM
# is set: the right number depends on the gateway or Gemini tier, and a guessed one either throttles
# for nothing or protects nothing.
if int(os.getenv("LLM_RPM", "0") or 0) > 0:
    core.llm.install_rate_limiter(flight.llm_gate(int(os.environ["LLM_RPM"])))

try:
    core.web.install_cache(store.cache_get, store.cache_put, store.cache_get_entry)
    store.cache_purge_expired()
except Exception:
    pass


def _get_local_df() -> "pd.DataFrame | None":
    global _local_df
    if not _LOCAL_XLSX:
        return None
    if _local_df is None:
        df = pd.read_excel(_LOCAL_XLSX).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        _local_df = df
    return _local_df

# Docs can be disabled in production deployments with API_DOCS=0.
_docs = os.getenv("API_DOCS", "1") == "1"
app = FastAPI(title="Siemens Startup Evaluation Agent API", version="0.2.0",
              docs_url="/docs" if _docs else None, redoc_url=None,
              openapi_url="/openapi.json" if _docs else None)

# Order matters: CORS outermost, then security headers/auth/rate-limit.
# CORS is locked to explicit origins (no wildcard) — the React dev server and the
# containerized UI. Override with CORS_ORIGINS (comma-separated).
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()]
app.add_middleware(SecurityMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"])
setup_telemetry(app)

# Build and validate auth config here rather than at import of api.auth: this runs after
# `import core` has loaded .env, and it is where a missing client secret should stop the
# process — not on the first sign-in attempt.
auth_settings()


def _log_admin_count() -> None:
    """Say how many admins exist, because the alternative is discovering it via a 403.

    Counts only — never the addresses. They are personal data, and this log is shipped to
    wherever the platform collects container output.

    A deployment with zero admins is a working app that nobody can administer, and the
    fail-closed default means that is exactly what you get until ADMIN_UPNS is set. Warn
    loudly rather than let it look like a permissions bug weeks later.
    """
    try:
        seeded = len(auth_admin_upns())
        granted = len(auth_db_admin_upns() - auth_admin_upns())
    except Exception:
        log.warning("[admin] could not determine the admin list at startup", exc_info=True)
        return
    if seeded + granted == 0:
        log.warning("[admin] NOBODY is an administrator: ADMIN_UPNS is unset and no in-app "
                    "grants exist. /admin will 403 for every user, including you.")
    else:
        log.info("[admin] %d seeded admin(s) from ADMIN_UPNS, %d granted in-app", seeded, granted)


_log_admin_count()

# Registered before the SPA catch-all at the bottom of this file, which would otherwise
# swallow /api/auth/* and serve index.html instead.
app.include_router(auth_router)
app.include_router(evidence_router)
from api.tracxn import router as tracxn_router, client_for as tracxn_client_for
app.include_router(tracxn_router)
from api.jobs import router as jobs_router
from api import workspace
app.include_router(jobs_router)
from api.interests import router as interests_router
app.include_router(interests_router)
from api.assessments import router as assessments_router
app.include_router(assessments_router)


class EvaluateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Startup name to evaluate")
    do_web: bool = True
    save: bool = True
    refresh: bool = Field(False, description="Force a fresh evaluation, bypassing the cache")
    # Accepted from older clients and ignored: every evaluation is assessed for all departments
    # and recommends the best one for Collaborate.
    department_id: str | None = Field(None, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")


class SolveBody(BaseModel):
    problem: str = Field(..., min_length=3, max_length=2000,
                         description="Problem statement to find solver startups for")
    do_web: bool = True


class AskTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(..., max_length=4000)


class AskBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    run_id: int | None = Field(None, description="Ground the answer in this evaluated run")
    # Earlier turns of this chat, so a follow-up keeps its subject. Bounded: the server keeps no
    # conversation state, and an unbounded history would be an unbounded prompt.
    history: list[AskTurn] = Field(default_factory=list, max_length=12)


# Neither of the two bodies below carries a `reviewer` any more: it is taken from the
# session. Pydantic ignores unknown fields by default, so a stale client still sending one
# is silently disregarded rather than rejected — which is exactly right, since the whole
# point is that a client cannot choose who gets credited. Do not add extra="forbid" here;
# that would turn a harmless old browser tab into a hard 422.
class OverrideBody(BaseModel):
    new_pillar: str = Field(..., pattern="^(Connect|Collaborate|Empower|Pass)$")
    reason: str = Field(..., min_length=5, max_length=1000)
    evidence_note: str = Field("", max_length=2000)


class ChallengeStatusBody(BaseModel):
    status: str = Field(..., pattern="^(pending|approved|rejected)$")


class SavedViewBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    columns: list[str] = Field(default_factory=list, max_length=40)
    filters: dict = Field(default_factory=dict)


def _gd_key() -> bool:
    return bool(core.GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", ""))


@app.get("/health")
def health() -> dict:
    """Liveness only, and deliberately empty of detail.

    This endpoint is unauthenticated because the Docker healthcheck and the load balancer
    both need it, which also means it is reachable from outside. It used to report the S3
    bucket name, the LLM provider and model, and which API keys were configured — a free
    reconnaissance summary for anyone who found the hostname. The diagnostics moved to
    /api/status, behind the session guard.
    """
    return {"status": "ok"}


@app.get("/api/status")
def status(user: Principal = Depends(current_user)) -> dict:
    """What /health used to say, for signed-in reviewers.

    The S3 bucket name is not repeated here: it is a target rather than something a
    reviewer can act on, and Settings never displayed it.
    """
    _llm = core.LLMClient()
    return {"status": "ok",
            "llm": _llm.available,
            "llm_provider": _llm.provider,
            "llm_model": _llm.model if _llm.available else "",
            "glassdollar_key": bool(core.GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")),
            "data_source": "glassdollar_api",
            "applications_file": os.path.basename(_LOCAL_XLSX) if _LOCAL_XLSX else "",
            "applications_count": int(len(_get_local_df())) if _LOCAL_XLSX else 0,
            "s3_available": _s3._available()}


@app.get("/api/search")
def search(q: str, limit: int = 10) -> dict:
    """Name search — GlassDollar API first, then the local applications xlsx.

    GlassDollar leads because it is the live, curated record: it spans far more companies
    than the 429-row export and its fields are the ones the pipeline would otherwise
    reconstruct from DuckDuckGo. The xlsx stays as the second source rather than being
    dropped — it carries pitch-form answers (business model, development stage, the Siemens
    function selections, the deck) that the API does not expose — and it is the only source
    at all when no key is configured."""
    q, limit = q[:200], max(1, min(limit, 25))
    if not q.strip():
        return {"results": []}

    results: list = []
    seen_names: set = set()

    if _gd_key():
        try:
            df = core.search_glassdollar(q.strip(), limit=limit)
            for row in df.to_dict("records"):
                name = str(row.get("company_name", "")).strip()
                if not name or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
                results.append({
                    "company_name": name,
                    "hq": str(row.get("hq", "")),
                    "website": str(row.get("website", "")),
                    "source": "glassdollar",
                })
        except Exception:
            # Don't fail the whole search if the API is down — local results still show.
            pass

    # Local xlsx — always available, no key needed.
    # Results are sorted so "starts with" matches appear before "contains" matches.
    local = _get_local_df()
    if local is not None:
        name_col = "company_name" if "company_name" in local.columns else local.columns[0]
        q_lower = q.strip().lower()
        names_series = local[name_col].astype(str)
        mask = names_series.str.lower().str.contains(q_lower, na=False)
        hits = local[mask].copy()
        # sort: names that start with the query first, then the rest alphabetically
        hits["_starts"] = names_series[mask].str.lower().str.startswith(q_lower).astype(int)
        hits = hits.sort_values("_starts", ascending=False).head(limit)
        for row in hits.to_dict("records"):
            name = str(row.get(name_col, "")).strip()
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            results.append({
                "company_name": name,
                "hq": str(row.get("hq", "")),
                "website": str(row.get("website", "")),
                "source": "applications",
            })

    return {"results": results[:limit]}


# Cache-first: a stored evaluation younger than this is returned instead of re-running
# the whole pipeline (external calls + LLM). Override with EVAL_TTL_DAYS; refresh=true bypasses.
EVAL_TTL_DAYS = float(os.getenv("EVAL_TTL_DAYS", "7"))


def _freshness(created_at: str) -> dict:
    from datetime import datetime, timezone
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(created_at)).total_seconds() / 86400
    except Exception:
        age = -1
    return {"last_evaluated_at": created_at, "age_days": round(age, 1),
            "ttl_days": EVAL_TTL_DAYS,
            "status": "fresh" if 0 <= age <= EVAL_TTL_DAYS else "stale"}


@app.post("/api/evaluate")
def evaluate(body: EvaluateBody, user: Principal = Depends(current_user)) -> dict:
    """Cache-first full pipeline run. Returns the stored evaluation when one exists and
    is younger than EVAL_TTL_DAYS; refresh=true forces a new run (old runs are retained
    for audit/history). Uses the GlassDollar API when a key is set; otherwise the local
    applications file serves as the dev/test company source.

    The evaluation itself is shared — one company is evaluated once for the whole team —
    but the *search* is recorded against the caller, which is what gives each reviewer
    their own list without duplicating any of the expensive work.
    """
    name = body.name.strip()
    principal = user.as_reviewer()
    cached = _evaluation_cached(name, body, user)
    return cached if cached is not None else _run_evaluation(name, body, principal, user=user)


def _department(department_id, user) -> dict:
    """The selected department's profile, or a 422 that says what is missing."""
    if not department_id:
        raise HTTPException(422, "Choose a department before starting an evaluation.")
    from api.interests import profiles
    dep = next((d for d in profiles(user)["departments"] if d["id"] == department_id), None)
    if dep is None:
        raise HTTPException(422, f"Unknown department '{department_id}'.")
    return dep


PREWARM_CONCURRENCY = int(os.getenv("PREWARM_CONCURRENCY", "2"))


def _all_departments(user) -> list[dict]:
    """Every configured department. An evaluation is assessed for all of them and recommends the
    one whose needs the startup answers best, so nobody has to guess a department up front."""
    from api.interests import profiles
    departments = profiles(user)["departments"]
    if not departments:
        raise HTTPException(503, "No departments are configured.")
    return departments


def _all_key(departments: list[dict]) -> str:
    """The assessment key an all-departments run must carry to count as current today."""
    from core import catalogs
    from core.assessment import all_departments_key
    return all_departments_key({"siemens_tools": catalogs.tools_catalog(),
                                "xcelerator": catalogs.xcelerator_catalog()},
                               {d["id"]: catalogs.department_catalog(d) for d in departments})


def _current_key(department: dict) -> str:
    """The assessment key a run must carry to count as current for this department today."""
    from core import catalogs
    from core.assessment import assessment_key
    return assessment_key({"siemens_tools": catalogs.tools_catalog(),
                           "xcelerator": catalogs.xcelerator_catalog(),
                           "department_needs": catalogs.department_catalog(department)})


def _evaluation_cached(name, body, user):
    """Only an exact hit: same company, assessed for every department against the current rubric
    and every current catalog. A run for one department (the old flow) is not a hit."""
    if body.refresh:
        return None
    key = _all_key(_all_departments(user))
    if tracxn_client_for(user):
        cached = workspace.private_latest(user.oid, name, "*", key)
    else:
        cached = store.latest_department_run(name, "*", key)
    if cached:
        cached["cached"] = True
        cached["freshness"] = _freshness(cached.get("run_created_at", ""))
        if not cached.get("private"):
            store.record_search(user.as_reviewer(), name, company_name=str(cached.get("company", "")),
                                run_id=cached.get("run_id"), served_from="cache")
    return cached


def _run_evaluation(name: str, body: "EvaluateBody", principal, on_partial=None, user=None,
                    departments: list | None = None, background: bool = False) -> dict:
    """The uncached half of /api/evaluate, shared with the streaming route and the job queue.

    Extracted rather than duplicated: the endpoints must agree on what a fresh evaluation is,
    including which searches get to replay from cache and what is recorded against the reviewer.
    Every fresh run passes through here, which is why the concurrency cap and the one-run-per-
    company rule (api/flight.py) live here and not on any one route.

    ``background`` is for work no reviewer is waiting on (scripts/prewarm.py): it takes a slot only
    when nobody is queued, at PREWARM_CONCURRENCY, and runs without a signed-in user, so it passes
    ``departments`` itself and records no search.
    """
    departments = departments or (_all_departments(user) if user else None)
    tracxn = tracxn_client_for(user, core.LLMClient()) if user else None

    def queued(emit):
        return lambda position: emit("queue", {"position": position})

    if tracxn:
        # A Tracxn-backed run is private to its reviewer, so it is never shared — only queued.
        emit = on_partial or (lambda s, d: None)
        with flight.slot(queued(emit)):
            return _fresh_evaluation(name, body, principal, emit, user, departments, tracxn)
    key = flight.flight_key(name, "refresh" if body.refresh else "")

    led = []

    def lead(emit):
        led.append(True)
        with flight.slot(queued(emit), **({"limit": PREWARM_CONCURRENCY, "background": True}
                                          if background else {})):
            return _fresh_evaluation(name, body, principal, emit, user, departments, None)

    res = flight.single_flight(key, lead, on_partial)
    if not led:
        # Attached to another reviewer's run of the same company: the work is theirs, the
        # search is ours.
        store.record_search(principal, name, company_name=str(res.get("company", "")),
                            run_id=res.get("run_id"), served_from="shared")
    return res


def _fresh_evaluation(name, body, principal, on_partial, user, departments, tracxn) -> dict:
    if departments and not body.refresh and not tracxn:
        # Recent research exists (a one-department run, or one assessed against older catalogs):
        # it is reused and only the department assessments are redone — as a NEW run, never a
        # rewrite of the old one.
        research = store.latest_research_run(name)
        if research and _freshness(research.get("run_created_at", ""))["status"] == "fresh":
            from core.pipeline import assess_departments
            res = assess_departments(research, departments, do_web=body.do_web)
            return _saved(res, name, body, principal, served_from="research")
    df = None if _gd_key() else _get_local_df()
    # An explicit refresh must re-search: serving cached hits would replay the very evidence
    # the caller asked to renew.
    token = core.web.set_cache_private(True) if tracxn else None
    try:
        res = core.evaluate(name, None, core.DEFAULT_TOOLS_CSV, do_web=body.do_web, df=df,
                            use_web_cache=not body.refresh, on_partial=on_partial, tracxn=tracxn,
                            departments=departments, prior_runs=store.prior_runs_for(name))
    finally:
        if token is not None:
            core.web.reset_cache_private(token)
    if not res.get("found"):
        raise HTTPException(status_code=404,
                            detail=f"No match for '{body.name}' in GlassDollar or on the web.")
    if res.get("source") == "tracxn":
        from datetime import datetime, timezone
        res.update(cached=False, run_created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return workspace.private_save(user.oid, name, res) if body.save else res
    return _saved(res, name, body, principal)


def _saved(res: dict, name: str, body: "EvaluateBody", principal, served_from: str = "fresh") -> dict:
    if body.save:
        # The typed query is filed as an alias so the next reviewer who types it the same
        # way is served from the database instead of re-running the pipeline.
        res["run_id"] = store.save_run(res, aliases=[name])
    store.record_search(principal, name, company_name=str(res.get("company", "")),
                        run_id=res.get("run_id"), served_from=served_from)
    from datetime import datetime, timezone
    res["cached"] = served_from != "fresh"
    res["run_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["freshness"] = _freshness(res["run_created_at"])
    return res


@app.post("/api/evaluate/stream")
def evaluate_stream(body: EvaluateBody, user: Principal = Depends(current_user)):
    """The same evaluation as /api/evaluate, delivered in pieces as they become available.

    A fresh run takes a minute or two, and all of it used to arrive at once: the page showed a
    skeleton until routing finished, even though the company profile was ready long before. The
    profile now reaches the browser the moment it is assembled.

    Server-sent events over POST, so `fetch` + a stream reader rather than `EventSource` — that is
    GET-only and this has to carry the session cookie. `core.evaluate` is blocking, so it runs on a
    worker thread and pushes onto a queue this generator drains; `copy_context()` carries the
    cache-bypass ContextVar across that boundary, the same rule as every other thread in the
    engine. The final `done` event carries the complete result, so a client that ignores every
    partial still gets exactly what /api/evaluate returns.
    """
    import contextvars
    import json
    import queue
    import threading

    name = body.name.strip()
    principal = user.as_reviewer()
    events: "queue.Queue" = queue.Queue()

    # A cache hit is not a pipeline run: it emits one `done` and nothing else, so the cached path
    # stays byte-identical to the non-streaming endpoint.
    cached = _evaluation_cached(name, body, user)
    if cached:
        events.put(("done", cached))
        events.put(None)

    def _work():
        try:
            res = _run_evaluation(name, body, principal,
                                  on_partial=lambda s, d: events.put(("partial",
                                                                      {"section": s, "data": d})), user=user)
            events.put(("done", res))
        except HTTPException as exc:
            events.put(("error", {"detail": exc.detail, "status": exc.status_code}))
        except Exception as exc:                        # pragma: no cover - defensive
            log.exception("[evaluate/stream] %s failed", name)
            events.put(("error", {"detail": str(exc), "status": 500}))
        finally:
            events.put(None)

    if events.empty():
        threading.Thread(target=contextvars.copy_context().run, args=(_work,),
                         daemon=True).start()

    def _stream():
        while True:
            item = events.get()
            if item is None:
                return
            event, payload = item
            # `default=str` rather than a bespoke encoder: a partial can carry a pandas or
            # datetime value, and a serialisation error mid-stream would truncate the response
            # with no way for the client to tell that from a dropped connection.
            yield f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             # Proxies buffer text/event-stream by default, which would hold every
                             # partial until the run finished and quietly undo the whole point.
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/my/searches")
def my_searches(limit: int = 200, user: Principal = Depends(current_user)) -> dict:
    """The startups THIS reviewer has searched. Explore's data source.

    Lists are private: there is no parameter that widens this to another principal. The
    team-wide view lives at /api/admin/searches behind require_admin.
    """
    return {"runs": sorted(workspace.private_list(user.oid) + store.list_user_runs(user.oid, limit=max(1, min(limit, 500))),
                           key=lambda r: r.get("created_at", ""), reverse=True)[:max(1, min(limit, 500))]}


@app.get("/api/my/views")
def my_views(user: Principal = Depends(current_user)) -> dict:
    return {"views": store.list_views(user.oid)}


@app.post("/api/my/views")
def my_view_save(body: SavedViewBody, user: Principal = Depends(current_user)) -> dict:
    """Upsert one grid view. Views used to live in localStorage, so they were per-browser
    rather than per-person; keying them on the Entra oid is what makes them follow a
    reviewer between machines."""
    return store.save_view(user.oid, body.name, body.columns, body.filters)


@app.delete("/api/my/views/{name}")
def my_view_delete(name: str, user: Principal = Depends(current_user)) -> dict:
    if not store.delete_view(user.oid, name):
        raise HTTPException(status_code=404, detail=f"No saved view named {name!r}.")
    return {"deleted": name}


@app.post("/api/solve")
def solve(body: SolveBody, user: Principal = Depends(current_user)) -> dict:
    import hashlib
    import json
    import time
    from api.auth import sessions

    problem = body.problem.strip()
    if len(problem) < 3:
        raise HTTPException(422, "Describe your problem in at least three characters.")
    llm = core.LLMClient(model=os.getenv("SCOUTING_LLM_MODEL", ""))
    tracxn = tracxn_client_for(user, llm)
    signature = json.dumps([problem.casefold(), body.do_web, tracxn.cache_identity if tracxn else "", bool(_gd_key()),
                            llm.model, llm.provider, llm.base_url, _LOCAL_XLSX], sort_keys=True)
    key = f"scout:v1:{user.oid}:" + hashlib.sha256(signature.encode()).hexdigest()
    cached = sessions().get(key)
    if cached:
        return {**cached, "cached": True}
    started = time.monotonic()
    # Private provider responses must not enter the shared SQLite-backed completion cache.
    token = core.web.set_cache_private(True) if tracxn else None
    try:
        result = solve_problem(problem, llm=llm, do_web=body.do_web,
                               use_glassdollar=bool(_gd_key()), local_df=_get_local_df(), tracxn=tracxn)
    finally:
        if token is not None:
            core.web.reset_cache_private(token)
    result.update(cached=False, elapsed_seconds=round(time.monotonic() - started, 1))
    if result["candidates"] and not any("unavailable" in s["status"] for s in result["sources"]):
        sessions().put(key, result, 600)
    return result


@app.get("/api/runs")
def runs(limit: int = 100, user: Principal = Depends(require_admin)) -> dict:
    """Every run from every reviewer. Admin-only since lists became private — reviewers
    read their own via /api/my/searches, which returns rows of exactly this shape."""
    return {"runs": store.list_runs(limit=limit)}


@app.get("/api/admin/overview")
def admin_overview(days: int = 30, user: Principal = Depends(require_admin)) -> dict:
    """Usage metrics: sessions, searches, distinct users, cache-hit rate, busiest companies."""
    return store.admin_overview(recent_days=max(1, min(days, 365)))


@app.get("/api/admin/searches")
def admin_searches(limit: int = 200, user: Principal = Depends(require_admin)) -> dict:
    """The raw activity log — who searched what, when, and whether it hit the cache."""
    return {"searches": store.list_searches(limit=limit)}


class AdminGrant(BaseModel):
    upn: str = Field(..., description="Sign-in name (UPN) to grant administrator access to")
    note: str = Field("", description="Optional note recorded with the grant")


@app.get("/api/admin/admins")
def admin_list(user: Principal = Depends(require_admin)) -> dict:
    """Both sources of admin rights, tagged, because they behave differently.

    An `env` row comes from ADMIN_UPNS and cannot be revoked here — it is the recovery path
    that guarantees the deployment is never left with nobody able to administer it. The UI
    needs the tag to omit the revoke control rather than offer one that would silently fail.
    """
    seeded = sorted(auth_admin_upns())
    granted = [a for a in store.list_admins() if a["upn"] not in set(seeded)]
    return {
        "admins": [{"upn": u, "source": "env", "granted_by": "", "granted_at": "", "note": ""}
                   for u in seeded] + granted,
        "you": user.upn,
    }


@app.post("/api/admin/admins")
def admin_grant(body: AdminGrant, user: Principal = Depends(require_admin)) -> dict:
    """Grant administrator access to another sign-in name."""
    upn = (body.upn or "").strip().lower()
    # Not full RFC 5322 — just enough to catch a display name or a typo'd domain before it
    # becomes a row nobody can match against and everybody assumes is working.
    if not upn or "@" not in upn or " " in upn or upn.startswith("@") or upn.endswith("@"):
        raise HTTPException(status_code=422, detail="Enter a full sign-in name, e.g. name@siemens.com.")
    if upn in auth_admin_upns():
        raise HTTPException(status_code=409,
                            detail=f"{upn} is already an administrator via ADMIN_UPNS.")
    row = store.grant_admin(upn, granted_by=user.upn, note=body.note or "")
    if row is None:
        raise HTTPException(status_code=409, detail=f"{upn} is already an administrator.")
    log.info("[admin] %s granted admin access (by %s)", upn, user.upn)
    return row


@app.delete("/api/admin/admins/{upn}")
def admin_revoke(upn: str, user: Principal = Depends(require_admin)) -> dict:
    """Revoke an in-app grant.

    Two refusals, both about not creating a state that can only be repaired from the AWS
    console: an ADMIN_UPNS-seeded admin does not live here to be removed, and the last
    remaining admin may not remove themselves.
    """
    target = (upn or "").strip().lower()
    if target in auth_admin_upns():
        raise HTTPException(
            status_code=409,
            detail=f"{target} is an administrator via the ADMIN_UPNS setting, which cannot be "
                   "changed from here. Edit it on the server and restart.")
    remaining = (auth_admin_upns() | auth_db_admin_upns()) - {target}
    if not remaining:
        raise HTTPException(
            status_code=409,
            detail="This is the only administrator left. Grant access to someone else first, "
                   "or nobody will be able to administer this deployment.")
    if not store.revoke_admin(target):
        raise HTTPException(status_code=404, detail=f"{target} is not an administrator.")
    log.info("[admin] %s revoked admin access (by %s)", target, user.upn)
    return {"upn": target, "revoked": True}


@app.get("/api/companies")
def companies() -> dict:
    """Canonical company records (normalized tables) with people/programs/customers."""
    return {"companies": store.list_companies()}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: int, user: Principal = Depends(current_user)) -> dict:
    res = workspace.private_get(user.oid, run_id) if run_id < 0 else store.get_run(run_id)
    if res is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return res


def _run_for(run_id: int, user: Principal) -> dict:
    res = workspace.private_get(user.oid, run_id) if run_id < 0 else store.get_run(run_id)
    if res is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return res


@app.post("/api/runs/{run_id}/business-flow")
def run_business_flow(run_id: int, user: Principal = Depends(current_user)) -> dict:
    """The profile's "How this startup works": five plain, cited sentences (core/business_flow.py).
    Written once per run and kept in the database; served from there on every later read."""
    from core.business_flow import business_flow
    res = _run_for(run_id, user)
    stored = store.latest_enrichment(str(res.get("company", "")), "business_flow", run_id=run_id)
    if stored:
        return stored
    out = business_flow(res, core.LLMClient())
    if out.get("status") == "ok":
        store.save_enrichment(str(res.get("company", "")), "business_flow", {**out, "provider": "model"},
                              run_id=run_id, user_oid=user.oid)
    return out


@app.post("/api/runs/{run_id}/lookup/{kind}")
def run_lookup(run_id: int, kind: Literal["funding", "headcount", "signals"], refresh: bool = False,
               user: Principal = Depends(current_user)) -> dict:
    """Funding rounds with investor profiles, a sourced headcount, or dated momentum signals in the
    company's market (core/traction_lookup.py, core/market_signals.py).

    Served from the database when this company's result was fetched before — by anyone, for any of
    its runs — and searched again only on Refresh. A fresh result is stored (history kept), whether
    it came from Tracxn or the web: Tracxn first through the reviewer's own connection, the model's
    web search second.
    """
    from core.market_signals import market_signals
    from core.traction_lookup import funding_details, headcount_details
    res = _run_for(run_id, user)
    company = str(res.get("company", ""))
    if not refresh:
        stored = store.latest_enrichment(company, kind)
        if stored:
            return stored
    profile = res.get("profile") or {}
    llm = core.LLMClient()
    tracxn = tracxn_client_for(user, llm)
    website = str(profile.get("website") or "")
    if kind == "signals":
        # Signals start from an understanding of the market, which needs the run's own research.
        out = market_signals(company, run=res, website=website, llm=llm, tracxn=tracxn, refresh=refresh)
    else:
        fetch = funding_details if kind == "funding" else headcount_details
        out = fetch(company, website=website, llm=llm, tracxn=tracxn, refresh=refresh)
    # Only a real answer is kept: "no model", "timed out" or a signals search with a failed domain
    # would otherwise be served back as if it were the finding.
    if out.get("provider") in ("tracxn", "web") and "failed" not in (out.get("domains") or {}).values():
        store.save_enrichment(company, kind, out, user_oid=user.oid)
    return out


@app.get("/api/admin/token-usage")
def admin_token_usage(limit: int = 100, user: Principal = Depends(require_admin)) -> dict:
    """Tokens per evaluation, newest first: the cost side of every research run."""
    return store.token_usage_runs(max(1, min(int(limit), 500)))


@app.get("/api/admin/token-usage/{run_id}")
def admin_token_usage_run(run_id: int, user: Principal = Depends(require_admin)) -> dict:
    """One run's model calls — stage, model, tokens, time, attempts — in the order they finished."""
    return {"run_id": run_id, "calls": store.token_usage_log(run_id)}


@app.get("/api/admin/tool-checks")
def admin_tool_checks(status: str | None = "not_found", user: Principal = Depends(require_admin)) -> dict:
    """Siemens catalog tools Empower recommended and a web search checked — by default the ones it
    could NOT find, which are the catalog rows worth a reviewer's look."""
    return {"tools": store.list_tool_checks(status or None)}


@app.get("/api/runs/{run_id}/departments")
def run_departments(run_id: int, user: Principal = Depends(current_user)) -> dict:
    """For each department: this company's saved run and whether it is current.

    What the profile's department switch reads. A department with no current run is listed with
    run_id None, and the page offers an explicit assessment rather than showing another
    department's result in its place.
    """
    res = _run_for(run_id, user)
    from api.interests import profiles
    company = str(res.get("company", ""))
    if run_id < 0:
        saved = {}
        for d in profiles(user)["departments"]:
            r = workspace.private_latest(user.oid, company, d["id"])
            if r:
                saved[d["id"]] = {"run_id": r.get("run_id"),
                                  "assessment_key": (r.get("assessment") or {}).get("assessment_key")}
    else:
        saved = {r["department_id"]: r for r in store.company_department_runs(company) if r["department_id"]}
    out = []
    for d in profiles(user)["departments"]:
        s = saved.get(d["id"]) or {}
        out.append({"id": d["id"], "label": d["label"], "demo": d["demo"], "run_id": s.get("run_id"),
                    "current": bool(s) and s.get("assessment_key") == _current_key(d)})
    return {"company": company, "department_id": (res.get("department") or {}).get("id"),
            "legacy": not res.get("department"), "departments": out}


@app.post("/api/runs/{run_id}/departments/{department_id}")
def run_assess_department(run_id: int, department_id: str, user: Principal = Depends(current_user)) -> dict:
    """Assess this run's startup for another department, reusing its research, as a NEW run.

    Idempotent against the current version: when a current run for that department already
    exists it is returned rather than recomputed.
    """
    res = _run_for(run_id, user)
    dep = _department(department_id, user)
    key = _current_key(dep)
    company = str(res.get("company", ""))
    existing = (workspace.private_latest(user.oid, company, dep["id"], key) if run_id < 0
                else store.latest_department_run(company, dep["id"], key))
    if existing:
        return existing
    from core.pipeline import assess_department
    new = assess_department(res, dep)
    from datetime import datetime, timezone
    new["run_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if run_id < 0:
        return workspace.private_save(user.oid, company, new)
    new["run_id"] = store.save_run(new, aliases=[company])
    store.record_search(user.as_reviewer(), company, company_name=company,
                        run_id=new["run_id"], served_from="research")
    return new


@app.delete("/api/runs/{run_id}")
def run_delete(run_id: int) -> dict:
    if not store.delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return {"deleted": run_id}


@app.post("/api/runs/{run_id}/override")
def override_run(run_id: int, body: OverrideBody,
                 user: Principal = Depends(current_user)) -> dict:
    """Reviewer override of the routing decision. The automated result is preserved;
    the change, its reason, and supporting evidence are logged for audit.

    The reviewer comes from the session, never from the body. This used to be a free-text
    field, which meant a partnership decision could be attributed to anyone who had not
    made it."""
    raise HTTPException(410, "Routing overrides have been retired.")


@app.get("/api/runs/{run_id}/audit")
def run_audit(run_id: int) -> dict:
    return {"overrides": store.list_overrides(run_id)}


@app.get("/api/challenges")
def challenges() -> dict:
    return {"challenges": load_challenges()}


@app.patch("/api/challenges/{index}")
def challenge_status(index: int, body: ChallengeStatusBody,
                     user: Principal = Depends(current_user)) -> dict:
    """Innovation-team approval control over submitted problems."""
    rec = set_challenge_status(index, body.status, user.name,
                               reviewer_oid=user.oid)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Challenge {index} not found.")
    return rec


@app.post("/api/ask")
def ask(body: AskBody, user: Principal = Depends(current_user)) -> dict:
    """The assistant: the evaluation in focus first, then the reviewer's own Tracxn connection,
    then the model's web search (core.chat.chat_assistant)."""
    company, brief, facts = "", "", None
    if body.run_id is not None:
        res = workspace.private_get(user.oid, body.run_id) if body.run_id < 0 else store.get_run(body.run_id)
        if res is None:
            raise HTTPException(status_code=404, detail=f"Run {body.run_id} not found.")
        company = str(res.get("company", ""))
        # What the evaluation already researched, as citable facts: the assistant answers from
        # these first and searches only for what they do not cover.
        brief, facts = run_brief(res)
    llm = core.LLMClient()
    tracxn = tracxn_client_for(user, llm)
    # Tracxn answers are licensed to this reviewer, and a private run is theirs alone; neither
    # may be served to someone else from the shared model cache.
    private = tracxn is not None or (body.run_id is not None and body.run_id < 0)
    token = core.web.set_cache_private(True) if private else None
    try:
        return core.chat_assistant(body.question, llm=llm, tracxn=tracxn, context_company=company,
                                   context_brief=brief, history=[t.model_dump() for t in body.history],
                                   run_facts=facts)
    finally:
        if token is not None:
            core.web.reset_cache_private(token)


# ── PDF management (S3-backed) ────────────────────────────────────────────────

@app.get("/api/pdfs")
def list_pdfs() -> dict:
    """List all pitch PDFs stored in S3."""
    return {"pdfs": _s3.list_pdfs()}


@app.post("/api/pdfs/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    """Upload a pitch PDF to S3."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    import tempfile, shutil, pathlib
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        key = _s3.upload_pdf(tmp_path, file.filename)
        if not key:
            raise HTTPException(status_code=500, detail="S3 upload failed — check credentials.")
    finally:
        pathlib.Path(tmp_path).unlink(missing_ok=True)
    return {"key": key, "filename": file.filename}


@app.delete("/api/pdfs/{filename}")
def delete_pdf(filename: str) -> dict:
    """Delete a pitch PDF from S3."""
    if not _s3.delete_pdf(filename):
        raise HTTPException(status_code=404, detail=f"PDF '{filename}' not found in S3.")
    return {"deleted": filename}


@app.get("/api/pdfs/{filename}/url")
def pdf_url(filename: str) -> dict:
    """Get a pre-signed download URL for a PDF stored in S3."""
    url = _s3.presigned_url(filename)
    if not url:
        raise HTTPException(status_code=404, detail=f"PDF '{filename}' not found or S3 unavailable.")
    return {"url": url, "filename": filename}


# ── Static file serving (single-container production mode) ───────────────────
_STATIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "static"
if (_STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        file = _STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_STATIC_DIR / "index.html"))
