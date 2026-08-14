"""Utility functions for aria‑sort handling.

This module provides a pure‑Python helper that can be unit‑tested
independently from the React UI. It mirrors the logic used in the
Explore component to compute the appropriate ARIA sort attribute value.
"""

from __future__ import annotations

from typing import Set


def compute_aria_sort(
    column: str,
    current_sort_key: str,
    current_sort_dir: int,
    sortable_columns: Set[str],
) -> str:
    """Return the ARIA sort value for *column*.

    Parameters
    ----------
    column:
        The column identifier being rendered.
    current_sort_key:
        The column currently used for sorting.
    current_sort_dir:
        ``1`` for ascending, ``-1`` for descending.
    sortable_columns:
        Set of column identifiers that support sorting.

    Returns
    -------
    str
        One of ``"none"``, ``"ascending"`` or ``"descending"``.
    """
    if column not in sortable_columns:
        return "none"
    if column != current_sort_key:
        return "none"
    return "ascending" if current_sort_dir == 1 else "descending"


__all__ = ["compute_aria_sort"]
