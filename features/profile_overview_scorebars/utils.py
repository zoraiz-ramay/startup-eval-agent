"""Utility functions for the Profile Overview ScoreBars feature.

Only standard‑library functionality is used so the module can be imported in
unit tests without pulling in the heavy application dependencies.
"""

from __future__ import annotations


def compute_evidence_strength(verified_facts: int, evidence_count: int) -> int:
    """Return the evidence‑strength percentage.

    The percentage is ``round(verified_facts / evidence_count * 100)``.  If
    ``evidence_count`` is zero the function safely returns ``0``.
    """
    if evidence_count <= 0:
        return 0
    return int(round((verified_facts / evidence_count) * 100))


__all__ = ["compute_evidence_strength"]
