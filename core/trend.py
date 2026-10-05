"""Market trend analysis — AI generates queries, DuckDuckGo fetches, AI synthesizes a verdict."""
from __future__ import annotations

import concurrent.futures
import contextvars
import functools
import os
import re

import pandas as pd

from .llm import LLMClient
from .text import _clean_source_url, _norm
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


# ------------------------------------------------------------------ market landscape
#
# The trend verdict answers "is this space growing". A reviewer deciding whether to spend a week on
# a startup also needs "who else is in it, and who is funding them" — and stage 1 has always ASKED
# for competitor and funding queries, then thrown everything except the prose away.
#
# These five queries ride in the SAME wave as stage 2's, so the landscape costs no extra search
# time: _ddg_many caps concurrency at 10 and the merged wave is exactly that. The one added cost is
# a completion, and it runs concurrently with the momentum call.
def _landscape_queries(niche: str, markets: list[str] | None = None) -> dict:
    """The landscape's queries. Size is searched under the PARENT market's name, the way reports
    are titled ("chemical recycling market"), not the 5-10 word niche label: "AI-powered robotics
    operating system for flexible industrial automation market size" returned a CAGR definition
    page and a calculator, never a report."""
    market = (markets or [""])[0] or niche
    return {
        "lc_competitors": f"{niche} competitors vendors alternatives landscape",
        "lc_funding": f"{niche} startup raised seed series A funding round 2025 2026",
        "lc_size": f"{market} market size billion CAGR report",
        "lc_investors": f"{niche} investors venture capital active portfolio",
        "lc_leaders": f"{(markets or [''])[-1] or niche} market size growth leading companies",
    }


# What a market figure looks like in a page: an amount with a magnitude, or a percentage.
_FIGURE = re.compile(r"(?:[$€£]|USD|EUR|US\$)\s?\d[\d.,]*\s?(?:billion|million|bn|mn|bln|B|M)\b"
                     r"|\d[\d.,]*\s?(?:billion|million|bn|bln)\b|\d+(?:[.,]\d+)?\s?%|CAGR", re.I)


def _figure_sentences(text: str, limit: int = 1500) -> str:
    """The sentences of a report page that state a market figure, up to ``limit`` characters.

    Search snippets end mid-sentence — Phena's "USD 12.5 billion in 2025, with a compound a…" lost
    its CAGR at the cut — so the top size results are read as pages, keeping only what matters."""
    out, total = [], 0
    for sentence in re.split(r"(?<=[.!?])\s+", str(text or "")):
        sentence = sentence.strip()
        if 20 <= len(sentence) <= 400 and len(_FIGURE.findall(sentence)) >= 2:
            out.append(sentence)
            total += len(sentence)
            if total >= limit:
                break
    return " ".join(out)


def _read_size_pages(hits: list[dict], pages: int = 2) -> list[dict]:
    """The top size-query results fetched as pages and cut to their figure sentences.

    A fetch, not a model call, through the SSRF-guarded and cached web.fetch_url; a page that does
    not load is simply skipped."""
    from .web import fetch_url
    urls = [h.get("href", "") for h in hits[:pages] if h.get("href")]
    if not urls:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as ex:
        texts = list(ex.map(lambda u: fetch_url(u, timeout=8.0), urls))
    return [{"title": h.get("title", ""), "url": u, "snippet": s}
            for h, u, t in zip(hits, urls, texts) if (s := _figure_sentences(t))]


def _blank(value) -> str:
    """A value as text, with the model's ways of saying 'nothing' made empty. str(None) once
    reached the page as the market size "None"."""
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in ("none", "null", "n/a", "na", "unknown", "-", "—") else text


def _numbers_cited(value: str, raw_text: str) -> bool:
    """Every number in ``value`` appears in the results it was read from. Simplifying is allowed;
    adding a number is not (the same rule as core/business_flow.py::_supported)."""
    numbers = re.findall(r"\d+(?:[.,]\d+)?", value)
    return bool(numbers) and all(n in raw_text for n in numbers)


def _grounded_rows(items, text_blob: str, name_key: str, fields: tuple) -> list[dict]:
    """Keep entries that name something the evidence actually mentions AND cite a real link.

    Two gates, and both matter. The source URL is the citation rule the whole app runs on. The
    name check is the same bar `profile._ground_customers` applies: asked for competitors in a
    niche, a model will happily list the three companies it remembers from training rather than
    the ones in the results, and a fabricated competitor is indistinguishable from a real one
    once it is on screen next to a link.
    """
    out, seen = [], set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get(name_key, "")).strip()
        url = _clean_source_url(item.get("source_url"))
        key = _norm(name)
        if not name or not url or key in seen:
            continue
        if key not in text_blob:
            continue
        seen.add(key)
        row = {name_key: name, "source_url": url}
        for f in fields:
            value = str(item.get(f, "")).strip()
            if value:
                row[f] = value
        out.append(row)
    return out


def _market_landscape(niche: str, evidence: list[dict], web_text: str,
                      llm: LLMClient, company: str = "", markets: list[str] | None = None) -> dict | None:
    """Competitors, funded peers, market size and active investors — strictly from the results."""
    if not (llm.available and web_text and niche):
        return None
    data = LLMClient.parse_json(llm.complete(
        f"WEB SEARCH RESULTS about the market niche '{niche}':\n{web_text}\n\n"
        "Extract the competitive and funding landscape STRICTLY from the results above. Use only "
        "companies, figures and investors that actually appear in the text — a plausible name you "
        "recall is worse than a short list, because a reader cannot tell the two apart.\n"
        "- competitors: companies offering a comparable product in this niche. NOT the startup "
        "being evaluated, and not generic categories.\n"
        "- funded_peers: companies in this niche that raised money, with the round, amount and "
        "date exactly as stated. Omit any field the results do not state.\n"
        "- market_size: the size of the market this startup sells into (or its closest parent "
        "market), only if a figure is actually cited. "
        + (f"Prefer a figure for '{markets[0]}'"
           + (f"; use '{markets[1]}' only when no figure for the first is cited" if len(markets) > 1 else "")
           + ", and never a broader market when a narrower one is cited. " if markets else "")
        + "`value` is the CURRENT or base-year size "
        "and `as_of` its year; a projected figure goes in `forecast_value` / `forecast_year`, "
        "never in `value`. `cagr` is the compound annual growth rate as stated. Copy figures "
        "exactly; leave a field empty when the results do not state it.\n"
        "- active_investors: investors named as backing companies in this niche.\n"
        "Every entry needs source_url: a real http link copied from the results.\n"
        'Return ONLY JSON: {"competitors":[{"name":"","note":"","source_url":""}],'
        '"funded_peers":[{"company":"","round":"","amount":"","date":"","investors":"",'
        '"source_url":""}],"market_size":{"value":"","as_of":"","forecast_value":"",'
        '"forecast_year":"","cagr":"","source_url":""},'
        '"active_investors":[{"name":"","note":"","source_url":""}]}',
        system="You extract structured market facts strictly from supplied evidence. JSON only.",
        max_tokens=900, reasoning="none")) or {}

    # Grounding is checked against the raw result text the model was shown, not its own output,
    # and against the same rows: the name check once read only the landscape queries' results
    # while the prompt also held the trend ones, so a competitor named there was dropped.
    raw_text = "\n".join(f"{e.get('title', '')} {e.get('snippet', '')} {e.get('url', '')}" for e in evidence)
    blob = _norm(raw_text)
    urls = {e.get("url", "") for e in evidence}
    size = data.get("market_size") if isinstance(data.get("market_size"), dict) else {}
    size_url = _clean_source_url(size.get("source_url"))
    # A figure stands only if every number in it is in the results, from a URL the search returned:
    # the size used to be the one landscape field with no grounding at all.
    fields = {k: _blank(size.get(k)) for k in ("value", "as_of", "forecast_value", "forecast_year", "cagr")}
    for k in ("value", "forecast_value", "cagr"):
        if fields[k] and not _numbers_cited(fields[k], raw_text):
            fields[k] = ""
    market_size = None
    if size_url in urls and (fields["value"] or fields["cagr"]):
        market_size = {"value": fields["value"], "cagr": fields["cagr"], "as_of": fields["as_of"],
                       **({"forecast_value": fields["forecast_value"], "forecast_year": fields["forecast_year"]}
                          if fields["forecast_value"] else {}),
                       "source_url": size_url}

    # The startup is not its own competitor. The prompt says so and the model lists it anyway —
    # Celonis came back at the top of its own process-mining landscape — because it is genuinely
    # the most prominent name in results about its own niche. Enforced here rather than argued
    # about in the prompt.
    self_ref = _norm(company)
    landscape = {
        "competitors": [c for c in _grounded_rows(data.get("competitors"), blob, "name", ("note",))
                        if not self_ref or _norm(c["name"]) != self_ref],
        "funded_peers": [p for p in _grounded_rows(data.get("funded_peers"), blob, "company",
                                                   ("round", "amount", "date", "investors"))
                         if not self_ref or _norm(p["company"]) != self_ref],
        "active_investors": _grounded_rows(data.get("active_investors"), blob, "name", ("note",)),
        "market_size": market_size,
    }
    # Returned even when every list came back empty. `landscape: {}` and no `landscape` key at all
    # are different statements — "we looked and found nothing" versus "this run never looked" —
    # and the UI says so differently.
    return landscape


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
    markets: list[str] = []
    if llm.available:
        q1_prompt = (
            f"A startup called '{company}' operates in this space: {pitch}\n"
            f"Niche keywords already identified: {', '.join(niche_terms[:12])}\n\n"
            "Produce:\n"
            "1. A concise market-niche label (5-10 words, e.g. 'industrial part traceability / digital fingerprinting').\n"
            "2. Five DuckDuckGo search queries that together cover: "
            "market trends, recent funding, market size/CAGR, key competitors, "
            "and geographic growth hotspots for this niche (use year 2025 or 2026 where helpful).\n"
            "3. One or two parent markets as market research reports name them, 2-4 words each, "
            "most specific first (e.g. 'chemical recycling', 'industrial machine vision').\n"
            'Return ONLY JSON: {"niche": "...", "queries": ["...", "...", "...", "...", "..."], '
            '"markets": ["...", "..."]}'
        )
        data = LLMClient.parse_json(llm.complete(q1_prompt, max_tokens=400))
        if data:
            niche   = str(data.get("niche",   "")).strip()
            queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()]
            markets = [re.sub(r"\s+market$", "", _blank(m), flags=re.I) for m in data.get("markets") or []
                       if _blank(m)][:2]

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
    landscape_evidence: list[dict] = []
    landscape_rows: list[dict] = []
    web_text = ""
    landscape_text = ""
    if do_web:
        # One wave for both the trend verdict and the landscape. Merged rather than run in
        # sequence because _ddg_many's semaphore caps concurrency at 10 anyway, so ten queries
        # cost one round trip and the landscape adds no search time at all.
        wave = {str(i): q for i, q in enumerate(queries)}
        wave.update(_landscape_queries(niche or " ".join(niche_terms[:4]) or company, markets))
        raw = _ddg_many(wave, max_results=4)

        def _collect(keys):
            out, seen_urls = [], set()
            for key in keys:
                for h in raw.get(key, []) or []:
                    url = h.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        # The whole snippet: cut at 200 characters, Phena's "USD 12.5 billion in
                        # 2025, with a compound a…" lost its CAGR. Snippets run to ~300 at most.
                        out.append({"title": h.get("title", ""), "url": url, "snippet": h.get("body", "")})
            return out

        evidence = _collect(str(i) for i in range(len(queries)))
        # The top market-size results read as pages (their figure sentences only) go first.
        pages = _read_size_pages(raw.get("lc_size", []) or [])
        landscape_evidence = pages + [e for e in _collect(_landscape_queries("").keys())
                                      if e["url"] not in {p["url"] for p in pages}]
        as_text = lambda rows: "\n".join(  # noqa: E731
            f"[{e['url']}] {e['title']}: {e['snippet']}" for e in rows)
        web_text = as_text(evidence[:20])
        # The landscape reads its own queries' results plus the trend ones: a funding round for a
        # peer turns up as often in a "market trends" result as in a "who raised" result. Each
        # gets its own budget — one shared cap of 20 let the landscape fill it and cut every trend
        # result, which is where the older runs' market figures were.
        landscape_rows = landscape_evidence[:22] + [e for e in evidence[:20]
                                                    if e["url"] not in {x["url"] for x in landscape_evidence}]
        landscape_text = as_text(landscape_rows)

    # ---- Stage 3: AI synthesizes verdict from search results -----------------
    if llm.available:
        # The momentum call reads the SAME evidence as the landscape, not just the trend queries'
        # share of it. Two calls over different slices produced a page that contradicted itself:
        # "no CAGR figures are cited" as the stated basis for a momentum of 50, directly above a
        # cited CAGR of 31.7%. The rubric asks the model to count what the evidence contains, so
        # narrowing what it can see was working against the calibration too.
        grounded = bool(landscape_text or web_text)
        context = f"WEB SEARCH RESULTS:\n{landscape_text or web_text}\n\n" if grounded else ""
        instruct = ("Use ONLY the web results above." if grounded
                    else "Use your training knowledge (no live data available).")
        # Momentum is CALIBRATED against named reference points, and counted rather than felt.
        # Left to itself the model returned 90, 92, 92 and 92 across every niche it was ever
        # asked about — plastic upcycling, industrial vision, enterprise decision intelligence —
        # so `market` sat at ~70 for every company and the dimension decided nothing. The scale
        # was not being used; only its top was. Anchoring each band to a real sector and asking
        # for the count of funding events actually present in the evidence gives the number
        # something to be wrong about.
        q3_prompt = (
            f"{context}"
            f"Based on the above, assess the global market trend for the niche: '{niche}'.\n"
            f"{instruct}\n\n"
            "MOMENTUM IS A CALIBRATED SCALE, not a verdict on whether the niche is interesting. "
            "Place it against these reference points:\n"
            "  90-100 : among the fastest-growing sectors in the world right now — the scale of "
            "AI infrastructure in 2024, or grid-scale storage. Multiple billion-dollar rounds "
            "inside twelve months. Rare; most niches are not here.\n"
            "  70-89  : clearly expanding, well funded, widely reported. Several sizeable raises "
            "and a published CAGR above roughly 15%.\n"
            "  40-69  : real and growing at about the rate of industry generally. A handful of "
            "raises, steady adoption, no surge. THIS IS THE MOST COMMON ANSWER.\n"
            "  20-39  : flat or consolidating; funding thin, incumbents entrenched.\n"
            "  0-19   : contracting, or so specialised the question barely applies.\n"
            "Justify the number from what the evidence COUNTS — how many funding events appear "
            "above, what CAGR figures are actually cited, how many distinct competitors are "
            "named — not from how promising the technology sounds. A niche you cannot find "
            "funding evidence for is not a 90.\n\n"
            "Return ONLY JSON with these keys:\n"
            "  momentum  : integer 0-100, placed on the scale above\n"
            "  basis     : one short sentence naming the counted evidence behind the number\n"
            "  summary   : 2-3 sentence assessment of the trend\n"
            "  signals   : list of 5 short bullet strings covering "
            "funding activity, market size/CAGR, recent news/momentum, "
            "competitor density, and geographic hotspots\n"
            'example: {"momentum": 54, "basis": "Three seed rounds and one Series A cited; no '
            'CAGR figure in the results.", "summary": "...", "signals": ["...", ...]}'
        )
        # The momentum call and the landscape extraction read the same evidence and neither needs
        # the other's answer, so they overlap instead of adding up. copy_context carries the
        # cache-bypass ContextVar across the thread boundary, the same rule as every other pool
        # in the engine — without it a forced refresh would replay cached completions here.
        def _spawn(ex, fn, *a):
            return ex.submit(contextvars.copy_context().run, functools.partial(fn, *a))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_momentum = _spawn(ex, lambda: llm.complete(q3_prompt, max_tokens=800))
            f_landscape = _spawn(ex, _market_landscape, niche, landscape_rows,
                                 landscape_text, llm, company, markets)
            try:
                data3 = LLMClient.parse_json(f_momentum.result())
            except Exception:
                data3 = None
            # Best-effort: the landscape is an addition to the verdict, never a precondition for
            # it. A failure here costs the landscape, not the trend.
            try:
                landscape = f_landscape.result()
            except Exception:
                landscape = None

        if data3 and "momentum" in data3:
            momentum = max(0, min(100, int(data3["momentum"])))
            label, color = _trend_label(momentum)
            return {
                "label":    label,
                "color":    color,
                "momentum": momentum,
                "niche":    niche,
                "summary":  str(data3.get("summary", "")).strip(),
                # What the number was counted from. Stored so a reviewer can see whether a
                # momentum of 85 rests on four cited rounds or on enthusiasm, which the score
                # alone cannot distinguish.
                "basis":    str(data3.get("basis", "")).strip(),
                "signals":  [str(s) for s in data3.get("signals", [])],
                "evidence": evidence,
                # Absent entirely when the landscape was never attempted, `{}`-shaped with empty
                # lists when it ran and found nothing. The UI reads those as different sentences:
                # "not researched on this run" versus "the search named no competitor".
                **({"landscape": landscape} if landscape is not None else {}),
                "method":   "web+llm" if grounded else "llm-knowledge",
            }

    # offline fallback
    return {
        "label": "➡️  Unknown", "color": "#5f6368", "momentum": 0,
        "niche": niche, "summary": "Trend analysis unavailable (no LLM or web).",
        "signals": [], "evidence": evidence, "method": "offline",
    }
