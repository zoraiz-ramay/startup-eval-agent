"""Market trend analysis — AI generates queries, DuckDuckGo fetches, AI synthesizes a verdict."""
from __future__ import annotations

import os

import pandas as pd

from .llm import LLMClient
from .web import _ddg_many

# Set TREND_ANALYSIS=off to disable globally (e.g. for batch runs where cost matters).
_TREND_ENABLED = os.getenv("TREND_ANALYSIS", "on").strip().lower() != "off"

_TREND_LABELS = {
    (80, 100): ("📈 Strongly Growing",  "#00875a"),
    (60,  79): ("📈 Growing",           "#00875a"),
    (40,  59): ("➡️  Stable / Emerging",  "#b8860b"),
    (20,  39): ("📉 Cooling",            "#a32d2d"),
    ( 0,  19): ("📉 Declining / Niche",  "#a32d2d"),
}


def _trend_label(score: int):
    for (lo, hi), (label, color) in _TREND_LABELS.items():
        if lo <= score <= hi:
            return label, color
    return "➡️  Unknown", "#5f6368"


def analyze_trend(row: "pd.Series", summary: str, niche_terms: list[str],
                 llm: LLMClient, do_web: bool = True) -> dict:
    """Three-stage trend analysis:
      1. AI generates targeted search queries from the startup's niche.
      2. DuckDuckGo fetches live results for those queries.
      3. AI synthesizes a verdict + momentum score + signal bullets + citations.
    Returns a dict with keys: label, color, momentum, niche, summary, signals, evidence, method.
    """
    if not _TREND_ENABLED:
        return {"label": "—", "color": "#5f6368", "momentum": 0,
                "niche": "", "summary": "Trend analysis disabled.",
                "signals": [], "evidence": [], "method": "disabled"}

    company = str(row.get("company_name", "")).strip() or "the startup"
    pitch   = str(row.get("Your pitch", "") or row.get("short_description", ""))[:600]

    # ---- Stage 1: AI generates search queries specific to this niche ---------
    niche = ""
    queries: list[str] = []
    if llm.available:
        q1_prompt = (
            f"A startup called '{company}' operates in this space: {pitch}\n"
            f"Niche keywords already identified: {', '.join(niche_terms[:12])}\n\n"
            "Produce:\n"
            "1. A concise market-niche label (5-10 words, e.g. 'industrial part traceability / digital fingerprinting').\n"
            "2. Five DuckDuckGo search queries that together cover: "
            "market trends, recent funding, market size/CAGR, key competitors, "
            "and geographic growth hotspots for this niche (use year 2025 or 2026 where helpful).\n"
            'Return ONLY JSON: {"niche": "...", "queries": ["...", "...", "...", "...", "..."]}'
        )
        data = LLMClient.parse_json(llm.complete(q1_prompt, max_tokens=400))
        if data:
            niche   = str(data.get("niche",   "")).strip()
            queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()]

    if not queries:
        # fallback: build basic queries from niche_terms directly
        niche = " / ".join(niche_terms[:4]) if niche_terms else company
        base  = " ".join(niche_terms[:4]) or company
        queries = [
            f"{base} market trend 2026",
            f"{base} startup funding 2025",
            f"{base} market size CAGR",
            f"{base} competitors landscape",
            f"{base} industry growth geography",
        ]

    # ---- Stage 2: DuckDuckGo fetches live results ----------------------------
    evidence: list[dict] = []
    web_text = ""
    if do_web:
        raw = _ddg_many({str(i): q for i, q in enumerate(queries)}, max_results=4)
        hits = [h for bucket in raw.values() for h in bucket]
        # deduplicate by URL
        seen_urls: set[str] = set()
        for h in hits:
            url = h.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                evidence.append({"title": h.get("title", ""),
                                  "url": url,
                                  "snippet": h.get("body", "")[:200]})
        web_text = "\n".join(
            f"[{e['url']}] {e['title']}: {e['snippet']}" for e in evidence[:20]
        )

    # ---- Stage 3: AI synthesizes verdict from search results -----------------
    if llm.available:
        grounded = bool(web_text)
        context  = f"WEB SEARCH RESULTS:\n{web_text}\n\n" if grounded else ""
        instruct = ("Use ONLY the web results above." if grounded
                    else "Use your training knowledge (no live data available).")
        q3_prompt = (
            f"{context}"
            f"Based on the above, assess the global market trend for the niche: '{niche}'.\n"
            f"{instruct}\n\n"
            "Return ONLY JSON with these keys:\n"
            "  momentum  : integer 0-100 (100 = fastest growing, 0 = declining)\n"
            "  summary   : 2-3 sentence assessment of the trend\n"
            "  signals   : list of 5 short bullet strings covering "
            "funding activity, market size/CAGR, recent news/momentum, "
            "competitor density, and geographic hotspots\n"
            'example: {"momentum": 74, "summary": "...", "signals": ["...", ...]}'
        )
        data3 = LLMClient.parse_json(llm.complete(q3_prompt, max_tokens=800))
        if data3 and "momentum" in data3:
            momentum = max(0, min(100, int(data3["momentum"])))
            label, color = _trend_label(momentum)
            return {
                "label":    label,
                "color":    color,
                "momentum": momentum,
                "niche":    niche,
                "summary":  str(data3.get("summary", "")).strip(),
                "signals":  [str(s) for s in data3.get("signals", [])],
                "evidence": evidence,
                "method":   "web+llm" if grounded else "llm-knowledge",
            }

    # offline fallback
    return {
        "label": "➡️  Unknown", "color": "#5f6368", "momentum": 0,
        "niche": niche, "summary": "Trend analysis unavailable (no LLM or web).",
        "signals": [], "evidence": evidence, "method": "offline",
    }
