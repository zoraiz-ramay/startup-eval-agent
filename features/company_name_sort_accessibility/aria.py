"""Utility for determining the appropriate ARIA sort attribute.

This module contains pure‑Python logic that can be unit‑tested without any
framework dependencies. It mirrors the behaviour used in the React UI for
accessible column sorting.
"""

from __future__ import annotations

from typing import Set

__all__ = ["aria_sort"]


def aria_sort(col: str, sort_key: str, sort_dir: int, sortable: Set[str]) -> str:
    """Return the ARIA sort value for a column.

    Args:
        col: Column identifier being queried.
        sort_key: Currently active sort column identifier.
        sort_dir: ``1`` for ascending, ``-1`` for descending.
        sortable: Set of column identifiers that support sorting.

    Returns:
        "none", "ascending", or "descending" according to the ARIA spec.
    """
    if col not in sortable:
        return "none"
    if col != sort_key:
        return "none"
    return "ascending" if sort_dir == 1 else "descending"
