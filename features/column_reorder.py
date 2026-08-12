"""Utility functions for column reordering UI logic.

These helpers are pure‑Python and have no external dependencies, making them
suitable for unit testing without pulling in the React frontend or heavy
application code.
"""

from __future__ import annotations


def is_move_up_disabled(index: int, length: int) -> bool:
    """Return ``True`` if the *Move up* button should be disabled.

    The button is disabled when the column is already at the top of the list.

    Args:
        index: Zero‑based position of the column in the current ordering.
        length: Total number of columns.
    """
    return index <= 0


def is_move_down_disabled(index: int, length: int) -> bool:
    """Return ``True`` if the *Move down* button should be disabled.

    The button is disabled when the column is at the bottom of the list.

    Args:
        index: Zero‑based position of the column.
        length: Total number of columns.
    """
    return index >= length - 1


__all__ = ["is_move_up_disabled", "is_move_down_disabled"]
