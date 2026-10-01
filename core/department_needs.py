"""Department needs sourced from Siemens' own stated requirements.

`api/interests.py`'s ``DEMO`` carries five hand-picked keywords per department — a guess at what
"Digital Industries" or "Siemens Mobility" cares about. `data/Startup_Evaluator_Departmental_
Requirements.xlsx` is the real thing: rows of needs Siemens itself defined, each a capability
(with its description and a semicolon-separated `Keywords` column) under a need category. This
module reads it two ways:

- `load_department_requirements()` — the structured needs per department, which the Collaborate
  pillar is assessed against (core/catalogs.py), one catalog entry per capability;
- `load_department_needs()` — the flattened keyword list per department, the same
  `{department_id: [terms]}` shape the demo list produces, for keyword screening.

Read once per process (`lru_cache`) — the file does not change at runtime. Any failure (file
missing, sheet renamed, openpyxl broken) degrades to an empty dict rather than raising, same as the
rest of the app when an optional data source is absent: a laptop or CI without the xlsx must still
run, and the departments fall back to their labelled example needs.
"""
from __future__ import annotations

import functools
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_NAME = "Startup_Evaluator_Departmental_Requirements.xlsx"
_ROOT = Path(__file__).resolve().parent.parent
# data/ beside the other workbooks; the repo root is where it was first dropped, still honoured.
_XLSX_PATH = next((p for p in (_ROOT / "data" / _NAME, _ROOT / _NAME) if p.exists()), _ROOT / "data" / _NAME)
_SHEET_NAME = "Startup_Needs"

# The sheet's Department values, mapped to the ids every other module keys on.
_DEPARTMENT_IDS = {
    "Smart Infrastructure": "si",
    "Siemens Mobility": "mobility",
    "Digital Industries": "di",
}


def _cell(row, col) -> str:
    return str(row[col]).strip() if col is not None and col < len(row) and row[col] is not None else ""


@functools.lru_cache(maxsize=1)
def load_department_requirements() -> dict:
    """``{department_id: {"label", "needs": [{id, need_id, category, category_description,
    capability, description, keywords}]}}`` from the requirements xlsx, or ``{}`` on any failure."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(_XLSX_PATH, read_only=True, data_only=True)
        try:
            rows = wb[_SHEET_NAME].iter_rows(values_only=True)
            header = [str(c).strip() if c is not None else "" for c in next(rows)]
            col = {name: header.index(name) if name in header else None
                   for name in ("Need_ID", "Department", "Need_Category", "Category_Description",
                                "Capability_ID", "Capability", "Capability_Description", "Keywords")}
            if col["Department"] is None or col["Keywords"] is None:
                raise ValueError("requirements sheet lacks Department or Keywords")
            out: dict = {}
            for row in rows:
                label = _cell(row, col["Department"])
                dept_id = _DEPARTMENT_IDS.get(label)
                capability = _cell(row, col["Capability"])
                if not dept_id or not (capability or _cell(row, col["Keywords"])):
                    continue
                keywords = list(dict.fromkeys(k.strip() for k in _cell(row, col["Keywords"]).split(";") if k.strip()))
                out.setdefault(dept_id, {"label": label, "needs": []})["needs"].append({
                    "id": _cell(row, col["Capability_ID"]) or _cell(row, col["Need_ID"]) or capability,
                    "need_id": _cell(row, col["Need_ID"]),
                    "category": _cell(row, col["Need_Category"]),
                    "category_description": _cell(row, col["Category_Description"]),
                    "capability": capability or (keywords[0] if keywords else ""),
                    "description": _cell(row, col["Capability_Description"]),
                    "keywords": keywords,
                })
            return out
        finally:
            wb.close()
    except Exception:
        log.warning("could not load department needs from %s", _XLSX_PATH, exc_info=True)
        return {}


@functools.lru_cache(maxsize=1)
def load_department_needs() -> dict:
    """``{department_id: [keyword, ...]}``, de-duplicated per department in first-appearance order."""
    return {dept: list(dict.fromkeys(k for n in data["needs"] for k in n["keywords"]))
            for dept, data in load_department_requirements().items()}


def clear_cache() -> None:
    load_department_requirements.cache_clear()
    load_department_needs.cache_clear()
