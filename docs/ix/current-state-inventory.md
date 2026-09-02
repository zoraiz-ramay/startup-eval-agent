# Current-state inventory — Tracxn-layout UI (pre-migration)

Phase 1 deliverable for the iX-authority migration. Read-only: describes what exists today, in
`ui/src`, so Phase 2 can decide what an iX-authoritative IA replaces it with. Nothing here is a
recommendation.

Regenerate the machine-readable companion with `node scripts/ui_inventory.py` — verified fresh
against source as of this writing (re-running it produced no diff). This document adds the
structural/behavioural reading that file doesn't carry: which regions compose each screen, which
components are actually wired in vs. dead code, and which patterns have no iX equivalent yet.

---

## 1. Screen-by-screen structural inventory

Every route renders inside the shared `Shell` (`ui/src/App.jsx:204-230`): fixed `TopBar` + fixed
`Rail` + conditional `SideNav` + `<main class="content">` + global `AssistantDock`. Below, "regions"
excludes that shared chrome (covered in §2) and lists only what each page contributes.

### `/` — Home (`ui/src/pages/Home.jsx`, 211 lines)

| Region | Detail |
|---|---|
| Breadcrumb + page head | `.crumb` "Command Centre" / `.page-title` "Home" |
| Stats strip | 5 tiles: companies evaluated, avg Fit Score, Siemens-aligned, watching, challenges recorded |
| Query composer panel | Free-text input + "Run query" button, 4 canned `QUICK_PROMPTS` chips, calls `api.solve` |
| Solve results list | `.list-row` per candidate: name, source badge (Applications/GlassDollar/Web), `ScoreBar` (relevance), "Evaluate" button → `/startup/new` |
| Recent evaluations panel | Up to 6 most recent runs, `.list-row` each, links to `/startup/:id` |
| Tracked companies panel | Up to 6 watchlisted companies with last score |
| Saved views panel | Links into `/explore?view=…` |
| Recent challenges panel | Last 4 challenges with approve/reject buttons (`api.setChallengeStatus`) |

### `/explore` — Explore (`ui/src/pages/Explore.jsx`, 502 lines) — the densest screen

| Region | Detail |
|---|---|
| Page head | Title, result count, active-view chip (`.fchip`) with close |
| Stats strip | Companies / avg Fit Score / Siemens-aligned / SFS relevant |
| Toolbar | Select-all checkbox, "Customise columns" (opens drawer), density toggle (dense/comfortable, in URL as `?density=`), portfolio-weighting toggle, selection count, CSV export |
| Weighting panel (conditional) | `WeightSliders` + live region reporting how many rows change pillar under the reviewer's weights + reset button |
| Filter row | Text filter, 4 pillar filter chips (Connect/Collaborate/Empower/Pass), active-filter chips with per-chip clear, "Clear all" |
| Data grid (`.grid-shell` → `.dtable`) | Sticky header row, sticky first column (company), per-row select checkbox, star/watch button, dynamic column set from a `COLUMNS` registry (13 possible columns: Fit Score, Siemens Fit, Description, Location, Founded, Stage, Funding, Founders, Evidence Strength, Market Signal, Route, SFS, Confidence, Evaluated), sortable column headers, kebab actions (re-evaluate, open) |
| Skeleton / empty / error states | 8 `.skel-row` placeholders while loading; `.empty` block with icon glyph when zero rows; `ErrorBox` on fetch failure |
| Column drawer (`ColumnDrawer`, same file) | Right-side overlay (`.drawer` + `.drawer-mask`), reorder (↑/↓), remove/add checkboxes, "Restore defaults", "Save view" (named, persisted server-side) |

Column state, filter, sort, density and active view all live in the URL query string (`useSearchParams`), not component state — this is why "table state survives a reload" is a tested contract (`ui/e2e/journeys.spec.js:62-66`).

### `/startup/:id` — Profile (`ui/src/pages/Profile.jsx`, 643 lines) — the most complex screen

| Region | Detail |
|---|---|
| Profile head (`.profile-head`, sticky) | Logo initial chip, company name + pillar pill(s), one-line summary, meta row (HQ, funding, score, confidence, engine tag), tag chips (business model / stage / SFS), action row (age badge, Refresh Data, Watch toggle, Assistant, back-to-Explore) |
| Pipeline ribbon | 7 static steps (Input→Enrich→Verify→Structure→Score→Review→Route), all marked "done"; web-sourced badge when applicable |
| Tab bar (`role="tablist"`, sticky) | Overview / Scoring & Fit / Market & Risk / Evidence / Ask — state in URL `?tab=` |
| **Overview tab** | Metric row (6 tiles incl. `WebSourced` provenance badges), executive summary panel (`Spec` rows: HQ, stage, business model, funding, website, LinkedIn, parent group), `HeadcountTrend` panel (2+ cited points or one-line empty state), Team & ecosystem panel (founders/advisors/programs, self-asserted programs marked "claimed"), Reference customers panel, Recent signals panel |
| **Scoring & Fit tab** | Score breakdown (`ScoreBar` per dimension + formula sentence), `WhatIfWeights` collapsible panel, Routing rationale (pillar pills, reasons, risks, route scorecards), Red flags & gaps panel, `OverridePanel` (reviewer decision form + audit history), Radar chart (+ what-if overlay), Siemens portfolio fit panel |
| **Market & Risk tab** | Market trend metrics, signals list, risks list, market evidence list (external links) |
| **Evidence tab** | *Locally defined inside Profile.jsx* (not the file at `ui/src/pages/EvidenceTab.jsx` — see §3 dead code): filterable fact table (Status/Claim/Value/Method/Source), verified-status dot |
| **Ask tab** | Suggested-prompt chips, chat transcript, evidence citations, input bar — same shape as `AssistantDock` |
| Loading state | `SkeletonProfile`: spinner sentence + 2 skeleton blocks while the pipeline runs (can take 1-2 min) |
| Error state | `.empty` block with "Back to Explore" |

### `/saved` — Saved views (`ui/src/pages/Saved.jsx`, 42 lines)

Simple list (`.panel` + `.list-row`) of saved column/filter configurations, each opens `/explore?view=…`; delete button per row; `.empty` state pointing back to Explore.

### `/alerts` — Tracking (`ui/src/pages/Alerts.jsx`, 74 lines)

One `.dtable` of watchlisted companies (star, company, score, pillar pill, last evaluated, re-evaluate action); `.empty` state.

### `/ask` — Ask AI (`ui/src/pages/AskAI.jsx`, 27 lines)

Static explainer panel; its only real effect is forcing `setDockOpen(true)` on mount — the actual interaction happens in `AssistantDock`, not on this page.

### `/settings` — Settings (`ui/src/pages/Settings.jsx`, 65 lines)

Account panel (name/email, stub-mode warning, sign-out), Backend status panel (`api.status()`: API, LLM reasoning, GlassDollar key, applications file) as `Row` (label + status dot + value).

### `/admin` — Admin (`ui/src/pages/Admin.jsx`, 344 lines) — behind `require_admin`, self-explains a 403

| Region | Detail |
|---|---|
| Forbidden state | `.empty` block explaining admin-only access rather than 404 |
| Administrators panel | Table of admins with source (`env` = `ADMIN_UPNS`, un-revocable / `db` = granted in-app, revocable), grant form (email input) |
| Stats strip | Reviewers, sign-ins, searches, companies searched/evaluated, cache-hit rate |
| Reviewers table | Per-user searches/companies/last-active |
| Most-searched companies table | Clickable rows → new evaluation |
| All companies evaluated table | Full company/pillar/score/HQ/evaluated list |
| Recent activity table | Every search: when, reviewer, typed query, resolved company, cache vs. pipeline |

### `/signin` (unauthenticated, outside the Shell entirely)

`SignIn.jsx` (100 lines): full-bleed centred card, 10 distinct Conditional-Access failure messages keyed by an error code in the query string, correlation-ID display (sanitised), "Sign in with Siemens" button → `/api/auth/login`.

---

## 2. Shared chrome components

| Component | File | Role | Used from |
|---|---|---|---|
| `TopBar` | `App.jsx:88-123` | Fixed 56px header: brand/logo (click→Home), `CommandBar`, advanced-search icon button, tracking bell (badge count), avatar button (→ Settings) | Every authenticated screen (inside `Shell`) |
| `CommandBar` | `App.jsx:23-85` | Global search input, Ctrl/Cmd+K focus shortcut, 350ms-debounced `api.search`, suggestion dropdown, `/solve` and `/explore` slash-command routing | Inside `TopBar`, so every screen |
| `Rail` | `App.jsx:141-167` | Fixed 68px left icon rail: Home, Explore, Views, Tracking, Ask AI (button, toggles dock — not a route), Settings, + Admin if `user.is_admin` | Every authenticated screen |
| `SideNav` | `App.jsx:169-201` | Fixed 236px secondary nav: quick links + dynamically listed saved views; hidden on `/startup/:id` (`noSidenav`) and below 1180px | Every screen except Profile |
| `AssistantDock` | `components/AssistantDock.jsx` | Fixed 332px right-side chat panel; auto-opens above 1181px viewport, one rail button toggles it; context-aware suggestions when a profile is open (`dockCtx`) | Global, rendered once in `Shell`, independent of route |
| `Icon` | `components/Icon.jsx` | Inlines a Siemens iX icon SVG string and repaints via `currentColor` (`fill`); necessary because `@siemens/ix-icons` ships `fill='none'` expecting a host paint, and neither `<img>` nor a CSS mask can do that | `App.jsx` rail/topbar icons; any component importing an `iconXxx` binding |
| `ErrorBox` | `components/ErrorBox.jsx` | The app's single error surface: `role="alert"`, optional hint | Home, Explore, Alerts, Admin, Profile, Settings, SignIn |
| `Loading` (used one) | `components/widgets.jsx:96-106` | `role="status"` + `aria-live="polite"` text + decorative spinner | Home, Settings, Profile (`SkeletonProfile` uses its own inline spinner text, not this one), AskAI panel copy references it conceptually |
| `ScoreBar` (used one) | `components/widgets.jsx:19-27` | Labelled horizontal bar, 0-100, no ARIA role | Home (relevance), Profile Scoring tab (dimension breakdown), Profile Fit matches |
| `Radar` | `components/widgets.jsx:29-76` | SVG radar chart of the 6 scoring dimensions, optional dashed what-if overlay, accessible `aria-label` describing both series and any off-scale clamping | Profile Scoring & Fit tab only |
| `Spec` | `components/widgets.jsx:78-85` | Label/value row (`.spec .k`/`.v`), falls back to em-dash | Profile Overview, Settings, Admin (indirectly via similar markup) |
| `ExtLink` | `components/widgets.jsx:87-94` | Renders a link only if the href is actually `http(s)://` — otherwise renders nothing/children as text; this is the UI half of the "no source, no display" rule | Home, Profile (all tabs), widely |
| `WeightSliders` / `useWeighting` | `components/WeightSliders.jsx` | 6 range inputs (one per scoring dimension), sum pinned to 100 by rebalancing the other 5; single shared state via `useApp().whatIfWeights` | Explore's portfolio-weighting panel AND Profile's `WhatIfWeights` panel |
| `WhatIfWeights` | `components/WhatIfWeights.jsx` (247 lines) | Collapsible panel: re-derives score + routing under the reviewer's weights, always shows the *stored* score/pillar alongside, explains every routing gate (including passing ones), computes "reachable in one dimension move" paths | Profile Scoring & Fit tab only |

---

## 3. Dead / orphaned code found during this audit (not imported anywhere)

These exist under `ui/src` but are not reachable from any route or component — flagging them
because a migration inventory should not be built on top of code nobody renders:

| File | Why it's dead |
|---|---|
| `components/ClaimEvidenceMatrix.jsx` | Calls `api.evidence(startup)` — **no such method exists** in `ui/src/api.js`. Not imported by any page. |
| `components/FitScoreHistogram.jsx` | Not imported anywhere. Inline styles, not tokens. |
| `components/ScoreBar.jsx` (default export) | A second, unrelated `ScoreBar` implementation (hardcoded `#e0e0e0`/`#3b82f6` colors, `role="progressbar"`) that is never imported — the one actually used everywhere is the named export in `components/widgets.jsx`. |
| `components/Loading.jsx` (default export) | A second `Loading` ("Loading..." with no `aria-live`) that is never imported — the one actually used is the named export in `components/widgets.jsx`, which has the accessibility contract. |
| `pages/EvidenceTab.jsx` | A whole separate Evidence-tab implementation (filter, `SourceQualityLegend`, generic key/value table) that is **not** what Profile.jsx renders for its Evidence tab — Profile defines its own local `EvidenceTab` function (`Profile.jsx:392-429`) instead. This file is orphaned. |
| `pages/Challenges.jsx`, `Dashboard.jsx`, `Evaluate.jsx`, `RunDetail.jsx`, `Solve.jsx` | Explicit stubs: `// Superseded by the enterprise redesign. See pages/Home, Explore, Profile, Saved, Alerts, AskAI, Settings.` — `export default null`. Kept only so nothing else 404s if something still imports them (nothing does). |
| `components/ResultView.jsx` | Same stub pattern as above. |

Phase 2 should decide whether to delete these outright (recommended, since they're pure carry-over risk during a rewrite) or migrate them if some intended-but-unshipped feature (e.g. a real claim-evidence matrix sourced from `api.evidence`, which doesn't exist server-side either) is still wanted.

---

## 4. Structural patterns unique to Tracxn — flagged for a Phase 2 IA decision, not solved here

- **Icon rail + fixed top bar + collapsible secondary side-nav, three-deep fixed chrome.** `Rail` (68px) + `SideNav` (236px) + `TopBar` (56px) stack via fixed positioning and `.content` margin offsets (`App.jsx`, `styles.css:76-124`). iX's own shell primitives (`ix-application-frame`? `ix-workspace-menu`? — needs a Phase-2 spike) don't obviously map to "rail always visible, side-nav conditionally hidden per-route (`noSidenav` on `/startup/:id`), side-nav collapses below 1180px" without an explicit IA call on what survives.
- **Ctrl/Cmd+K global command bar with slash commands.** `CommandBar` (`App.jsx:23-85`) does live suggestion search AND doubles as a mini command palette (`/solve`, `/explore` prefixes navigate instead of searching). No iX component is a command palette; this is a genuinely new pattern to place, not a re-skin.
- **Dense, sortable, sticky-column, customisable data table with URL-persisted state.** `Explore.jsx`'s `.dtable` (sticky header + sticky first column + row selection + inline column reordering via a right-side drawer + CSV export + saved views) is the single most complex surface in the app. iX has table primitives but not this exact combination of column-drawer-as-overlay + URL-as-source-of-truth + portfolio re-weighting overlay.
- **The pillar color ramp (Connect/Collaborate/Empower/Pass).** `tokens.css:56-75` hand-derives 4 categorical colors from the iX palette because iX ships no 4-way categorical scale, and 3 of the 4 needed hand-darkening off the nearest iX token to clear AA contrast as pill labels (`--pillar-connect`, `-collaborate`, `-pass` are literals; only `-empower` reuses `--theme-color-primary` directly). This ramp has no anchor in the iX design system and needs a Phase-2 decision: keep hand-derived literals, or pick a different semantic vocabulary iX does support.
- **Dark chrome over a light canvas.** The whole rail/top-bar dark treatment (`--chrome-900/800/700/border/text/muted` in `tokens.css:20-27`) is stated in the token file itself to be "iX's DARK-schema values as literals" bolted onto an app pinned to iX's LIGHT schema — there is no first-class "dark chrome, light workspace" construct in iX. If Phase 2 makes iX authoritative for IA as well as styling, this seam either needs an iX-sanctioned equivalent or an explicit exception.
- **`WeightSliders.jsx` + the shared `se.whatIfWeights.v1` localStorage mechanism.** One weighting state feeds two different presentations: Explore's portfolio-wide "who moves under my weights" table overlay, and Profile's single-company `WhatIfWeights` breakdown with reachability analysis. This cross-screen shared-state pattern (a reviewer's personal lens, not a per-screen control) has no analog to reuse from iX and needs an explicit IA decision on where "my weighting" lives in a new structure (global settings? a persistent toolbar affordance? per-screen only?).
- **The `AssistantDock` auto-open breakpoint behavior.** A fixed-position 332px panel that auto-opens above 1181px and is otherwise one tap away from the rail, with no responsive layout reflow (it just shifts `.content`'s right margin) — a pattern to explicitly re-decide rather than carry over mechanically.
- **Dual/duplicate component pairs already in the tree** (see §3) — a symptom that iX-adoption in Phase 2 must pick ONE Evidence tab, ONE ScoreBar, ONE Loading, not merge behaviors from both.

---

## 5. Design tokens actually consumed

`ui/src/tokens.css` defines 37 custom properties (`ui-inventory.json → design_tokens`). Grepping
`var(--*)` usage across `ui/src/**/*.{jsx,css}` confirms **all 37 are referenced at least once** —
there is no dead token today:

| Token | Uses | Token | Uses | Token | Uses |
|---|---|---|---|---|---|
| `--accent` | 34 | `--danger` | 8 | `--sidenav-w` | 2 |
| `--accent-soft` | 9 | `--danger-soft` | 2 | `--success` | 8 |
| `--ai` | 7 | `--fs-body` | 11 | `--success-soft` | 3 |
| `--ai-soft` | 1 | `--fs-meta` | 8 | `--surface` | 31 |
| `--border` | 36 | `--fs-section` | 1 | `--surface-2` | 14 |
| `--border-2` | 12 | `--fs-table` | 1 | `--text-1` | 10 |
| `--canvas` | 2 | `--fs-title` | 2 | `--text-2` | 18 |
| `--chrome-700` | 2 | `--pillar-collaborate` | 1 | `--text-3` | 10 |
| `--chrome-800` | 5 | `--pillar-connect` | 1 | `--topbar-h` | 8 |
| `--chrome-900` | 1 | `--pillar-empower` | 1 | `--warning` | 8 |
| `--chrome-border` | 3 | `--pillar-pass` | 1 | `--warning-soft` | 2 |
| `--chrome-muted` | 6 | `--radius` | 21 | | |
| `--chrome-text` | 4 | `--rail-w` | 5 | | |

Notable single-use tokens worth Phase 2 attention even though they're "used": `--ai-soft` (1),
`--chrome-900` (1), `--fs-section` (1), `--fs-table` (1), and each of the 4 pillar tokens (1 each,
by design — each backs exactly one `.pill.<Name>` rule in `styles.css:208-211`). These aren't dead,
but a token used once is worth re-examining when the token *source of truth* changes in Phase 2 —
either it's load-bearing and should stay a first-class token, or it was one-off and can fold into
a utility.

`--radius` (21 uses), `--surface`/`--border`/`--accent`/`--text-2` are the structural backbone of
nearly every panel/table/input — expect these to be the highest-blast-radius renames if iX's own
token names replace the app's.

---

## 6. Test surface

### Vitest (`ui/src/**/*.test.jsx`) — 6 files

| File | Asserts (one line each) |
|---|---|
| `App.test.jsx` | Auth gate shows sign-in when signed out and never calls data APIs while signed out; renders shell + stub-mode banner when signed in; assistant dock auto-opens only ≥1181px and has exactly one control (the rail button), which reopens it after close. |
| `components/ErrorBox.test.jsx` | `ErrorBox` announces via `role="alert"`, appends optional hint text, renders nothing when there's no message. |
| `components/widgets.test.jsx` | `Loading` exposes `role="status"`/`aria-live="polite"` and hides its spinner from AT; `Radar` draws one polygon with no overlay, two (one dashed) with an overlay, leaves the evidence polygon's points unchanged when an overlay is added, clamps an over-100 contribution to the outer ring, and names both series + discloses clamping in its `aria-label`. |
| `pages/Admin.test.jsx` | Lists admins from both sources (`env`/`db`) with correct labels; offers no "Remove" control for an `env`-sourced admin but does for a `db`-sourced one; grant flow re-fetches the list rather than optimistically updating; a rejected grant surfaces the error and keeps the typed value; a 403 renders the "access required" explainer instead of an error box; empty admin list says so explicitly. |
| `pages/Explore.test.jsx` | Column drawer opens from the toolbar and closes on Escape; every drawer control (reorder, add/remove) has an accessible name; the backdrop mask is `aria-hidden` (not a fake unlabelled button); opening the drawer moves focus in and Escape returns focus to the trigger; a saved view applies its columns+filters on a same-mount URL change (no remount); saving a view round-trips to the server and opens it; closing the view chip restores defaults; portfolio weighting leaves the grid on engine numbers until a slider moves, then shows `(engine NN)` beside the re-weighted figure, and resets cleanly. |
| `pages/Profile.test.jsx` | Tab bar is a real `tablist` with exactly one selected tab and carries the `sticky-header` class; a web-sourced field's link has the correct href and a field-specific (not generic "web") accessible name; two provenance badges on the same row get distinguishable accessible names; an unevidenced field renders an em-dash, never a guess; headcount trend shows a one-line empty state below 2 points and per-point sourced links at ≥2; what-if weighting panel stays collapsed by default, changes only the what-if figure (never the stored score), resets in one action, and states plainly when a run has no dimensions; what-if routing explains every gate including passing ones, marks weighting-immune clauses, states when a verdict "cannot" change, leaves the header pillar untouched, and keeps exactly one live region. |
| `pages/SignIn.test.jsx` | Default state offers sign-in with no alert; each of 6 sampled Conditional-Access error codes renders its specific actionable copy (Company Portal, VPN+device, request access, "not something you can fix", generic fallback); the correlation ID is displayed with injected characters stripped; the sign-in click preserves the current path+query in the `next` redirect param. |

### Playwright (`ui/e2e/`) — 2 spec files, 8 screenshots across 4 breakpoints

| Spec | Contract IDs covered | Screenshots produced |
|---|---|---|
| `journeys.spec.js` | SHELL-01/02/04 (rail + Ctrl+K), EXP-02/08/09 (drawer, URL state), PROF-02/04/05/12/14/15 (tabs, provenance, what-if weights & routing, headcount trend), X-03 (error announced), X-06 (pillar-pill AA contrast measured from painted colors), X-05/X-06 (layout screenshots), X-05 (no horizontal scroll) | `explore-{desktop,laptop,tablet,mobile}.png`, `profile-{desktop,laptop,tablet,mobile}.png` — **all 8** baselines live in this one spec, under `test.describe("layout")` |
| `auth.spec.js` | AUTH-01/02/03 (signed-out gate, mid-session 401 swap without navigation, sign-out/back-to-signed-out) | None — deliberately no screenshots; behavior-only per the file's own comment |

All 8 visual baselines belong to `journeys.spec.js`'s two `toHaveScreenshot` calls (`explore-*`
and `profile-*`), parametrized over 4 Playwright projects (breakpoints: desktop/laptop/tablet/mobile
— see `ui/e2e/fixtures.js` / Playwright config for the exact viewport sizes). Both screens
(`Explore`, `Profile`) will need new baselines the moment the iX-authoritative layout replaces the
Tracxn shell; `auth.spec.js`'s three tests should be unaffected by a pure layout swap since they
assert only `role`/URL/visibility, not markup shape — useful to know when sequencing which PR
re-baselines what.
