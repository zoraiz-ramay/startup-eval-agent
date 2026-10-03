"""Navigation-independent evaluation jobs. Redis holds snapshots, a bounded pool executes work.
In-flight work is not restartable; stale jobs are explicitly marked interrupted, never retried silently.
"""
import json
import contextvars
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from api.auth import Principal, current_user, sessions
from api.workspace import locked

router = APIRouter(prefix="/api/jobs", tags=["workspace"])
# Threads here only wait: how many evaluations actually run at once is api/flight.slot's job,
# shared with the other two entry points. This pool used to BE the limit (2 per worker), which
# queued workspace searches while the stream route ran unbounded.
_slots = threading.BoundedSemaphore(40)
_pool = ThreadPoolExecutor(max_workers=40, thread_name_prefix="evaluation")
TTL = 86400


class JobBody(BaseModel):
    kind: Literal["evaluate", "solve"] = "evaluate"
    names: list[str] = Field(default_factory=list, max_length=10)
    problem: str = Field("", max_length=2000)
    refresh: bool = False
    # Applied to every startup in the batch: one department's search, many startups.
    department_id: str | None = Field(None, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    request_id: str = Field(..., min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9-]+$")


def _key(oid, job_id):
    return f"job:{oid}:{job_id}"


def _execute(oid, job_id, body, user):
    from api.main import evaluate, solve, EvaluateBody, SolveBody, _run_evaluation
    key = _key(oid, job_id)
    record = sessions().get(key)
    if not record:
        _slots.release(); return
    def update(**fields):
        record.update(fields, updated_at=time.time())
        sessions().put(key, json.loads(json.dumps(record, default=str)), TTL)
    try:
        update(status="running")
        if body.kind == "solve":
            result = solve(SolveBody(problem=record["query"]), user)
        else:
            # Preserve partial rendering; use the same source/cache semantics as the public endpoint.
            def partial(section, data):
                previous = record.get("partial") or {"found": True, "streaming": True}
                previous.update(data if section in ("identity", "profile") else {section: data})
                update(partial=previous)
            from api.main import _evaluation_cached
            request = EvaluateBody(name=record["query"], refresh=body.refresh,
                                   department_id=body.department_id)
            result = _evaluation_cached(record["query"], request, user)
            if result is None:
                result = _run_evaluation(record["query"], request, user.as_reviewer(), partial, user)
        update(status="complete", result=result, partial=None)
    except Exception as exc:
        # Do not expose vendor responses or credentials in job errors.
        detail = exc.detail if isinstance(exc, HTTPException) else "Research failed. Please retry this startup."
        update(status="error", error=str(detail), partial=None)
    finally:
        _slots.release()


@router.post("")
def start(body: JobBody, user: Principal = Depends(current_user)):
    values = [body.problem.strip()] if body.kind == "solve" else [v.strip() for v in body.names]
    values = list({v.casefold(): v for v in values}.values())
    if not values or any(not v or len(v) > (2000 if body.kind == "solve" else 200) for v in values):
        raise HTTPException(422, "Provide 1–10 startup names (up to 200 characters each) or a problem.")
    if body.kind == "solve" and len(values[0]) < 3:
        raise HTTPException(422, "Describe the problem in at least three characters.")
    if body.kind == "evaluate":
        from api.main import _department
        _department(body.department_id, user)       # 422 before anything is queued
    dedup = f"job-request:{user.oid}:{body.request_id}"
    with locked(dedup):
        prior = sessions().get(dedup)
        if prior:
            return prior
        acquired = 0
        for _ in values:
            if not _slots.acquire(blocking=False):
                for _ in range(acquired): _slots.release()
                raise HTTPException(429, "The evaluation queue is full. Please try again shortly.")
            acquired += 1
        jobs = []
        for value in values:
            job_id = secrets.token_hex(16)
            row = {"id": job_id, "kind": body.kind, "query": value, "status": "queued",
                   "department_id": body.department_id if body.kind == "evaluate" else None,
                   "updated_at": time.time()}
            sessions().put(_key(user.oid, job_id), row, TTL)
            jobs.append(row)
        response = {"jobs": jobs}
        sessions().put(dedup, response, TTL)
        for row in jobs:
            _pool.submit(contextvars.copy_context().run, _execute, user.oid, row["id"], body, user)
        return response


@router.get("/{job_id}")
def get_job(job_id: str, user: Principal = Depends(current_user)):
    record = sessions().get(_key(user.oid, job_id))
    if not record:
        raise HTTPException(404, "This job has expired or is not in your workspace.")
    if record["status"] in ("queued", "running") and time.time() - record["updated_at"] > 1800:
        record.update(status="error", error="Research was interrupted. Start it again.")
        sessions().put(_key(user.oid, job_id), record, TTL)
    return record
