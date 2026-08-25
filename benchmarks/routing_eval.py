"""Measure routing and SFS against human labels.

    py -3 -m benchmarks.routing_eval                 # report
    py -3 -m benchmarks.routing_eval --seed          # add unlabelled entries for new companies
    py -3 -m benchmarks.routing_eval --min-f1 0.6    # non-zero exit below a floor (CI use)

Why this exists
---------------
Every scoring change so far has been argued from a handful of hand-inspected runs. That is enough
to spot a broken formula and not nearly enough to know whether a fix helped: the challenge-library
blend looked reasonable in review and was silently producing every `Pass` verdict in the corpus.
Without labels there is no way to tell an improvement from a change.

The labels are the hard part and they are not something this file can generate. `benchmarks/
labels.json` starts empty of judgements and a reviewer fills in the pillar each company should have
been routed to. Everything here is arithmetic on top of that. The report always leads with coverage
— how many companies are actually labelled — because a precision of 1.00 over three labels is not
a result, and presenting it as one is how a benchmark starts lying.

Reading the output
------------------
Per pillar: precision is "when we said Connect, how often was it Connect", recall is "of the
companies that should have been Connect, how many did we find". They trade off, and which one
matters depends on the pillar — a false Connect wastes a business unit's time, a missed Empower
costs a startup some free software. Both are reported, plus F1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.replay import DEFAULT_DB, load_runs, replay  # noqa: E402

LABELS_PATH = os.path.join(os.path.dirname(__file__), "labels.json")
PILLARS = ("Connect", "Collaborate", "Empower", "Pass")
SFS_VALUES = ("relevant", "not_relevant")

_HEADER = (
    "Ground truth for benchmarks/routing_eval.py. `pillar` is the route a reviewer judges the "
    "company should get; `sfs` is whether Siemens Financial Services is genuinely an avenue. "
    "Leave a field null to mark it unlabelled — the report counts coverage and never guesses. "
    "Add `note` to record why, so a later disagreement is a conversation and not a mystery."
)


# ------------------------------------------------------------------ labels

def load_labels() -> dict:
    try:
        with open(LABELS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"_comment": _HEADER, "labels": []}
    data.setdefault("labels", [])
    return data


def save_labels(data: dict) -> None:
    data["_comment"] = _HEADER
    with open(LABELS_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def seed(runs: list[dict]) -> int:
    """Add an unlabelled entry for every company not already present. Never overwrites."""
    data = load_labels()
    known = {str(e.get("company", "")).strip().lower() for e in data["labels"]}
    added = 0
    for run in runs:
        key = str(run["company"]).strip().lower()
        if key in known:
            continue
        known.add(key)
        data["labels"].append({"company": run["company"], "pillar": None, "sfs": None,
                               "labelled_by": "", "note": ""})
        added += 1
    data["labels"].sort(key=lambda e: str(e.get("company", "")).lower())
    save_labels(data)
    return added


# ------------------------------------------------------------------ metrics

def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def evaluate(pairs: list[tuple[str, str]], classes) -> dict:
    """Per-class precision/recall/F1 plus a confusion matrix, from (truth, predicted) pairs."""
    matrix = {t: {p: 0 for p in classes} for t in classes}
    for truth, predicted in pairs:
        if truth in matrix and predicted in matrix[truth]:
            matrix[truth][predicted] += 1
    per_class = {}
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[t][c] for t in classes if t != c)
        fn = sum(matrix[c][p] for p in classes if p != c)
        precision, recall, f1 = _prf(tp, fp, fn)
        per_class[c] = {"support": sum(matrix[c].values()), "tp": tp, "fp": fp, "fn": fn,
                        "precision": precision, "recall": recall, "f1": f1}
    total = len(pairs)
    correct = sum(matrix[c][c] for c in classes)
    supported = [c for c in classes if per_class[c]["support"]]
    return {
        "n": total,
        "accuracy": correct / total if total else 0.0,
        # Macro, not micro: the corpus is dominated by one pillar, and a micro average would
        # report the majority class's performance as the system's.
        "macro_f1": (sum(per_class[c]["f1"] for c in supported) / len(supported)
                     if supported else 0.0),
        "per_class": per_class,
        "matrix": matrix,
    }


# ------------------------------------------------------------------ report

def _bar(value: float, width: int = 12) -> str:
    filled = int(round(value * width))
    return "#" * filled + "." * (width - filled)


def report(db_path: str = DEFAULT_DB) -> dict:
    runs = load_runs(db_path)
    labels = {str(e.get("company", "")).strip().lower(): e for e in load_labels()["labels"]}

    pillar_pairs, sfs_pairs, unreplayable = [], [], []
    rows = []
    for run in runs:
        label = labels.get(str(run["company"]).strip().lower())
        replayed = replay(run["result"])
        if not replayed:
            unreplayable.append(run["company"])
            continue
        routing = replayed["routing"]
        predicted = routing["pillar"]
        # `conditional` is folded in with `not_relevant`: it means a line might apply but the
        # evidence for it is missing, which is not a recommendation. `unassessed` stays distinct
        # and is excluded from the metrics below — see there.
        sfs_status = str(routing.get("sfs_status") or "unassessed")
        if sfs_status == "conditional":
            sfs_status = "not_relevant"

        truth = (label or {}).get("pillar")
        truth_sfs = (label or {}).get("sfs")
        rows.append({"company": run["company"], "predicted": predicted, "truth": truth,
                     "sfs_predicted": sfs_status, "sfs_truth": truth_sfs,
                     "score": replayed["score"]["final_score"],
                     "status": routing.get("pillar_status", "")})
        if truth in PILLARS:
            pillar_pairs.append((truth, predicted))
        # `unassessed` is excluded from the SFS metrics on purpose: it is the engine declining to
        # answer, and scoring a declined answer as wrong would reward guessing.
        if truth_sfs in SFS_VALUES and sfs_status in SFS_VALUES:
            sfs_pairs.append((truth_sfs, sfs_status))

    return {"runs": rows, "unreplayable": unreplayable,
            "pillar": evaluate(pillar_pairs, PILLARS),
            "sfs": evaluate(sfs_pairs, SFS_VALUES),
            "corpus": len(runs)}


def render(result: dict, brief: bool = False) -> None:
    rows, pillar, sfs = result["runs"], result["pillar"], result["sfs"]
    labelled = sum(1 for r in rows if r["truth"] in PILLARS)
    print(f"routing_eval: {result['corpus']} companies in the corpus, "
          f"{labelled} with a pillar label\n")

    if result["unreplayable"]:
        print(f"  not replayable ({len(result['unreplayable'])}): "
              f"{', '.join(result['unreplayable'][:6])}\n")

    width = max((len(r["company"]) for r in rows), default=7)
    if not brief:
        print(f"  {'company'.ljust(width)}  {'predicted':<12} {'label':<12} {'score':>5}"
              "  agreement")
    for r in [] if brief else sorted(rows, key=lambda x: x["company"].lower()):
        if r["truth"] is None:
            mark = "unlabelled"
        elif r["truth"] == r["predicted"]:
            mark = "match"
        else:
            mark = "MISS"
        print(f"  {r['company'][:width].ljust(width)}  {r['predicted']:<12} "
              f"{str(r['truth'] or '—'):<12} {r['score']:>5.1f}  {mark}")

    if not labelled:
        print("  Nothing to measure: no company carries a pillar label, so the engine is only\n"
              "  agreeing with itself. Fill in `pillar` for each company in\n"
              f"  benchmarks/labels.json ({', '.join(PILLARS)}) and re-run.\n"
              "  Around 30 labelled companies is where the per-pillar numbers start to mean\n"
              "  something; below about 10 they move several points on a single disagreement.")
        return

    print(f"\n  PILLAR — {pillar['n']} labelled, accuracy {pillar['accuracy']:.2f}, "
          f"macro F1 {pillar['macro_f1']:.2f}")
    print(f"  {'':<14}{'n':>4} {'precision':>10} {'recall':>8} {'f1':>6}")
    for name, m in pillar["per_class"].items():
        if not m["support"] and not m["fp"]:
            continue
        print(f"  {name:<14}{m['support']:>4} {m['precision']:>10.2f} {m['recall']:>8.2f} "
              f"{m['f1']:>6.2f}  {_bar(m['f1'])}")

    print("\n  confusion (rows = label, cols = predicted)")
    header = "".join(f"{p[:6]:>8}" for p in PILLARS)
    print(f"  {'':<14}{header}")
    for truth in PILLARS:
        cells = "".join(f"{pillar['matrix'][truth][p]:>8}" for p in PILLARS)
        print(f"  {truth:<14}{cells}")

    if sfs["n"]:
        print(f"\n  SFS — {sfs['n']} labelled, accuracy {sfs['accuracy']:.2f}")
        for name, m in sfs["per_class"].items():
            print(f"  {name:<14}{m['support']:>4} {m['precision']:>10.2f} {m['recall']:>8.2f} "
                  f"{m['f1']:>6.2f}")
    else:
        print("\n  SFS — no labels. Set `sfs` to \"relevant\" or \"not_relevant\" to measure it; "
              "leave it null\n        where the answer is genuinely unclear.")

    if labelled < 10:
        print(f"\n  Caveat: {labelled} labels. Every figure above moves by several points on one\n"
              "  disagreement. Treat it as a smoke test, not a measurement.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--seed", action="store_true",
                    help="add unlabelled entries for companies not yet in labels.json")
    ap.add_argument("--min-f1", type=float, default=None,
                    help="exit non-zero if macro F1 falls below this (needs labels)")
    ap.add_argument("--brief", action="store_true",
                    help="skip the per-company table; headline and metrics only")
    ap.add_argument("--json", action="store_true", help="emit the raw result as JSON")
    args = ap.parse_args()

    if args.seed:
        added = seed(load_runs(args.db))
        print(f"routing_eval: added {added} unlabelled entr{'y' if added == 1 else 'ies'} "
              f"to {os.path.relpath(LABELS_PATH, _ROOT)}")
        if added:
            print("  Fill in `pillar` (and optionally `sfs`) for each, then re-run without --seed.")
        return 0

    result = report(args.db)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    render(result, brief=args.brief)

    if args.min_f1 is not None:
        if not result["pillar"]["n"]:
            print(f"\n  --min-f1 {args.min_f1} requested but nothing is labelled; not failing on "
                  "an absence of ground truth.")
            return 0
        if result["pillar"]["macro_f1"] < args.min_f1:
            print(f"\n  FAIL: macro F1 {result['pillar']['macro_f1']:.2f} "
                  f"is below the floor of {args.min_f1:.2f}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
