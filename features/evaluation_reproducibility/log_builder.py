"""Pure helpers for assembling stable reproducibility log payloads.

The builder is intentionally standard-library only so it can be tested without
loading the FastAPI app or agent stack. Callers may pass partial data from the
existing evaluation pipeline; missing values are normalized to null or empty
arrays to keep the response schema stable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_list_of_strings(value: Optional[Iterable[object]]) -> List[str]:
    """Normalize an iterable into a list of non-empty strings."""
    if value is None:
        return []

    result: List[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def build_reproducibility_log(
    *,
    startup_name: Optional[str] = None,
    query: Optional[str] = None,
    steps_executed: Optional[Iterable[object]] = None,
    source_urls_considered: Optional[Iterable[object]] = None,
    source_urls_used: Optional[Iterable[object]] = None,
    model_identifiers: Optional[Iterable[object]] = None,
    report_id: Optional[str] = None,
    evaluation_id: Optional[str] = None,
    run_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a stable reproducibility log payload.

    All required keys are always present. Unknown data is represented as None or
    an empty list instead of omitting fields.
    """
    considered = _dedupe_preserve_order(
        ensure_list_of_strings(source_urls_considered)
    )
    used = _dedupe_preserve_order(ensure_list_of_strings(source_urls_used))
    steps = ensure_list_of_strings(steps_executed)
    models = _dedupe_preserve_order(ensure_list_of_strings(model_identifiers))

    payload: Dict[str, Any] = {
        "run_id": run_id or str(uuid4()),
        "timestamp": timestamp or _utc_now_iso(),
        "startup_name": startup_name,
        "query": query,
        "steps_executed": steps,
        "source_urls_considered": considered,
        "source_urls_used": used,
        "used_source_count": len(used),
        "model_identifiers": models,
        "report_id": report_id,
        "evaluation_id": evaluation_id,
        "final_report_ref": report_id or evaluation_id,
        "extra": dict(extra or {}),
    }
    return payload
