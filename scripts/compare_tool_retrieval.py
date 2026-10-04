#!/usr/bin/env python3
"""Does hybrid (semantic + word) tool search find more of the relevant Siemens tools than words alone?

For every stored company (its latest run), build the 20-tool Empower shortlist both ways, from the
run's own stored concepts. One judge call per company labels which tools in the pooled candidates
(the union of both shortlists) a Siemens reviewer would consider relevant — offerable alongside,
integrable with, or competing with the startup. Then, per method:

    recall@20  = relevant tools in its shortlist / relevant tools in the pool
    noise      = shortlist tools judged not relevant

The judge is a model, so this is a proxy, not ground truth; it sees only names and descriptions,
never which method proposed a tool. Spot-check the per-company lists it prints.

Usage:
    py -3 scripts/compare_tool_retrieval.py            # all companies with concepts
    py -3 scripts/compare_tool_retrieval.py --limit 5
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import statistics
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

JUDGE = (
    "A Siemens reviewer is deciding which Siemens tools are relevant to a startup: tools the startup "
    "could be offered alongside, could integrate with or build on, or competes with. Judge ONLY from "
    "the startup description and each tool's own description below; generic overlap (both mention "
    "'industrial' or 'AI') is not relevance.\n\nSTARTUP:\n{startup}\n\nTOOLS:\n{tools}\n\n"
    'Return ONLY JSON {{"relevant": ["T1", ...]}} listing the ids of the relevant tools.'
)


def latest_runs(db: str) -> list[dict]:
    con = sqlite3.connect(db)
    out = {}
    for company, raw in con.execute("SELECT company, result_json FROM runs ORDER BY id"):
        r = json.loads(raw)
        if (r.get("assessment") or {}).get("concepts"):
            out[company.casefold()] = r
    return list(out.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/runs.db")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    import core  # noqa: F401
    from core import catalogs, tool_search
    from core.llm import LLMClient
    from core.pillar_match import shortlist, empower_query
    llm, cat = LLMClient(), catalogs.tools_catalog()
    runs = latest_runs(args.db)[: args.limit or None]
    rows = []
    for r in runs:
        concepts = r["assessment"]["concepts"]
        words = shortlist("Empower", concepts, cat, r)
        semantic, why = tool_search.semantic_ranking(empower_query(r, concepts), cat, llm)
        if semantic is None:
            print(f"{r['company']}: no semantic ranking ({why})")
            continue
        hybrid = shortlist("Empower", concepts, cat, r, semantic=semantic)
        pool = {t["id"]: t for t in words + hybrid}
        order = list(pool.values())
        random.Random(r["company"]).shuffle(order)                     # the judge sees no method order
        tags = {f"T{i + 1}": t for i, t in enumerate(order)}
        tools = "\n".join(f"{k} | {t['name']} | {t['description'][:160]}" for k, t in tags.items())
        data = LLMClient.parse_json(llm.complete(JUDGE.format(startup=str(r.get("summary") or "")[:1500], tools=tools),
                                                 max_tokens=600, reasoning="none")) or {}
        relevant = {tags[k]["id"] for k in data.get("relevant") or [] if k in tags}
        if not relevant:
            print(f"{r['company']}: judge found nothing relevant; skipped")
            continue
        row = {"company": r["company"], "relevant": len(relevant)}
        for name, sl in (("words", words), ("hybrid", hybrid)):
            ids = {t["id"] for t in sl}
            row[f"{name}_recall"] = len(ids & relevant) / len(relevant)
            row[f"{name}_noise"] = len(ids - relevant)
            row[f"{name}_only"] = sorted(t["name"] for t in sl if t["id"] in relevant and t not in (hybrid if name == "words" else words))
        rows.append(row)
        print(f"\n{r['company']}: {len(relevant)} relevant in a pool of {len(pool)}")
        print(f"  words : recall {row['words_recall']:.0%}, noise {row['words_noise']:>2}  | relevant only here: {row['words_only'][:6]}")
        print(f"  hybrid: recall {row['hybrid_recall']:.0%}, noise {row['hybrid_noise']:>2}  | relevant only here: {row['hybrid_only'][:6]}")
    if rows:
        print("\n=== across", len(rows), "companies ===")
        for name in ("words", "hybrid"):
            print(f"{name:>6}: median recall {statistics.median(r[f'{name}_recall'] for r in rows):.0%}, "
                  f"mean recall {statistics.mean(r[f'{name}_recall'] for r in rows):.0%}, "
                  f"mean noise {statistics.mean(r[f'{name}_noise'] for r in rows):.1f} of 20")
        better = sum(r["hybrid_recall"] > r["words_recall"] for r in rows)
        worse = sum(r["hybrid_recall"] < r["words_recall"] for r in rows)
        print(f"hybrid better on {better}, worse on {worse}, equal on {len(rows) - better - worse}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
