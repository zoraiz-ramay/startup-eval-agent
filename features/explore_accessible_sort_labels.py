"""Utility functions for accessible sort label generation.

This module provides a pure‑Python helper that constructs ARIA label strings for
sortable table columns. It is deliberately lightweight and has no external
dependencies, making it easy to unit‑test.
"""

from __future__ import annotations

__all__ = ["generate_aria_label"]


def generate_aria_label(col_label: str, is_current: bool, direction: int) -> str:
    """Return an appropriate ARIA label for a sortable column.

    Args:
        col_label: Human‑readable column name (e.g., "Fit Score").
        is_current: ``True`` if this column is the active sort key.
        direction: ``1`` for ascending, ``-1`` for descending. Only relevant when
            ``is_current`` is ``True``; otherwise the function assumes the next
            sort will be *ascending*.

    Returns:
        A string suitable for an ``aria-label`` attribute.
    """
    if is_current:
        dir_word = "ascending" if direction == 1 else "descending"
        return f"Sorted by {col_label} {dir_word}"
    # When the column is not currently sorted, the label should describe the
    # action of sorting *by* this column in the default (ascending) direction.
    return f"Sort by {col_label} ascending"

# Example usage (not executed at import time):
# generate_aria_label("Fit Score", True, -1) -> "Sorted by Fit Score descending"
# generate_aria_label("Fit Score", False, 1) -> "Sort by Fit Score ascending"
