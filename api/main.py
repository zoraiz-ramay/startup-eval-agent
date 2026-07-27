"""FastAPI backend for the Siemens Startup Evaluation Agent.

Wraps the existing core pipeline (evaluate / solve / search) behind a REST API so a
proper frontend (React, Tracxn-style) can drive it. Run history persists in SQLite.

Run locally:   uvicorn api.main:app --reload --port 8000
In Docker:     see docker-compose.yml (service `api`)
"""
from __future__ import annotations

import os
import sys
import pathlib

# Ensure the project root is importable when launched as `uvicorn api.main:app`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File
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
from api.security import SecurityMiddleware


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
                   allow_headers=["Authorization", "Content-Type"])


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


class OverrideBody(BaseModel):
    new_pillar: str = Field(..., pattern="^(Connect|Collaborate|Empower|Pass)$")
    reason: str = Field(..., min_length=5, max_length=1000)
    evidence_note: str = Field("", max_length=2000)
    reviewer: str = Field("", max_length=120)


class ChallengeStatusBody(BaseModel):
    status: str = Field(..., pattern="^(pending|approved|rejected)$")
    reviewer: str = Field("", max_length=120)


def _gd_key() -> bool:
    return bool(core.GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", ""))


@app.get("/health")
def health() -> dict:
    _llm = core.LLMClient()
    return {"status": "ok",
            "llm": _llm.available,
            "llm_provider": _llm.provider,
            "llm_model": _llm.model if _llm.available else "",
            "glassdollar_key": bool(core.GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")),
            "data_source": "glassdollar_api",
            "applications_file": os.path.basename(_LOCAL_XLSX) if _LOCAL_XLSX else "",
            "applications_count": int(len(_get_local_df())) if _LOCAL_XLSX else 0,
            "s3_bucket": _s3.S3_BUCKET,
            "s3_available": _s3._available()}


@app.get("/api/search")
def search(q: str, limit: int = 10) -> dict:
    """Name search — always queries the local applications xlsx first, then the
    GlassDollar API (when a key is set). Results are merged and deduplicated so
    local applicants appear even when a live API key is configured."""
    q, limit = q[:200], max(1, min(limit, 25))
    if not q.strip():
        return {"results": []}

    results: list = []
    seen_names: set = set()

    # 1. Local xlsx — always available, no key needed.
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

    # 2. GlassDollar API — live results appended after local ones.
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
        except Exception as e:
            # Don't fail the whole search if the API is down — local results still show.
            pass

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
def evaluate(body: EvaluateBody) -> dict:
    """Cache-first full pipeline run. Returns the stored evaluation when one exists and
    is younger than EVAL_TTL_DAYS; refresh=true forces a new run (old runs are retained
    for audit/history). Uses the GlassDollar API when a key is set; otherwise the local
    applications file serves as the dev/test company source."""
    name = body.name.strip()
    if not body.refresh:
        # Any stored evaluation is served from the DB — regardless of age. Fresh external
        # calls happen ONLY on explicit refresh (Re-evaluate / Refresh Data buttons).
        # Freshness metadata tells the UI how old the data is.
        cached = store.latest_run_for_company(name)
        if cached:
            cached["cached"] = True
            cached["freshness"] = _freshness(cached.get("run_created_at", ""))
            return cached
    df = None if _gd_key() else _get_local_df()
    res = core.evaluate(name, None, core.DEFAULT_TOOLS_CSV, do_web=body.do_web, df=df)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail=f"No match for '{body.name}' in GlassDollar or on the web.")
    if body.save:
        res["run_id"] = store.save_run(res)
    from datetime import datetime, timezone
    res["cached"] = False
    res["run_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["freshness"] = _freshness(res["run_created_at"])
    return res


@app.post("/api/solve")
def solve(body: SolveBody) -> dict:
    """Problem -> ranked solver startups. The ONLY endpoint that searches the local
    applications Excel; GlassDollar + web fill in the rest. Records the challenge."""
    return solve_problem(body.problem, llm=core.LLMClient(), do_web=body.do_web,
                         use_glassdollar=bool(core.GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")),
                         local_df=_get_local_df())


@app.get("/api/runs")
def runs(limit: int = 100) -> dict:
    return {"runs": store.list_runs(limit=limit)}


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
def override_run(run_id: int, body: OverrideBody) -> dict:
    """Reviewer override of the routing decision. The automated result is preserved;
    the change, its reason, and supporting evidence are logged for audit."""
    rec = store.add_override(run_id, body.new_pillar, body.reason,
                             body.evidence_note, body.reviewer)
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
def challenge_status(index: int, body: ChallengeStatusBody) -> dict:
    """Innovation-team approval control over submitted problems."""
    rec = set_challenge_status(index, body.status, body.reviewer)
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
if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        file = _STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_STATIC_DIR / "index.html"))
