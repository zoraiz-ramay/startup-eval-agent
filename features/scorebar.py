"""Utility functions for the ScoreBar component.

The UI component lives in the JavaScript/React layer, but the clamping logic
that constrains a raw score to the 0‑100 range is useful in other contexts and
can be unit‑tested without pulling in the heavy frontend stack.
"""

from __future__ import annotations


def clamp_score(value: float | int | str) -> int:
    """Return *value* clamped to the integer range 0‑100.

    The function mirrors the behaviour of the JavaScript ``ScoreBar`` component:
    * ``value`` is coerced to ``float`` (or ``int``) – non‑numeric inputs become ``0``.
    * The result is bounded between ``0`` and ``100`` inclusive.
    * The final return type is ``int`` for easy consumption.
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = 0.0
    # Clamp to [0, 100]
    if num < 0:
        return 0
    if num > 100:
        return 100
    return int(num)
