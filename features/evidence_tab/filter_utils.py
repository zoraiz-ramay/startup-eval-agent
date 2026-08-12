"""Utility functions for EvidenceTab filtering.

These functions are pure Python and have no external dependencies, making them
easy to test in isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List


def filter_evidence(
    evidence_list: List[Dict[str, Any]], filter_str: str
) -> List[Dict[str, Any]]:
    """Return items whose any value contains *filter_str* case‑insensitively.

    An empty *filter_str* returns a shallow copy of *evidence_list*.
    """
    lowered = filter_str.lower()
    if not lowered:
        return evidence_list[:]
    result: List[Dict[str, Any]] = []
    for item in evidence_list:
        for value in item.values():
            if lowered in str(value).lower():
                result.append(item)
                break
    return result


def is_empty_after_filter(
    evidence_list: List[Dict[str, Any]], filter_str: str
) -> bool:
    """Return ``True`` when a non‑empty filter yields no matching rows."""
    if not filter_str:
        return False
    return len(filter_evidence(evidence_list, filter_str)) == 0
