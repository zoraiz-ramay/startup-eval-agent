"""Private run storage and durable job snapshots in the existing Redis backend."""
import json
import hashlib
import secrets
import threading
from contextlib import contextmanager
from api.auth import sessions

TTL = 30 * 86400
_lock = threading.RLock()


@contextmanager
def locked(key, timeout=30, blocking_timeout=5):
    backend = sessions()
    lock = backend._client.lock("workspace-lock:" + key, timeout=timeout, blocking_timeout=blocking_timeout) if hasattr(backend, "_client") else _lock
    with lock:
        yield


def private_save(oid, name, result):
    run_id = -secrets.randbelow(2**52 - 1) - 1
    result = json.loads(json.dumps(result, default=str))
    result = {**result, "run_id": run_id, "private": True, "retention_days": 30}
    sessions().put(f"private-run:{oid}:{run_id}", result, TTL)
    # Filed under the department too: a private run for one department is not another's result.
    sessions().put(alias_key(oid, name, (result.get("department") or {}).get("id", "")), {"id": run_id}, TTL)
    with locked(oid):
        index = sessions().get("private-runs:" + oid) or {"ids": []}
        index["ids"] = [run_id, *index["ids"]][:100]
        sessions().put("private-runs:" + oid, index, TTL)
    return result


def alias_key(oid, name, department_id=""):
    digest = hashlib.sha256(name.strip().casefold().encode()).hexdigest()
    return f"private-alias:{oid}:{digest}" + (f":{department_id}" if department_id else "")


def private_latest(oid, name, department_id="", assessment_key=None):
    ref = sessions().get(alias_key(oid, name, department_id)) or {}
    run = private_get(oid, ref.get("id")) if ref else None
    if run and assessment_key and (run.get("assessment") or {}).get("assessment_key") != assessment_key:
        return None
    return run


def private_get(oid, run_id):
    from core.assessment import hydrate
    run = sessions().get(f"private-run:{oid}:{run_id}")
    return hydrate(run) if run else run


def private_list(oid):
    out = []
    for run_id in (sessions().get("private-runs:" + oid) or {}).get("ids", []):
        r = private_get(oid, run_id)
        if r:
            out.append({"id": run_id, "company": r["company"], "summary": r.get("summary", ""),
                "final_score": r.get("score", {}).get("final_score", 0), "pillar": r.get("routing", {}).get("pillar", ""),
                "created_at": r.get("run_created_at", ""), "private": True,
                "siemens_fit": r.get("score", {}).get("dimensions", {}).get("siemens_fit"),
                "department_assessments": r.get("department_assessments", {}),
                "hq": r.get("profile", {}).get("hq", ""), "dimensions": r.get("score", {}).get("dimensions", {}),
                "department_id": (r.get("department") or {}).get("id", ""),
                "department_label": (r.get("department") or {}).get("label", ""),
                "legacy": not r.get("department"),
                "total_status": (r.get("assessment") or {}).get("total_status", "")})
    return out


def private_assessment(oid, run_id, score, department_fit, routing=None):
    from api.store import merge_assessment
    with locked(f"private-assessment:{oid}:{run_id}"):
        result = private_get(oid, run_id)
        if result is None: return None
        result = merge_assessment(result, score, department_fit, routing)
        sessions().put(f"private-run:{oid}:{run_id}", result, TTL)
        return result
