"""Which Siemens department a Collaborate candidate belongs to — the registry, and the verdict.

Collaborate is a venture-client programme: Siemens becomes an early customer, so the decision is
not really "is this a good startup" but "does some department want to buy this". `core/programs.py`
already answers half of it — which of the five published innovation domains the company falls in —
and a domain is a category, not a buyer. The other half is per-department, and only Siemens can
supply it.

**The registry below is deliberately empty.** Nothing here invents what a department is looking
for. `DEPARTMENTS = ()` is the honest state until real criteria arrive, and `assess_departments`
reports `configured: False` so the UI says "not yet configured" rather than showing every
department as a non-match — which is the same failure `employees_history_status` and the SFS
`unassessed` state exist to prevent: never report "we looked and the answer is no" for something
nobody ever looked at.

Filling this in is data, not code. One entry per department:

    {"id": "di_factory_automation",              # stable key
     "unit": "Digital Industries",               # the business unit, as Siemens names it
     "department": "Factory Automation",
     "domains": ("automation", "connectivity_iot"),   # ids from programs.COLLABORATE_DOMAINS
     "looking_for": "Flexible cell-level automation that shortens changeover on mixed lines.",
     "criteria": ({"id": "cell_level", "label": "Operates at cell level",
                   "terms": (r"\\bcell\\b", r"work ?cell", r"\\bstation\\b")},),
     "source_url": "https://..."}                # where the criteria came from

Once entries exist, `assess_departments` needs no change: it matches on `domains` and `criteria`
exactly as written here. Pure data and pure predicates; no I/O, no imports from api/.
"""
from __future__ import annotations

import re

import pandas as pd

from .programs import _match, _startup_text, classify_collaborate_domains

# Empty until Siemens' per-department criteria are supplied. See the module docstring for the
# shape; adding entries here is the whole change.
DEPARTMENTS: tuple = ()

# How much of a department's stated criteria a startup has to satisfy before the match is worth a
# reviewer's attention. Thresholds rather than a raw count so a department with two criteria and
# one with eight are read on the same scale.
_STRONG_SHARE = 0.75
_POSSIBLE_SHARE = 0.34


def _assess_one(dept: dict, blob: str, domain_ids: set) -> dict:
    """One department's verdict on one startup."""
    criteria = dept.get("criteria") or ()
    matched, missing = [], []
    for crit in criteria:
        target = matched if _match(blob, crit.get("terms") or ()) else missing
        target.append({"id": crit.get("id", ""), "label": crit.get("label", "")})

    wanted = set(dept.get("domains") or ())
    shared = sorted(wanted & domain_ids)
    share = (len(matched) / len(criteria)) if criteria else 0.0

    # A department that named domains and shares none of them is not a candidate however many
    # keyword criteria happen to hit: the domain is what the programme takes applications under.
    if wanted and not shared:
        fit = "weak"
    elif share >= _STRONG_SHARE and (shared or not wanted):
        fit = "strong"
    elif share >= _POSSIBLE_SHARE or shared:
        fit = "possible"
    else:
        fit = "weak"

    return {"id": dept.get("id", ""), "unit": dept.get("unit", ""),
            "department": dept.get("department", ""),
            "looking_for": dept.get("looking_for", ""),
            "source_url": dept.get("source_url", ""),
            "domains": shared, "fit": fit, "matched": matched, "missing": missing}


def assess_departments(row: pd.Series, profile: dict, fit: dict) -> dict:
    """Per-department verdicts for a Collaborate candidate.

    ``configured`` is the load-bearing field. False means the registry is empty and NOTHING should
    be read into the empty list — no department has declined this startup, because no department
    has been asked. Never raises: a malformed entry costs that entry, not the panel.
    """
    domains = classify_collaborate_domains(row if row is not None else pd.Series(dtype=str),
                                           profile or {}, fit or {})
    domain_ids = {d["id"] for d in domains}
    if not DEPARTMENTS:
        return {"configured": False, "departments": [], "domains": domains}

    blob = _startup_text(row if row is not None else pd.Series(dtype=str), profile or {}, fit or {})
    out = []
    for dept in DEPARTMENTS:
        try:
            out.append(_assess_one(dept, blob, domain_ids))
        except (re.error, TypeError, AttributeError):   # pragma: no cover - defensive
            continue
    # Strongest first: a reviewer reads the top of this list and stops.
    order = {"strong": 0, "possible": 1, "weak": 2}
    out.sort(key=lambda d: (order.get(d["fit"], 3), d.get("unit", ""), d.get("department", "")))
    return {"configured": True, "departments": out, "domains": domains}
