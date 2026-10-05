#!/usr/bin/env python3
"""Fail when a scored dimension has stopped varying across stored runs.

A dimension that returns the same number for every company carries no information, however
carefully it is computed — and nothing in the test suite can notice, because each individual
score is arithmetically correct. Only the distribution across real runs shows it.

Three of these were live at once when this script was written, and every one had survived a full
green test suite for weeks:

* ``ecosystem`` scored exactly 100 in all 18 stored runs. Web presence was a ladder — 30 points
  plus 20 per corroborated search fact — so four facts, which a normal enrichment wave produces
  for almost anybody, already reached 110. The prestige tiers, the self-asserted discount and the
  corporate-parent bonus below it decided nothing at all.
* ``market`` sat at ~70 for everyone, because the trend model returned a momentum of 90, 92, 92
  and 92 for every niche it was ever asked about.
* ``siemens_fit`` varied only with a four-valued relation multiplier, because the fit model
  returned a confidence between 85 and 100 for all 54 matches it has ever made.

Usage:
    py -3 scripts/dimension_variance.py            # report and exit non-zero on a finding
    py -3 scripts/dimension_variance.py --report   # report only, always exit 0
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DB = os.getenv("RUNS_DB", os.path.join(os.path.dirname(__file__), "..", "data", "runs.db"))

# Below this many distinct values a dimension is not telling companies apart. Deliberately a
# COUNT of distinct values rather than a standard deviation: the failure is a dimension pinned at
# one end of its scale, and a handful of runs at 99.8 and 100.0 has a tiny stdev but is genuinely
# discriminating, while eighteen runs at exactly 100 is the bug.
MIN_DISTINCT = 3
# A dimension pinned at either end of its range is a stronger signal than one merely bunched, so
# it is reported even when it clears MIN_DISTINCT.
SATURATION_SHARE = 0.8
# Fewer runs than this cannot support the claim either way; the script says so and passes.
MIN_RUNS = 8


def _load(db_path: str) -> list[dict]:
    if not os.path.exists(db_path):
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT id, company, result_json FROM runs ORDER BY id").fetchall()
    finally:
        con.close()
    out = []
    for rid, company, payload in rows:
        try:
            result = json.loads(payload or "{}")
        except (ValueError, TypeError):
            continue
        # Read the way the app reads it, so `traction` here is the rubric's number. The rubric's
        # divisions are listed too: a division that scores the same for every company (say, every
        # run evidencing ≥ €2M) is the ladder-that-always-maxes-out failure, one level down.
        from core.traction import with_traction
        result = with_traction(result)
        dims = dict((result.get("score") or {}).get("dimensions") or {})
        for d in (result.get("traction") or {}).get("divisions") or []:
            if d.get("points") is not None:
                dims[f"traction.{d['id']}"] = d["points"]
        # Connect's criteria and, from rubric v5, how many sellers already sell the same thing, so
        # the crowded bands (config.CONNECT_CROWDED) are tuned from the distribution rather than
        # argued: a count that is 0 for everyone means no seller is ever labelled same, and one
        # past the last band for everyone means every startup is crowded.
        connect = (((result.get("assessment") or {}).get("pillars") or {}).get("Connect") or {})
        if connect.get("status") == "assessed":
            for c in connect.get("criteria") or []:
                dims[f"connect.{c['id']}"] = c["score"]
            if connect.get("similar"):
                dims["connect.similar_count"] = connect["similar"]["count"]
        if dims:
            out.append({"id": rid, "company": company, "dimensions": dims})
    return out


def analyse(runs: list[dict]) -> list[dict]:
    """One row per dimension: distinct values, spread, and whether it is saturated."""
    names = sorted({k for r in runs for k in r["dimensions"]})
    findings = []
    for name in names:
        values = [float(r["dimensions"][name]) for r in runs if name in r["dimensions"]]
        if not values:
            continue
        distinct = sorted(set(values))
        top = max(values)
        at_top = sum(1 for v in values if v == top) / len(values)
        findings.append({
            "dimension": name,
            "n": len(values),
            "distinct": len(distinct),
            "min": min(values),
            "max": top,
            "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "modal_share": at_top,
            "saturated": (top in (0.0, 100.0) and at_top >= SATURATION_SHARE),
            "flat": len(distinct) < MIN_DISTINCT,
        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="report only; always exit 0")
    ap.add_argument("--db", default=DB)
    args = ap.parse_args()

    runs = _load(args.db)
    if len(runs) < MIN_RUNS:
        print(f"dimension_variance: {len(runs)} scored runs — fewer than {MIN_RUNS}, "
              "not enough to judge a distribution. Passing.")
        return 0

    findings = analyse(runs)
    width = max(len(f["dimension"]) for f in findings)
    print(f"dimension_variance: {len(runs)} scored runs\n")
    print(f"  {'dimension'.ljust(width)}  {'n':>3} {'distinct':>8} {'min':>6} {'max':>6} "
          f"{'stdev':>6}  note")
    problems = []
    for f in findings:
        note = ""
        if f["flat"]:
            note = f"FLAT — only {f['distinct']} distinct value(s); tells companies apart barely"
        elif f["saturated"]:
            note = (f"SATURATED — {f['modal_share']:.0%} of runs sit at {f['max']:g}, "
                    "the end of the scale")
        if note:
            problems.append((f, note))
        print(f"  {f['dimension'].ljust(width)}  {f['n']:>3} {f['distinct']:>8} "
              f"{f['min']:>6.1f} {f['max']:>6.1f} {f['stdev']:>6.1f}  {note}")

    if not problems:
        print("\nEvery dimension varies across the corpus.")
        return 0

    print(f"\n{len(problems)} dimension(s) are not discriminating:")
    for f, note in problems:
        print(f"  - {f['dimension']}: {note}")
    print("\nA dimension that returns the same number for every company contributes nothing to "
          "the score no matter how it is weighted. Either the inputs are saturated (a ladder "
          "that always maxes out, a model that always answers 90) or the dimension is measuring "
          "something every startup has.")
    return 0 if args.report else 1


if __name__ == "__main__":
    raise SystemExit(main())
