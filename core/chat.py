"""Ad-hoc chat / Q&A over AI knowledge, the web, and the GlassDollar database."""
from __future__ import annotations

import os

import pandas as pd

from .llm import LLMClient
from .web import ddg_search
from .text import _norm, _STOP


def search_glassdollar_db(df: "pd.DataFrame", query: str, max_results: int = 6) -> list[dict]:
    """Keyword-rank rows of the GlassDollar export against a free-form question."""
    terms = [t for t in _norm(query).split() if len(t) > 2 and t not in _STOP]
    if df is None or not terms:
        return []
    cols = list(df.columns)
    scored = []
    for _, row in df.iterrows():
        blob = " ".join(str(row.get(c, "")) for c in cols).lower()
        score = sum(blob.count(t) for t in terms)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, row in scored[:max_results]:
        out.append({
            "company": str(row.get("company_name", "") or row.get("submission_title", "")),
            "hq": str(row.get("hq", "")),
            "funding": str(row.get("funding", "")),
            "customers": str(row.get("customers", "") or row.get("Reference customers", "")),
            "website": str(row.get("website", "")),
            "description": str(row.get("short_description", "") or row.get("Your pitch", ""))[:400],
            "score": int(score),
        })
    return out


# Chat verbosity. Pick a level with the CHAT_DETAIL env var:
#   concise  - one-line answer + 1-2 sentences of reasoning
#   balanced - direct answer + a short paragraph (3-5 sentences)   [default]
#   detailed - direct answer + fuller multi-point reasoning with caveats
# Each level sets BOTH the prompt instruction and the visible-answer token budget, because on
# gpt-5.x reasoning models the prompt is what really governs length (raising tokens alone does
# little). Set CHAT_MAX_TOKENS to override the budget independently of the level.
_CHAT_STYLES = {
    "concise": (
        " Be concise. Lead with a direct one-line answer (start with Yes or No when the "
        "question is yes/no), then add at most 1-2 short sentences of reasoning. No preamble, "
        "no headings, no essays.",
        900),
    "balanced": (
        " Lead with a direct one-line answer (start with Yes or No when the question is "
        "yes/no), then give a short paragraph of 3-5 sentences explaining the reasoning. "
        "No preamble, no headings.",
        1600),
    "detailed": (
        " Lead with a direct one-line answer (start with Yes or No when the question is "
        "yes/no), then explain your reasoning in a few short paragraphs or bullet points, "
        "covering the key factors and any caveats. Stay focused and avoid filler.",
        3000),
}
CHAT_DETAIL = os.getenv("CHAT_DETAIL", "balanced").strip().lower()
_CHAT_BREVITY, _CHAT_BUDGET = _CHAT_STYLES.get(CHAT_DETAIL, _CHAT_STYLES["balanced"])
# CHAT_MAX_TOKENS caps the visible answer; defaults to the chosen level's budget.
# Hard cap of 600 tokens so chat answers stay short regardless of the chosen level.
CHAT_MAX_TOKENS = min(600, int(os.getenv("CHAT_MAX_TOKENS", str(_CHAT_BUDGET))))


def chat_answer(question: str, source: str, *, df: "pd.DataFrame" = None,
                llm: "LLMClient" = None, context_company: str = "",
                context_brief: str = "", max_results: int = 5) -> dict:
    """Answer a free-form question using ONE selected source.

    source: 'ai' (Siemens LLM knowledge) | 'web' (DuckDuckGo) | 'database' (GlassDollar export).
    context_brief: optional facts about the currently evaluated startup, used to ground answers.
    Returns {'answer': markdown, 'evidence': [{title,url,snippet}], 'source': source}.
    """
    source = (source or "ai").lower()

    # ---- GlassDollar database -------------------------------------------------
    if source == "database":
        rows = search_glassdollar_db(df, question, max_results=max_results)
        evidence = [{"title": r["company"], "url": r["website"], "snippet": r["description"]} for r in rows]
        if not rows:
            return {"answer": "No matching rows in the GlassDollar database.", "evidence": [], "source": source}
        if llm and llm.available:
            ctx = "\n".join(
                f"- {r['company']} | HQ: {r['hq']} | Funding: {r['funding']} | "
                f"Customers: {r['customers']} | {r['description']}" for r in rows)
            prompt = (f"Answer the question using ONLY the GlassDollar database rows below. "
                      f"If the answer is not present, say so plainly.\n\nQUESTION: {question}\n\nROWS:\n{ctx}")
            ans = llm.complete(prompt, system="You answer strictly from the provided GlassDollar database rows." + _CHAT_BREVITY,
                               max_tokens=CHAT_MAX_TOKENS)
            if ans.strip():
                return {"answer": ans.strip(), "evidence": evidence, "source": source}
        md = "**Top matches in GlassDollar:**\n" + "\n".join(
            f"- **{r['company']}** — {r['description'] or 'no description'}"
            + (f"  · _Customers:_ {r['customers']}" if r["customers"] else "")
            for r in rows)
        return {"answer": md, "evidence": evidence, "source": source}

    # ---- Web (DuckDuckGo) -----------------------------------------------------
    if source == "web":
        q = f"{context_company} {question}".strip() if context_company else question
        hits = ddg_search(q, max_results=max_results)
        evidence = [{"title": h.get("title", ""), "url": h.get("href", ""),
                     "snippet": h.get("body", "")} for h in hits]
        if not hits:
            return {"answer": "No web results found via DuckDuckGo.", "evidence": [], "source": source}
        if llm and llm.available:
            ev = "\n".join(f"- [{h.get('href','')}] {h.get('title','')}: {h.get('body','')[:240]}" for h in hits)
            prompt = (f"Answer the question using ONLY the web results below. Cite sources inline as [n] "
                      f"matching their order.\n\nQUESTION: {question}\n\nWEB RESULTS:\n{ev}")
            ans = llm.complete(prompt, system="You answer strictly from the supplied web search results and cite sources." + _CHAT_BREVITY,
                               max_tokens=CHAT_MAX_TOKENS)
            if ans.strip():
                return {"answer": ans.strip(), "evidence": evidence, "source": source}
        md = "**Top DuckDuckGo results:**\n" + "\n".join(
            f"- [{h.get('title','(link)')}]({h.get('href','')}) — {h.get('body','')[:160]}" for h in hits)
        return {"answer": md, "evidence": evidence, "source": source}

    # ---- AI (model knowledge) -------------------------------------------------
    if not (llm and llm.available):
        return {"answer": "AI search is unavailable — Azure OpenAI credentials are not configured.",
                "evidence": [], "source": source}
    parts = []
    if context_brief:
        parts.append("Context — the startup currently in focus (from this app's evaluation):\n" + context_brief)
    elif context_company:
        parts.append(f"Current startup in focus: {context_company}.")
    parts.append("Question: " + question)
    ans = llm.complete(
        "\n\n".join(parts),
        system=("You are a helpful Siemens startup-scouting analyst. Build on the provided "
                "startup context when it is relevant." + _CHAT_BREVITY),
        max_tokens=CHAT_MAX_TOKENS)
    ans = ans.strip()
    if not ans:
        why = getattr(llm, "last_error", "") or "the model returned an empty response"
        return {"answer": f"⚠️ AI call failed — {why}", "evidence": [], "source": source}
    return {"answer": ans, "evidence": [], "source": source}


def chat_smart(question: str, *, llm: "LLMClient" = None, context_company: str = "",
               context_brief: str = "", max_results: int = 4) -> dict:
    """Single combined AI + web flow (credit-efficient: at most 2 LLM calls).

    1. ONE LLM call drafts an answer from model knowledge AND derives 2-3 targeted
       DuckDuckGo queries — including the exact startup name, so the web search hits
       the RIGHT company instead of a fuzzy guess.
    2. The queries run on DuckDuckGo (free).
    3. ONE LLM call refines: it merges its draft with the web evidence, corrects
       anything the evidence contradicts, and cites sources inline as [n].

    Falls back to a plain DDG search (with the context company prepended) when no
    LLM key is set. Returns {'answer', 'evidence', 'source'}.
    """
    from .web import _ddg_many

    # ---------------- offline fallback: web-only ----------------
    if not (llm and llm.available):
        q = f"{context_company} {question}".strip() if context_company else question
        hits = ddg_search(q, max_results=max_results + 2)
        evidence = [{"title": h.get("title", ""), "url": h.get("href", ""),
                     "snippet": h.get("body", "")} for h in hits]
        if not hits:
            return {"answer": "No web results found, and no LLM key is set for AI answers.",
                    "evidence": [], "source": "web"}
        md = "**Top web results** (configure Azure OpenAI for AI-refined answers):\n" + "\n".join(
            f"- [{h.get('title','(link)')}]({h.get('href','')}) — {h.get('body','')[:160]}" for h in hits)
        return {"answer": md, "evidence": evidence, "source": "web"}

    # ---------------- stage 1: draft + targeted queries (1 LLM call) ----------------
    ctx = ""
    if context_brief:
        ctx = "Context — the startup currently in focus (from this app's evaluation):\n" + context_brief + "\n\n"
    elif context_company:
        ctx = f"Current startup in focus: {context_company}.\n\n"
    stage1 = LLMClient.parse_json(llm.complete(
        f"{ctx}QUESTION: {question}\n\n"
        "Do two things:\n"
        "1. Draft a direct answer from your own knowledge (2-4 sentences; say 'unknown' where unsure).\n"
        "2. Write 2-3 web search queries to verify/extend the answer. Use the EXACT company name "
        "from the context when the question concerns it, so the search finds the right startup.\n"
        'Return ONLY JSON: {"draft": "...", "queries": ["...", "..."]}',
        system="You are a Siemens startup-scouting analyst. JSON only.", max_tokens=500)) or {}
    draft = str(stage1.get("draft", "")).strip()
    queries = [str(q).strip() for q in (stage1.get("queries") or []) if str(q).strip()][:3]
    if not queries:
        queries = [f"{context_company} {question}".strip()]

    # ---------------- stage 2: web evidence ----------------
    results = _ddg_many({str(i): q for i, q in enumerate(queries)}, max_results=max_results)
    hits, seen = [], set()
    for i in range(len(queries)):
        for h in results.get(str(i), []):
            url = h.get("href", "")
            if url and url not in seen:
                seen.add(url)
                hits.append(h)
    evidence = [{"title": h.get("title", ""), "url": h.get("href", ""),
                 "snippet": h.get("body", "")} for h in hits[:8]]

    # ---------------- stage 3: refine draft with evidence (1 LLM call) ----------------
    # The LLM adjudicates relevance: it reports WHICH evidence items it actually used, and
    # only those are surfaced as sources — irrelevant DDG hits are dropped, not displayed.
    if hits:
        ev = "\n".join(f"[{i+1}] {h.get('title','')}: {h.get('body','')[:220]} ({h.get('href','')})"
                       for i, h in enumerate(hits[:8]))
        data = LLMClient.parse_json(llm.complete(
            f"{ctx}QUESTION: {question}\n\nYOUR DRAFT ANSWER:\n{draft or '(no draft)'}\n\n"
            f"WEB EVIDENCE:\n{ev}\n\n"
            "Produce the final answer: merge your draft with the evidence, correct the draft "
            "wherever the evidence contradicts it, and cite evidence inline as [n]. IGNORE "
            "irrelevant evidence entirely — do not cite it. If nothing is relevant, rely on "
            "the draft and say the web added nothing.\n"
            'Return ONLY JSON: {"answer": "...", "used": [1, 3]} where used lists the evidence '
            "numbers you actually relied on (empty list if none).",
            system="You give one refined, evidence-grounded answer with [n] citations. JSON only." + _CHAT_BREVITY,
            max_tokens=CHAT_MAX_TOKENS))
        if data and str(data.get("answer", "")).strip():
            used = {int(n) for n in data.get("used", []) if str(n).isdigit()}
            kept = [evidence[n - 1] for n in sorted(used) if 1 <= n <= len(evidence)]
            return {"answer": str(data["answer"]).strip(), "evidence": kept,
                    "source": "AI + web (combined)" if kept else "AI (web added nothing)"}
    if draft:
        return {"answer": draft + "\n\n_(no usable web results — answer from AI knowledge only)_",
                "evidence": [], "source": "AI"}
    why = getattr(llm, "last_error", "") or "the model returned an empty response"
    return {"answer": f"⚠️ AI call failed — {why}", "evidence": evidence, "source": "AI + web"}


_SOURCE_LABELS = {"ai": "AI (OpenAI)", "web": "Web (DuckDuckGo)", "database": "GlassDollar database"}


def chat_answer_multi(question: str, sources, *, df: "pd.DataFrame" = None,
                      llm: "LLMClient" = None, context_company: str = "",
                      context_brief: str = "", max_results: int = 5) -> dict:
    """Answer a question using one OR MORE selected sources and combine the results.

    sources: any subset of ['ai', 'web', 'database']. Each source is queried independently;
    when more than one is selected the answers are returned as labelled sections and all
    evidence is merged. Returns {'answer': markdown, 'evidence': [...], 'source': 'a, b'}.
    """
    picked = [s.lower() for s in (sources or []) if s] or ["ai"]
    sections, evidence = [], []
    for s in picked:
        r = chat_answer(question, s, df=df, llm=llm, context_company=context_company,
                        context_brief=context_brief, max_results=max_results)
        sections.append((_SOURCE_LABELS.get(s, s), r["answer"]))
        evidence.extend(r.get("evidence", []))
    if len(sections) == 1:
        answer = sections[0][1]
    else:
        answer = "\n\n".join(f"**{label}**\n\n{text}" for label, text in sections)
    return {"answer": answer, "evidence": evidence,
            "source": ", ".join(_SOURCE_LABELS.get(s, s) for s in picked)}
