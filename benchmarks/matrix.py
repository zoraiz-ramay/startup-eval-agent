"""Build a claim-evidence matrix from a stored evaluation run.

Pure functions (no I/O, no heavy deps) so they are trivially unit-testable and
reusable by the API layer. Each verified claim is mapped to a Tracxn benchmark
dimension (see benchmarks.tracxn).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .tracxn import benchmark_coverage, map_field_to_dimension

# Internal verification status -> (matrix verdict, credibility weight).
_STATUS_VERDICT = {
    "verified": ("supported", "high"),
    "partial": ("partially_supported", "medium"),
    "unverified": ("unsupported", "low"),
    "contradicted": ("contradicted", "low"),
}


def _verdict(status: str) -> tuple:
    return _STATUS_VERDICT.get((status or "").strip().lower(), ("unclear", "low"))


def build_claim_evidence_matrix(run: dict) -> dict:
    """Transform a run result dict into a claim-evidence matrix payload."""
    run = run or {}
    verification = run.get("verification", {}) or {}
    claims = verification.get("claims", []) or []

    facts_by_field: dict = {}
    for f in run.get("facts", []) or []:
        if isinstance(f, dict):
            facts_by_field.setdefault(str(f.get("key", "")).strip().lower(), f)

    rows: list = []
    fields: list = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        field = str(c.get("field", "")).strip()
        fields.append(field)
        verdict, quality = _verdict(c.get("status", ""))
        fact = facts_by_field.get(field.lower(), {})
        rows.append({
            "field": field,
            "claim": str(c.get("value", "")),
            "benchmark_dimension": map_field_to_dimension(field),
            "verdict": verdict,
            "source_quality": quality,
            "confidence": float(c.get("confidence", 0) or 0),
            "evidence_url": str(c.get("evidence_url", "") or fact.get("source_url", "")),
            "note": str(c.get("note", "")),
        })

    return {
        "startup": str(run.get("company", "")),
        "run_id": run.get("run_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": benchmark_coverage(fields),
        "summary": {
            "total_claims": len(rows),
            "supported": sum(1 for r in rows if r["verdict"] == "supported"),
            "partially_supported": sum(1 for r in rows
                                       if r["verdict"] == "partially_supported"),
            "unsupported": sum(1 for r in rows if r["verdict"] == "unsupported"),
            "contradicted": sum(1 for r in rows if r["verdict"] == "contradicted"),
        },
        "matrix": rows,
    }
