"""Siemens portfolio fit — two-stage LLM tool matching with an offline fallback."""
from __future__ import annotations

import logging
import os

import pandas as pd

from .config import FIT_ALIGN_THRESHOLD, MIN_OFFLINE_OVERLAP
from .text import _norm, _keywords
from .llm import LLMClient

log = logging.getLogger(__name__)

# Size of the LLM-ranked shortlist sent to the final fit match. Override with FIT_SHORTLIST_SIZE.
FIT_SHORTLIST_SIZE = int(os.getenv("FIT_SHORTLIST_SIZE", "80"))


def _derive_fit_keywords(startup_text: str, llm: LLMClient) -> list[str]:
    """Stage 1 — ask the LLM for the search terms most relevant to matching THIS startup against
    the Siemens portfolio: its core capabilities, technologies, industry verticals and the
    industrial/engineering function areas it touches. Falls back to offline keyword extraction
    from the startup text when the LLM is unavailable or returns nothing."""
    if llm and llm.available:
        prompt = (
            "A startup is described below. List the search terms that best capture what it does and "
            "which Siemens software/portfolio areas are relevant to match it against — its core "
            "capabilities, technologies, industry verticals, and the industrial/engineering function "
            "areas it touches. Prefer short terms (1-3 words) and include close synonyms.\n\n"
            f"STARTUP:\n{startup_text}\n\n"
            'Return ONLY JSON: {"keywords": ["...", "..."]}'
        )
        data = LLMClient.parse_json(llm.complete(prompt, max_tokens=400))
        if data and isinstance(data.get("keywords"), list):
            terms = [str(k).strip() for k in data["keywords"] if str(k).strip()]
            if terms:
                return terms
    # offline fallback: significant words straight from the startup text
    return sorted(_keywords(startup_text))


def _shortlist_tools(tools: list[dict], terms: list[str], limit: int) -> list[dict]:
    """Stage 2 — rank the full catalogue by relevance to the derived terms and return the top
    `limit`. Each tool scores by full-phrase substring hits (strong) plus word overlap (weak)."""
    norm_terms = [(_norm(t), set(_norm(t).split())) for t in terms if str(t).strip()]
    scored = []
    for tool in tools:
        blob = _norm(f"{tool['product']} {tool['category']} {tool['division']} {tool['description']}")
        blob_words = set(blob.split())
        score = 0
        for phrase, words in norm_terms:
            if phrase and phrase in blob:
                score += 3
            elif words:
                score += len(words & blob_words)
        if score > 0:
            scored.append((score, tool))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [tool for _, tool in scored[:limit]]


def match_siemens_tools(row: pd.Series, pitch_pdf: str, tools: list[dict], llm: LLMClient) -> dict:
    """Return {'aligned': bool, 'matches': [{tool, division, confidence, rationale}], 'method': ...}.

    LLM path is two-stage: (1) the LLM derives startup-specific search terms, (2) those terms
    shortlist the catalogue to the most relevant tools, (3) the LLM picks the best fits from
    that shortlist. This keeps the final prompt small and focused instead of sending all tools.
    """
    startup_text = " ".join(str(row.get(c, "")) for c in
                            ("company_name", "Your pitch", "short_description", "Differentiation",
                             "about_enriched", "Which Siemens function will profit from your solution?")) + " " + pitch_pdf[:1500]

    if llm.available:
        terms = _derive_fit_keywords(startup_text, llm)
        shortlist = _shortlist_tools(tools, terms, FIT_SHORTLIST_SIZE)
        log.info("[fit] %s — catalogue=%d keywords=%d shortlist=%d",
                 row.get("company_name","?"), len(tools), len(terms), len(shortlist))
        if shortlist:
            catalogue = "\n".join(f"- {t['product']} | {t['category']} | {t['division']} | {t['description']}"
                                  for t in shortlist)
            prompt = (
                "You match a startup to the Siemens software portfolio below. Pick the 3 tools whose "
                "deployable capability the startup most closely relates to (functional adjacency, "
                "not keyword overlap). For each, classify the RELATION:\n"
                "- complement: the startup adds capability the tool lacks (best for partnership)\n"
                "- integration: the startup plugs into / extends the tool\n"
                "- substitute: the startup does the same thing (competitor — weak partnership fit)\n"
                "- adjacent: same domain, different function\n"
                "If NONE are a credible fit, return aligned=false with an empty matches list.\n\n"
                f"STARTUP:\n{startup_text}\n\n"
                f"SIEMENS PORTFOLIO (top {len(shortlist)} candidates):\n{catalogue}\n\n"
                'Return ONLY JSON: {"aligned": true/false, "matches": '
                '[{"tool": "...", "division": "...", "confidence": 0-100, '
                '"relation": "complement|integration|substitute|adjacent", "rationale": "one sentence"}]}'
            )
            data = LLMClient.parse_json(llm.complete(prompt, max_tokens=900))
            if data and "matches" in data:
                data.setdefault("aligned", bool(data["matches"]))
                data["method"] = "llm"
                data["shortlist_size"] = len(shortlist)
                data["keywords"] = terms
                data["challenge_match"] = _challenge_match(startup_text)
                return data

    # ---- offline keyword fallback ----
    skw = _keywords(startup_text)
    scored = []
    for t in tools:
        tkw = _keywords(f"{t['product']} {t['category']} {t['description']}")
        overlap = skw & tkw
        if len(overlap) >= MIN_OFFLINE_OVERLAP:
            conf = min(95, 25 + 12 * len(overlap))
            scored.append({"tool": t["product"], "division": t["division"], "confidence": conf,
                           "rationale": f"Shared focus: {', '.join(sorted(overlap)[:4])}.", "_n": len(overlap)})
    scored.sort(key=lambda x: x["_n"], reverse=True)
    top = [{k: v for k, v in m.items() if k != "_n"} for m in scored[:3]]
    aligned = bool(top) and top[0]["confidence"] >= FIT_ALIGN_THRESHOLD
    return {"aligned": aligned, "matches": top if aligned else [], "method": "offline_keyword",
            "challenge_match": _challenge_match(startup_text)}


def _challenge_match(startup_text: str) -> dict:
    """Demand-side fit: score the startup against the recorded challenge library
    (problems Siemens people asked to be solved). Keyword-overlap based, so it works
    offline and adds no LLM latency; grows stronger as the library grows."""
    try:
        from .solve import load_challenges
        # Governance: ONLY approved challenges influence production scoring. Pending
        # (unreviewed) and rejected items are excluded.
        challenges = [c for c in load_challenges() if c.get("status") == "approved"]
    except Exception:
        challenges = []
    if not challenges:
        return {"score": 0.0, "best_problem": "", "library_size": 0}
    skw = _keywords(startup_text)
    best_score, best_problem = 0.0, ""
    for ch in challenges:
        ckw = _keywords(str(ch.get("problem", "")) + " " + " ".join(ch.get("keywords", [])))
        if not ckw:
            continue
        overlap = len(skw & ckw) / max(3, len(ckw))          # fraction of the need covered
        if overlap > best_score:
            best_score, best_problem = overlap, str(ch.get("problem", ""))
    return {"score": round(min(100.0, best_score * 100), 1),
            "best_problem": best_problem[:200], "library_size": len(challenges)}
