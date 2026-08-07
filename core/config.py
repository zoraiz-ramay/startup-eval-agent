"""Paths, weighted-scoring config, and model/threshold constants.

Resolves the GlassDollar export and the downloaded pitch PDFs relative to the project
root, so the agent works no matter which directory it is launched from. Note this module
lives inside the ``core`` package, so ``_AGENT_DIR`` walks up TWO levels (core/ -> agent dir).
"""
from __future__ import annotations

import os
import pathlib

# six weighted dimensions from the deck (sum = 1.00)
WEIGHTS = {
    "traction": 0.28,
    "siemens_fit": 0.27,
    "product": 0.15,
    "market": 0.12,
    "founder": 0.10,
    "ecosystem": 0.08,
}
THIN_PROFILE_CAP = 75.0          # sparse/unverifiable profiles top out here
FIT_ALIGN_THRESHOLD = 50.0       # below this, "not aligned with Siemens portfolio"
MIN_OFFLINE_OVERLAP = 2          # offline mode needs >=2 meaningful shared terms to count
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.4")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

# --- Program prestige -------------------------------------------------------------------
# Membership in a startup program is a credibility signal, but not all programs are equal: a
# spot in Y Combinator / Techstars or a Siemens-run program (Xcelerator, Startup Autobahn) is
# far stronger evidence than a generic local incubator. The ecosystem score therefore weights
# each EVIDENCED membership by a prestige tier instead of counting them flat. The tier is
# graded by the LLM (global reputation) and falls back to KNOWN_PROGRAM_TIERS offline.
PROGRAM_PRESTIGE_WEIGHTS = {"tier1": 16.0, "tier2": 11.0, "tier3": 6.0}
PROGRAM_PRESTIGE_CAP = 36.0      # max ecosystem points contributed by program prestige
KNOWN_PROGRAM_TIERS = {
    "y combinator": "tier1", "techstars": "tier1", "siemens xcelerator": "tier1",
    "startup autobahn": "tier1", "nvidia inception": "tier1", "intel ignite": "tier1",
    "entrepreneur first": "tier1", "sosv": "tier1", "500 global": "tier1",
    "microsoft for startups": "tier2", "google for startups": "tier2", "aws activate": "tier2",
    "sap.io": "tier2", "plug and play": "tier2", "antler": "tier2", "masschallenge": "tier2",
    "startupbootcamp": "tier2", "seedcamp": "tier2", "alchemist accelerator": "tier2",
    "station f": "tier2", "eit": "tier2", "esa bic": "tier2",
}


def _find_data_dir(start: pathlib.Path) -> pathlib.Path:
    # also scan the repo's data/ folder, where the shipped xlsx/pdfs/runs.db live —
    # local (non-Docker) runs previously missed it unless env vars were set.
    for p in [start, *start.parents]:
        for cand in (p, p / "data", p / "glassdollar_scraper"):
            if (cand / "pdfs").is_dir() or (cand / "glassdollar_applications.xlsx").exists():
                return cand
    return start


# config.py sits in core/, so the agent directory is one level up from this file's parent.
_AGENT_DIR = pathlib.Path(__file__).resolve().parent.parent
BASE_DIR = pathlib.Path(os.getenv("DATA_DIR") or _find_data_dir(_AGENT_DIR))
PDF_DIR = os.getenv("PDF_DIR", str(BASE_DIR / "pdfs"))
DEFAULT_GLASSDOLLAR = os.getenv("GLASSDOLLAR_XLSX", str(BASE_DIR / "glassdollar_applications.xlsx"))
DEFAULT_TOOLS_CSV = os.getenv("SIEMENS_TOOLS_CSV", str(_AGENT_DIR / "siemens_tools.csv"))

# ----------------------------------------------------------------------------- GlassDollar API
# Live GlassDollar public REST API (replaces the local Excel export). Auth is a two-step flow:
# POST {BASE}/v1/token with header `X-API-Key: <key>` returns a short-lived bearer token, which
# is then sent as `Authorization: Bearer <token>` on every data call. The API key is read from
# the environment so the secret never lives in source. Set it once per session (PowerShell):
#     $env:GLASSDOLLAR_API_KEY = "<your api key>"
GLASSDOLLAR_API_BASE = os.getenv("GLASSDOLLAR_API_BASE", "https://actions-api.glassdollar.com").rstrip("/")
GLASSDOLLAR_API_KEY = os.getenv("GLASSDOLLAR_API_KEY", "").strip()
# Per-request timeout (seconds) for GlassDollar API calls.
GLASSDOLLAR_API_TIMEOUT = float(os.getenv("GLASSDOLLAR_API_TIMEOUT", "60"))
