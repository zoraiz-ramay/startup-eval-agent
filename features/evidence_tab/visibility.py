"""Utility functions for the EvidenceTab UI component.

This module is deliberately lightweight and contains only pure‑Python logic
that can be unit‑tested without requiring the heavy frontend or backend stack.
"""

from __future__ import annotations


def should_show_clear_button(filter_text: str) -> bool:
    """Return ``True`` when a clear button should be displayed.

    The UI shows the clear (✕) button only when the filter input contains any
    characters. An empty string (or a string consisting solely of whitespace)
    results in the button being hidden.

    Parameters
    ----------
    filter_text: str
        The current value of the filter input.

    Returns
    -------
    bool
        ``True`` if ``filter_text`` is non‑empty after stripping whitespace.
    """
    return bool(filter_text.strip())
