"""Deep structured profile research: founders, advisors, employees, parent group,
startup programs (Xcelerator / incubators / corporate programs), reference customers,
and Siemens Financial Services (SFS) relevance.

LLM path: LLM-generated queries -> DuckDuckGo -> LLM extraction strictly from evidence,
every populated field backed by a source URL. Offline fallback: keyword detection over
the same search corpus, so a profile is always returned.
"""
from __future__ import annotations

import re

import pandas as pd

from .provenance import Fact
from .web import _ddg_many
from .llm import LLMClient
from .config import KNOWN_PROGRAM_TIERS
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
    "programs": [],           # [{name, type: incubator|accelerator|corporate_program, source_url}]
    "reference_customers": [],  # NAMED accounts only, grounded in evidence
    "customer_segment": "",    # segment/scale descriptor when customers aren't named (e.g. "7-8 figure e-commerce brands")
    "sfs": {"relevant": False, "rationale": ""},
    "method": "none",
}


def _corpus(results: dict) -> str:
    lines = []
    for key, hits in results.items():
        for h in hits or []:
            lines.append(f"[{key}] {h.get('title','')} :: {h.get('body','')} :: {h.get('href','')}")
    return "\n".join(lines)[:9000]


def _queries(company: str, row: pd.Series, llm: LLMClient) -> dict:
    base = {
        "founders": f"{company} founders co-founder CEO CTO LinkedIn",
        "founder_bg": f"{company} founder previous company career university",
        "advisors": f"{company} advisory board scientific advisor professor",
        "programs": f"{company} accelerator incubator startup program member cohort",
        # Generic membership signals rather than a few brand names, so the evidence surfaces
        # whatever program the startup actually belongs to (YC, Techstars, Antler, ...). The
        # grounding gate (see _program_grounded) requires the program to co-occur with the
        # company in a single result, so naming programs here can't create false positives.
        "corp_programs": f'{company} ("backed by" OR alumni OR cohort OR portfolio OR '
                         f'accelerator OR incubator OR "Y Combinator" OR Techstars)',
        "parent": f"{company} subsidiary parent company acquired part of group",
        "team": f"{company} number of employees headcount team size",
        "customers": f"{company} customer case study deployment client announcement",
    }
    if llm.available:
        known = " ".join(str(row.get(c, "")) for c in ("short_description", "Your pitch"))[:600]
        prompt = (f"We research the startup '{company}' ({known}). Suggest up to 4 additional web "
                  "search queries that would surface: its founders' backgrounds, scientific/industry "
                  "advisors, membership in incubators/accelerators/corporate startup programs, or a "
                  'corporate parent. Return ONLY JSON: {"queries": ["..."]}')
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=300))
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


def _program_grounded(name: str, company: str, app_text: str, results: dict) -> str | None:
    """Decide whether a program membership is actually tied to THIS startup.

    Returns a source_url (possibly '') when grounded, or None when it is not:
      * evidenced  -> the program name and the company co-occur in a SINGLE web result;
                      returns that result's URL.
      * self-claim -> the startup's own application text names the program; returns ''.
      * ungrounded -> returns None (caller drops it).

    Matching a program name anywhere in the concatenated corpus is NOT enough: the
    program search query names specific programs, so DuckDuckGo returns generic program
    directory pages that mention many unrelated startups. Requiring the program and the
    company in the same result is what prevents false memberships (e.g. AfterFlow showing
    Nvidia Inception / Microsoft for Startups / Google for Startups it never had)."""
    n = str(name).strip().lower()
    if not n:
        return None
    if company:
        for hits in results.values():
            for h in hits or []:
                blob = (str(h.get("title", "")) + " " + str(h.get("body", ""))).lower()
                if n in blob and company in blob:
                    return h.get("href", "") or ""
    if n in app_text:                    # self-claim in the startup's own text
        return ""
    return None


def _detect_programs(row: pd.Series, results: dict) -> list[dict]:
    """Keyword scan for KNOWN_PROGRAMS, kept only for programs grounded to THIS startup
    (see _program_grounded). Used offline AND as a safety net alongside LLM extraction,
    so a genuine known-program mention never disappears if the LLM omitted it."""
    company = str(row.get("company_name", "")).strip().lower()
    app_text = _startup_text(row).lower()
    found = []
    for name, ptype in KNOWN_PROGRAMS.items():
        src = _program_grounded(name, company, app_text, results)
        if src is not None:
            found.append({"name": name.strip().title(), "type": ptype, "source_url": src})
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
        src = _program_grounded(name, company, app_text, results)
        if src is None:
            continue
        seen.add(key)
        out.append({"name": name,
                    "type": str(p.get("type") or "program").strip() or "program",
                    "source_url": src})
    return out


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
        "Also judge: is Siemens Financial Services (equipment/project financing, leasing) a relevant "
        "partnership avenue for this startup (e.g. hardware, capex-heavy, energy/infrastructure)?\n\n"
        'Return ONLY JSON:\n'
        '{"founders": [{"name":"","role":"","background":"","linkedin":"","source_url":""}],\n'
        ' "key_team": [{"name":"","role":"","source_url":""}],\n'
        ' "advisors": [{"name":"","role":"","affiliation":"","source_url":""}],\n'
        ' "employees": "", "parent_group": "",\n'
        ' "programs": [{"name":"","type":"incubator|accelerator|corporate_program","source_url":""}],\n'
        ' "reference_customers": [""], "customer_segment": "",\n'
        ' "sfs": {"relevant": true, "rationale": "one sentence"}}'
    )
    data = LLMClient.parse_json(llm.complete(prompt, system="You extract structured company facts "
                                             "strictly from supplied evidence. JSON only.",
                                             max_tokens=1200))
    if not data:
        return None
    prof = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in EMPTY_PROFILE.items()}
    for key in ("founders", "key_team", "advisors", "programs", "reference_customers"):
        if isinstance(data.get(key), list):
            prof[key] = [x for x in data[key] if x]
    prof["employees"] = str(data.get("employees") or "").strip()
    prof["parent_group"] = str(data.get("parent_group") or "").strip()
    prof["customer_segment"] = str(data.get("customer_segment") or "").strip()
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
        max_tokens=700)) or {}
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
        max_tokens=700)) or {}
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
            add("program", label, p.get("source_url", ""))
    add("parent_group", prof.get("parent_group", ""))
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
    extra = _ddg_many(queries, max_results=5, overall_timeout=20.0)
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
                max_tokens=500)) or {}
            found = _ground_programs(data.get("programs", []), row, combined)
    if found:
        seen = set()
        deduped = []
        for p in found:
            k = str(p.get("name", "")).strip().lower()
            if k and k != company_l and k not in seen:
                seen.add(k)
                deduped.append(p)
        prof["programs"] = deduped


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
        system="You grade startup-program prestige. JSON only.", max_tokens=300)) or {}
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
        max_tokens=600)) or {}
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
        results = _ddg_many(_queries(company, row, llm), max_results=4,
                            overall_timeout=25.0) if do_web else {}
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
            prof["programs"] = _ground_programs(prof.get("programs", []), row, results)
            seen = {p["name"].lower() for p in prof["programs"]}
            for p in _detect_programs(row, results):
                if p["name"].lower() not in seen:
                    prof["programs"].append(p)
        # Named-companies-only filter + grounding (a web-extracted name must co-occur with
        # the company or be self-declared), then backfill from the DB row if research found
        # none. DB-declared customers are trusted, so the backfill needs no grounding.
        prof["reference_customers"] = _ground_customers(
            _clean_customers(prof["reference_customers"]), row, results)
        if not prof["reference_customers"]:
            raw = str(row.get("customers", "") or row.get("Reference customers", ""))
            prof["reference_customers"] = _clean_customers(re.split(r"[,\n;·|]+", raw))
        # Employees: never leave blank when the application row already knows it.
        if not str(prof.get("employees", "")).strip():
            prof["employees"] = str(row.get("employees_count", "") or row.get("employee_band", "")).strip()
        # Headcount-over-time: dedicated, evidence-cited series (empty unless >=2 cited points).
        if do_web:
            try:
                prof["employees_over_time"] = _employee_history(company, row, results, llm)
            except Exception:
                prof["employees_over_time"] = []
        # Recall check: when programs come back empty, don't conclude "none" yet — run a
        # dedicated ecosystem/program search wave (plus the site text) and re-ground before
        # declaring the field unavailable. Best-effort; never costs the profile.
        if do_web:
            try:
                _recheck_programs(prof, row, company, results, llm)
            except Exception:
                pass
        # Grade the surviving (grounded) memberships by prestige tier so the ecosystem
        # score can weight a top-tier accelerator above a generic one. In place; never
        # adds or removes a program.
        try:
            _grade_programs(prof.get("programs", []), company, llm)
        except Exception:
            pass
        # Founder recovery (when extraction found none) then deep-dive (fill thin
        # backgrounds). Both best-effort: a failure here must never cost the profile.
        if do_web:
            try:
                _recover_founders(prof, company, llm)
            except Exception:
                pass
            try:
                _deepen_founders(prof, company, llm)
            except Exception:
                pass
        return {"profile": prof, "facts": _profile_facts(prof)}
    except Exception:
        return {"profile": dict(EMPTY_PROFILE), "facts": []}
