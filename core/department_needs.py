"""Department interest terms sourced from Siemens' own stated capability needs.

`api/interests.py`'s ``DEMO`` used to carry five hand-picked keywords per department — a guess at
what "Digital Industries" or "Siemens Mobility" cares about. `Startup_Evaluator_Departmental_
Requirements.xlsx` at the repo root is the real thing: 52 rows of departmental needs Siemens
itself defined, each with a semicolon-separated `Keywords` column. This module turns that sheet
into the same `{department_id: [terms]}` shape the demo list already produces, so the interest
matching in `interest_score()` and the evidence line in `judgment.department_fit()` read Siemens'
actual requirements instead of a placeholder.

Reads the workbook once per process (`lru_cache`) rather than per request — the file does not
change at runtime. Any failure (file missing, sheet renamed, openpyxl broken) degrades to an empty
dict rather than raising, same as the rest of the app when an optional data source is absent
(`GLASSDOLLAR_API_KEY`, described in CLAUDE.md): a laptop or CI without the xlsx must still run.
"""
from __future__ import annotations

import functools
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_XLSX_PATH = Path(__file__).resolve().parent.parent / "Startup_Evaluator_Departmental_Requirements.xlsx"
_SHEET_NAME = "Startup_Needs"

# The sheet's Department values, mapped to the ids interest_score() and department_fit() already
# key on everywhere else.
_DEPARTMENT_IDS = {
    "Smart Infrastructure": "si",
    "Siemens Mobility": "mobility",
    "Digital Industries": "di",
}


@functools.lru_cache(maxsize=1)
def load_department_needs() -> dict:
    """Return ``{department_id: [keyword, ...]}`` from the requirements xlsx, or ``{}`` on any
    failure. Keywords are de-duplicated per department, preserving first-appearance order."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(_XLSX_PATH, read_only=True, data_only=True)
        ws = wb[_SHEET_NAME]
        rows = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(rows)]
        dept_col = header.index("Department")
        keywords_col = header.index("Keywords")

        needs: dict = {}
        for row in rows:
            if dept_col >= len(row) or keywords_col >= len(row):
                continue
            dept_id = _DEPARTMENT_IDS.get(str(row[dept_col]).strip() if row[dept_col] else "")
            if not dept_id:
                continue
            raw = row[keywords_col]
            if not raw:
                continue
            terms = needs.setdefault(dept_id, [])
            for term in str(raw).split(";"):
                term = term.strip()
                if term and term not in terms:
                    terms.append(term)
        return needs
    except Exception:
        log.warning("could not load department needs from %s", _XLSX_PATH, exc_info=True)
        return {}
