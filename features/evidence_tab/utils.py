"""Utility functions for the Evidence Tab feature.

The functions in this module are deliberately pure and have no external
dependencies, making them easy to test with the standard library only.
"""

from typing import List, Dict, Any


def filter_evidence(evidence_list: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Return a filtered list of evidence dictionaries.

    Args:
        evidence_list: A list of dictionaries representing evidence rows.
        query: The search string used to filter rows. Matching is case‑insensitive
            and checks whether *any* value in the dictionary contains the query
            substring.

    Returns:
        A new list containing only the dictionaries that match the query. If
        ``query`` is empty, the original ``evidence_list`` is returned unchanged.
    """
    if not query:
        return evidence_list
    lowered = query.lower()
    filtered: List[Dict[str, Any]] = []
    for item in evidence_list:
        for value in item.values():
            if lowered in str(value).lower():
                filtered.append(item)
                break
    return filtered
