"""A refresh adds evidence; it never quietly loses what an earlier run of the same company found.

Each evaluation is a fresh sample of the web, and the newest one used to replace everything shown.
Across stored runs, Radical Dot's investors went 8 → 8 → 3 → 0 → 2 → 2 → 2 → 4 → 2 → 6 and Phena's
programmes 6 → 2: a reviewer refreshing a company could watch sourced evidence disappear.

This module merges the prior runs of a company into a fresh one. Like core/profile.py it
TRANSCRIBES — no I/O, no model, no judgement — so every rule below is about which evidence to keep,
never about what the evidence means:

- **Lists** (people, programmes, investors, competitors, headcount points) are a union keyed on
  identity. An item this run found again is current; an item only earlier runs found is kept, with
  its own source URL and ``last_confirmed_at`` — the date a run last found it — so the page can say
  so rather than present it as freshly confirmed.
- **Carried items must pass today's grounding**: an http source on the item itself. Runs made under
  older, weaker gates must not resurrect evidence those gates should have dropped.
- **Single values**: a blank or unsourced fresh value never replaces a sourced earlier one; when
  both are sourced the newer wins (fresh retrieval is the later date), and the value it replaced is
  kept in ``history`` with its source. A web value always beats an ``*_origin="llm"`` recall.
- **Market size / CAGR older than 18 months is dropped** — fresh or carried. A year-only ``as_of``
  counts as 31 December of that year.
- **Identity first**: a prior run is used only if it is the same company (same registrable domain,
  or, with no domain on either side, the same normalised name). A namesake's investors are worse
  than none.

Not carried: free-text string lists (``reference_customers``), which carry no per-item source to
re-check, and anything model-judged (fit, pillars, scores), which is recomputed from the merged
evidence.
"""
from __future__ import annotations

import copy
import datetime as _dt
import re
from urllib.parse import urlparse

MARKET_MAX_AGE_DAYS = 548                    # 18 months

# (container path in the profile result, key fields that identify an item)
_PROFILE_LISTS = (
    (("founders",), ("name",)),
    (("key_team",), ("name",)),
    (("advisors",), ("name",)),
    (("programs",), ("name",)),
    (("commercial", "investors"), ("name",)),
    (("employees_over_time",), ("date", "source_url")),
)
_TREND_LISTS = (
    (("landscape", "competitors"), ("name",)),
    (("landscape", "funded_peers"), ("company",)),
    (("landscape", "active_investors"), ("name",)),
)
# Single values and where their source is recorded. "facts" names the fact keys in the same run
# that evidence the value; "source" a sibling *_source field; "origin" a sibling *_origin field.
_SCALARS = (
    (("hq",), {"origin": "hq_origin", "facts": ("hq", "location_research")}),
    (("founded_year",), {"facts": ("founded_year", "founded_year_research")}),
    (("funding",), {"facts": ("funding", "funding_research")}),
    (("employees",), {"facts": ("employees", "employees_research")}),
    (("linkedin_url",), {"origin": "linkedin_url_origin"}),
    (("crunchbase_url",), {"origin": "crunchbase_url_origin"}),
    (("parent_group",), {"facts": ("parent_group",)}),
    (("customer_segment",), {"source": "customer_segment_source"}),
    (("linkedin_size_band",), {"source": "linkedin_size_source"}),
    (("commercial", "deployment"), {"source": "deployment_source"}),
    (("commercial", "has_public_api"), {"source": "api_source", "facts": ("public_api",)}),
    (("commercial", "pricing_public"), {"source": "pricing_source"}),
    (("commercial", "sells_hardware"), {"source": "hardware_source"}),
    (("commercial", "revenue_signal"), {"source": "revenue_source", "facts": ("revenue_signal",)}),
    (("commercial", "funding_stage"), {"facts": ("funding_stage",)}),
)


# ----------------------------------------------------------------------------------- helpers

def _http(url) -> bool:
    return str(url or "").strip().lower().startswith(("http://", "https://"))


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).strip()


def _get(d: dict, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _set(d: dict, path, value) -> None:
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def _blank(value) -> bool:
    return value is None or value is False or (isinstance(value, (str, list, dict)) and not value) \
        or str(value).strip().lower() in ("", "nan", "none")


def _domain(url) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    host = urlparse(raw if "//" in raw else "//" + raw).netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _own_domain(domain: str, name: str) -> bool:
    """Whether a domain plausibly belongs to the company rather than a page ABOUT it.

    A run's website field is sometimes a directory listing — Makkook AI's latest run recorded
    clutch.co/profile/makkook-ai — and comparing that against makkook.ai would call one company
    two. A domain counts as the company's own only when its label carries a word of the name.
    """
    label = domain.split(".")[0].replace("-", "")
    return any(len(t) >= 3 and t in label for t in name.split())


def identity(company: str, *urls) -> dict:
    name = _norm(company)
    return {"name": name, "domain": next((d for d in map(_domain, urls) if d and _own_domain(d, name)), "")}


def _run_identity(run: dict) -> dict:
    prof, dp = run.get("profile") or {}, run.get("deep_profile") or {}
    return identity(run.get("company") or prof.get("company_name", ""),
                    prof.get("website"), prof.get("domain"), dp.get("website"))


def same_company(a: dict, b: dict) -> bool:
    """Two own domains must agree; without one on either side, the full normalised name must."""
    if a["domain"] and b["domain"]:
        return a["domain"] == b["domain"]
    return bool(a["name"]) and a["name"] == b["name"]


def _when(run: dict) -> str:
    return str(run.get("run_created_at") or run.get("created_at") or "")


def _item_key(item, fields) -> tuple:
    if not isinstance(item, dict):
        return ()
    return tuple(_norm(item.get(f)) if f != "source_url" else str(item.get(f) or "").strip()
                 for f in fields)


def _grounded(item) -> bool:
    """Today's bar for a carried list item: it names its own http source."""
    return isinstance(item, dict) and (_http(item.get("source_url")) or _http(item.get("linkedin")))


def _sourced(container: dict, path, spec: dict, facts: list) -> bool:
    parent = _get(container, path[:-1]) if len(path) > 1 else container
    parent = parent if isinstance(parent, dict) else {}
    if spec.get("origin") and parent.get(spec["origin"]) == "web":
        return True
    if spec.get("source") and _http(parent.get(spec["source"])):
        return True
    keys = set(spec.get("facts", ()))
    return any(f.get("key") in keys and _backed(f) for f in facts or ())


def _backed(fact: dict) -> bool:
    """A fact with a source: a web URL, or the database / application form it came from.

    GlassDollar facts carry source_url "GlassDollar", not a URL. They are the most authoritative
    source a run has (the database wins over web extraction), so treating them as unsourced would
    let an older web value overwrite the database.
    """
    return _http(fact.get("source_url")) \
        or str(fact.get("method", "")).startswith(("glassdollar", "tracxn")) \
        or fact.get("source_type") in ("private", "self_reported")


def _facts_of(run_like: dict) -> list:
    return [f if isinstance(f, dict) else f.as_dict() for f in run_like.get("facts") or ()]


# ------------------------------------------------------------------------------- list merging

def _merge_list(fresh_items, prior_runs, path, fields, getter, now: str, report: dict, label: str):
    """Fresh items first (current), then every grounded item only earlier runs found."""
    fresh_items = list(fresh_items or [])
    seen = {_item_key(i, fields) for i in fresh_items if _item_key(i, fields)}
    carried: dict = {}
    for run in prior_runs:                                  # oldest → newest: later runs win
        for item in getter(run, path) or []:
            key = _item_key(item, fields)
            if not key or not any(key) or key in seen or not _grounded(item):
                continue
            entry = copy.deepcopy(item)
            entry["last_confirmed_at"] = item.get("last_confirmed_at") or _when(run)
            carried[key] = entry
    reconfirmed = 0
    for item in fresh_items:
        if isinstance(item, dict):
            reconfirmed += any(_item_key(item, fields) == _item_key(i, fields)
                               for run in prior_runs for i in getter(run, path) or [])
            item.pop("last_confirmed_at", None)             # found by this run: it is current
    report[label] = {"new": len(fresh_items) - reconfirmed, "reconfirmed": reconfirmed,
                     "carried": len(carried)}
    return fresh_items + list(carried.values())


def _profile_of(run: dict) -> dict:
    return run.get("deep_profile") or {}


# ----------------------------------------------------------------------------------- public API

def usable_priors(prior_runs, fresh_identity: dict) -> list:
    """The prior runs that are the same company, oldest first."""
    runs = [r for r in prior_runs or () if isinstance(r, dict) and same_company(_run_identity(r), fresh_identity)]
    return sorted(runs, key=_when)


def merge_profile(fresh: dict, prior_runs: list, now: str, report: dict) -> dict:
    """``fresh`` is research_profile's result: {"profile": deep_profile, "facts": [...], ...}."""
    if not prior_runs:
        return fresh
    out = dict(fresh)
    dp = copy.deepcopy(fresh.get("profile") or {})
    fresh_facts = _facts_of(fresh)
    for path, fields in _PROFILE_LISTS:
        merged = _merge_list(_get(dp, path), prior_runs, path, fields,
                             lambda run, p: _get(_profile_of(run), p), now, report, ".".join(path))
        if merged or _get(dp, path) is not None:
            _set(dp, path, merged)
    history = dp["history"] if isinstance(dp.get("history"), dict) else {}
    for path, spec in _SCALARS:
        fresh_val = _get(dp, path)
        fresh_ok = not _blank(fresh_val) and _sourced(dp, path, spec, fresh_facts)
        best = None                                          # newest sourced prior value
        for run in prior_runs:
            pdp, val = _profile_of(run), _get(_profile_of(run), path)
            if not _blank(val) and _sourced(pdp, path, spec, _facts_of(run)):
                best = (val, run, pdp)
        if best is None:
            continue
        val, run, pdp = best
        name = ".".join(path)
        if fresh_ok:
            if _norm(val) != _norm(fresh_val):
                history.setdefault(name, []).append({"value": val, "replaced_at": now,
                                                     "found_at": _when(run)})
            continue
        # Blank, unsourced, or an *_origin="llm" recall on this run: the sourced value stands.
        if not _blank(fresh_val):
            history.setdefault(name, []).append({"value": fresh_val, "replaced_at": now,
                                                 "reason": "unsourced on this run"})
        _set(dp, path, copy.deepcopy(val))
        for side in ("origin", "source"):
            if spec.get(side):
                sib = path[:-1] + (spec[side],)
                _set(dp, sib, _get(pdp, sib))
        dp.setdefault("carried_fields", {})[name] = _when(run)
        report.setdefault("fields_carried", []).append(name)
    if history:
        dp["history"] = history
    out["profile"] = dp
    out["facts"] = list(fresh.get("facts") or []) + _carried_facts(fresh_facts, prior_runs, dp)
    return out


def _carried_facts(fresh_facts: list, prior_runs: list, dp: dict) -> list:
    """The prior facts behind carried items and fields, so the Evidence view can still show them."""
    from .provenance import Fact
    have = {(f.get("key"), _norm(f.get("value")), f.get("source_url")) for f in fresh_facts}
    wanted_names = {_norm(i.get("name")) for path, _ in _PROFILE_LISTS
                    for i in _get(dp, path) or [] if isinstance(i, dict) and i.get("last_confirmed_at")}
    wanted_keys = {k for path, spec in _SCALARS if ".".join(path) in (dp.get("carried_fields") or {})
                   for k in spec.get("facts", ())}
    out, added = [], set()
    for run in prior_runs:
        for f in _facts_of(run):
            sig = (f.get("key"), _norm(f.get("value")), f.get("source_url"))
            if sig in have or sig in added or not _http(f.get("source_url")):
                continue
            if _norm(f.get("value")) in wanted_names or f.get("key") in wanted_keys:
                added.add(sig)
                kept = {k: f[k] for k in ("key", "value", "source_url", "method", "confidence",
                                          "verified", "retrieved_at", "source_type") if k in f}
                out.append(Fact(**kept))
    return out


def _as_of(size: dict, today: _dt.date):
    raw = str((size or {}).get("as_of") or "").strip()
    m = re.search(r"(19|20)\d{2}", raw)
    if not m:
        return None
    year = int(m.group(0))
    month = (re.search(r"(?:19|20)\d{2}-(0?[1-9]|1[0-2])\b", raw)
             or re.search(r"\b(0?[1-9]|1[0-2])/(?:19|20)\d{2}\b", raw))
    if month:
        return _dt.date(year, int(month.group(1)), 28)
    return _dt.date(year, 12, 31)            # year only: the latest reading of that year


def market_size_current(size, today: _dt.date) -> bool:
    """A cited market figure no older than 18 months; an undated one is not current."""
    when = _as_of(size, today) if isinstance(size, dict) else None
    return when is not None and (today - when).days <= MARKET_MAX_AGE_DAYS


def merge_trend(fresh: dict, prior_runs: list, now: str, today: _dt.date, report: dict) -> dict:
    """``fresh`` is analyze_trend's result. Applies the 18-month market rule even with no priors."""
    if not isinstance(fresh, dict):
        return fresh
    out = copy.deepcopy(fresh)
    land = out.get("landscape")
    if isinstance(land, dict):
        size = land.get("market_size")
        if size and not market_size_current(size, today):
            land["market_size"] = None
            report["market_size_dropped"] = {"as_of": (size or {}).get("as_of", ""), "reason": "older than 18 months"}
        if prior_runs:
            for path, fields in _TREND_LISTS:
                land[path[-1]] = _merge_list(_get(out, path), prior_runs, path, fields,
                                             lambda run, p: _get(run.get("trend") or {}, p), now, report,
                                             ".".join(path))
            if not land.get("market_size"):
                for run in reversed(prior_runs):            # newest qualifying prior figure
                    prior = _get(run.get("trend") or {}, ("landscape", "market_size"))
                    if prior and _http(prior.get("source_url")) and market_size_current(prior, today):
                        land["market_size"] = {**prior, "last_confirmed_at": prior.get("last_confirmed_at") or _when(run)}
                        report.setdefault("fields_carried", []).append("landscape.market_size")
                        break
    return out
