#!/usr/bin/env python3
"""Evaluate known startups ahead of time, so a reviewer's lookup is served from the database.

A fresh evaluation takes about a minute and ~26 model calls; a stored one is instant. Most
lookups are for startups the team already knows — the applications file, a watchlist — so
evaluating those off-peak turns the slow path into the rare one. Runs land in runs.db like any
other and are served while younger than EVAL_TTL_DAYS.

It can never delay a reviewer: each run takes an evaluation slot only when nobody is waiting and
fewer than PREWARM_CONCURRENCY runs (default 2) are active in total (api/flight.slot,
background=True). Run it inside the container, where it shares the API's Redis queue; with
SESSION_BACKEND=memory it only coordinates with itself.

A startup that already has a current all-departments run is skipped, so re-running the script
costs only the startups that went stale. No search is recorded: no reviewer asked.

Usage:
    py -3 scripts/prewarm.py --applications            # every company in the applications file
    py -3 scripts/prewarm.py --names "Phena, Bliro"    # named startups
    py -3 scripts/prewarm.py --file watchlist.txt      # one name per line
    add --dry-run to list what would be evaluated, --limit N to cap a run
"""
from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

log = logging.getLogger("prewarm")


def plan(names, is_current) -> tuple[list[str], list[str]]:
    """(to evaluate, already current), de-duplicated case-insensitively, order kept."""
    seen, todo, fresh = set(), [], []
    for raw in names:
        name = str(raw or "").strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        (fresh if is_current(name) else todo).append(name)
    return todo, fresh


def _names(args) -> list[str]:
    names: list[str] = []
    if args.names:
        names += [n for n in args.names.replace(";", ",").split(",")]
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            names += fh.read().splitlines()
    if args.applications:
        from api import main
        df = main._get_local_df()
        if df is not None and "company_name" in df.columns:
            names += df["company_name"].astype(str).tolist()
    return names


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--names", help="comma-separated startup names")
    ap.add_argument("--file", help="a file with one startup name per line")
    ap.add_argument("--applications", action="store_true", help="every company in the applications file")
    ap.add_argument("--limit", type=int, default=0, help="evaluate at most this many")
    ap.add_argument("--dry-run", action="store_true", help="list what would be evaluated, then stop")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    from api import main as app, store
    departments = app._all_departments(None)
    key = app._all_key(departments)
    todo, fresh = plan(_names(args), lambda n: store.latest_department_run(n, "*", key) is not None)
    if args.limit:
        todo = todo[:args.limit]
    log.info("prewarm: %d to evaluate, %d already current", len(todo), len(fresh))
    if args.dry_run:
        for name in todo:
            print(name)
        return 0

    def one(name):
        started = time.time()
        body = app.EvaluateBody(name=name)
        try:
            res = app._run_evaluation(name, body, {}, departments=departments, background=True)
            log.info("prewarm: %s done in %.0fs (run %s)", name, time.time() - started, res.get("run_id"))
            return True
        except Exception as exc:                     # one bad name must not stop the batch
            log.warning("prewarm: %s failed: %s", name, getattr(exc, "detail", exc))
            return False

    # Threads only wait here; flight.slot decides how many actually run.
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, app.PREWARM_CONCURRENCY)) as ex:
        ok = sum(ex.map(one, todo))
    log.info("prewarm: %d of %d evaluated", ok, len(todo))
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
