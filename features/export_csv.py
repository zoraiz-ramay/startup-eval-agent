"""Utility functions for CSV export used by the frontend.

This module provides pure‑Python helpers that generate CSV content from a list of
watched company run dictionaries and return the static export‑completion message.
It deliberately avoids any external dependencies so it can be imported safely in
unit tests.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Mapping, Sequence


def generate_csv(watched: Iterable[Mapping[str, object]]) -> str:
    """Return CSV text for the given *watched* runs.

    The expected keys in each mapping are:
        - ``company`` (str)
        - ``final_score`` (numeric)
        - ``pillar`` (str)
        - ``created_at`` (ISO timestamp string)

    The output mirrors the logic in the React component: a header row followed by
    rows containing ``company,score,pillar,last_evaluated`` where ``score`` is the
    integer score rounded to the nearest whole number and ``last_evaluated`` is the
    first ten characters of the ``created_at`` timestamp (YYYY‑MM‑DD).
    """
    header: Sequence[str] = ["company", "score", "pillar", "last_evaluated"]
    output = io.StringIO()
    writer = csv.writer(
        output,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writerow(header)
    for row in watched:
        company = str(row.get("company", ""))
        # ``final_score`` may be missing or non‑numeric; default to empty string
        try:
            value: Any = row.get("final_score", 0)
            score = f"{int(round(float(str(value))))}"
        except Exception:
            score = ""
        pillar = str(row.get("pillar", ""))
        created_at = str(row.get("created_at", ""))
        last_evaluated = created_at[:10]
        writer.writerow([company, score, pillar, last_evaluated])
    return output.getvalue().rstrip("\n")


def exported_message() -> str:
    """Return the static live‑region message announced after export."""
    return "CSV exported"
