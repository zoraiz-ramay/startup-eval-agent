"""Paths, weighted-scoring config, and model/threshold constants.

Resolves the GlassDollar export and the downloaded pitch PDFs relative to the project
root, so the agent works no matter which directory it is launched from. Note this module
lives inside the ``core`` package, so ``_AGENT_DIR`` walks up TWO levels (core/ -> agent dir).
"""
from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv

# Loads .env from the project root (if present) before any env var below is read, so a
# local .env can carry secrets like GEMINI_API_KEY without exporting them in the shell.
load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

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
# A claim the web CONTRADICTS is worse evidence than a claim nobody addressed, and until this
# existed it cost nothing: completeness measures how much a run knows and cannot notice that what
# it knows disagrees with itself. Applied to data confidence rather than to a dimension, because
# the doubt is about the whole record. Floored, because these contradictions are frequently
# aggregators being stale rather than a startup misreporting — one disagreement between Tracxn and
# CB Insights should dent the confidence, not condemn the company.
# Mirrored in ui/src/scoring/engine-constants.json; pinned by tests/test_whatif_weight_parity.py.
CONTRADICTION_PENALTY = 0.05     # per contradicted claim
CONTRADICTION_FLOOR = 0.85       # never costs more than 15% of confidence
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
# Memberships evidenced ONLY by the company's own site ("self_asserted") earn a fraction of
# their tier, under their own lower cap. They cannot be treated as equal to third-party
# corroboration — a startup can put any logo on its /partners page — but discarding them
# outright is also wrong: NVIDIA Inception and Microsoft for Startups publish no searchable
# member directory, so a genuine membership there is frequently impossible to corroborate.
PROGRAM_SELF_ASSERTED_FACTOR = 0.5
PROGRAM_SELF_ASSERTED_CAP = 18.0
KNOWN_PROGRAM_TIERS = {
    "y combinator": "tier1", "techstars": "tier1", "siemens xcelerator": "tier1",
    "startup autobahn": "tier1", "nvidia inception": "tier1", "intel ignite": "tier1",
    "entrepreneur first": "tier1", "sosv": "tier1", "500 global": "tier1",
    "microsoft for startups": "tier2", "google for startups": "tier2", "aws activate": "tier2",
    "sap.io": "tier2", "plug and play": "tier2", "antler": "tier2", "masschallenge": "tier2",
    "startupbootcamp": "tier2", "seedcamp": "tier2", "alchemist accelerator": "tier2",
    "station f": "tier2", "eit": "tier2", "esa bic": "tier2",
}


# --- Traction rubric (core/traction.py) ----------------------------------------------------
# The product owner's points table, as data. Each band is (lower bound inclusive, points, label),
# highest first; amounts are EUR. A division with no evidence is dropped and the rest are
# normalised, so the maxima below are also what "confidence" is measured in: a run that evidences
# funding and customers has seen 60 of the 100 points it could have.
TRACTION_RUBRIC = {
    "funding": {"label": "Funding", "max": 30, "bands": (
        (2_000_000, 25, "≥ €2M"), (1_500_000, 15, "€1.5M – 2M"), (1_000_000, 10, "€1M – 1.5M"),
        (500_000, 5, "€500k – 1M"), (0.01, 2.5, "< €500k"))},
    "customers": {"label": "Customers", "max": 30},
    "revenue": {"label": "Revenue", "max": 30, "bands": (
        (10_000_000, 30, "≥ €10M"), (5_000_000, 25, "€5M – 10M"), (1_000_000, 20, "€1M – 5M"),
        (500_000, 15, "€500k – 1M"), (100_000, 10, "€100k – 500k"), (0.01, 5, "< €100k"))},
    "employees": {"label": "Employees", "max": 10, "bands": (
        (21, 10, "> 20"), (11, 8, "11 – 20"), (7, 6, "7 – 10"), (4, 4, "4 – 6"), (1, 2, "1 – 3"))},
}
# When the amount is undisclosed, the stage alone scores. With an amount, the amount bands decide,
# except that Series B+ at ≥ €2M lifts to the division maximum — without it the top band (25) would
# leave 30 unreachable. A grant is not on the ladder: it says nothing about size.
FUNDING_STAGE_POINTS = {"pre_seed": 5, "seed": 10, "series_a": 25, "series_b_plus": 30}
# Big-name and SME points add up (capped at the division max); a generically stated customer base
# ("chemical producers") is graded 1–3 and counts only if it beats the named total.
CUSTOMER_BIG_POINTS = ((3, 20), (2, 15), (1, 7.5))
CUSTOMER_SME_POINTS = ((6, 20), (3, 15), (2, 7), (1, 3.5))
CUSTOMER_GENERIC_POINTS = {1: 7.5, 2: 11.25, 3: 15}
# "Clearly strong recurring revenue growth" lifts revenue to 30 — only when the recurring nature,
# the growth figure and a material amount are all evidenced, never from the adjective alone.
GROWTH_STRONG_PCT = 100.0
GROWTH_STRONG_MIN_EUR = 1_000_000
HEADCOUNT_MAX_PLAUSIBLE = 500_000
# Static reference rates to EUR, stated with their date so a reader can see how old they are. A
# band edge is a coarse cut (€500k, €1M), so a rate that has moved a few percent changes nothing
# except an amount sitting right on an edge — which the panel shows in its original currency.
FX_AS_OF = "2026-09-01"
FX_TO_EUR = {
    "EUR": 1.0, "USD": 0.86, "GBP": 1.16, "CHF": 1.07, "SAR": 0.23, "AED": 0.234, "QAR": 0.236,
    "INR": 0.0098, "JPY": 0.0058, "CNY": 0.12, "SEK": 0.091, "NOK": 0.085, "DKK": 0.134,
    "PLN": 0.235, "CAD": 0.62, "AUD": 0.56, "SGD": 0.66, "HKD": 0.11, "ILS": 0.25, "BRL": 0.16,
    "KRW": 0.00062, "TRY": 0.021,
}
# Big-name baseline for customer classification. Offline this list alone decides; with a model, a
# grounded customer may be UPGRADED to large_enterprise but a name here is never downgraded. It is
# an identifying attribute of a third party (how big Bosch is), not a claim about the startup —
# the claim "Bosch is a customer" is still grounded by profile._ground_customers.
NOTABLE_COMPANIES = (
    'Siemens', 'Siemens Energy', 'Siemens Healthineers', 'Siemens Mobility', 'Siemens Gamesa',
    'Bosch', 'BASF', 'Bayer', 'BMW', 'Mercedes-Benz', 'Daimler Truck', 'Volkswagen', 'Audi',
    'Porsche', 'Continental', 'Infineon', 'SAP', 'Deutsche Bahn', 'Deutsche Telekom', 'DHL',
    'Lufthansa', 'Airbus', 'thyssenkrupp', 'ZF Friedrichshafen', 'Schaeffler', 'Merck', 'Henkel',
    'Covestro', 'Evonik', 'RWE', 'E.ON', 'EnBW', 'Uniper', 'Allianz', 'Munich Re', 'Deutsche Bank',
    'Commerzbank', 'adidas', 'Beiersdorf', 'Heidelberg Materials', 'Fresenius', 'TRUMPF', 'Festo',
    'KUKA', 'Voith', 'ABB', 'Schneider Electric', 'Rockwell Automation', 'Honeywell', 'Emerson',
    'General Electric', 'GE Vernova', 'GE HealthCare', 'Philips', 'ASML', 'STMicroelectronics',
    'NXP', 'Ericsson', 'Nokia', 'Volvo', 'Scania', 'Saab', 'Atlas Copco', 'Sandvik', 'SKF',
    'Hitachi', 'Toshiba', 'Mitsubishi', 'Panasonic', 'Sony', 'Toyota', 'Honda', 'Nissan',
    'Hyundai', 'Samsung', 'LG', 'Tata Steel', 'Tata Motors', 'Infosys', 'Wipro',
    'Reliance Industries', 'Saudi Aramco', 'SABIC', 'Shell', 'BP', 'TotalEnergies', 'Equinor',
    'Eni', 'Repsol', 'ExxonMobil', 'Chevron', 'Enel', 'Iberdrola', 'Engie', 'EDF', 'Orsted',
    'Vattenfall', 'Nestle', 'Unilever', 'Procter & Gamble', "L'Oreal", 'Danone', 'Novartis',
    'Roche', 'Sanofi', 'AstraZeneca', 'GSK', 'Pfizer', 'Johnson & Johnson', 'Medtronic', '3M',
    'Caterpillar', 'John Deere', 'Boeing', 'Lockheed Martin', 'Rolls-Royce', 'Safran', 'Thales',
    'Dassault Systemes', 'Renault', 'Stellantis', 'Ford', 'General Motors', 'Tesla', 'Microsoft',
    'Google', 'Amazon', 'Apple', 'Meta', 'IBM', 'Intel', 'NVIDIA', 'Oracle', 'Cisco', 'Dell', 'HP',
    'Accenture', 'Capgemini', 'Deloitte', 'PwC', 'KPMG', 'EY', 'McKinsey', 'Walmart', 'IKEA',
    'Maersk', 'UPS', 'FedEx', 'Dow', 'DuPont', 'Linde', 'Air Liquide', 'Saint-Gobain',
    'ArcelorMittal', 'Holcim', 'Heineken', 'AB InBev', 'Coca-Cola', 'PepsiCo',
)


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


# ----------------------------------------------------------------------------- Siemens Directory
# Employee directory (core/directory_api.py) for the "Relevant Siemens Contact" under Empower's
# Tool fit. API-key header; /people filtered by department. Like the GlassDollar key, it resolves
# only inside the Siemens network, so nothing about it can be verified from a laptop or CI. The
# header and parameter names are configurable because only the endpoint is documented here.
SIEMENS_DIRECTORY_API_BASE = os.getenv("SIEMENS_DIRECTORY_API_BASE", "https://api.siemens.com/directory").rstrip("/")
SIEMENS_DIRECTORY_KEY_HEADER = os.getenv("SIEMENS_DIRECTORY_KEY_HEADER", "x-api-key")
SIEMENS_DIRECTORY_DEPARTMENT_PARAM = os.getenv("SIEMENS_DIRECTORY_DEPARTMENT_PARAM", "department")
SIEMENS_DIRECTORY_CURSOR_PARAM = os.getenv("SIEMENS_DIRECTORY_CURSOR_PARAM", "cursor")
# The docs recommend low limits: one page of this size, at most DIRECTORY_MAX_PAGES pages.
SIEMENS_DIRECTORY_LIMIT = int(os.getenv("SIEMENS_DIRECTORY_LIMIT", "25"))
SIEMENS_DIRECTORY_MAX_PAGES = int(os.getenv("SIEMENS_DIRECTORY_MAX_PAGES", "4"))
SIEMENS_DIRECTORY_TIMEOUT = float(os.getenv("SIEMENS_DIRECTORY_TIMEOUT", "15"))
# How many contacts are shown per tool, and how long a tool's contacts are reused before asking again.
SIEMENS_CONTACTS_PER_TOOL = 3
SIEMENS_CONTACTS_TTL_DAYS = 7


# --- Connect: similar sellers and market signals (core/pillars.py, core/pillar_match.py) -------
# How many Xcelerator sellers nearest the startup's offering the Connect match labels same /
# different. Similarity scores alone cannot count "sells the same thing" — measured on the stored
# index every seller sits within 0.58-0.70 of the startup — so the model confirms each one, and the
# count can only reach this many ("30 or more").
CONNECT_NEIGHBOURS = 30
# The crowded case: (at least this many sellers sell the same kind of solution, Connect's total
# out of 9). Below the first band the open case scores the startup itself.
CONNECT_CROWDED = ((2, 3), (4, 2), (8, 1), (12, 0))
# How many similar sellers are named; the rest are "+ N more".
CONNECT_SIMILAR_SHOWN = 5
# "Good market signals", one point each of Market signals: a cited size or CAGR at or above these
# core/market.py levels (3 = >= EUR 5B / >= 5% CAGR), and this many grounded funded peers.
CONNECT_GOOD_MARKET = {"size_level": 3, "growth_level": 3, "funded_peers": 2}
