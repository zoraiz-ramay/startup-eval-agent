"""Utility logic for determining radar visibility.

This module provides a pure‑Python function that can be unit‑tested
without any heavy application dependencies. It checks whether a
run dictionary contains any of the dimension fields required for the
radar chart.
"""

from __future__ import annotations

from typing import Any, Mapping

_DIMENSION_FIELDS = {
    "traction",
    "market",
    "product",
    "founder",
    "ecosystem",
    "siemens_fit",
}


def should_show_radar(run: Mapping[str, Any] | None) -> bool:
    """Return ``True`` if *run* has at least one non‑null dimension field.

    Parameters
    ----------
    run:
        Mapping representing a run object returned from the API. ``None``
        or an empty mapping results in ``False``.
    """
    if not run:
        return False
    for field in _DIMENSION_FIELDS:
        if field in run and run[field] is not None:
            return True
    return False
