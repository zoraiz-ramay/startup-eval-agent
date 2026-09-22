"""Re-score a stored evaluation offline, from the evidence it already gathered.

The point is to make a scoring change *measurable*. Everything expensive and non-reproducible in
an evaluation — the searches, the extraction, the fit match — is already recorded in
`runs.result_json`. Scoring and routing are pure functions over that record. So the current engine
can be replayed across the whole history with no network, no model, and no cost, and the outcomes
compared against what a human said the answer should be.

That is the difference between "the score looks more sensible now" and "routing precision on
Connect went from 0.4 to 0.7 over 30 labelled companies". Until this existed, every change to
`core/score.py` was argued from a handful of hand-inspected runs.

What is replayed and what is not
--------------------------------
Replayed: `score_startup`, `route`, `assess_pillar`, `assess_sfs` — the deterministic layer.
Not replayed: enrichment, extraction, fit matching, trend. Those are the model's readings of the
web at the time, and re-running them would change the inputs under the experiment. A replay
therefore measures the *decision* layer against fixed evidence, which is exactly the layer that
changes most often.

Consequence worth knowing: a stored run carries the evidence its own engine version gathered. A
run from before the commercial-posture extraction has no `commercial` block, so its pillar criteria
come back `unproven` and its SFS answer `unassessed`. That is honest — the replay reports coverage
so the numbers are read against how much of the corpus can actually answer.
"""
from __future__ import annotations

import json
import os
import sqlite3

import pandas as pd

from core.provenance import Fact
from core.route import route
from core.score import score_startup

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB = os.path.join(_ROOT, "data", "runs.db")

# The stored profile header, plus the columns scoring reads that live outside it.
_ROW_KEYS = ("company_name", "hq", "founded_year", "employees_count", "employee_band", "funding",
             "customers", "Reference customers", "linkedin_url", "crunchbase_url", "website",
             "domain", "Your pitch", "short_description", "Business model",
             "Development stage of your solution", "Differentiation")


class _OfflineLLM:
    """`_route_reasons` takes its template branch when the client is unavailable.

    A replay must not call a model: the prose is not what is being measured, and generating it
    would make a 25-run sweep cost real money and real minutes for output nothing reads.
    """
    available = False


def _facts(raw: list) -> list:
    """Rebuild Fact objects from stored dicts — `score_startup` reads `.method` and `.verified`."""
    out = []
    for f in raw or []:
        if not isinstance(f, dict):
            continue
        try:
            out.append(Fact(
                key=str(f.get("key", "")), value=f.get("value", ""),
                source_url=str(f.get("source_url", "")), method=str(f.get("method", "")),
                confidence=float(f.get("confidence", 0) or 0),
                verified=f.get("verified") in (True, "True", "true", 1),
                retrieved_at=str(f.get("retrieved_at", "")) or None,
                source_type=str(f.get("source_type", "")),
            ))
        except Exception:
            continue
    return out


def _row(result: dict) -> pd.Series:
    profile = result.get("profile") or {}
    row = {k: profile.get(k, "") for k in _ROW_KEYS if k in profile}
    row.setdefault("company_name", result.get("company", ""))
    # The pitch text is the main input to the Collaborate domain and Empower bundle matchers, and
    # a web-sourced run keeps it only in the generated summary.
    if not str(row.get("Your pitch", "")).strip():
        row["Your pitch"] = result.get("summary", "")
    return pd.Series(row)


def replay(result: dict) -> dict:
    """Re-derive score and routing for one stored run. Returns {} if it cannot be replayed."""
    if not result.get("found", True) or not result.get("score"):
        return {}
    row = _row(result)
    enrichment = {"facts": _facts(result.get("facts"))}
    verification = result.get("verification") or {"claims": [], "red_flags": []}
    fit = result.get("fit") or {}
    profile = result.get("deep_profile") or {}
    trend = result.get("trend") or {}
    score = score_startup(row, enrichment, verification, fit, profile, trend)
    routing = route(score, fit, row, _OfflineLLM(), profile)
    return {"score": score, "routing": routing}


def load_runs(db_path: str = DEFAULT_DB, latest_per_company: bool = True) -> list[dict]:
    """Stored runs, newest first. Read-only: a benchmark must never mutate the history.

    `latest_per_company` keeps one row per company, because the corpus contains the same startup
    re-evaluated many times and counting each as an independent case would weight whichever
    company someone happened to debug against most heavily.
    """
    if not os.path.exists(db_path):
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, company, created_at, result_json FROM runs ORDER BY id DESC").fetchall()
    finally:
        con.close()
    out, seen = [], set()
    for rid, company, created_at, payload in rows:
        key = (company or "").strip().lower()
        if latest_per_company and key in seen:
            continue
        seen.add(key)
        try:
            result = json.loads(payload or "{}")
        except (ValueError, TypeError):
            continue
        out.append({"run_id": rid, "company": company, "created_at": created_at,
                    "result": result})
    return out
