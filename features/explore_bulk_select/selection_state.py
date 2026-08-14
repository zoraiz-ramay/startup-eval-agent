"""Utility functions for bulk‑selection checkbox state.

These helpers are pure Python and depend only on the standard library. They are used
by the React component to decide which ARIA attributes to apply and whether the
checkbox should be rendered in an indeterminate state.

Functions
---------
- ``is_all_selected``: ``True`` when every item is selected.
- ``is_some_selected``: ``True`` when at least one but not all items are selected.
- ``get_aria_checked``: Returns the string value for ``aria‑checked`` ("true",
  "false", or "mixed").
- ``get_indeterminate``: Returns ``True`` when the indeterminate visual cue
  should be shown.
"""

from __future__ import annotations

from typing import Any, Set


def is_all_selected(selected: Set[Any], total: int) -> bool:
    """Return ``True`` if *selected* contains *total* items.

    ``total`` may be ``0``; in that case the function returns ``False`` because there
    is nothing to select.
    """
    return total > 0 and len(selected) == total


def is_some_selected(selected: Set[Any], total: int) -> bool:
    """Return ``True`` when at least one item is selected but not all.
    """
    return 0 < len(selected) < total


def get_aria_checked(selected: Set[Any], total: int) -> str:
    """Return the appropriate ``aria‑checked`` value.

    * "true"  – all items selected.
    * "mixed" – partially selected.
    * "false" – none selected.
    """
    if is_all_selected(selected, total):
        return "true"
    if is_some_selected(selected, total):
        return "mixed"
    return "false"


def get_indeterminate(selected: Set[Any], total: int) -> bool:
    """Return ``True`` when the checkbox should be rendered indeterminate.
    """
    return is_some_selected(selected, total)
