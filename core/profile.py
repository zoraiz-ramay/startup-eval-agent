"""Deep structured profile research: founders, advisors, employees, parent group,
startup programs (Xcelerator / incubators / corporate programs), reference customers,
and Siemens Financial Services (SFS) relevance.

LLM path: LLM-generated queries -> DuckDuckGo -> LLM extraction strictly from evidence,
every populated field backed by a source URL. Offline fallback: keyword detection over
the same search corpus, so a profile is always returned.
"""
from __future__ import annotations

import concurrent.futures
import contextvars
import functools
import os
import re

import pandas as pd

from .provenance import Fact
from .web import _ddg_many
from .llm import LLMClient
from .config import KNOWN_PROGRAM_TIERS
from .text import has_funding_signal
# Known startup programs for offline detection (matched case-insensitively).
KNOWN_PROGRAMS = {
    "siemens xcelerator": "corporate_program",
    "startup autobahn": "corporate_program",
    "nvidia inception": "corporate_program",
    "microsoft for startups": "corporate_program",
    "google for startups": "corporate_program",
    "aws activate": "corporate_program",
    "intel ignite": "corporate_program",
    "sap.io": "corporate_program",
    "y combinator": "accelerator",
    "techstars": "accelerator",
    "plug and play": "accelerator",
    "500 global": "accelerator",
    "entrepreneur first": "accelerator",
    "sosv": "accelerator",
    "antler": "accelerator",
    "startupbootcamp": "accelerator",
    "masschallenge": "accelerator",
    "seedcamp": "accelerator",
    "alchemist accelerator": "accelerator",
    "eit ": "incubator",
    "station f": "incubator",
    "cdl": "incubator",
    "unternehmertum": "incubator",
    "tum venture labs": "incubator",
    "respond accelerator": "accelerator",
    "xpreneurs": "incubator",
    "esa bic": "incubator",
}

# Signals that Siemens Financial Services (equipment/project financing) is a relevant avenue.
_SFS_KEYWORDS = ("hardware", "equipment", "machine", "robot", "manufactur", "capex",
                 "energy", "grid", "infrastructure", "leasing", "asset", "plant",
                 "factory", "charging", "battery", "solar", "wind", "turbine")

EMPTY_PROFILE = {
    "founders": [],           # [{name, role, background, linkedin, source_url}]
    "key_team": [],           # early/core non-founder team [{name, role, source_url}]
    "advisors": [],           # [{name, role, affiliation, source_url}]
    "employees": "",          # best-evidence headcount
    "employees_over_time": [],  # [{year, count, source_url}] — evidence-cited points only
    "parent_group": "",       # part of a major group / corporate parent
    "founded_year": "",       # web-researched; backfills a blank DB column (see pipeline)
    "founded_year_source": "",  # URL supporting founded_year, when the evidence cited one
    "funding": "",            # web-researched round/amount; backfills a blank DB column
    "funding_source": "",     # URL supporting funding, when the evidence cited one
    # [{name, type: incubator|accelerator|corporate_program, source_url,
    #   confidence: corroborated|self_asserted}]
    "programs": [],
    "reference_customers": [],  # NAMED accounts only, grounded in evidence
    "customer_segment": "",    # segment/scale descriptor when customers aren't named (e.g. "7-8 figure e-commerce brands")
    "sfs": {"relevant": False, "rationale": ""},
    "method": "none",
}


_CORPUS_CHARS = int(os.getenv("PROFILE_CORPUS_CHARS", "24000"))


def _corpus(results: dict) -> str:
    """Flatten {query_key: hits} into the evidence block handed to the LLM.

    Results are interleaved ROUND-ROBIN across query keys, with the company's own fetched
    pages (``__site__*``) first, rather than concatenated key by key. A flat concatenation
    spends the whole budget on whichever queries happen to come first in the dict: for a
    typical 11-query wave the corpus ran to ~19k chars, so a 9k cap meant only the first four
    keys ever reached the model and everything after them — headcount, founding year,
    customers, and the site text itself — was silently dropped. That is indistinguishable
    downstream from "the web knows nothing", and it is why researched employee counts and
    founding years kept coming back empty even when the searches had found them.

    Interleaving makes truncation cost every query roughly equally instead of erasing the
    tail wholesale. Override the budget with PROFILE_CORPUS_CHARS.
    """
    ordered = sorted((results or {}).items(), key=lambda kv: not str(kv[0]).startswith("__site__"))
    queues = [[f"[{key}] {h.get('title','')} :: {h.get('body','')} :: {h.get('href','')}"
               for h in (hits or [])] for key, hits in ordered]
    lines, total = [], 0
    for rank in range(max((len(q) for q in queues), default=0)):
        for q in queues:
            if rank >= len(q):
                continue
            line = q[rank]
            if total + len(line) + 1 > _CORPUS_CHARS:
                return "\n".join(lines)
            lines.append(line)
            total += len(line) + 1
    return "\n".join(lines)


def _clean_source_url(value) -> str:
    """Keep a real http(s) link, otherwise ''.

    Asked for a source_url, the model sometimes answers with the corpus label it read the fact
    from ('f1, f2') rather than the link. Those reach profile_sources and the UI renders them as
    a broken 'web-sourced' link, so anything that is not a URL is dropped — the fact is still
    kept, just without a citation. Mirrors the guard in _clean_employee_series."""
    url = str(value or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""


def _site_hint(row: pd.Series) -> str:
    """Bare host ('phena.tech') from the row's domain/website, or '' when unknown.

    Used to disambiguate identity-sensitive searches. A bare company name is frequently
    ambiguous — 'Phena' collides with Tryphena, Phena International Ltd, Phena's Studio — and
    those queries come back as noise, which downstream is indistinguishable from "the web
    knows nothing". Pinning the query to the company's own domain is what surfaces its
    LinkedIn ('Company size 2-10 employees') and CB Insights ('founded in 2026') entries."""
    raw = str(row.get("domain", "") or row.get("website", "")).strip()
    if not raw:
        return ""
    from urllib.parse import urlparse
    host = urlparse(raw if "//" in raw else "https://" + raw).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _queries(company: str, row: pd.Series, llm: LLMClient) -> dict:
    # Only the identity-sensitive queries take the domain hint. The founder/advisor/customer
    # searches already resolve well on the name alone, and the wave is budget-sensitive: see
    # _ddg_many, where an oversized wave gets throttled into silently empty results.
    hint = _site_hint(row)
    q = f"{company} {hint}".strip() if hint else company
    base = {
        "founders": f"{company} founders co-founder CEO CTO LinkedIn",
        "founder_bg": f"{company} founder previous company career university",
        "advisors": f"{company} advisory board scientific advisor professor",
        "programs": f"{company} accelerator incubator startup program member cohort",
        # Generic membership signals rather than a few brand names, so the evidence surfaces
        # whatever program the startup actually belongs to (YC, Techstars, Antler, ...). The
        # grounding gate (see _program_grounded) requires the program to co-occur with the
        # company in a single result, so naming programs here can't create false positives.
        "corp_programs": f'{q} ("backed by" OR alumni OR cohort OR portfolio OR '
                         f'accelerator OR incubator OR "Y Combinator" OR Techstars)',
        "parent": f"{company} subsidiary parent company acquired part of group",
        "team": f"{q} number of employees company size linkedin",
        # Nothing searched for the founding year or the funding round before, so both were
        # only ever extracted from whatever the other queries happened to return.
        "founded": f"{q} founded year established headquarters",
        "funding": f"{q} funding round raised investors pre-seed seed series",
        "customers": f"{company} customer case study deployment client announcement",
    }
    if llm.available:
        known = " ".join(str(row.get(c, "")) for c in ("short_description", "Your pitch"))[:600]
        prompt = (f"We research the startup '{company}' ({known}). Suggest up to 4 additional web "
                  "search queries that would surface: its founders' backgrounds, scientific/industry "
                  "advisors, membership in incubators/accelerators/corporate startup programs, or a "
                  'corporate parent. Return ONLY JSON: {"queries": ["..."]}')
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=300, reasoning="none"))
        if data and isinstance(data.get("queries"), list):
            # cap the extras: an oversized wave triggers DuckDuckGo throttling, which
            # silently empties the program/advisor queries
            for i, q in enumerate(data["queries"][:2]):
                if str(q).strip():
                    base[f"llm_{i}"] = str(q).strip()
    return base


def _startup_text(row: pd.Series) -> str:
    return " ".join(str(row.get(c, "")) for c in
                    ("company_name", "short_description", "Your pitch", "Business model",
                     "customers", "Reference customers"))


@functools.lru_cache(maxsize=512)
def _word_match(needle: str) -> "re.Pattern":
    """Whole-word matcher for a program name.

    Plain substring matching mis-fires badly on short names: the KNOWN_PROGRAMS key for EIT is
    written ``"eit "`` with a trailing space precisely to avoid that, but this function's
    caller strips the name before comparing — so it degraded to a bare ``"eit" in blob`` and
    matched inside ordinary words (Zeit, arbeit, ...). Meili Robots consequently picked up a
    fabricated "Eit" membership, labelled *corroborated*, which inflated its ecosystem score.

    ``\\b`` is unreliable next to non-word characters (``sap.io``, ``500 global``), so the
    boundaries are asserted only on the sides that actually begin/end with a word character.
    """
    n = needle.strip()
    left = r"(?<!\w)" if n[:1].isalnum() or n[:1] == "_" else ""
    right = r"(?!\w)" if n[-1:].isalnum() or n[-1:] == "_" else ""
    return re.compile(left + re.escape(n) + right, re.I)


def _program_grounded(name: str, company: str, app_text: str,
                      results: dict) -> tuple[str, str] | None:
    """Decide whether a program membership is actually tied to THIS startup.

    Returns ``(source_url, confidence)`` when grounded, or None when it is not:
      * ``corroborated``  -> program and company co-occur in a SINGLE THIRD-PARTY result;
                             returns that result's URL.
      * ``self_asserted`` -> the only support is the company itself — its own fetched site
                             pages (the ``__site__*`` pseudo-results merged by
                             _merge_site_results) or its application text. URL may be ''.
      * ungrounded        -> returns None (caller drops it).

    Matching a program name anywhere in the concatenated corpus is NOT enough: the
    program search query names specific programs, so DuckDuckGo returns generic program
    directory pages that mention many unrelated startups. Requiring the program and the
    company in the same result is what prevents false memberships (e.g. AfterFlow showing
    Nvidia Inception / Microsoft for Startups / Google for Startups it never had).

    The corroborated/self_asserted split matters because a company's own site is evidence
    that it CLAIMS a membership, not that the membership exists. Programs like NVIDIA
    Inception and Microsoft for Startups publish no searchable public member directory, so
    a claim found only on the startup's site is frequently uncheckable. Dropping it loses a
    real signal; presenting it as verified overstates it. Labelling lets the UI show it
    honestly. Third-party corroboration is preferred, so search results are scanned first.
    """
    n = str(name).strip().lower()
    if not n:
        return None
    n_re = _word_match(n)
    if company:
        fallback = None
        for key, hits in results.items():
            for h in hits or []:
                blob = (str(h.get("title", "")) + " " + str(h.get("body", ""))).lower()
                if n_re.search(blob) and company in blob:
                    if str(key).startswith("__site__"):
                        # Remember, but keep scanning: a third-party hit outranks the site.
                        if fallback is None:
                            fallback = h.get("href", "") or ""
                    else:
                        return (h.get("href", "") or "", "corroborated")
        if fallback is not None:
            return (fallback, "self_asserted")
    if n_re.search(app_text):            # self-claim in the startup's own application text
        return ("", "self_asserted")
    return None


def _detect_programs(row: pd.Series, results: dict) -> list[dict]:
    """Keyword scan for KNOWN_PROGRAMS, kept only for programs grounded to THIS startup
    (see _program_grounded). Used offline AND as a safety net alongside LLM extraction,
    so a genuine known-program mention never disappears if the LLM omitted it."""
    company = str(row.get("company_name", "")).strip().lower()
    app_text = _startup_text(row).lower()
    found = []
    for name, ptype in KNOWN_PROGRAMS.items():
        grounded = _program_grounded(name, company, app_text, results)
        if grounded is not None:
            src, conf = grounded
            found.append({"name": name.strip().title(), "type": ptype,
                          "source_url": src, "confidence": conf})
    return found


def _ground_programs(programs: list, row: pd.Series, results: dict) -> list[dict]:
    """Validate an arbitrary program list (e.g. LLM-extracted, which can name ANY program
    worldwide) against the fetched evidence. Keeps only memberships tied to this startup
    and rewrites source_url to the real co-occurring result, so a program the LLM lifted
    from a generic 'top startups' directory page — or invented — is dropped rather than
    trusted. Prioritises correctness over recall: an unverifiable membership is removed."""
    company = str(row.get("company_name", "")).strip().lower()
    app_text = _startup_text(row).lower()
    out, seen = [], set()
    for p in programs or []:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name", "")).strip()
        key = name.lower()
        if not name or key in seen:
            continue
        grounded = _program_grounded(name, company, app_text, results)
        if grounded is None:
            continue
        src, conf = grounded
        seen.add(key)
        out.append({"name": name,
                    "type": str(p.get("type") or "program").strip() or "program",
                    "source_url": src, "confidence": conf})
    return out


_PROGRAM_NOISE = re.compile(
    r"\b(the|program|programme|accelerator|incubator|startups?|inc|ltd|gmbh)\b", re.I)


def _program_key(name: str) -> str:
    """Canonical identity for a program, so spelling variants collapse to one entry.

    The LLM and the keyword scan name the same membership differently ('NVIDIA Inception
    Program' vs 'Nvidia Inception'), and an exact-string dedup let both through — the profile
    then listed one membership twice and the ecosystem score counted it twice."""
    n = _PROGRAM_NOISE.sub(" ", str(name).lower())
    return re.sub(r"[^a-z0-9]+", "", n)


def _dedupe_programs(programs: list) -> list[dict]:
    """One entry per membership, preferring the independently corroborated spelling."""
    best: dict = {}
    for p in programs or []:
        if not isinstance(p, dict) or not str(p.get("name", "")).strip():
            continue
        key = _program_key(p["name"]) or str(p["name"]).strip().lower()
        cur = best.get(key)
        if cur is None:
            best[key] = p
            continue
        # Corroborated beats self-asserted; otherwise keep whichever already has a source URL.
        if (str(p.get("confidence", "")).lower() == "corroborated"
                and str(cur.get("confidence", "")).lower() != "corroborated"):
            best[key] = p
        elif not str(cur.get("source_url", "")).strip() and str(p.get("source_url", "")).strip():
            best[key] = p
    return list(best.values())


def _offline_extract(company: str, row: pd.Series, results: dict) -> dict:
    """Keyword-based fallback: detect known programs and SFS relevance without an LLM."""
    prof = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in EMPTY_PROFILE.items()}
    prof["programs"] = _detect_programs(row, results)
    sfs_hits = sorted({k for k in _SFS_KEYWORDS if k in _startup_text(row).lower()})
    if sfs_hits:
        prof["sfs"] = {"relevant": True,
                       "rationale": "Capex/asset-heavy signals: " + ", ".join(sfs_hits[:5]) + "."}
    prof["method"] = "offline_keyword"
    return prof


def _llm_extract(company: str, row: pd.Series, results: dict, llm: LLMClient) -> dict | None:
    corpus = _corpus(results)
    known = _startup_text(row)[:1200]
    prompt = (
        f"You are researching the startup '{company}'. Below are web search results and what we "
        "already know. Extract a structured profile using ONLY supported facts — leave fields "
        "empty/[] if the evidence does not support them. Never invent names. For every founder, "
        "advisor, program and the parent group, include the source_url of the search result that "
        "supports it.\n\n"
        f"KNOWN:\n{known}\n\nWEB RESULTS:\n{corpus}\n\n"
        "Rules:\n"
        "- reference_customers: NAMED companies/organisations ONLY (e.g. 'Deutsche Bahn', 'Bosch') "
        "that the evidence ties to THIS startup as a customer. NEVER generic descriptions — put "
        "those in customer_segment instead.\n"
        "- customer_segment: if the customers are described by type/scale rather than named "
        "(e.g. '7-8 figure e-commerce brands', 'Fortune 500 manufacturers'), capture that one "
        "short phrase here; leave empty if the customers are named or unknown.\n"
        "- founders: include role AND a specific background (prior companies, roles, university/PhD) "
        "whenever the evidence mentions it; include the LinkedIn URL if present in the results.\n"
        "- employees: a number or tight range (e.g. '25' or '50-100'), not vague words.\n"
        "- founded_year: 4-digit year only (e.g. '2021'), and ONLY if a result states when the "
        "company was founded/incorporated/started. Never infer it from a copyright notice, a "
        "domain registration date, or the earliest news article.\n"
        "- funding: the most recent round as a short phrase with stage and amount when both are "
        "evidenced (e.g. 'Seed, $2.5M (2024)'). If the stage is evidenced but the amount is NOT "
        "public — Crunchbase renders it as 'obfuscated', or the source says undisclosed — STILL "
        "report the stage, e.g. 'Pre-Seed, amount undisclosed'. Leave empty only when the "
        "evidence names neither a stage nor an amount, and NEVER guess an amount.\n"
        "- founded_year_source / funding_source: the source_url of the result supporting each — a "
        "real http link from the results, never a label; leave empty if the value came from the "
        "KNOWN block rather than a search result.\n"
        "Also judge: is Siemens Financial Services (equipment/project financing, leasing) a relevant "
        "partnership avenue for this startup (e.g. hardware, capex-heavy, energy/infrastructure)?\n\n"
        'Return ONLY JSON:\n'
        '{"founders": [{"name":"","role":"","background":"","linkedin":"","source_url":""}],\n'
        ' "key_team": [{"name":"","role":"","source_url":""}],\n'
        ' "advisors": [{"name":"","role":"","affiliation":"","source_url":""}],\n'
        ' "employees": "", "parent_group": "",\n'
        ' "founded_year": "", "founded_year_source": "",\n'
        ' "funding": "", "funding_source": "",\n'
        ' "programs": [{"name":"","type":"incubator|accelerator|corporate_program","source_url":""}],\n'
        ' "reference_customers": [""], "customer_segment": "",\n'
        ' "sfs": {"relevant": true, "rationale": "one sentence"}}'
    )
    data = LLMClient.parse_json(llm.complete(prompt, system="You extract structured company facts "
                                             "strictly from supplied evidence. JSON only.",
                                             max_tokens=1200, reasoning="none"))
    if not data:
        return None
    prof = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in EMPTY_PROFILE.items()}
    for key in ("founders", "key_team", "advisors", "programs", "reference_customers"):
        if isinstance(data.get(key), list):
            prof[key] = [x for x in data[key] if x]
    prof["employees"] = str(data.get("employees") or "").strip()
    prof["parent_group"] = str(data.get("parent_group") or "").strip()
    prof["customer_segment"] = str(data.get("customer_segment") or "").strip()
    # Founded year is only accepted as a bare 4-digit year in a plausible range: the model
    # otherwise happily returns '2021 (est.)', 'circa 2019' or a copyright year, none of which
    # a downstream consumer can treat as a number.
    fy = re.sub(r"\D", "", str(data.get("founded_year") or ""))[:4]
    prof["founded_year"] = fy if len(fy) == 4 and 1800 <= int(fy) <= 2100 else ""
    prof["founded_year_source"] = (_clean_source_url(data.get("founded_year_source"))
                                   if prof["founded_year"] else "")
    # Same bar as the recall net: a round must name a stage or an amount to be a usable fact.
    funding = str(data.get("funding") or "").strip()
    prof["funding"] = funding if has_funding_signal(funding) else ""
    prof["funding_source"] = (_clean_source_url(data.get("funding_source"))
                              if prof["funding"] else "")
    sfs = data.get("sfs") or {}
    prof["sfs"] = {"relevant": bool(sfs.get("relevant")),
                   "rationale": str(sfs.get("rationale") or "").strip()}
    prof["method"] = "llm"
    return prof


# Words that betray a generic customer *description* (a segment/scale) rather than a named
# company. Such phrases belong in customer_segment, never in reference_customers.
_GENERIC_CUSTOMER = re.compile(
    r"\b(factor(y|ies)|sectors?|industr(y|ies)|companies|clients?|customers?|various|"
    r"several|leading|multiple|enterprises?|manufacturers?|startups?|and more|etc|"
    r"brands?|businesses|firms?|high[- ]?ticket|mid[- ]?market|figure|smbs?|smes?)\b", re.I)

# A genuine customer statement puts the customer, the company, and a relationship phrase
# close together ("ShopSolar uses AfterFlow", "AfterFlow's client Acme"). Requiring all
# three within a short window rejects listicles where both names appear far apart on the
# same page with an unrelated verb elsewhere.
_CUSTOMER_REL = re.compile(
    r"customer|client|case stud|works? with|working with|deployed|deployment|"
    r"partner|trusted by|uses |used by|powered by|helps? ", re.I)
_REL_WINDOW = 140


def _rel_grounded(blob: str, name: str, company: str) -> bool:
    """True if `name`, `company` and a relationship phrase all fall within a short window —
    evidence of an actual customer relationship rather than incidental co-mention."""
    start = 0
    while True:
        i = blob.find(name, start)
        if i == -1:
            return False
        seg = blob[max(0, i - _REL_WINDOW): i + len(name) + _REL_WINDOW]
        if company in seg and _CUSTOMER_REL.search(seg):
            return True
        start = i + 1


def _ground_customers(names: list, row: pd.Series, results: dict) -> list[str]:
    """Keep only customer names actually tied to THIS startup: either the startup self-declared
    the customer in its application row, or a single web result states the relationship with the
    customer name, the company, and a relationship phrase all close together (see _rel_grounded).
    Web-extracted names that merely appear somewhere in the corpus — competitors, investors,
    companies from an unrelated listing, or a name matched to the wrong entity when the startup's
    name is ambiguous (e.g. AfterFlow -> 'ShopSolar.com') — are dropped. Prioritises correctness
    over recall: an unverifiable customer is removed."""
    company = str(row.get("company_name", "")).strip().lower()
    declared = str(row.get("customers", "") or row.get("Reference customers", "")).lower()
    out: list[str] = []
    for name in names or []:
        n = str(name).strip()
        nl = n.lower()
        if not n:
            continue
        grounded = bool(nl) and nl in declared          # self-declared in the application
        if not grounded and company:                    # else: name + company + relationship
            for hits in results.values():               # phrase all close together in a result
                for h in hits or []:
                    blob = (str(h.get("title", "")) + " " + str(h.get("body", ""))).lower()
                    if _rel_grounded(blob, nl, company):
                        grounded = True
                        break
                if grounded:
                    break
        if grounded and n not in out:
            out.append(n)
    return out


def _clean_customers(items: list) -> list[str]:
    """Keep only entries that look like NAMED organisations; drop generic descriptions
    like 'factories in the semiconductor and new energy sectors'."""
    out = []
    for c in items or []:
        s = str(c).strip().strip(".")
        if not s or len(s) > 60 or _GENERIC_CUSTOMER.search(s):
            continue
        if not any(ch.isupper() for ch in s):     # named orgs carry capitals
            continue
        if s not in out:
            out.append(s)
    return out


def _recover_founders(prof: dict, company: str, llm: LLMClient) -> None:
    """Safety net mirroring the programs scan: when the main extraction returns ZERO
    founders (throttled queries, truncated corpus, or the LLM simply omitting them),
    run a dedicated founder-only search wave with its own focused extraction call."""
    if prof.get("founders") or not llm.available:
        return
    queries = {
        "f1": f"{company} founders who founded",
        "f2": f"{company} founder CEO co-founder LinkedIn",
        "f3": f"{company} startup team about us founders",
    }
    corpus = _corpus(_ddg_many(queries, max_results=5))
    if not corpus:
        return
    data = LLMClient.parse_json(llm.complete(
        f"Web results about the startup '{company}':\n\n{corpus}\n\n"
        "Extract the FOUNDERS of this company: name, role, specific background (prior "
        "companies/roles, education), LinkedIn URL, and the supporting source_url. Only "
        "people the results clearly identify as founders/co-founders/founding CEO-CTO. "
        "Never invent names; return an empty list if the results name nobody.\n"
        'Return ONLY JSON: {"founders": [{"name":"","role":"","background":"","linkedin":"","source_url":""}]}',
        system="You extract structured facts strictly from supplied evidence. JSON only.",
        max_tokens=700, reasoning="none")) or {}
    found = [f for f in data.get("founders", [])
             if isinstance(f, dict) and str(f.get("name", "")).strip()]
    if found:
        prof["founders"] = found


def _deepen_founders(prof: dict, company: str, llm: LLMClient) -> None:
    """Second research pass: for founders whose background is still empty, run
    person-targeted searches and one LLM call to fill role/background/LinkedIn."""
    thin = [f for f in prof.get("founders", [])
            if isinstance(f, dict) and f.get("name") and not str(f.get("background", "")).strip()][:3]
    if not thin or not llm.available:
        return
    queries = {f"f{i}": f"\"{f['name']}\" {company} founder background LinkedIn"
               for i, f in enumerate(thin)}
    corpus = _corpus(_ddg_many(queries, max_results=4))
    if not corpus:
        return
    names = ", ".join(f["name"] for f in thin)
    data = LLMClient.parse_json(llm.complete(
        f"Web results about the founders of '{company}' ({names}):\n\n{corpus}\n\n"
        "For each founder, extract role, a SPECIFIC background (prior companies/roles, "
        "education/PhD), and LinkedIn URL — only what the results support; leave empty otherwise.\n"
        'Return ONLY JSON: {"founders": [{"name":"","role":"","background":"","linkedin":"","source_url":""}]}',
        system="You extract structured facts strictly from supplied evidence. JSON only.",
        max_tokens=700, reasoning="none")) or {}
    updates = {str(f.get("name", "")).strip().lower(): f
               for f in data.get("founders", []) if isinstance(f, dict) and f.get("name")}
    for f in prof["founders"]:
        u = updates.get(str(f.get("name", "")).strip().lower())
        if u:
            for k in ("role", "background", "linkedin", "source_url"):
                if not str(f.get(k, "")).strip() and str(u.get(k, "")).strip():
                    f[k] = str(u[k]).strip()


def _profile_facts(prof: dict) -> list[Fact]:
    facts: list[Fact] = []

    def add(key, value, src=""):
        if str(value).strip():
            facts.append(Fact(key=key, value=str(value)[:300], source_url=src or "",
                              method="profile_research", confidence=0.65, verified=bool(src)))

    for f in prof.get("founders", []):
        if isinstance(f, dict) and f.get("name"):
            add("founder", f"{f.get('name')} — {f.get('role','')} {f.get('background','')}".strip(),
                f.get("source_url", ""))
    for t in prof.get("key_team", []):
        if isinstance(t, dict) and t.get("name"):
            add("key_team", f"{t.get('name')} — {t.get('role','')}".strip(), t.get("source_url", ""))
    for a in prof.get("advisors", []):
        if isinstance(a, dict) and a.get("name"):
            add("advisor", f"{a.get('name')} — {a.get('role','')} {a.get('affiliation','')}".strip(),
                a.get("source_url", ""))
    for p in prof.get("programs", []):
        if isinstance(p, dict) and p.get("name"):
            tier = str(p.get("prestige", "")).strip()
            label = f"{p.get('name')} ({p.get('type', 'program')}"
            label += f", {tier})" if tier else ")"
            if str(p.get("confidence", "")).lower() == "self_asserted":
                label += " — company-claimed, not independently corroborated"
            add("program", label, p.get("source_url", ""))
    add("parent_group", prof.get("parent_group", ""))
    add("founded_year_research", prof.get("founded_year", ""),
        prof.get("founded_year_source", ""))
    add("funding_research", prof.get("funding", ""), prof.get("funding_source", ""))
    add("employees_research", prof.get("employees", ""))
    if prof.get("sfs", {}).get("relevant"):
        add("sfs_relevance", prof["sfs"].get("rationale") or "SFS financing avenue relevant")
    return facts


def _merge_site_results(results: dict, company: str, row: pd.Series,
                        site: dict | None) -> dict:
    """Fold the company's own fetched pages into the search-results dict as pseudo-hits.

    The grounding gate (_program_grounded / _rel_grounded) requires a program/customer name
    and the company to co-occur in a SINGLE result. A company's own /partners or /ecosystem
    page trivially satisfies "company co-occurs" (it is their site), so we prepend the company
    name to each page's body and use the site URL as href. This lets memberships published
    only on the site be grounded, without weakening the co-occurrence rule for real search
    results. Returns a new dict; the input is not mutated."""
    merged = dict(results or {})
    if not site:
        return merged
    website = str(row.get("website", "") or row.get("domain", "")).strip()
    for i, (path, text) in enumerate(site.items()):
        if not str(text).strip():
            continue
        merged[f"__site__{i}"] = [{
            "title": f"{company} — {path}",
            "body": f"{company} {text}",
            "href": website,
        }]
    return merged


def _recheck_programs(prof: dict, row: pd.Series, company: str,
                      results: dict, llm: LLMClient) -> None:
    """Second-pass recall check for program/ecosystem membership.

    When the first pass found NO grounded programs, an empty result is not yet proof of
    "no memberships" — the ecosystem queries may have been throttled or the membership may
    live on a page DuckDuckGo skipped. Run a dedicated ecosystem/accelerator search wave,
    merge it with whatever site evidence we already have, and re-run the same grounded
    detection. Only memberships tied to THIS startup (co-occurrence) survive, so recall
    improves without sacrificing correctness. No-op when programs already exist."""
    if prof.get("programs"):
        return
    company_l = company.lower()
    queries = {
        "e1": f'{company} ("part of" OR member OR backed OR portfolio) ecosystem',
        "e2": f"{company} accelerator incubator cohort alumni program",
        "e3": f"{company} strategic partner alliance network",
    }
    extra = _ddg_many(queries, max_results=5, overall_timeout=30.0)
    combined = dict(results or {})
    combined.update(extra)
    found = _detect_programs(row, combined)
    if not found and llm.available:
        # Let the LLM name any program the evidence supports, then ground it hard.
        corpus = _corpus(combined)
        if corpus:
            data = LLMClient.parse_json(llm.complete(
                f"Web/company-site results about '{company}':\n\n{corpus}\n\n"
                "List ONLY startup programs, accelerators, incubators, corporate startup "
                "programs, or partner ecosystems that the evidence clearly ties to THIS "
                "company as a member/participant. Never guess; empty list if none.\n"
                'Return ONLY JSON: {"programs":[{"name":"","type":"incubator|accelerator|'
                'corporate_program","source_url":""}]}',
                system="You extract structured facts strictly from supplied evidence. JSON only.",
                max_tokens=500, reasoning="none")) or {}
            found = _ground_programs(data.get("programs", []), row, combined)
    if found:
        # Drop any "membership" that is just the company's own name echoed back.
        prof["programs"] = _dedupe_programs(
            [p for p in found if str(p.get("name", "")).strip().lower() != company_l])


def _recover_headline_facts(prof: dict, company: str, row: pd.Series, llm: LLMClient) -> None:
    """Second-pass recall net for founded_year / employees / funding, like _recover_founders.

    All three live on aggregator pages (LinkedIn "Company size 2-10 employees", CB Insights
    "It was founded in 2026", Crunchbase funding profiles) that rank below the company's own
    pages and drop in and out of a 5-result window between runs. The main wave therefore finds
    them only sometimes, and an empty field is indistinguishable from "the web does not know".
    When one is still blank, spend a focused wave plus one extraction call on it rather than
    declaring it unavailable. Only blank fields are filled; never raises.
    """
    need_year = not str(prof.get("founded_year", "")).strip()
    need_emp = not str(prof.get("employees", "")).strip()
    need_funding = not str(prof.get("funding", "")).strip()
    if not (need_year or need_emp or need_funding) or not llm.available:
        return
    hint = _site_hint(row)
    q = f"{company} {hint}".strip() if hint else company
    corpus = _corpus(_ddg_many({
        "h1": f"{q} linkedin company size employees",
        "h2": f"{q} crunchbase pitchbook cbinsights company profile founded",
        "h3": f"{q} founded in year headquarters about the company",
        "h4": f"{q} crunchbase pitchbook funding rounds total raised",
        "h5": f"{q} pre-seed seed series A investment announcement",
    }, max_results=5, overall_timeout=25.0))
    if not corpus:
        return
    # A name-based search for a small startup returns near-namesakes (Phena -> FENA Holdings,
    # Phenna Group, Fena Private Limited), several carrying their own headcount. Without an
    # anchor the model either declines or picks the wrong row, so the company's own
    # description/HQ/website go into the prompt as the identity test.
    known = _startup_text(row)[:600]
    data = LLMClient.parse_json(llm.complete(
        f"Web results about the startup '{company}':\n\n{corpus}\n\n"
        f"THIS COMPANY IS:\nname: {company}\nwebsite: {hint or 'unknown'}\n{known}\n\n"
        "Extract ONLY these facts, strictly from the evidence and only from results that "
        "match THIS company — the results contain other organisations with similar names, and "
        "a fact taken from one of those is worse than no answer:\n"
        "- founded_year: 4-digit year the company was founded/incorporated. NEVER infer it "
        "from a copyright notice, a domain registration, or the date of the earliest article.\n"
        "- employees: a number or tight range exactly as stated (e.g. '25', '2-10'), not a "
        "vague word.\n"
        "- funding: the most recent round, stage and amount when both are evidenced (e.g. "
        "'Seed, $2.5M (2024)'). If the stage is evidenced but the amount is NOT public — "
        "Crunchbase renders it as 'obfuscated', or the source says undisclosed — STILL report "
        "the stage, e.g. 'Pre-Seed, amount undisclosed'. Leave empty only when not even a "
        "stage is evidenced, and NEVER guess an amount.\n"
        "Give the supporting source_url (a real http link from the results, not a label) for "
        "each. Leave a field empty if unsupported.\n"
        'Return ONLY JSON: {"founded_year":"","founded_year_source":"",'
        '"employees":"","employees_source":"","funding":"","funding_source":""}',
        system="You extract structured facts strictly from supplied evidence. JSON only.",
        max_tokens=500, reasoning="none")) or {}
    if need_year:
        fy = re.sub(r"\D", "", str(data.get("founded_year") or ""))[:4]
        if len(fy) == 4 and 1800 <= int(fy) <= 2100:
            prof["founded_year"] = fy
            prof["founded_year_source"] = _clean_source_url(data.get("founded_year_source"))
    if need_emp:
        emp = str(data.get("employees") or "").strip()
        # A bare count or range only — the prompt asks for one, but a model can still answer
        # "a small team", which is not a fact a downstream consumer can use.
        if emp and re.fullmatch(r"[\d,]+(\s*[-–]\s*[\d,]+)?\+?", emp):
            prof["employees"] = emp
    if need_funding:
        fund = str(data.get("funding") or "").strip()
        # Must name a stage or an amount; "raised funding" on its own is not a fact.
        if fund and has_funding_signal(fund):
            prof["funding"] = fund
            prof["funding_source"] = _clean_source_url(data.get("funding_source"))


def _program_tier_offline(name: str) -> str:
    """Deterministic prestige tier from the known-program map; unknown -> tier3."""
    n = str(name).lower()
    for key, tier in KNOWN_PROGRAM_TIERS.items():
        if key and key in n:
            return tier
    return "tier3"


def _grade_programs(programs: list, company: str, llm: LLMClient) -> None:
    """Annotate each program with a prestige ``tier`` (tier1/tier2/tier3) in place.

    Every program first gets a deterministic tier from KNOWN_PROGRAM_TIERS (unknown -> tier3),
    so scoring is stable even offline. When the LLM is available it re-grades by global
    reputation (tier1 = top-tier / Siemens-run, tier3 = generic local), but it may ONLY set
    the tier — it can never add, drop, or rename a membership, so grading can't fabricate
    credibility. Invalid/absent LLM tiers keep the deterministic baseline."""
    if not programs:
        return
    for p in programs:
        if isinstance(p, dict):
            p["prestige"] = _program_tier_offline(str(p.get("name", "")))
    if not llm.available:
        return
    named = [str(p.get("name", "")).strip() for p in programs
             if isinstance(p, dict) and str(p.get("name", "")).strip()]
    if not named:
        return
    listing = "; ".join(named)
    data = LLMClient.parse_json(llm.complete(
        f"Rate the prestige of these startup programs that '{company}' belongs to: {listing}.\n"
        "Tiers: tier1 = globally top-tier accelerator/program or run by a major corporate "
        "(e.g. Y Combinator, Techstars, Siemens Xcelerator, Startup Autobahn, Intel Ignite); "
        "tier2 = well-known but broad-access (e.g. Microsoft/Google for Startups, Plug and "
        "Play, Antler); tier3 = regional/generic/unknown. Judge by the program's reputation, "
        "not this company.\n"
        'Return ONLY JSON: {"tiers": {"<program name>": "tier1|tier2|tier3"}}',
        system="You grade startup-program prestige. JSON only.", max_tokens=300,
        reasoning="none")) or {}
    tiers = data.get("tiers") or {}
    if not isinstance(tiers, dict):
        return
    lut = {str(k).strip().lower(): str(v).strip().lower() for k, v in tiers.items()}
    for p in programs:
        if not isinstance(p, dict):
            continue
        t = lut.get(str(p.get("name", "")).strip().lower())
        if t in ("tier1", "tier2", "tier3"):
            p["prestige"] = t


def _clean_employee_series(points: list) -> list[dict]:
    """Sanitise raw {year, count, source_url} points into a trustworthy time series.

    Correctness over recall: a point is kept ONLY when it has a plausible year
    (2000..current+1), a positive integer headcount, and an http(s) source_url — an
    uncited number is dropped rather than guessed. Duplicated years collapse to one
    (highest count wins) and the result is sorted ascending. Fewer than TWO cited points
    returns [] so the UI can honestly show 'insufficient data' instead of a misleading
    single dot or a fabricated line."""
    import datetime
    max_year = datetime.date.today().year + 1
    by_year: dict[int, dict] = {}
    for p in points or []:
        if not isinstance(p, dict):
            continue
        src = str(p.get("source_url", "")).strip()
        if not src.startswith("http"):
            continue
        try:
            year = int(str(p.get("year", "")).strip()[:4])
            count = int(float(str(p.get("count", "")).strip().replace(",", "")))
        except (ValueError, TypeError):
            continue
        if year < 2000 or year > max_year or count <= 0:
            continue
        prev = by_year.get(year)
        if prev is None or count > prev["count"]:
            by_year[year] = {"year": year, "count": count, "source_url": src}
    series = [by_year[y] for y in sorted(by_year)]
    return series if len(series) >= 2 else []


def _employee_history(company: str, row: pd.Series, results: dict,
                      llm: LLMClient) -> list[dict]:
    """Best-effort headcount-over-time series, every point backed by a source URL.

    Runs a small dedicated wave of historical-headcount queries, then asks the LLM to pull
    ONLY year+count pairs the evidence supports, each with the supporting URL. The result is
    passed through _clean_employee_series, so anything uncited or implausible is discarded and
    a series with <2 cited points collapses to []. Returns [] on any failure — never raises."""
    if not llm.available:
        return []
    queries = {
        "h1": f"{company} number of employees 2021 2022 2023 2024 headcount growth",
        "h2": f"{company} linkedin employees company size over time",
        "h3": f"{company} crunchbase employee count history",
    }
    try:
        extra = _ddg_many(queries, max_results=5, overall_timeout=18.0)
    except Exception:
        extra = {}
    combined = dict(results or {})
    combined.update(extra)
    corpus = _corpus(combined)
    if not corpus:
        return []
    data = LLMClient.parse_json(llm.complete(
        f"Web results about the headcount of the startup '{company}':\n\n{corpus}\n\n"
        "Extract the number of EMPLOYEES per YEAR, using ONLY figures the evidence states "
        "for this company. For each data point give the calendar year, the employee count as "
        "an integer, and the source_url of the result that supports it. Never estimate or "
        "interpolate; omit any year you cannot cite. Return an empty list if none are cited.\n"
        'Return ONLY JSON: {"employees_over_time":[{"year":2023,"count":42,"source_url":""}]}',
        system="You extract structured facts strictly from supplied evidence. JSON only.",
        max_tokens=600, reasoning="none")) or {}
    return _clean_employee_series(data.get("employees_over_time", []))


def research_profile(row: pd.Series, llm: LLMClient, do_web: bool = True,
                     site: dict | None = None) -> dict:
    """Return {'profile': {...}, 'facts': [Fact...]}; never raises.

    ``site`` is the optional {path: text} map of the company's OWN pages already fetched
    during enrichment (web.fetch_site_text). Folding it into the evidence lets the recall
    check ground ecosystem/program memberships that live only on the site and were never
    indexed by DuckDuckGo."""
    company = str(row.get("company_name", "")).strip()
    if not company:
        return {"profile": dict(EMPTY_PROFILE), "facts": []}
    try:
        # Uses _ddg_many's default budget, which is sized for the full wave; a tighter
        # deadline here silently empties the program/advisor queries under throttling.
        # 5 results, not 4: the aggregator pages that actually carry headcount and founding
        # year (LinkedIn's "Company size 2-10 employees", CB Insights) routinely rank fifth
        # behind the company's own pages, so a 4-result window cut them off.
        results = _ddg_many(_queries(company, row, llm), max_results=5) if do_web else {}
        # Fold the company's own site text in as pseudo-results so the grounding gate
        # (name + company must co-occur in one result) can see facts published only there.
        results = _merge_site_results(results, company, row, site)
        prof = None
        if llm.available:
            prof = _llm_extract(company, row, results, llm)
        if prof is None:
            prof = _offline_extract(company, row, results)
        else:
            # Ground the LLM's programs against the evidence (it may name any program
            # worldwide, but each membership must be tied to THIS startup), then union
            # with the KNOWN_PROGRAMS keyword scan so a known program never vanishes
            # because the LLM skipped it or the corpus was truncated.
            prof["programs"] = _dedupe_programs(
                _ground_programs(prof.get("programs", []), row, results)
                + _detect_programs(row, results))
        # Named-companies-only filter + grounding (a web-extracted name must co-occur with
        # the company or be self-declared), then backfill from the DB row if research found
        # none. DB-declared customers are trusted, so the backfill needs no grounding.
        prof["reference_customers"] = _ground_customers(
            _clean_customers(prof["reference_customers"]), row, results)
        if not prof["reference_customers"]:
            raw = str(row.get("customers", "") or row.get("Reference customers", ""))
            prof["reference_customers"] = _clean_customers(re.split(r"[,\n;·|]+", raw))
        # ---- second-pass recall nets ------------------------------------------------------
        # Four independent passes, each firing its own search wave plus one extraction call:
        # the headline facts (founded_year / employees), founder recovery, the program recheck,
        # and the headcount series. Run sequentially they dominated the evaluation — ~29s of
        # the ~67s profile chain — yet they touch DISJOINT profile fields, so they overlap
        # safely and the wall time collapses to the slowest one. Each decides for itself
        # whether it is needed (all no-op when their field is already populated), and each is
        # individually best-effort: one failure must never cost the profile.
        if do_web:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                # Pool threads start with an empty context, so each job runs inside a copy of
                # this one — that is what carries core.web's cache-bypass flag into the search
                # calls these passes make.
                def _spawn(fn, *a):
                    return ex.submit(contextvars.copy_context().run, functools.partial(fn, *a))

                jobs = {
                    "headline": _spawn(_recover_headline_facts, prof, company, row, llm),
                    "founders": _spawn(_recover_founders, prof, company, llm),
                    "programs": _spawn(_recheck_programs, prof, row, company, results, llm),
                    "history": _spawn(_employee_history, company, row, results, llm),
                }
                for name, fut in jobs.items():
                    try:
                        out = fut.result()
                    except Exception:
                        out = None
                    if name == "history":
                        prof["employees_over_time"] = out or []
        # Employees: never leave blank when the application row already knows it. After the
        # recall net, so a researched figure still wins over the application's.
        if not str(prof.get("employees", "")).strip():
            prof["employees"] = str(row.get("employees_count", "") or row.get("employee_band", "")).strip()
        # Grade the surviving (grounded) memberships by prestige tier so the ecosystem score
        # can weight a top-tier accelerator above a generic one. Must follow the program
        # recheck — it grades whatever that found. In place; never adds or removes a program.
        try:
            _grade_programs(prof.get("programs", []), company, llm)
        except Exception:
            pass
        # Founder deep-dive fills thin backgrounds, so it must follow the recovery pass above.
        if do_web:
            try:
                _deepen_founders(prof, company, llm)
            except Exception:
                pass
        return {"profile": prof, "facts": _profile_facts(prof)}
    except Exception:
        return {"profile": dict(EMPTY_PROFILE), "facts": []}
