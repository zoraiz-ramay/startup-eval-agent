"""
Core engine for the Siemens Startup Evaluation Agent.

Pipeline (per the deck):
    INPUT -> ENRICH -> VERIFY -> STRUCTURE -> SCORE -> REVIEW (+ ROUTE)

This package re-exports the public API so callers can keep doing `import core` and
reference `core.evaluate`, `core.LLMClient`, etc. exactly as before the split.
The engine is organised into focused modules:

    config       paths, weights, thresholds, model settings
    text         normalisation / keyword / stopword helpers
    provenance   the Fact dataclass (evidence with provenance)
    llm          Azure OpenAI LLMClient
    web          DuckDuckGo search helpers
    data         GlassDollar / web-profile / Siemens-tools / PDF loading
    enrich       claim verification + fact enrichment
    summarize    offering summary
    verify       fact verification (LLM + heuristic)
    fit          Siemens-tool matching / fit scoring
    score        weighted six-dimension scoring
    route        Connect / Collaborate / Empower / Pass routing
    trend        live market-trend analysis
    chat         ad-hoc Q&A over AI / web / GlassDollar DB
    pipeline     evaluate() orchestration
"""
from __future__ import annotations

from .config import (
    WEIGHTS, THIN_PROFILE_CAP, FIT_ALIGN_THRESHOLD, MIN_OFFLINE_OVERLAP,
    LLM_MODEL, LLM_TIMEOUT, BASE_DIR, PDF_DIR,
    DEFAULT_GLASSDOLLAR, DEFAULT_TOOLS_CSV,
    GLASSDOLLAR_API_BASE, GLASSDOLLAR_API_KEY, GLASSDOLLAR_API_TIMEOUT,
)
from .provenance import Fact
from .llm import LLMClient
from .web import ddg_search
from .data import (
    load_glassdollar, load_glassdollar_api, search_glassdollar, find_startup, web_profile_row,
    load_siemens_tools, extract_pdf_text,
)
from .glassdollar_api import (
    GlassDollarClient, GlassDollarError, load_all_as_df, search_as_df,
    search_companies, get_company, get_company_row, company_to_row,
)
from .enrich import enrich
from .summarize import summarize_offering
from .verify import verify_facts, build_claims
from .fit import match_siemens_tools, FIT_SHORTLIST_SIZE
from .score import score_startup
from .route import route
from .trend import analyze_trend
from .chat import (
    chat_answer, chat_answer_multi, chat_smart, search_glassdollar_db,
    CHAT_DETAIL, CHAT_MAX_TOKENS,
)
from .pipeline import evaluate

__all__ = [
    # config
    "WEIGHTS", "THIN_PROFILE_CAP", "FIT_ALIGN_THRESHOLD", "MIN_OFFLINE_OVERLAP",
    "LLM_MODEL", "LLM_TIMEOUT", "BASE_DIR", "PDF_DIR",
    "DEFAULT_GLASSDOLLAR", "DEFAULT_TOOLS_CSV",
    "GLASSDOLLAR_API_BASE", "GLASSDOLLAR_API_KEY", "GLASSDOLLAR_API_TIMEOUT",
    # provenance
    "Fact",
    # llm
    "LLMClient",
    # web
    "ddg_search",
    # data
    "load_glassdollar", "load_glassdollar_api", "search_glassdollar", "find_startup", "web_profile_row",
    "load_siemens_tools", "extract_pdf_text",
    # glassdollar api
    "GlassDollarClient", "GlassDollarError", "load_all_as_df", "search_as_df",
    "search_companies", "get_company", "get_company_row", "company_to_row",
    # enrich / summarize / verify / fit / score / route / trend
    "enrich", "summarize_offering", "verify_facts", "build_claims",
    "match_siemens_tools", "FIT_SHORTLIST_SIZE", "score_startup", "route",
    "analyze_trend",
    # chat
    "chat_answer", "chat_answer_multi", "chat_smart", "search_glassdollar_db",
    "CHAT_DETAIL", "CHAT_MAX_TOKENS",
    # pipeline
    "evaluate",
]
