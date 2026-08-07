"""Utility functions for column drawer focus management.

These helpers are deliberately lightweight and pure‑Python so they can be
unit‑tested without pulling in any of the heavy frontend or backend modules.
"""

from typing import Any, List, Optional


def first_column_key(cols: List[Any]) -> Optional[Any]:
    """Return the first column key from the list, or ``None`` if the list is empty.

    The UI uses this to decide which checkbox should receive focus when the
    column drawer opens.
    """
    return cols[0] if cols else None
