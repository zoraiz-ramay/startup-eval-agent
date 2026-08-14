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
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import glob

import pandas as pd

import core
from core.solve import solve_problem, load_challenges, set_challenge_status
from core import s3 as _s3
from api import store
from api.auth import Principal, current_user, require_admin, settings as auth_settings
from api.auth import admin_upns as auth_admin_upns, db_admin_upns as auth_db_admin_upns
from api.auth import router as auth_router
from api.security import SecurityMiddleware
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
except Exception:
    pass

# Give the engine its result cache. Injected rather than imported by core/ so nothing in core/
# depends on api/ and the engine still runs (uncached) from tests, scripts and Streamlit.
try:
    core.web.install_cache(store.cache_get, store.cache_put)
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
                   allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"])

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


class EvaluateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Startup name to evaluate")
    do_web: bool = True
    save: bool = True
    refresh: bool = Field(False, description="Force a fresh evaluation, bypassing the cache")


class SolveBody(BaseModel):
    problem: str = Field(..., min_length=3, max_length=2000,
                         description="Problem statement to find solver startups for")
    do_web: bool = True


class AskBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    run_id: int | None = Field(None, description="Ground the answer in this evaluated run")


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
    if not body.refresh:
        # Any stored evaluation is served from the DB — regardless of age. Fresh external
        # calls happen ONLY on explicit refresh (Re-evaluate / Refresh Data buttons).
        # Freshness metadata tells the UI how old the data is.
        cached = store.latest_run_for_alias(name)
        if cached:
            cached["cached"] = True
            cached["freshness"] = _freshness(cached.get("run_created_at", ""))
            store.record_search(principal, name, company_name=str(cached.get("company", "")),
                                run_id=cached.get("run_id"), served_from="cache")
            return cached
    df = None if _gd_key() else _get_local_df()
    # An explicit refresh must re-search: serving cached hits would replay the very evidence
    # the caller asked to renew.
    res = core.evaluate(name, None, core.DEFAULT_TOOLS_CSV, do_web=body.do_web, df=df,
                        use_web_cache=not body.refresh)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail=f"No match for '{body.name}' in GlassDollar or on the web.")
    if body.save:
        # The typed query is filed as an alias so the next reviewer who types it the same
        # way is served from the database instead of re-running the pipeline.
        res["run_id"] = store.save_run(res, aliases=[name])
    store.record_search(principal, name, company_name=str(res.get("company", "")),
                        run_id=res.get("run_id"), served_from="fresh")
    from datetime import datetime, timezone
    res["cached"] = False
    res["run_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["freshness"] = _freshness(res["run_created_at"])
    return res


@app.get("/api/my/searches")
def my_searches(limit: int = 200, user: Principal = Depends(current_user)) -> dict:
    """The startups THIS reviewer has searched. Explore's data source.

    Lists are private: there is no parameter that widens this to another principal. The
    team-wide view lives at /api/admin/searches behind require_admin.
    """
    return {"runs": store.list_user_runs(user.oid, limit=max(1, min(limit, 500)))}


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
def solve(body: SolveBody) -> dict:
    """Problem -> ranked solver startups. The ONLY endpoint that searches the local
    applications Excel; GlassDollar + web fill in the rest. Records the challenge."""
    return solve_problem(body.problem, llm=core.LLMClient(), do_web=body.do_web,
                         use_glassdollar=bool(core.GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")),
                         local_df=_get_local_df())


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
def run_detail(run_id: int) -> dict:
    res = store.get_run(run_id)
    if res is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return res


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
    rec = store.add_override(run_id, body.new_pillar, body.reason,
                             body.evidence_note, reviewer=user.as_reviewer())
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return rec


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
def ask(body: AskBody) -> dict:
    """Combined AI + web answer (credit-efficient 2-LLM-call flow). Optionally grounded
    in a stored evaluation via run_id."""
    company, brief = "", ""
    if body.run_id is not None:
        res = store.get_run(body.run_id)
        if res is None:
            raise HTTPException(status_code=404, detail=f"Run {body.run_id} not found.")
        company = str(res.get("company", ""))
        sc, rt, fit = res.get("score", {}) or {}, res.get("routing", {}) or {}, res.get("fit", {}) or {}
        p = res.get("profile", {}) or {}
        tools = ", ".join(m.get("tool", "") for m in (fit.get("matches") or [])[:5]) or "none"
        brief = (f"Company: {company}\nSummary: {res.get('summary','')}\n"
                 f"HQ: {p.get('hq','—')} | Funding: {p.get('funding','—')}\n"
                 f"Final score: {sc.get('final_score','—')} | Routing: {rt.get('pillar','—')} "
                 f"(+{', '.join(rt.get('secondary', []) or [])})\nSiemens fit tools: {tools}")
    return core.chat_smart(body.question, llm=core.LLMClient(),
                           context_company=company, context_brief=brief)


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
# Gate on assets/, not on static/ itself. StaticFiles raises RuntimeError from its
# constructor when the directory is missing, so a static/ holding anything other than a
# real vite build took the whole process down at import time rather than degrading to the
# API-only mode this branch exists to allow.
if (_STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        file = _STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_STATIC_DIR / "index.html"))
