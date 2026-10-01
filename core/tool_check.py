"""Does a Siemens tool from siemens_tools.csv actually exist?

Empower recommends a tool from the catalog, and a catalog row can be wrong — a renamed product, a
typo, an internal codename. Before a tool is put in front of a reviewer it is looked up once with
the model's own web search, and the answer is one of three:

- `verified`  — a cited page describes it as a Siemens offering;
- `not_found` — the search says no such Siemens offering exists (cited or not, that is the answer);
- `unchecked` — no search could be made (no web search on this model, or it timed out). That is
  NOT a finding about the tool, so it neither removes the recommendation nor flags the catalog.

Checks are cached by tool id, so each catalog row is searched once, not on every run.
"""
from __future__ import annotations

import concurrent.futures
import contextvars
import datetime
import re
from urllib.parse import urlparse

from . import web

VERSION = "tool-check-v1"


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def verify_tool(entry: dict, llm) -> dict:
    """{'id', 'name', 'status', 'url', 'note', 'checked_at'} for one catalog tool entry."""
    base = {"id": entry.get("id", ""), "name": entry.get("name", ""), "category": entry.get("category", ""),
            "division": entry.get("division", ""), "url": "", "note": ""}
    key = web._cache_key(VERSION, base["id"] or base["name"].lower())
    cached = web._cached("tool_check", key)
    if isinstance(cached, dict) and cached.get("status") in ("verified", "not_found"):
        return cached
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not (llm and getattr(llm, "available", False) and callable(getattr(llm, "web_answer", None))):
        return {**base, "status": "unchecked", "note": "No web search available.", "checked_at": now}
    desc = str(entry.get("description") or "")[:160]
    answer = llm.web_answer(
        f'Is there a Siemens product, software or service named "{base["name"]}"'
        + (f" (described in a catalog as: {desc})" if desc else "")
        + "? Start your answer with exactly FOUND or NOT FOUND on its own line. Then, in one sentence, say "
        "what it is — citing the official Siemens page if there is one — or what it was confused with.",
        max_tokens=400)
    if not isinstance(answer, dict) or not str(answer.get("text") or "").strip():
        return {**base, "status": "unchecked", "note": "The web search did not answer.", "checked_at": now}
    head = str(answer["text"]).strip()[:80].upper()
    sources = [s for s in answer.get("sources") or [] if isinstance(s, dict) and s.get("url")]
    if "NOT FOUND" in head:
        status = "not_found"
    elif re.search(r"\bFOUND\b", head) and sources:
        status = "verified"
    else:
        status = "unchecked"            # an answer we cannot read either way proves nothing
    siemens = next((s for s in sources if "siemens" in (s.get("title", "") + _host(s["url"])).lower()), None)
    out = {**base, "status": status, "url": (siemens or (sources[0] if sources else {})).get("url", ""),
           "note": re.sub(r"\s+", " ", str(answer["text"]).split("\n", 1)[-1]).strip()[:300], "checked_at": now}
    if status != "unchecked":
        web._store("tool_check", key, out)
    return out


def verify_tools(entries: list[dict], llm) -> dict:
    """{tool id: check} for several tools, searched in parallel."""
    unique = {e["id"]: e for e in entries if e.get("id")}
    if not unique:
        return {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(unique))) as pool:
        futures = {i: pool.submit(contextvars.copy_context().run, verify_tool, e, llm) for i, e in unique.items()}
        return {i: f.result() for i, f in futures.items()}
