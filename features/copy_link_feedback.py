"""Utility functions for copy‑link accessible feedback.

This module provides a small, pure‑Python helper that formats the
aria‑live announcement text used when a user copies a startup permalink.
It is deliberately lightweight so it can be imported in tests without
pulling in any heavy application dependencies.
"""

from __future__ import annotations


def copy_feedback_message(company: str) -> str:
    """Return the live‑region message for a copied link.

    Args:
        company: The name of the company whose link was copied.

    Returns:
        A string suitable for an ``aria‑live="polite"`` region, e.g.
        ``"Link for Acme Corp copied"``.
    """
    # Guard against empty or whitespace‑only names – still produce a sensible message.
    name = company.strip() if company else ""
    return f"Link for {name} copied"
