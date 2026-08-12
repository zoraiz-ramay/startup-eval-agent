"""Utility functions for the AssistantDock auto‑focus feature.

The UI component uses a simple rule: when the dock becomes visible
(`dockOpen` is ``True``) the input field should receive focus.  This module
exposes the decision logic as a pure‑Python function so it can be unit‑tested
without pulling in any front‑end dependencies.
"""

from __future__ import annotations


def should_focus(dock_open: bool) -> bool:
    """Return ``True`` when the input should be auto‑focused.

    The current policy is straightforward – focus when the dock is open.
    The function exists mainly to provide a testable unit of logic.

    Args:
        dock_open: ``True`` if the assistant dock is currently open.

    Returns:
        ``True`` if focus should be applied, ``False`` otherwise.
    """
    return bool(dock_open)
