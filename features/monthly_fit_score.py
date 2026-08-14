"""
Utility functions for computing monthly average fit scores from a list of runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Mapping, Tuple, cast


def _parse_date(
    run: Mapping[str, object],
    key: str = "created_at",
) -> datetime | None:
    """Extract a datetime from a run dict using the given key."""
    value = run.get(key)
    if not isinstance(value, str):
        return None
    # Try common ISO formats
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # Fallback to fromisoformat (handles offset)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def monthly_average(
    runs: Iterable[Mapping[str, object]],
    date_key: str = "created_at",
) -> List[Tuple[str, float]]:
    """Compute the average ``final_score`` per calendar month.

    Returns a list of (label, average) tuples sorted from oldest to newest,
    where label is formatted as ``Jan 2024``.
    """
    buckets: dict[Tuple[int, int], dict[str, float]] = {}
    for run in runs:
        dt = _parse_date(run, date_key)
        if dt is None:
            continue
        month_key = (dt.year, dt.month)
        raw_score = run.get("final_score", 0)
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)
        else:
            try:
                score = float(cast(str, raw_score))
            except Exception:
                score = 0.0
        if month_key not in buckets:
            buckets[month_key] = {"sum": 0.0, "count": 0}
        buckets[month_key]["sum"] += score
        buckets[month_key]["count"] += 1

    result: List[Tuple[str, float]] = []
    for (year, month), data in buckets.items():
        avg = data["sum"] / data["count"] if data["count"] else 0.0
        label = datetime(year, month, 1).strftime("%b %Y")
        result.append((label, avg))

    # Sort by chronological order
    result.sort(key=lambda x: datetime.strptime(x[0], "%b %Y"))
    return result
