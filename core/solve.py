"""Problem -> startup mode: a Siemens user states a problem to be solved; the agent
derives capability keywords, gathers candidate startups from GlassDollar and the web,
and ranks them against the problem (LLM, with an offline keyword fallback).

Every stated problem is also appended to a persistent challenge library
(challenges.json in DATA_DIR), which over time becomes the demand-side catalogue
that the normal evaluate-mode fit can score against.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import concurrent.futures
from datetime import datetime, timezone

from .config import BASE_DIR
from .text import _keywords
from .web import _ddg_many
from .llm import LLMClient

CHALLENGES_PATH = os.getenv("CHALLENGES_JSON", str(pathlib.Path(BASE_DIR) / "challenges.json"))

_SOCIAL = ("linkedin.", "crunchbase.", "wikipedia.", "facebook.", "twitter.", "x.com",
           "youtube.", "instagram.", "reddit.", "medium.", "glassdoor.")


# ----------------------------------------------------------------- challenge library
def load_challenges() -> list[dict]:
    try:
        with open(CHALLENGES_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def set_challenge_status(index: int, status: str, reviewer: str = "",
                         reviewer_oid: str = "") -> dict | None:
    """Innovation-team approval control: mark a challenge approved/rejected/pending.

    `reviewer_oid` is the caller's verified directory id when the API supplies one, so that
    an approval here is as attributable as a pillar override. Optional and plain strings:
    core/ stays runnable from scripts and tests with no web request in sight.
    """
    if status not in ("pending", "approved", "rejected"):
        return None
    items = load_challenges()
    if not (0 <= index < len(items)):
        return None
    items[index]["status"] = status
    items[index]["reviewer"] = reviewer
    items[index]["reviewer_oid"] = reviewer_oid
    try:
        with open(CHALLENGES_PATH, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2, ensure_ascii=False)
    except Exception:
        return None
    return items[index]


def save_challenge(problem: str, keywords: list[str], asked_by: str = "") -> None:
    """Append the stated problem to the persistent challenge library (best-effort)."""
    try:
        items = load_challenges()
        norm = problem.strip().lower()
        if any(str(c.get("problem", "")).strip().lower() == norm for c in items):
            return                          # already recorded
        items.append({"problem": problem.strip(), "keywords": keywords, "asked_by": asked_by,
                      "status": "pending",       # innovation-team oversight: pending|approved|rejected
                      "reviewer": "", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        os.makedirs(os.path.dirname(CHALLENGES_PATH) or ".", exist_ok=True)
        with open(CHALLENGES_PATH, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ----------------------------------------------------------------- keyword derivation
def _derive_keywords(problem: str, llm: LLMClient) -> list[str]:
    if llm.available:
        prompt = ("A Siemens employee states a problem they need solved:\n\n"
                  f"PROBLEM: {problem}\n\n"
                  "List 4-8 short search phrases (2-4 words) describing the startup capabilities "
                  "or product categories that could solve it. Include close synonyms.\n"
                  'Return ONLY JSON: {"keywords": ["..."]}')
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=300, reasoning="none"))
        if data and isinstance(data.get("keywords"), list):
            terms = [str(k).strip() for k in data["keywords"] if str(k).strip()]
            if terms:
                return terms[:8]
    kws = sorted(_keywords(problem))
    return [" ".join(kws[i:i + 2]) for i in range(0, min(len(kws), 8), 2)] or [problem[:60]]


# ----------------------------------------------------------------- candidate gathering
def _application_candidates(keywords: list[str], local_df, limit: int = 10) -> list[dict]:
    """Search the LOCAL Siemens applications Excel (pitch-form rows) for solver startups.
    Rank rows by keyword overlap across the descriptive columns. Only used in problem
    mode — general name search/evaluation stays on the GlassDollar API."""
    if local_df is None or not len(local_df):
        return []
    kws = set()
    for kw in keywords:
        kws |= _keywords(kw)
    desc_cols = [c for c in ("Your pitch", "short_description", "Differentiation",
                             "Business model", "customers", "Reference customers",
                             "Which Siemens function will profit from your solution?")
                 if c in local_df.columns]
    name_col = "company_name" if "company_name" in local_df.columns else local_df.columns[0]
    scored = []
    for _, row in local_df.iterrows():
        blob = " ".join(str(row.get(c, "")) for c in desc_cols)
        overlap = kws & _keywords(blob)
        if len(overlap) >= 2:
            # description carries the pitch text too, so the ranking stage sees the
            # same evidence that matched the row (short_description alone is often thin)
            desc = " — ".join(x for x in (str(row.get("short_description", "")).strip(),
                                          str(row.get("Your pitch", "")).strip()) if x)
            scored.append((len(overlap), {
                "name": str(row.get(name_col, "")).strip(), "source": "applications",
                "description": desc[:400], "website": str(row.get("website", ""))}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit] if c["name"]]


def _glassdollar_candidates(keywords: list[str], limit_per_kw: int = 5) -> list[dict]:
    """Best-effort candidate search in GlassDollar. The API searches by NAME, so keyword
    hits are opportunistic — a miss is normal and web candidates fill the gap."""
    from . import glassdollar_api
    out, seen = [], set()
    # Small parallel batch; one timeout attempt per search prevents retry cascades.
    client = glassdollar_api.GlassDollarClient(timeout=8, max_attempts=1)
    def search(kw):
        try:
            return client.search_companies(kw, limit=limit_per_kw)
        except glassdollar_api.GlassDollarError:
            return []
    try:
        # Authenticate once before fan-out: creating a client per keyword races the
        # heavily rate-limited token endpoint on a cold cache.
        client._valid_token()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            batches = list(pool.map(search, keywords[:3]))
    except glassdollar_api.GlassDollarError:
        return []
    finally:
        client._session.close()
    for batch in batches:
        for c in batch:
            name = str(c.get("name", "")).strip()
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            out.append({"name": name, "source": "glassdollar",
                        "glassdollar_id": c.get("id", ""),
                        "description": str(c.get("description") or c.get("short_description") or "")[:1200],
                        "website": str(c.get("website") or c.get("domain") or "")})
    return out



def _web_candidates(keywords: list[str], llm: LLMClient) -> list[dict]:
    queries = {f"kw_{i}": f"startup {kw} solution company" for i, kw in enumerate(keywords[:6])}
    results = _ddg_many(queries, max_results=5)
    hits = [h for hs in results.values() for h in (hs or [])]
    if not hits:
        return []
    if llm.available:
        text = "\n".join(f"- {h.get('title','')} :: {h.get('body','')} :: {h.get('href','')}"
                         for h in hits)[:7000]
        prompt = ("From the web search results below, extract the STARTUP COMPANIES mentioned "
                  "(company names, not articles or lists). For each give a one-line description "
                  "based only on the results, and the most likely website URL from the results.\n\n"
                  f"RESULTS:\n{text}\n\n"
                  'Return ONLY JSON: {"companies": [{"name":"","description":"","website":""}]}')
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=900, reasoning="none"))
        if data and isinstance(data.get("companies"), list):
            return [{"name": str(c.get("name", "")).strip(), "source": "web",
                     "description": str(c.get("description", ""))[:400],
                     "website": str(c.get("website", ""))}
                    for c in data["companies"] if isinstance(c, dict) and str(c.get("name", "")).strip()][:15]
    # offline: treat non-social result domains as candidate companies
    out, seen = [], set()
    for h in hits:
        href = str(h.get("href", ""))
        m = re.search(r"https?://(?:www\.)?([^/]+)/?", href)
        if not m or any(s in href for s in _SOCIAL):
            continue
        domain = m.group(1)
        name = domain.split(".")[0].capitalize()
        if name.lower() in seen or len(name) < 3:
            continue
        seen.add(name.lower())
        out.append({"name": name, "source": "web", "description": str(h.get("body", ""))[:300],
                    "website": f"https://{domain}"})
    return out[:12]


# ----------------------------------------------------------------- ranking
def _rank(problem: str, candidates: list[dict], llm: LLMClient) -> list[dict]:
    if not candidates:
        return []
    if llm.available:
        listing = "\n".join(f"{i}. {c['name']} [{c['source']}] :: {c['description']}"
                            for i, c in enumerate(candidates))
        prompt = ("Rank the candidate startups below by how directly they could solve this "
                  f"problem for Siemens:\n\nPROBLEM: {problem}\n\nCANDIDATES:\n{listing}\n\n"
                  "Score each 0-100 for relevance and give a one-sentence rationale. Drop anything "
                  "that is not actually a startup/company or is clearly irrelevant (<30).\n"
                  'Return ONLY JSON: {"ranked": [{"index": 0, "relevance": 0, "rationale": ""}]}')
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=1000))
        if data and isinstance(data.get("ranked"), list):
            out, used = [], set()
            for r in data["ranked"]:
                try:
                    index = int(r["index"])
                    if index < 0 or index >= len(candidates) or index in used:
                        continue
                    relevance = max(0, min(100, int(r.get("relevance", 0))))
                    c = dict(candidates[index])
                except (KeyError, ValueError, TypeError):
                    continue
                used.add(index)
                c["relevance"] = relevance
                c["rationale"] = str(r.get("rationale", ""))[:300]
                if c["relevance"] >= 30:
                    out.append(c)
            out.sort(key=lambda x: x["relevance"], reverse=True)
            return out
    # offline: keyword overlap between the problem and each candidate description
    pkw = _keywords(problem)
    out = []
    for c in candidates:
        overlap = pkw & _keywords(f"{c['name']} {c['description']}")
        rel = min(95, 20 + 15 * len(overlap))
        if rel >= 30:
            c = dict(c)
            c["relevance"] = rel
            c["rationale"] = "Shared terms: " + ", ".join(sorted(overlap)[:4]) + "."
            out.append(c)
    out.sort(key=lambda x: x["relevance"], reverse=True)
    return out


# ----------------------------------------------------------------- entry point
def _fill_candidate_gaps(candidates: list[dict]) -> None:
    """One web wave for missing descriptions. Use snippets verbatim with their URLs.

    A missing company website stays unknown: a search-result URL may be a news article.
    Full evaluation can establish that identity with its existing grounding checks.
    """
    gaps = [c for c in candidates if not c.get("description")][:5]
    if not gaps:
        return
    hits = _ddg_many({str(i): f'{c["name"]} company products solutions'
                      for i, c in enumerate(gaps)}, max_results=3)
    for i, c in enumerate(gaps):
        for h in hits.get(str(i), []) or []:
            body, url = str(h.get("body") or ""), str(h.get("href") or "")
            if c["name"].casefold() in body.casefold() and url.startswith(("https://", "http://")):
                c["description"] = body[:1200]
                c.setdefault("field_sources", {})["description"] = {"provider": "web", "url": url}
                break


def solve_problem(problem: str, llm: LLMClient = None, do_web: bool = True,
                  use_glassdollar: bool = True, local_df=None, tracxn=None) -> dict:
    """Tracxn -> GlassDollar fallback -> web gaps, plus matching internal applications.

    Tracxn is a request-scoped client for the signed-in user, never a global credential.
    LLMs extract/rank supplied evidence; unknown company facts stay unknown.
    """
    problem = str(problem or "").strip()
    if not problem:
        return {"problem": "", "keywords": [], "candidates": [], "method": "none", "sources": []}
    llm = llm or LLMClient(model=os.getenv("SCOUTING_LLM_MODEL", ""))
    sources = []
    candidates = []
    if tracxn is not None:
        try:
            candidates = tracxn.search(problem)
            sources.append({"provider": "tracxn", "status": "used" if candidates else "empty"})
        except Exception:
            sources.append({"provider": "tracxn", "status": "unavailable"})
    else:
        sources.append({"provider": "tracxn", "status": "not_connected"})
    # Keywords are unnecessary for a complete Tracxn result unless local applications exist.
    need_keywords = not candidates or local_df is not None
    keywords = _derive_keywords(problem, llm) if need_keywords else []
    save_challenge(problem, keywords)
    if not candidates and use_glassdollar:
        candidates = _glassdollar_candidates(keywords)
        sources.append({"provider": "glassdollar", "status": "used" if candidates else "empty_or_unavailable"})
    else:
        sources.append({"provider": "glassdollar", "status": "skipped" if candidates else "not_configured"})
    candidates = _application_candidates(keywords, local_df) + candidates
    # Source priority is retained and lower-priority duplicate records only fill blanks.
    unique = {}
    for c in candidates:
        key = c["name"].casefold()
        if key not in unique:
            unique[key] = c
            c["field_sources"] = {k: {"provider": c["source"]} for k in ("description", "website") if c.get(k)}
        else:
            for field in ("description", "website"):
                if not unique[key].get(field) and c.get(field):
                    unique[key][field] = c[field]
                    unique[key]["field_sources"][field] = {"provider": c["source"]}
    candidates = list(unique.values())[:20]
    if do_web:
        _fill_candidate_gaps(candidates)
    ranked = _rank(problem, candidates, llm)
    if do_web and len(ranked) < 5:
        if not keywords:
            keywords = _derive_keywords(problem, llm)
        web_candidates = _web_candidates(keywords[:3], llm)
        additions = [c for c in web_candidates if c["name"].casefold() not in unique]
        ranked += _rank(problem, additions, llm)
        ranked.sort(key=lambda c: c["relevance"], reverse=True)
        sources.append({"provider": "web", "status": "used" if web_candidates else "empty"})
    else:
        filled = any(v.get("provider") == "web" for c in candidates for v in c.get("field_sources", {}).values())
        sources.append({"provider": "web", "status": "used" if filled else "skipped" if do_web else "disabled"})
    # Raw vendor payloads can be large and are not part of the browser contract.
    for c in ranked:
        c.pop("provider_record", None)
    priority = {"applications": 0, "tracxn": 1, "glassdollar": 2, "web": 3}
    ranked.sort(key=lambda c: (priority.get(c["source"], 4), -c["relevance"]))
    return {"problem": problem, "keywords": keywords, "candidates": ranked[:10], "sources": sources,
            "method": "llm" if llm.available else "offline_keyword"}
