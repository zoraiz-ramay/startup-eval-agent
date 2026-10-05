"""Relevant Siemens contacts for the tools Empower's Tool fit cites.

For each tool the input is its name, category and department — the `division` column of
siemens_tools.csv ("DI SW PLM", "SI B"). The department is kept exactly as supplied and shown as
such: a high-level one ("DI", "SI") is not replaced by a guessed sub-department.

What the directory can say is who works in a department, not who owns a tool, so every contact is
labelled as the app's inference. That matters most for a broad department, which can return many
people: they are ranked by how closely their department matches the tool — an exact or deeper match
of the tool's department first, then departments that name a word of the tool's name or category
("PLM" for a PLM tool), then the more specific department — and only the top few are shown.

The only translation is for the few divisions written as a name rather than a code ("Digital
Industries Software"): the directory files people under codes, so the code is what is searched,
and the result says that mapping was the app's.
"""
from __future__ import annotations

import datetime as dt
import re

from . import config, web
from .directory_api import DirectoryClient, DirectoryError, configured

# Division names in the tools catalogue mapped to the code the directory files people under.
_ALIASES = {"digital industries software": "DI SW", "digital industries": "DI", "smart infrastructure": "SI",
            "siemens eda": "DI SW EDA", "mobility": "MO", "grid software": "SI GSW"}
INFERENCE_NOTE = ("Ranked by the app from how closely each person's department matches the tool's: an "
                  "inference. A matching department shows organisational relevance, not tool ownership.")
_STOP = {"and", "for", "the", "with", "products", "product", "software", "solution", "solutions",
         "service", "services", "siemens", "mgmt", "management", "system", "systems"}


def department_query(department: str) -> tuple[str, bool]:
    """(what to search the directory for, whether the app translated it)."""
    dept = str(department or "").strip()
    code = _ALIASES.get(dept.casefold())
    return (code, True) if code else (dept, False)


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(text or "").casefold()) if len(t) >= 2 and t not in _STOP}


def rank(people: list[dict], tool: dict, query: str) -> list[dict]:
    """The people most likely relevant to ``tool``, best first, at most SIEMENS_CONTACTS_PER_TOOL."""
    want = query.casefold()
    words = _tokens(tool.get("name")) | _tokens(tool.get("category"))

    def score(p):
        dept = str(p.get("department") or "").casefold()
        exact = dept == want
        deeper = bool(want) and dept.startswith(want + " ")
        return (exact or deeper, len(_tokens(dept) & words), len(dept.split()), bool(p.get("email")))

    seen, ranked = set(), []
    for p in sorted(people, key=score, reverse=True):
        key = (p.get("email") or p.get("name") or "").casefold()
        if key in seen:
            continue
        seen.add(key)
        ranked.append(p)
    return ranked[:config.SIEMENS_CONTACTS_PER_TOOL]


def _fresh(entry) -> bool:
    try:
        when = dt.datetime.fromisoformat(entry["fetched_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return (dt.datetime.now(dt.timezone.utc) - when).days < config.SIEMENS_CONTACTS_TTL_DAYS


def contacts_for_tool(tool: dict, client: DirectoryClient | None = None, refresh: bool = False) -> dict:
    department = str(tool.get("division") or "").strip()
    query, translated = department_query(department)
    row = {"tool": tool.get("name", ""), "category": tool.get("category", ""), "department": department,
           "department_query": query, "translated": translated, "contacts": [], "note": ""}
    if not query:
        return {**row, "note": "This tool has no department in the catalogue, so no contact can be looked up."}
    key = web._cache_key("contacts", query, row["tool"], row["category"])
    cached = None if refresh else web._cached("contacts", key)
    if isinstance(cached, dict) and _fresh(cached):
        return {**row, "contacts": cached.get("contacts", [])}
    try:
        people = (client or DirectoryClient()).people_in(query)
    except DirectoryError as e:
        return {**row, "note": f"The directory could not be searched: {e}"}
    contacts = rank(people, tool, query)
    web._store("contacts", key, {"contacts": contacts,
                                 "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    return {**row, "contacts": contacts, "note": "" if contacts else f"Nobody is listed under {query}."}


def contacts(tools: list[dict], client: DirectoryClient | None = None, refresh: bool = False) -> dict:
    """{status, note, tools: [...]} for the tools Tool fit cites. Never raises."""
    tools = [t for t in tools or [] if isinstance(t, dict) and t.get("name")]
    if not tools:
        return {"status": "no_tools", "note": "Tool fit cites no Siemens tool.", "tools": []}
    if client is None and not configured():
        return {"status": "not_configured", "tools": [],
                "note": "The Siemens Directory is not configured (SIEMENS_DIRECTORY_API_KEY)."}
    return {"status": "ok", "note": INFERENCE_NOTE,
            "tools": [contacts_for_tool(t, client, refresh) for t in tools]}
