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
default** and has to be named in `PUBLIC_PATHS` to opt out. Identity reaches the three routes that
need it via `Depends(current_user)`.

`overrides.reviewer` used to be free text a client chose. It is now the authenticated principal,
alongside `reviewer_oid/upn/tid/source`. Those are **NULL on pre-SSO rows and are never backfilled**
— promoting unverified history to verified is the one thing an audit trail must not do.

## Running it

```bash
AUTH_MODE=stub SESSION_BACKEND=memory \
  py -3 -m uvicorn api.main:app --port 8000    # backend (single process — see below)
cd ui && npm run dev                           # frontend on :5173
py -3 -m pytest tests/ -q                      # backend tests
bash scripts/gates.sh                          # ALL gates (run before finishing any change)
```

The e2e suite needs the backend in stub mode, and in **one** process: `SESSION_BACKEND=memory`
splits across gunicorn workers, so a request landing on the other worker looks signed out.

The backend serves the API only — `/` returns 404 by design. The UI is `:5173` in dev.

`.env` at the repo root holds `GEMINI_API_KEY` (gitignored). Without a key the engine degrades to
keyword-only extraction rather than failing.

## Frontend map

Routes (`ui/src/App.jsx`): `/` Home · `/explore` · `/startup/:id` Profile · `/saved` · `/alerts` ·
`/ask` · `/settings`. API client: `ui/src/api.js`. Shared state: `ui/src/state.jsx`.

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
