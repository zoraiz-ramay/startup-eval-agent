"""Utility functions for the alerts‑export‑csv feature.

Only standard‑library imports are used so the module can be imported in tests
without pulling in the heavy application dependencies.
"""

import csv
import io
from typing import Iterable, Mapping


def generate_tracked_companies_csv(watched: Iterable[Mapping[str, object]]) -> str:
    """Return a CSV string for a collection of watched company records.

    Each record must provide the keys ``company``, ``score``, ``pillar`` and
    ``last_evaluated``. The function is tolerant of missing keys – it will emit an
    empty string for any missing value.

    Parameters
    ----------
    watched:
        An iterable of mappings (e.g. ``dict``) representing the watched rows.

    Returns
    -------
    str
        CSV formatted text with a header row followed by one row per record.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    # Header as required by the specification
    writer.writerow(["company", "score", "pillar", "last_evaluated"])  # noqa: WPS601

    for row in watched:
        writer.writerow([
            row.get("company", ""),
            row.get("score", ""),
            row.get("pillar", ""),
            row.get("last_evaluated", ""),
        ])
    return output.getvalue()
