"""Utility helpers for determining Alerts component UI state.

This module is deliberately pure‑Python and has no external dependencies so it
can be unit‑tested in isolation.
"""

from typing import Any, List, Optional


def get_alerts_state(runs: Optional[List[Any]], error: str) -> str:
    """Return a string representing the UI state for the Alerts page.

    The possible return values are:
    * "loading" – runs is ``None`` and there is no error.
    * "error"   – an error message is present.
    * "empty"   – runs resolved to an empty list (no watched companies).
    * "data"    – runs contains one or more entries.
    """
    if error:
        return "error"
    if runs is None:
        return "loading"
    if len(runs) == 0:
        return "empty"
    return "data"
