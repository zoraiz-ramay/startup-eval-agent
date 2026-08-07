"""API route: claim-evidence matrix for an evaluated startup.

GET /api/evidence/{startup}

Reads the most recent stored evaluation for the given startup and returns a
claim-evidence matrix benchmarked against the Tracxn profile schema
(https://tracxn.com). Returns 404 when no evaluation exists yet.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api import store
from benchmarks.matrix import build_claim_evidence_matrix

router = APIRouter()


@router.get("/api/evidence/{startup}")
def evidence_matrix(startup: str) -> dict:
    run = store.latest_run_for_company(startup)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation found for '{startup}'. Evaluate it first.",
        )
    return build_claim_evidence_matrix(run)
