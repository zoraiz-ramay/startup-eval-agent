"""Utility functions for evidence filter UI.

These helpers are pure‑Python and have no external dependencies, making them
easy to test in isolation.
"""

from __future__ import annotations


def should_show_clear_button(filter_text: str) -> bool:
    """Return ``True`` when the clear button should be displayed.

    The button is shown whenever *filter_text* contains any characters. An empty
    string results in ``False``.
    """
    return bool(filter_text)
