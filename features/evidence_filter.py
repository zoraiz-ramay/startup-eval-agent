"""Utility functions for filtering evidence facts.

This module is deliberately lightweight and depends only on the Python
standard library so that it can be imported in unit tests without pulling in
any heavy application dependencies.
"""

from __future__ import annotations

from typing import List, Mapping, Any


def filter_facts(facts: List[Mapping[str, Any]], query: str) -> List[Mapping[str, Any]]:
    """Return a subset of *facts* that match *query*.

    The match is case‑insensitive and checks the ``key``, ``value`` and ``method``
    fields of each fact dictionary. If ``query`` is empty, the original list is
    returned unchanged.
    """
    if not query:
        return facts
    q = query.lower()
    result: List[Mapping[str, Any]] = []
    for f in facts:
        if not isinstance(f, Mapping):
            continue
        if any(q in str(f.get(k, "")).lower() for k in ("key", "value", "method")):
            result.append(f)
    return result


def should_show_clear_button(filter_text: str) -> bool:
    """Return ``True`` when the clear button should be displayed.

    The button is shown whenever *filter_text* contains any characters. An empty
    string results in ``False``.
    """
    return bool(filter_text)
