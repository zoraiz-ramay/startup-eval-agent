"""Utility for mapping source quality strings to badge style information.

The mapping mirrors the front‑end badge colors used in
`ui/src/components/ClaimEvidenceMatrix.jsx`. It provides a pure‑Python function
that can be unit‑tested without pulling in heavy application dependencies.
"""

from __future__ import annotations

from typing import Dict

# Mapping from normalized quality strings to style dicts.
_QUALITY_MAP: Dict[str, Dict[str, str]] = {
    "high": {"label": "High", "background": "#d4edda", "color": "#155724"},
    "medium": {"label": "Medium", "background": "#fff3cd", "color": "#856404"},
    "low": {"label": "Low", "background": "#f8d7da", "color": "#721c24"},
}

# Fallback style for unrecognised values.
_FALLBACK_STYLE: Dict[str, str] = {
    "background": "#e0e0e0",
    "color": "#000000",
}


def get_quality_badge(quality: str | None) -> Dict[str, str]:
    """Return a dict describing a badge for the given *quality*.

    The returned dict always contains ``label``, ``background`` and ``color``
    keys. ``label`` is the human‑readable text shown inside the badge. For known
    values ("high", "medium", "low") a specific colour scheme is used; any
    other value falls back to a grey badge while preserving the raw value as the
    label.
    """
    if not quality:
        # Empty or None -> treat as unknown.
        return {"label": "", **_FALLBACK_STYLE}

    key = str(quality).lower()
    base = _QUALITY_MAP.get(key)
    if base:
        return base
    # Unknown quality – preserve original text as label.
    style = _FALLBACK_STYLE.copy()
    style["label"] = str(quality)
    return style
