"""Utility helpers for list‑row keyboard navigation.

The frontend uses a simple check for activation keys (Enter or Space) to trigger a
click on the focused row.  Keeping the logic in a pure‑Python module allows us to
unit‑test it without pulling in any heavy React or application code.
"""

from __future__ import annotations

__all__ = ["is_activation_key"]


def is_activation_key(key: str) -> bool:
    """Return ``True`` if *key* represents a keyboard activation (Enter or Space).

    The browser ``KeyboardEvent.key`` property is ``"Enter"`` for the Enter key and
    either ``" "`` (a single space character) or ``"Space"`` for the space bar.
    This helper normalises those possibilities.
    """
    return key in {"Enter", " ", "Space"}
