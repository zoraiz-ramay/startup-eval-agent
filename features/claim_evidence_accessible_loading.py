"""Utility helpers for ClaimEvidenceMatrix accessibility attributes.

The functions in this module are pure‑Python and have no external
dependencies, making them easy to test with standard Pytest.
"""

from typing import Dict


def get_aria_props(loading: bool, error: str) -> Dict[str, str]:
    """Return ARIA attributes for the ClaimEvidenceMatrix component.

    Args:
        loading: ``True`` when the component is fetching data.
        error:   Non‑empty error message indicating a failure state.

    Returns:
        A dictionary mapping attribute names to values. Empty when no
        special ARIA attributes are required.
    """
    if loading:
        return {"role": "status", "aria-live": "polite"}
    if error:
        return {"role": "alert"}
    return {}
