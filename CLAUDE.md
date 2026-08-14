# Siemens Startup Evaluation Agent

Evaluates startups for Siemens partnership decisions: enrich from web evidence → verify → score six
weighted dimensions → route to a pillar (Connect / Collaborate / Empower / Pass). A FastAPI backend
wraps a pure-Python engine; a React SPA is the product surface.

## The one rule everything else serves

**Every displayed fact must be traceable to a source, or it must not be displayed.**

This app informs partnership decisions, so an invented number is worse than a blank field. The
codebase enforces this in several places, and changes must not weaken them:

- `core/profile.py` — `_program_grounded` requires a program name and the company name to
  co-occur in a *single* result before a membership counts; `_ground_customers` requires a
  relationship phrase in a short window; `_clean_employee_series` drops any datapoint without an
  `http` source; `_clean_source_url` rejects a "source" that is not a URL.
- `core/data.py` — `web_profile_row` deliberately does **not** fill verifiable fields (funding,
  founded year, employees, HQ, customers) from model memory. It used to, and produced a funding
  round of "SAR 3.75 million" for makkook.ai that exists nowhere on the web.
- `core/score.py` — a self-asserted program membership scores at a discount to an independently
  corroborated one; a source URL alone is not evidence.

If a field cannot be evidenced, leave it empty and let the UI show "—".

## Architecture

| Path | Role |
|---|---|
| `core/` | The engine. Pure Python, no web framework, no `api/` imports. |
| `api/` | FastAPI wrapper + SQLite persistence (`api/store.py`, S3-backed). |
| `ui/` | React 18 + Vite SPA (the product surface). |
| `tests/` | pytest, backend + engine. |
| `data/` | `glassdollar_applications.xlsx` (429 rows), `runs.db`. |

`core/` must never import `api/` — the engine runs standalone from scripts and tests. The web
result cache is injected the other way round: `api/main.py` calls `core.web.install_cache(...)`.

Pipeline: `core/pipeline.py::evaluate` → `enrich` → (verify ‖ summarize ‖ fit ‖ profile ‖ trend,
concurrent) → `score` → `route`.

## Data sources: GlassDollar first, the web for the rest

`core/glassdollar_api.py` is the live REST client (`GLASSDOLLAR_API_KEY`, base
`https://actions-api.glassdollar.com`). It is the **first** source everywhere: `_evaluate`
resolves a name through it, then a domain via `get_company_by_domain`, and only then falls back
to `data.web_profile_row`; `/api/search` lists its hits ahead of the local xlsx.

What it can and cannot answer decides how much scraping is left:

- **It answers** name, website, domain, HQ, founded year, headcount, total funding,
  LinkedIn/Crunchbase URLs, referenced customers, descriptions, tags.
- **It does not answer** business model, development stage (Siemens pitch-form fields it does not
  expose), founders, advisors, programs, parent group, headcount history, trend, verification,
  Siemens-tool fit, scoring or routing. Those still need the web pipeline.

`profile._seed_from_database` takes the three headline fields it does answer *before* the recall
nets run, so `_recover_headline_facts` — a whole search wave plus an extraction call, and the most
fragile part of the chain — skips itself. The database also **wins over** the main wave's
extraction, not merely over a blank. Two rules hold there: a researched `*_source` URL is dropped
when the two disagree (it evidences the value that lost), and the headcount never enters
`employees_over_time`, whose `_clean_employee_series` gate requires an `http` source per datapoint.

A GlassDollar value has no URL, so it is `source_type: private` in `core/provenance.py` — not
`public` (which would be demoted to `inferred` for lacking a URL) and not `self_reported` (the API
corroborates across sources rather than repeating the pitch form). The xlsx keeps `glassdollar_db`
/ `self_reported`, because that one *is* the application form.

The xlsx stays: it carries the pitch-form answers and decks the API does not expose, and it is the
only source when no key is set. **The key only resolves inside the Siemens network**, so nothing
about the live API can be verified from a laptop or CI — `tests/test_glassdollar_first.py` drives
the client contract with a fake and says so at the top.

## Authentication

Sign-in is Microsoft Entra ID, as a **backend-for-frontend**: `api/auth.py` is the confidential
client, does the code exchange, and keeps every token server-side. The browser gets an opaque
session id in an httpOnly cookie and never sees a token — which is what lets `ui/src/api.js` keep
its "no tokens in the browser bundle" stance. Sessions live in Redis (db 1), not in a signed cookie
(that would put the payload in the browser) and not in SQLite (`api/store.py` uploads the whole DB
file to S3 after every write).

Entra is behind a Conditional Access policy requiring a compliant device on a trusted location, so
**no CI runner can ever complete a real sign-in.** `AUTH_MODE=stub` replaces only the round trip to
Entra; cookies, CSRF, the session store and the guard are all production code. It is sealed twice —
`APP_ENV=production` (baked into the `Dockerfile`) and a gunicorn check — and the process exits
rather than starting with auth stubbed. Do not add a third mode, and do not add a "not configured,
so allow" branch anywhere: fail-closed is the point.

The guard lives in `SecurityMiddleware.dispatch()`, so **a new `/api` route is protected by
default** and has to be named in `PUBLIC_PATHS` to opt out. Identity reaches a route via
`Depends(current_user)`, and admin-only routes via its sibling `Depends(require_admin)`.

`overrides.reviewer` used to be free text a client chose. It is now the authenticated principal,
alongside `reviewer_oid/upn/tid/source`. Those are **NULL on pre-SSO rows and are never backfilled**
— promoting unverified history to verified is the one thing an audit trail must not do.

## Per-reviewer workspaces, one shared evaluation

The split that everything in `api/store.py` below `web_cache` exists for: **an evaluation is
shared, the record of who asked for it is private.**

- `searches` — one row per `/api/evaluate`, keyed on the Entra `oid`, with `served_from`
  (`cache` | `fresh`). This is both the reviewer's list (`GET /api/my/searches`, what Explore,
  Home and Tracking read) and the admin activity log.
- `company_aliases` — every string a company can be reached by: the typed query, the resolved
  name, the domain. Without it the cache-first lookup in `/api/evaluate` misses its own writes,
  because it searches on what was typed while `save_run` files the run under what the pipeline
  resolved. `save_run(result, aliases=[...])` records them; `latest_run_for_alias` reads them and
  falls back to the exact-name match for pre-alias rows.
- `sessions` — one row per sign-in, written from `create_session`. Redis holds only *live*
  sessions, so it can say who is online but never how many sessions there have been.
- `saved_views` — grid views keyed on the `oid`; they used to be `localStorage` and so belonged
  to a browser rather than a person.

Lists are strictly private: no parameter widens `/api/my/searches` to another principal. The
team-wide view is `/api/runs` and `/api/admin/*`, behind `require_admin`, which reads `ADMIN_UPNS`
(comma-separated). **Unset means nobody is an admin, never everybody** — same fail-closed rule as
the rest of `api/auth.py`.

## Running it

```bash
AUTH_MODE=stub SESSION_BACKEND=memory ADMIN_UPNS=e2e.reviewer@siemens.com \
  py -3 -m uvicorn api.main:app --port 8000    # backend (single process — see below)
cd ui && npm run dev                           # frontend on :5173
py -3 -m pytest tests/ -q                      # backend tests
bash scripts/gates.sh                          # ALL gates (run before finishing any change)
```

`ADMIN_UPNS` is what makes `/admin` reachable in dev — `e2e.reviewer@siemens.com` is the stub
principal's UPN. Leave it unset to exercise the forbidden path.

The e2e suite needs the backend in stub mode, and in **one** process: `SESSION_BACKEND=memory`
splits across gunicorn workers, so a request landing on the other worker looks signed out.

The backend serves the API only — `/` returns 404 by design. The UI is `:5173` in dev.

`.env` at the repo root holds `GEMINI_API_KEY` and, in the Siemens environment,
`GLASSDOLLAR_API_KEY` (both gitignored). Without either the engine degrades — keyword-only
extraction, xlsx + web instead of the live database — rather than failing.

## Frontend map

Routes (`ui/src/App.jsx`): `/` Home · `/explore` · `/startup/:id` Profile · `/saved` · `/alerts` ·
`/ask` · `/settings` · `/admin` (rail entry hidden unless `/api/auth/me` reports `is_admin`; the
page itself explains a 403 rather than 404ing, so a shared link is diagnosable). API client:
`ui/src/api.js`. Shared state: `ui/src/state.jsx`.

Icons are Siemens iX, via `ui/src/components/Icon.jsx`. It inlines the SVG and repaints it in
`currentColor` because the shipped glyphs carry `fill='none'` and expect the host to paint them —
an `<img>` or a CSS mask renders them blank. Do not reintroduce Unicode or emoji glyphs in chrome.

The six weight sliders (`ui/src/components/WeightSliders.jsx`) and the single
`se.whatIfWeights.v1` behind them are shared by the profile what-if and Explore's portfolio
re-weighting on purpose: "my weighting" is something a reviewer has, not a per-screen setting.

`ui/src/tokens.css` is the **single source of truth for design tokens** — chrome (product shell),
canvas (data surface), text, semantic, pillar ramp, type scale. Components reference tokens, never
raw colours. `docs/ui-inventory.json` is generated from source by `scripts/ui_inventory.py`; read
it instead of recalling the component list from memory.

## Design contract: Tracxn layout, Siemens iX styling

The layout is deliberately modelled on Tracxn — icon rail, top command bar (Ctrl/Cmd-K), dense
data canvas, evidence-forward tables. **That structure is not up for redesign.** Siemens iX
(`@siemens/ix`) supplies colour, typography, spacing and component primitives *within* that
structure. When the two conflict, iX wins on styling and accessibility; Tracxn wins on information
architecture.

Rules that are mechanically enforced by `scripts/ix_lint.mjs`, not left to judgement: no raw
hex/rgb outside `tokens.css`; interactive elements need accessible names; every data view needs
visible loading, empty and error states.

## Testing

Three layers, and they are not interchangeable:

- `tests/` — pytest for engine and API behaviour.
- `ui/src/**/*.test.jsx` — Vitest + Testing Library. Render the component and assert **behaviour**.
- `ui/e2e/` — Playwright journeys + visual regression at four breakpoints.

**Never assert on source text.** Tests of the form `assert "sticky-header" in open(file).read()`
were generated by a previous agent system; they verify nothing, are satisfied by pasting a string,
and all of them rotted into permanent failures. They have been replaced. Do not reintroduce the
pattern.

Visual baselines in `ui/e2e/__screenshots__/` are the record of "the layout still works". Agents
must not update them; a human runs `--update-snapshots` after reviewing an intended change.

## Conventions

- Comments explain **why**, especially where the code looks odd on purpose (the grounding gates
  above are all non-obvious and all deliberate). Do not add narration of what the next line does.
- Prefer editing existing modules over adding new ones; the engine is deliberately small.
- One concern per commit.
