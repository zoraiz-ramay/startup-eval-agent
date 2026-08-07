"""Utility helpers for keyboard navigation.

Provides a small pure‑python function used by tests to verify which key
presses should activate a navigation action.
"""

from __future__ import annotations


def is_activation_key(key: str) -> bool:
    """Return ``True`` if *key* should trigger navigation.

    The UI treats the *Enter* key and the space character (``" "``) as
    activation keys for a table row.
    """
    return key in ("Enter", " ")
