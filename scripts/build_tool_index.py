#!/usr/bin/env python3
"""Embed a catalog once for semantic search (core/tool_search.py): siemens_tools.csv into
data/tool_index/ (Empower and the fit stage), the Xcelerator sellers into data/xcelerator_index/
(Connect's ecosystem-gap neighbours), or every department's stated needs into data/needs_index/
(Collaborate's need shortlist).

Run after any change to that catalog. The index records the catalog's checksum, the embedding
model and the vector size; an evaluation uses it only when all three still match, and falls back to
word matching (and says so) when they do not — so a stale index is never used silently.

Tools: about 2,900 short texts, in batches of 100, roughly a minute. Xcelerator: 500 sellers.
Needs: the ~50 capabilities in Startup_Evaluator_Departmental_Requirements.xlsx, a few seconds.

Usage:
    py -3 scripts/build_tool_index.py                       # tools
    py -3 scripts/build_tool_index.py --catalog xcelerator  # Xcelerator sellers
    py -3 scripts/build_tool_index.py --catalog needs       # department needs
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", choices=("tools", "xcelerator", "needs"), default="tools")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import core  # noqa: F401  (loads .env)
    from core import catalogs, tool_search
    from core.llm import LLMClient
    catalog = {"xcelerator": catalogs.xcelerator_catalog, "needs": catalogs.needs_index_catalog,
               "tools": catalogs.tools_catalog}[args.catalog]()
    if not catalog.get("available"):
        print(f"{args.catalog} catalog unavailable:", catalog.get("reason"))
        return 1
    llm = LLMClient()
    started = time.time()
    index = tool_search.build_index(catalog, llm)
    print(f"indexed {len(index.names)} {args.catalog} entries with {index.meta['model']} "
          f"({index.meta['dims']} dims) in {time.time() - started:.0f}s -> {tool_search._dir(catalog)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
