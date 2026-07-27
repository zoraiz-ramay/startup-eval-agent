# Startup Evaluation Agent — Project Status

A problem-led, evidence-led, route-specific startup collaboration engine for
**Siemens for Startups**. Type a startup name (or describe a problem) → the agent
gathers evidence, verifies claims, scores, and routes the startup to
**Empower / Collaborate / Connect / Pass** — with full provenance, persistence,
and human oversight.

---

## Architecture

```
React SPA (:3000, nginx)  ──proxy──►  FastAPI (:8000)  ──►  core/ pipeline  ──►  SQLite (data/runs.db)
Streamlit legacy (:8501)  ────────────────────────────────►  core/ (same logic, marked legacy)
```

| Layer | Location | Role |
|---|---|---|
| React UI | `ui/` | Main product (Tracxn-style enterprise dashboard) |
| FastAPI | `api/` | REST API, security, persistence |
| Core pipeline | `core/` | All business logic (UI-independent) |
| Data | `data/` | Applications xlsx, pitch PDFs, runs.db, challenges.json |
| Docker | `Dockerfile`, `ui/Dockerfile`, `docker-compose.yml` | 3 services: app / api / ui, non-root, healthchecks |

Run: `docker compose up --build` → UI at **localhost:3000** (API :8000, legacy Streamlit :8501).
Dev: `uvicorn api.main:app --port 8000` + `cd ui && npm run dev` (:5173).

---

## Evaluation pipeline (core/)

`INPUT → ENRICH → VERIFY / STRUCTURE / PROFILE / TREND (parallel) → SCORE → ROUTE`

1. **INPUT** (`data.py`) — GlassDollar API search (key set) or local applications
   xlsx (dev fallback); web-profile fallback for unknown companies with an
   existence guard (name must appear in results; LLM exists-check). If DDG returns
   nothing, a last-resort LLM-knowledge profile is built, marked `llm_knowledge`.
   Any columns left blank get one gap-fill LLM call ("empty if unknown, never guess").
2. **ENRICH** (`enrich.py`) — parallel DDG queries + pitch-PDF extraction; every
   fact carries `value · source_url · method · source_type · confidence · retrieved_at`.
3. **VERIFY** (`verify.py`) — LLM checks each self-reported claim against web
   evidence → `verified / partial / unverified / contradicted` + red flags.
4. **STRUCTURE** (`summarize.py`, `fit.py`) — offering summary; two-stage tool
   matching against the Siemens catalogue (~3.2k tools) with **relation
   classification** (complement / integration / adjacent / substitute — substitutes
   discounted) blended 70/30 with the **challenge-library match** (approved
   challenges only).
5. **PROFILE** (`profile.py`) — LLM-orchestrated research: founders (with
   backgrounds, LinkedIn), key team, scientific advisors, employees, parent group,
   programs (Siemens Xcelerator, Nvidia Inception, Microsoft for Startups, AWS
   Activate, Google for Startups, TUM Venture Labs, …), named reference customers
   (generic phrases filtered out), SFS-financing relevance. Safety nets: keyword
   program scan + founder recovery pass + founder deep-dive; employee backfill
   from the application row.
6. **TREND** (`trend.py`) — LLM-generated market queries → DDG → verdict,
   momentum, signals, citations.
7. **SCORE** (`score.py`) — six dimensions (traction 28, siemens_fit 27,
   product 15, market 12, founder 10, ecosystem 8) × data-confidence discount +
   thin-profile cap. Anti-gaming: unverified customers weighted 0.25, contradicted 0.
   Programs only score with an evidence URL. Output includes **route scorecards**
   (per-pillar weight profiles), **red flags** (negative evidence) kept separate
   from **missing evidence** (unknowns).
8. **ROUTE** (`route.py`) — eligibility per route on its own scorecard; primary =
   highest-scoring eligible route; can return **multiple pillars** (e.g.
   Connect + Collaborate + Empower); per-route recommendation text; SFS flag.

**LLM providers** (`llm.py`): `GEMINI_API_KEY` → Gemini (`gemini-2.5-flash`,
OpenAI-compatible endpoint) with priority over `OPENAI_API_KEY` (Siemens
gateway/OpenAI). No key → free offline keyword fallbacks everywhere.

**Problem → startup mode** (`solve.py`) — describe a challenge → capability
keywords → candidates from the **local applications xlsx (only here)** +
GlassDollar + web → LLM-ranked with rationale. Every problem is saved to the
challenge library (`pending/approved/rejected`; only approved influence scoring).

**Ask / chat** (`chat.py` `chat_smart`) — max 2 LLM calls: draft + targeted
queries → DDG → refine with citations; only evidence the LLM actually used is
shown as sources.

---

## Persistence (SQLite, `data/runs.db`)

Cache-first: an evaluated startup is **always served from the DB**; external
calls happen only via explicit **⟳ Re-evaluate** (Explore rows) or **Refresh
Data** (profile header). Old runs are retained for history/audit. Freshness
metadata + badge (stale > 7 days, `EVAL_TTL_DAYS`).

| Table | Contents |
|---|---|
| `companies` | canonical record (unique name, website, HQ, founded, employees, funding, stage, parent group, latest_run_id) |
| `people` | founders / advisors / key team (role, background, LinkedIn, source) |
| `programs` | incubator / accelerator / corporate program memberships |
| `reference_customers` | named customers + verification status |
| `evidence_facts` | per-run fact history with full provenance |
| `tool_matches` | Siemens tool matches per run (relation, confidence) |
| `runs` | evaluation snapshots (summary columns + full JSON) |
| `overrides` | reviewer route overrides (audit log) |

Idempotent backfill promotes pre-schema runs at API startup.

---

## API (FastAPI, `api/`)

`GET /health` (LLM provider/model, data source, applications file) ·
`GET /api/search` · `POST /api/evaluate` (cache-first, `refresh` flag) ·
`POST /api/solve` · `POST /api/ask` (run-grounded) · `GET /api/runs` (enriched
listing) · `GET/DELETE /api/runs/{id}` · `POST /api/runs/{id}/override` +
`GET /api/runs/{id}/audit` · `GET/PATCH /api/challenges` · `GET /api/companies`.

**Security**: security headers on every response, optional bearer auth
(`API_AUTH_TOKEN`, constant-time compare), per-IP sliding-window rate limits
(tight budget on evaluate/solve/ask), strict input bounds, CORS locked to
explicit origins, docs disableable, non-root containers, no tokens in the
browser bundle (nginx same-origin proxy), parameterized SQL throughout.

---

## UI (React, `ui/`) — enterprise research workstation

Design tokens in `src/tokens.css` (dark slate chrome, light data canvas,
disciplined blue accent, violet AI accent). Shell: top bar with **Ctrl/Cmd+K**
command search (GlassDollar autocomplete → evaluate), icon rail, secondary nav
with Quick Access + saved views, right-side **AI assistant dock** (context-aware).

- **Home** — command centre: KPI strip, compact scouting-query composer with
  quick prompts, recent evaluations, tracked companies, saved views, challenge
  approvals (✓/✕).
- **Explore** — one row per company: KPI strip, toolbar (density, CSV export,
  column drawer with reorder/save-as-view), filter chips + pillar facets, sticky
  header/first column, multi-select, star-to-watch (company-keyed),
  **⟳ Re-evaluate** per row, URL-persisted state, skeletons/empty states.
- **Startup Profile** — sticky header (route pills, freshness badge, Refresh
  Data, Watch, Assistant), compact 7-stage pipeline ribbon, tabs:
  **Overview** (metrics, exec summary, team & ecosystem, customers, signals) ·
  **Scoring & Fit** (dimension bars, radar, route scorecards + recommendations,
  tool matches with relation, red flags & gaps, **reviewer override with audit
  trail**) · **Market & Risk** · **Evidence** (filterable, status dots, sources) ·
  **Ask** (suggested prompts, cited answers).
- **Saved Views / Tracking / Ask AI / Settings** (backend status page).

---

## Data & testing

- `data/glassdollar_applications.xlsx` — 9 real startups (KONUX, Sereact,
  Instagrid, RIIICO, Voliro, Fernride, Tacto, Q.ANT, Proxima Fusion) + KONUX
  pitch PDF; exercises growth/early/prototype paths, SFS, parent-group detection.
- All features verified by sandbox test runs (offline mocks, no API spend):
  pipeline end-to-end, cache/refresh, normalized tables, backfill, security
  (auth/rate-limit/validation), routing, gating, founder/program recovery.

## Governance & auditability

Reviewer route overrides with reason + evidence (automated result preserved);
challenge approval workflow; evidence source-typing
(self_reported / public / inferred); red flags vs missing evidence separation;
override-on-refresh keeps history.

## Known limitations / next steps

- DDG is free but rate-limited → swap for Tavily/Brave/Exa in `core/web.py` when budget allows.
- Table not virtualised (fine below ~few-thousand rows).
- Reviewer identity is a free-text field — wire to real auth when multi-user.
- Deferred deliberately: full person/investor/funding-round entity graph,
  Postgres+Redis, job queue, CI, role-based auth, ecosystem graph view.
- `.env` must never be committed; rotate any key that ever was.
