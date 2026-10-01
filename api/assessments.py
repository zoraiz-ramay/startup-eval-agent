"""Assess existing research without fetching startup data again."""
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from api.auth import Principal, current_user, sessions
from api import store, workspace
from api.interests import profiles
from core.judgment import VERSION, PROMPT_VERSION, score_research, department_fit, evidence_for
from core.llm import LLMClient
from core.traction import apply_traction
from core.web import set_cache_private, reset_cache_private

router = APIRouter(prefix="/api/runs", tags=["assessments"])


@router.post("/{run_id}/assessment/{department_id}")
def assess(run_id: int, department_id: str, user: Principal = Depends(current_user)):
    run = workspace.private_get(user.oid, run_id) if run_id < 0 else store.get_run(run_id)
    if not run: raise HTTPException(404, "Evaluation not found in your workspace.")
    if run.get("department"):
        # A department run is scored at evaluation time; merging a department_fit score into it
        # would overwrite the pillar-based Siemens Fit and total it carries.
        raise HTTPException(409, "This run was assessed for a department at evaluation time.")
    department = next((d for d in profiles(user)["departments"] if d["id"] == department_id), None)
    if not department: raise HTTPException(404, "Unknown department.")
    digest = hashlib.sha256(json.dumps(evidence_for(run), sort_keys=True, default=str).encode()).hexdigest()
    scope = user.oid if run_id < 0 else "public"
    base = f"assessment:{scope}:{VERSION}:{PROMPT_VERSION}:{digest}"
    dep_digest = hashlib.sha256(json.dumps(department, sort_keys=True).encode()).hexdigest()
    llm = LLMClient()
    token = set_cache_private(True)  # No private run or department judgment enters the shared LLM cache.
    try:
        # Coalesce StrictMode mounts and overlapping department selections.
        with workspace.locked(base, timeout=180, blocking_timeout=150):
            score = run.get("score", {})
            if score.get("version") != VERSION or score.get("status") != "assessed":
                score = sessions().get(base) or score_research(run, llm)
                if score.get("status") == "assessed": sessions().put(base, score, 86400)
            # After the cache, not inside it: a rubric change then reaches a cached model score
            # without the cache being cleared. The run was read through with_traction.
            score = apply_traction(score, run.get("traction"))
            key = base + ":" + dep_digest
            saved = (run.get("department_assessments") or {}).get(department_id) or {}
            fit = saved if saved.get("prompt_version") == PROMPT_VERSION and saved.get("department") == department and saved.get("status") == "assessed" else sessions().get(key)
            fit = fit or department_fit(run, department, llm)
            if fit.get("status") == "assessed": sessions().put(key, fit, 86400)
            if score.get("status") == "assessed" or fit.get("status") == "assessed":
                if run_id < 0: workspace.private_assessment(user.oid, run_id, score, fit)
                else: store.save_assessment(run_id, score, fit)
            return {"score": score, "department_fit": fit}
    finally:
        reset_cache_private(token)


@router.post("/{run_id}/decision")
def decide(run_id: int, user: Principal = Depends(current_user)):
    from core.judgment import DECISION_VERSION, decision_research
    run = workspace.private_get(user.oid, run_id) if run_id < 0 else store.get_run(run_id)
    if not run: raise HTTPException(404, "Evaluation not found in your workspace.")
    digest = hashlib.sha256(json.dumps(evidence_for(run), sort_keys=True, default=str).encode()).hexdigest()
    scope = user.oid if run_id < 0 else "public"
    key = f"decision:{scope}:{DECISION_VERSION}:{digest}"
    token = set_cache_private(True)
    try:
        with workspace.locked(key, timeout=180, blocking_timeout=150):
            saved = run.get("routing") or {}
            decision = saved if saved.get("version") == DECISION_VERSION and saved.get("status") == "assessed" else sessions().get(key)
            decision = decision or decision_research(run, LLMClient())
            if decision.get("status") == "assessed":
                sessions().put(key, decision, 86400)
                if run_id < 0: workspace.private_assessment(user.oid, run_id, {}, {}, decision)
                else: store.save_assessment(run_id, {}, {}, decision)
            return {"routing": {**saved, **decision}}
    finally:
        reset_cache_private(token)
