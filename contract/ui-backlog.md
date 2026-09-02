# UI backlog

Durable, evidence-cited findings. `ui-auditor` appends; `ui-implementer` takes **one** at a time.

Status is the memory that stops the system re-proposing what you already declined — the previous
agent system had no such record and re-litigated the same ideas across 59 cycles. A `rejected` row
stays here forever, with its reason.

Impact: **high** = a user is misled or blocked · **med** = friction or inconsistency ·
**low** = polish.

| ID | Finding | Where | Impact | Contract | Status |
|----|---------|-------|--------|----------|--------|
| UI-01 | Provenance link's accessible name is just "web" — a screen-reader user hears "web" with no indication of what it sources or where it goes. The `title` is ignored because link text wins. | `ui/src/pages/Profile.jsx:38` | high | X-01, X-04 | done |
| UI-02 | 47 raw colour literals outside `tokens.css`. Each is a site the iX theme cannot reach, so the token migration cannot fully land while they exist. | 12 files, see `contract/ix-lint-baseline.json` | high | X-06 | proposed |
| UI-03 | `var(--bg)` is referenced but never declared, so it resolves to nothing and the rule silently does nothing. | `ui/src/pages/Explore.css:4` | med | — | proposed |
| UI-04 | One real `onClick` handler on a `<div>` with no role — the drawer backdrop, not keyboard reachable and invisible to assistive tech. (Originally reported as three sites; `Explore.jsx:246,247` are `ix_lint` false positives — see note below — and remain unfixed on purpose.) | `ui/src/pages/Explore.jsx:65` | high | X-04 | done |
| UI-05 | `ClaimEvidenceMatrix` hard-codes its entire palette (9 literals) rather than using the pillar/semantic tokens that already exist for exactly this. | `ui/src/components/ClaimEvidenceMatrix.jsx:10-34` | med | X-06 | proposed |
| UI-06 | Employees is web-researched and `profile_sources.employees_count` is populated (`core/pipeline.py:27`), but the metric renders with no provenance badge — while Founded, two lines below, has one. A reviewer cannot tell which figures are sourced. | `ui/src/pages/Profile.jsx:55` vs `:57` | high | X-01, PROF-02 | done |
| UI-07 | Alerts has an error state and an empty state but no loading state, so the list appears empty while it is still fetching — indistinguishable from "you are tracking nothing". | `ui/src/pages/Alerts.jsx` | med | X-03, MISC-02 | proposed |
| UI-08 | Five orphaned page stubs ("Superseded by the enterprise redesign") remain in `ui/src/pages/`: Dashboard, Evaluate, Challenges, Solve, RunDetail. Nothing imports them; they inflate `docs/ui-inventory.json` and give agents dead surface to reason about. | `ui/src/pages/{Dashboard,Evaluate,Challenges,Solve,RunDetail}.jsx` | med | — | done |
| UI-09 | The iX token migration (fb1568f) dropped text contrast on two of the four pillar pills — the control that displays the routing decision. `.pill.Pass` resolves to `rgba(0,10,20,.4)` on `#f0f2f5` = **2.69:1**; `.pill.Collaborate` resolves to `#009999` on `#e7f4f8` = **3.11:1**. 11px bold text needs 4.5:1 (AA). Pre-migration: 4.22:1 and 4.77:1 — a measured regression, not inherited debt. Root cause is `--theme-color-weak-text`, an iX token intended for de-emphasised text on the page background, used as a label colour on a filled pill. | `ui/src/styles.css:178,180` resolving `ui/src/tokens.css:60,63` | high | X-06 | done |
| UI-11 | The visual gate does not notice a whole new panel. Adding the PROF-12 "Headcount trend" panel to the Overview tab left `profile-desktop/laptop/tablet.png` **passing** — a white panel on the near-white canvas falls under Playwright's per-pixel colour threshold, so only its thin border and heading text count, staying below `maxDiffPixelRatio: 0.02` (`ui/playwright.config.js:27`). The baselines catch geometry shifts and text reflow, but not low-contrast additions or removals — so "the Tracxn layout still works" is a weaker guarantee than it reads. Consider a structural assertion (panel count / DOM shape per tab) alongside the pixel diff. | `ui/playwright.config.js:24-30`, `ui/e2e/journeys.spec.js:215-221` | med | X-05 | proposed |
| UI-10 | Four components are imported by nothing: `pages/EvidenceTab.jsx`, `components/{ClaimEvidenceMatrix,FitScoreHistogram,ScoreBar}.jsx` (Profile.jsx defines its own local `EvidenceTab` and takes `ScoreBar` from `widgets.jsx`). They carry 17 of the 51 `ix_lint` findings, so a third of UI-02/UI-05's effort would be spent on code no user renders. `EvidenceTab.jsx` additionally calls `useState`/`useMemo` after two conditional early returns — a Rules-of-Hooks violation that would throw if it were ever wired up. | `ui/src/pages/EvidenceTab.jsx:44-57` and three component files | med | — | proposed |
| UI-12 | Eight primary-navigation controls across five files are `onClick` on a non-interactive element with no `role`, `tabIndex` or key handler, and — unlike Explore's row click, which offers a real `aria-label="Open …"` button as the keyboard path (`Explore.jsx:334-335`) — none has any keyboard equivalent at all: Home's recent-evaluations, tracked-companies and saved-views rows; Saved's view row; Alerts' table row; and the SideNav saved-views item and page logo, both in the persistent shell on every page. The primary action on those pages (open a company) is unreachable without a mouse. | `ui/src/pages/Home.jsx:139-140,160-161,174-175` · `ui/src/pages/Saved.jsx:23-25` · `ui/src/pages/Alerts.jsx:50` · `ui/src/App.jsx:85,146-148` | high | X-04 | proposed |
| UI-13 | Explore's column-sort headers (`<th onClick>`, both the pinned company column and every configured column) have no keyboard path — no `tabIndex`, no Enter/Space handler. Sorting is mouse-only. | `ui/src/pages/Explore.jsx:293,297-303` | med | X-04 | proposed |
| UI-14 | The column drawer gained a keyboard entry and exit (UI-04) but no focus **trap**: no `role="dialog"`/`aria-modal`, so Tab from the last control moves focus behind the 28%-opacity mask onto dimmed content the panel visually implies is unreachable. `Explore.test.jsx:78-93` covers open-focus and Escape-return but never Tab-cycling, so the gap is untested as well as unfixed. | `ui/src/pages/Explore.jsx:41-115`, `ui/src/styles.css:272-277` | med | X-04 | proposed |
| UI-15 | `ix_lint`'s `a11y/clickable-non-interactive` rule has three independent blind spots in five lines, so its finding count understates real debt: it matches `onClick=` and `<div\|span` **on the same source line** only (missing four sites where `onClick` sits on the next line), checks `div`/`span` but never `tr`/`th` (missing UI-12's Alerts row and all of UI-13), and treats any `role=` as sufficient without checking tabbability (missing `App.jsx:85`, a `role="link"` with no `tabIndex`). Fixing the linter is higher leverage than patching the sites it happens to catch — UI-04 already established it produces false positives too, so it is wrong in both directions. | `scripts/ix_lint.mjs:84-88` | high | X-04 | proposed |
| UI-16 | Explore's stat tiles count **runs**; the table below counts **companies**, so the same screen contradicts itself. `stats` reduces over raw `runs` (`Explore.jsx:176-184`) while `rows` deduplicates to the latest run per company (`:155-173`). Observed live against the real backend: header reads "7 Companies · 35 Avg Fit Score · 3 Siemens-aligned" above a table of 2 rows, where both current companies route to Pass — so the true aligned count is **0**, not 3. Superseded re-evaluations vote in the aggregate, and a reviewer reads three companies worth pursuing when the answer is none. Fixtures carry one run per company, so no test can catch this; it appears the moment anyone clicks "Refresh Data". | `ui/src/pages/Explore.jsx:176-184` vs `:155-173` | high | X-01 | proposed |

## Phase 3 migration rows (iX IA authority)

Ordered, independently-shippable rows implementing `docs/ix/ia-mapping.md`. Shared primitives and
tokens first, app shell next (leads the screen work), screens after — sequence matters, later rows
assume earlier ones landed. **Command bar, dense tables, and dark chrome are now decided** (custom
in the header slot; semantic `<table>` + iX tokens; drop dark chrome, go light everywhere) — the
two rows that were BLOCKED on those picks are unblocked below. A row can still say **pending** where
a sub-decision inside it (e.g. `IxMessageBar`'s `role="alert"` status) hasn't been checked yet — that
blocks only that row's affected part, not the sequence.

Renumbered again from the prior 26-row draft, per five approved plan changes — this is now **29
rows**:
1. `ErrorBox` → `IxMessageBar` is split out of the old combined status/feedback row into its own
   row (new **MIG-03**), gated on verifying `role="alert"` and updating `ix_lint.mjs` rule 5 in the
   same change.
2. Dark chrome removal (`--chrome-*` token removal + the `styles.css` rewrite it forces) gets its
   own row (new **MIG-05**) instead of being folded into the shell-root row — it's the single most
   visible diff in the migration and is reviewed alone.
3. The pipeline-ribbon deletion now ships **before** the Profile head row (new **MIG-17** then
   **MIG-18** — reversed from the old MIG-15/MIG-16 order) since deleting the ribbon first shrinks
   what the head row has to touch.
4. A new row (**MIG-21**) adds Playwright visual baselines for Home and one non-default Profile tab
   (Scoring & Fit) before any further screen-content rows land — seven rows in the old draft shipped
   with **no visual coverage at all** (every "baselines invalidated: none of the current 8" line
   below is a coverage gap, not a clean bill of health). This row only writes the spec; a human runs
   `--update-snapshots` to create the baselines, same as always.
5. **MIG-06 through MIG-11 (the shell block) are a documented exception to the green-gate rule.**
   Each of those six rows individually invalidates chrome present on *every* screen, so re-baselining
   after each one would mean six human `--update-snapshots` passes for what is really one continuous
   change to the shell. The visual gate is expected to stay **RED** for the whole span. **End
   condition: MIG-11 (`AssistantDock`) merges → a human runs `--update-snapshots` once → the gate is
   green again and stays green from MIG-12 onward.** No row outside MIG-06–MIG-11 may be added to
   this exception without it being called out explicitly here.

Every "invalidates baselines" call below is a prediction, not a promise — verify against the actual
rendered screenshot before treating a baseline as untouched, then get a human to run
`--update-snapshots` for anything genuinely changed. Agents never regenerate baselines themselves.

| ID | Row | Size | Baselines invalidated | e2e impact | Status |
|----|-----|------|------------------------|------------|--------|
| MIG-00 | Delete the dead files current-state-inventory §3 flags — 11 total across two passes (7 orphaned pages/imports + `ClaimEvidenceMatrix.jsx`, `FitScoreHistogram.jsx`, `ScoreBar.jsx`, `Loading.jsx`, each independently confirmed unimported, distinct from same-named live exports in `widgets.jsx`) | trivial | none | none | done |
| MIG-01 | Pillar pill delivery → `IxPill` | small | none (verified: all 8 pass) | 2 selectors rewritten | done |
| MIG-02 | Status/feedback primitives → `IxSpinner`; `ScoreBar` → `role="meter"` or `IxKpi` (not `IxProgressIndicator`) | medium | none (verified: all 8 pass) | none | done |
| MIG-03 | `ErrorBox` → `IxMessageBar`, own row, gated on `role="alert"` + `ix_lint.mjs` rule-5 update | small | verify | none expected | gated |
| MIG-04 | Data-display primitives → `IxKeyValue(List)`, `IxKpi`, `IxEmptyState` | large | `profile-*`; `explore-*` unlikely (verify) | none expected | proposed |
| MIG-05 | Dark chrome removal — `--chrome-*` tokens + `styles.css` rewrite, own row | medium | both | none expected | proposed |
| MIG-06 | App shell root → `IxApplication` + `IxContent` — **gate goes RED here, see exception #5 above** | large | all 8 | `X-05` re-verify | proposed |
| MIG-07 | `TopBar` → `IxApplicationHeader` | medium | both | none yet | proposed |
| MIG-08 | `Rail` → `IxMenu` (main nav only) | large | both | `SHELL-01` full rewrite | proposed |
| MIG-09 | `SideNav` → `IxMenu` second-level (own row) | medium | `profile-*`/`explore-*` differ where SideNav is hidden vs. shown | none beyond `SHELL-01` (already covered by MIG-08) | proposed |
| MIG-10 | Command bar → custom, inside `IxApplicationHeader`'s left slot | medium-large | both, if position/appearance changes visibly | `SHELL-02/04` full rewrite | proposed |
| MIG-11 | `AssistantDock` → `IxPane`/`IxPaneLayout` — **gate exception ends here, re-baseline once** | medium | desktop/laptop (verify tablet/mobile unaffected) | `X-05` re-verify at 2 breakpoints | proposed |
| MIG-12 | Explore filter row → `IxCategoryFilter` | medium | `explore-*` | none of `SHELL-*`; spot-check filter interactions | proposed |
| MIG-13 | Explore page head/stats → `IxContentHeader` + `IxKpi` | small | `explore-*` | none expected | proposed |
| MIG-14 | Explore column drawer → `IxPane` | medium | none expected (drawer closed by default) | possibly `EXP-02/08` (verify role) | proposed |
| MIG-15 | Explore data grid → semantic `<table>` + iX tokens (re-skin only, behavior unchanged) | large | `explore-*`; possibly `profile-*` if Evidence tab shares styling | any test asserting `<table>`/`<th>` structure — verify, not assume rewrite | proposed |
| MIG-16 | Explore toolbar toggles → `IxToggleButton`/`IxToggle` | small | `explore-*` | none expected | proposed |
| MIG-17 | Profile pipeline ribbon → **delete**, do not re-skin (moved before the head row) | small | `profile-*` (ribbon removed from view) | none expected | proposed |
| MIG-18 | Profile head → `IxContentHeader` + `IxPill` | medium | `profile-*` | none (`PROF-04` unaffected, verified) | proposed |
| MIG-19 | Profile tab bar → `IxTabs`/`IxTabItem` | small-medium | `profile-*` | `PROF-04` rewrite | proposed |
| MIG-20 | Profile Overview tab → `IxKeyValueList`, `IxCard` | medium | `profile-*` | none beyond MIG-04/19 | proposed |
| MIG-21 | Add Playwright visual baselines: Home + one non-default Profile tab (test-authoring only) | small | none — this row creates baselines, doesn't invalidate them | additive only | proposed |
| MIG-22 | Profile Scoring & Fit tab → `IxBlind`, `IxSlider`, `ScoreBar` per MIG-02, `IxMessageBar` per MIG-03 | medium-large | new Home/Scoring-&-Fit baselines from MIG-21 (verify) | none expected | proposed |
| MIG-23 | Profile Evidence/Market&Risk/Ask tabs → `IxChip`, `IxCard`; Evidence table uses MIG-15's pattern (unblocked) | medium | none of current 8 | none expected | proposed |
| MIG-24 | Home → `IxKpi`, `IxCardList`+`IxEventListItem`, `IxChip` | medium-large | new Home baseline from MIG-21 (verify) | none expected | proposed |
| MIG-25 | Saved + Alerts → `IxCardList`/`IxEventListItem`; Alerts table uses MIG-15's pattern (unblocked) | small–medium | none of current 8 | none expected | proposed |
| MIG-26 | Settings → `IxKeyValueList`, status-row primitive (open question) | small | none of current 8 | none expected | proposed |
| MIG-27 | Admin → `IxKpi`, `IxInput`/`IxButton`; 4 tables use MIG-15's pattern (unblocked) | small (non-table) + medium (4 tables) | none of current 8 | none expected | proposed |
| MIG-28 | SignIn → `IxCard` + `IxMessageBar` per MIG-03 + `IxButton`; stays outside `IxApplication` (decided) | small-medium | none (uncaptured) | none expected | proposed |
| MIG-29 | Consolidate the remaining `.pill.<Pillar>` renderers (`Home.jsx`, `Alerts.jsx`, `WhatIfWeights.jsx`, `widgets.jsx`'s routing-summary use of `scoring/routing.js`'s output) onto `PillarPill`/`IxPill`, retiring `.pill.Connect/.Collaborate/.Empower/.Pass`. Appended out of number order — see row detail for why. **Ships before MIG-22/24/25**, despite the higher number. | small | Home (once captured by MIG-21/24), Scoring & Fit (once captured by MIG-21) — verify against whichever of MIG-21/22/24 lands first | none expected | proposed |

### MIG-00 — Delete dead files
- **Files (pass 1, `bd01eb9`):** `ui/src/components/ResultView.jsx`, 5 stub pages (`ui/src/pages/{Dashboard,Evaluate,Challenges,Solve,RunDetail}.jsx`), `ui/src/pages/EvidenceTab.jsx` — 7 files, and their orphaned imports/tests, per `current-state-inventory.md` §3.
- **Files (pass 2, follow-up commit):** `ui/src/components/ClaimEvidenceMatrix.jsx`, `ui/src/components/FitScoreHistogram.jsx`, `ui/src/components/ScoreBar.jsx`, `ui/src/components/Loading.jsx` — 4 files. The finding actually named 7 rows, not 7 files; one row bundled the 5 stub pages together and the other four files were missed in pass 1. Each was verified independently via import-specifier grep (`grep -rn "from ['\"].*<Name>" ui/src ui/e2e`, hits inspected for the resolved path) rather than a bare component-name grep, because `ui/src/components/widgets.jsx` exports live `ScoreBar` and `Loading` symbols of the same name that every real importer actually resolves to — a bare name grep would have wrongly suggested the standalone files were in use.
- **Replaces:** nothing (pure deletion) — but shrinks the surface every later row and every `docs/ui-inventory.json` regen has to reason about.
- **Fixes:** dead code inflating the inventory; overlaps `UI-08` above (same finding, do once). Also removed 13 pre-existing `ix_lint` findings tied to the pass-2 files (49 known → 36 known against the unchanged baseline).
- **Could break:** nothing if truly unimported — confirmed via grep before deleting, not from the inventory listing alone.
- **Size:** trivial.
- **Baselines invalidated:** none (unreachable pages/components, not in any captured route) — verified: full `bash scripts/gates.sh` including Playwright visual regression is green with zero screenshot diffs after both passes.
- **e2e rewrites:** none.
- **Status:** all 11 dead files across both passes are deleted; row closed.

### MIG-01 — Pillar pill delivery mechanism
- **Files:** `ui/src/tokens.css` (new `--pillar-*-bg` tokens, literals moved from `styles.css`), `ui/src/components/widgets.jsx` (new `PillarPill` wrapping `IxPill variant="custom"`), `ui/src/pages/Profile.jsx` (3 sites), `ui/src/pages/Explore.jsx` (pillar column), `ui/src/styles.css` (`.pill.*` rules kept — still consumed directly by `Home.jsx`, `Alerts.jsx`, `WhatIfWeights.jsx`, `scoring/routing.js`, migrating those is separate unscoped work), `ui/vite.config.js`, `ui/src/test/setup.js`. `ClaimEvidenceMatrix.jsx` confirmed deleted by MIG-00 — moot.
- **Replaces:** hand-rolled `.pill` class with `IxPill variant="custom"` + `background`/`pillColor`, at the 4 sites above. The four literal colors are unchanged — only the delivery mechanism moves, per `ia-mapping.md`.
- **Fixes:** delivers the pill through an iX component instead of bespoke CSS at those sites. Also fixed a real bug found along the way: `@siemens/ix-react`'s `"node"` export condition resolves to an SSR stub whose props never reach the underlying custom element — Vitest (jsdom) was hitting that stub, so `IxPill`'s `variant`/`background`/`pillColor` were silently dropped in every test and would have been in production too. Fixed via `resolve: { conditions: ["browser"] }` in `ui/vite.config.js`.
- **Could break:** `UI-09`'s existing contrast fix — re-measured directly against the `IxPill`-rendered shadow-DOM `.container` node (color is painted there, not on the host element): Connect 5.80:1, Collaborate 5.64:1, Empower 4.98:1, Pass 5.16:1 — all clear AA (4.5:1), unchanged from UI-09 because the same literal color strings are now passed through `background`/`pillColor` instead of CSS classes.
- **Size:** small.
- **Baselines invalidated:** none — both `profile-*` and `explore-*` (all 4 breakpoints each) verified passing with zero diff; `IxPill`'s custom-variant rendering is pixel-identical to the retired `.pill` class at the 4 migrated sites.
- **e2e rewrites:** 2 selectors in `journeys.spec.js` (PROF-15's `.ph-title .pill` → `.ph-title ix-pill`; X-06's contrast check rewritten to pierce `ix-pill`'s shadow DOM) — everything else (`Explore.test.jsx`, remaining `journeys.spec.js` cases) needed no change.
- **Status:** done. Branch `mig-01-pillar-pill`, rebased onto a combined base (`step-b-ix-design-contract` merged with `mig-00-delete-dead-pages`) after the implementer discovered it had been built on `step-b` alone, which predates the MIG plan landing anywhere.

### MIG-02 — Status/feedback primitives
- **Files:** `ui/src/components/widgets.jsx` (`Loading`, `ScoreBar`), `ui/src/components/widgets.test.jsx`, `docs/ui-inventory.json` (regenerated). No importer needed a code change — `Loading`'s and `ScoreBar`'s call sites (`Profile.jsx`, `Home.jsx`, `Settings.jsx`, `Admin.jsx`, `App.jsx`) pass only `text`/`label`/`value` props, which are unchanged.
- **Replaces:** `Loading`'s decorative `<span className="spinner">` → `<IxSpinner size="xx-small" aria-hidden="true" />`, verified against `@siemens/ix/dist/collection/components/spinner/spinner.js`: `IxSpinner` unconditionally sets `role="status"`/`aria-busy="true"` on its own host (not gated on any prop), so leaving it visible to assistive tech would create two competing status regions on one `Loading`. `aria-hidden="true"` survives that (only `role`/`aria-busy` are forced; `aria-hidden` passes through `a11yHostAttributes` untouched), which removes the whole element from the accessibility tree per spec regardless of the role iX forces onto it — so the outer `<p role="status" aria-live="polite">` stays the only thing announced, unchanged from before. `ScoreBar` → kept **custom with `role="meter"`**, not `IxKpi`: `IxKpi`'s prop table (`label`/`value`/`unit`/`state`/`orientation`, `components.md:1224-1234`) has no notion of a range or a visual fill, and `ScoreBar`'s `bar-track`/`bar-fill` *is* the 0-100 scale the row displays — moving to `IxKpi` would drop exactly the thing being measured. Added `role="meter"` + `aria-valuenow`/`aria-valuemin`/`aria-valuemax`/`aria-label` to the existing `bar-track` div; the visual markup (bar-fill width, rounded value text) is unchanged. `ErrorBox` is **out of scope for this row** — see `MIG-03`, its own gated row.
- **Fixes:** a score now exposes itself as a fixed-range measurement (`role="meter"`) instead of the completion semantics `IxProgressIndicator`'s `role="progressbar"` would have implied; `Loading`'s spinner is delivered through iX's own primitive.
- **Could break:** `widgets.test.jsx` asserted DOM structure (`.spinner` class, no `ScoreBar` coverage at all) — rewritten: the `Loading` tests now query the rendered `ix-spinner` element instead of a `.spinner` class name (same behavioral assertions: hidden from AT, message is the sole accessible content), and three new `ScoreBar` tests assert `getByRole("meter", {name})`, the `aria-valuenow/min/max` triple, the 0-100 clamp, and that no `role="progressbar"` exists.
- **Size:** medium.
- **Baselines invalidated:** none — verified, not assumed: `ScoreBar` only renders on Profile's Scoring & Fit tab; the `profile-*` visual fixture (`journeys.spec.js:284-291`) navigates straight to `/startup/1` and screenshots whatever tab is default (Overview), never opening Scoring & Fit, so `ScoreBar` is never in frame. Ran the full `bash scripts/gates.sh` (not `--fast`) — all 8 current baselines (`explore-*`/`profile-*` × 4 breakpoints) passed with zero diff.
- **e2e rewrites:** none — grepped `journeys.spec.js` and `auth.spec.js` for `Loading`/`ScoreBar`/`.spinner`/`.bar-track`/`.bar-fill`; no journey test asserts on either widget's markup. Full `npx playwright test` run: 76/76 passed.
- **Status:** done. Branch `mig-02-status-primitives`, off `latest` (post `mig-01-pillar-pill` merge).

### MIG-03 — `ErrorBox` → `IxMessageBar` (own row, gated)
- **Files:** `ErrorBox` (wherever it's defined) and every importer, `scripts/ix_lint.mjs:96-99` (rule 5).
- **Replaces:** `ErrorBox`→`IxMessageBar type="alarm"` (severity per call site) — **not decided outright, gated on a verification step**: `ix_lint.mjs:96-99` names `ErrorBox` as the only sanctioned error surface specifically because it guarantees `role="alert"`, and `IxMessageBar`'s prop table (`persistent`, `type` — checked in `docs/ix/components.md:1274-1285`) documents no ARIA role at all. Build `IxMessageBar`, inspect its rendered DOM for `role="alert"`:
  - **If present:** update `ix_lint.mjs` rule 5 to sanction `IxMessageBar` (replacing or alongside `ErrorBox`) in the *same* change that swaps any call site — never leave the rule pointing at `ErrorBox` alone while call sites move to `IxMessageBar`, or the lint rule becomes wrong in a new direction instead of catching the old one.
  - **If absent:** this row does not ship. `ErrorBox` stays, and the row is marked `rejected` here with that finding as the reason, so it isn't re-proposed later.
- **Fixes:** consistent alarm/warning severity tokens for error surfaces, contingent entirely on the role check above.
- **Could break:** `ErrorBox`'s `role="alert"` contract if the swap proceeds without confirming the role first — do not merge under any circumstance until confirmed. `ErrorBox.test.jsx` (if it exists) must be rewritten to assert *behavior*, not markup.
- **Size:** small (isolated to one component, its importers, and one lint rule) — kept separate from MIG-02 specifically so this gate doesn't block the rest of that row's unconditional work.
- **Baselines invalidated:** verify — `ErrorBox` renders in error states, and none of the 8 current baselines capture a screen in an error state per current fixtures, so expected **not** invalidated.
- **e2e rewrites:** none expected — no journey test asserts on `ErrorBox`'s markup.
- **Status:** gated, not proposed outright — do not schedule downstream rows (`MIG-22`, `MIG-28`) that reference `IxMessageBar` ahead of this one resolving.

### MIG-04 — Data-display primitives
- **Files:** `ui/src/components/widgets.jsx` (`Spec`), `ui/src/pages/{Profile,Settings,Admin,Home,Explore,Alerts,Saved}.jsx` (`.empty` blocks), stat-tile markup wherever it's hand-rolled.
- **Replaces:** `Spec`→`IxKeyValueList`/`IxKeyValue`; ad hoc stat tiles→`IxKpi`; `.empty` blocks→`IxEmptyState`.
- **Fixes:** consistent key/value and empty-state rendering across 7 screens instead of 7 hand-rolled versions.
- **Could break:** any Vitest asserting `.empty` text content directly (rewrite to query rendered text via Testing Library queries, not source-text matching — already required by CLAUDE.md).
- **Size:** large (cross-cutting, many files) — consider splitting into `Spec`-only and `.empty`-only sub-PRs if it grows unwieldy in practice.
- **Baselines invalidated:** `profile-*` (Overview tab renders `Spec`) — invalidated. `explore-*`: only if Explore's captured fixture state is empty; current fixtures carry rows, so expected **not** invalidated — verify.
- **e2e rewrites:** none expected.

### MIG-05 — Dark chrome removal
- **Files:** `ui/src/tokens.css` (every `--chrome-*` declaration), `ui/src/styles.css` (every rule consuming a `--chrome-*` token — `TopBar`, `Rail`, `SideNav`, `AssistantDock`, and any other chrome surface).
- **Replaces:** dark-chrome tokens/colors with iX-native light tokens throughout the shell — decided option (b): the dark-chrome-over-light-canvas seam is retired outright, not redrawn onto an iX scale, because by the user's own framing it **is** the Tracxn look this migration exists to remove, and it's the single most visible diff in the whole plan — hence its own row, reviewed alone rather than folded into the shell-root rewrite.
- **Fixes:** nothing broken — this is a pure visual change, given its own row specifically so it can be reviewed as one isolated diff rather than mixed into `MIG-06`'s structural shell rewrite.
- **Could break:** any rule anywhere that still reads a `--chrome-*` custom property after this row removes the declarations — grep for every consumer before deleting; a removed-but-still-referenced token resolves to nothing, the same failure mode as `UI-03`.
- **Size:** medium — the token removal itself is small, but the diff touches every shell file's color rules at once.
- **Baselines invalidated:** both (`explore-*`, `profile-*`) — chrome color is visible in every captured screenshot.
- **e2e rewrites:** none expected — no journey test asserts on `--chrome-*` tokens or color values.
- **Sequencing:** lands *before* the shell-component rewrites (`MIG-06` onward) so those rows build directly against the final light token set instead of needing a second pass once dark chrome is later removed underneath them.

### MIG-06 — App shell root
- **Files:** `ui/src/App.jsx` (`Shell`), `ui/src/styles.css` (removes `.content` margin-offset layout).
- **Replaces:** the `<>TopBar/><Rail/><SideNav/><main></>` fragment with `IxApplication` wrapping `IxContent`, per `ia-mapping.md`'s "Application shell" citation.
- **Fixes:** the fixed-position-siblings structure `guidance.md` explicitly says not to build; hands layout/breakpoint responsibility to iX instead of hand-rolled margin math.
- **Could break:** every screen's layout assumptions (margin offsets, sticky positioning relative to `.content`) — this is the row most likely to cause incidental regressions since it changes the layout engine under everything else.
- **Size:** large.
- **Baselines invalidated:** all 8 (`explore-*` and `profile-*`, all 4 breakpoints each) — layout container changes under every screen.
- **e2e rewrites:** `X-05` ("no horizontal body scroll at any width") must be re-verified against the new layout engine, though its assertion itself doesn't need rewriting unless it starts failing.
- **Visual gate note:** this row opens the MIG-06–MIG-11 gate-RED exception (see the numbered list above) — do not treat a red visual gate on this row's PR as a regression to fix; it's expected through `MIG-11`.

### MIG-07 — `TopBar` → `IxApplicationHeader`
- **Files:** `App.jsx` (`TopBar`), `styles.css`.
- **Replaces:** the fixed 56px bar with `IxApplicationHeader` (brand via `companyLogo`/`appIcon`, `name`, right-slot for advanced-search/tracking-bell/avatar).
- **Fixes:** adopts iX's own responsive header collapse (guidance: menu hides behind an icon below the `sm` breakpoint, `nameSuffix` hides) instead of a hand-rolled fixed bar with no responsive behavior of its own.
- **Could break:** low direct Vitest risk (`App.test.jsx` only asserts the auth gate and dock breakpoint behavior, not `TopBar` internals, per `current-state-inventory.md`). The tracking-bell badge has no verified iX slot (see mapping's open question #1) — resolve that before or during this row.
- **Size:** medium. Keep the command bar **out** of this row — it's `MIG-10`, a decided-but-separate build.
- **Baselines invalidated:** both (`explore-*`, `profile-*`) — header chrome is in every captured viewport. (Still inside the gate-RED exception.)
- **e2e rewrites:** none yet (`SHELL-01`/`SHELL-02/04` are Rail/CommandBar-specific, untouched by this row).

### MIG-08 — `Rail` → `IxMenu` (main navigation only)
- **Files:** `App.jsx` (`Rail`, `RAIL`/`ADMIN_RAIL` arrays), `App.test.jsx`, `ui/e2e/journeys.spec.js`.
- **Replaces:** the fixed icon rail with `IxMenu` (`IxMenuItem` per nav entry: Home/Explore/Views/Tracking/Settings/Admin; `IxMenuItem` in the bottom slot for "Ask AI"). **SideNav is out of scope for this row** — see `MIG-09`.
- **Fixes:** nothing broken — swaps one hand-rolled nav for iX's own menu component.
- **Could break:** **forces `SHELL-01`'s rewrite** — `IxMenu`'s default `i18nAriaLabelMenu` is "Application Navigation," not "Primary," so `getByRole("navigation", {name: /primary/i})` breaks outright unless the label prop is explicitly overridden to match, and even then the exact link set needs re-verifying against the rendered `IxMenu` DOM. Depends on resolving mapping open question #2 (Settings: main list vs. bottom slot) before this can be built.
- **Size:** large.
- **Baselines invalidated:** both (`explore-*`, `profile-*`) — nav chrome is in both. (Still inside the gate-RED exception.)
- **e2e rewrites:** `SHELL-01` (full rewrite, not a tweak).

### MIG-09 — `SideNav` → `IxMenu` second-level (own row, not bundled into MIG-08)
- **Files:** `App.jsx` (`SideNav`), `App.test.jsx` if it asserts SideNav visibility per route.
- **Replaces:** the second fixed chrome layer (Quick access links + dynamic Saved-views list, hidden on Profile, hidden <1180px) with second-level items under an `IxMenuCategory` inside the *same* `IxMenu` `MIG-08` builds — not a second component. This is the row that actually collapses two chrome layers into one, per `ia-mapping.md`'s open question #6.
- **Fixes:** the two-layer rail+sidenav structure `current-state-inventory.md` §4 flags as needing a Phase 2/3 decision.
- **Could break:** depends on `MIG-08` landing first (there must be an `IxMenu` to add second-level items to). The "hidden on Profile, hidden <1180px" conditional visibility logic needs an equivalent inside `IxMenuCategory`'s expand/collapse behavior — not guaranteed to be a like-for-like carry-over, verify before assuming it just works.
- **Size:** medium.
- **Baselines invalidated:** `explore-*` and `profile-*` will now differ (SideNav is present on one, absent on the other) — check both regardless of which one is expected to change. (Still inside the gate-RED exception.)
- **e2e rewrites:** none beyond what `MIG-08`'s `SHELL-01` rewrite already covers, since it's the same `IxMenu` instance.

### MIG-10 — Command bar → custom, inside `IxApplicationHeader`'s left slot
- **Files:** `App.jsx` (`CommandBar`), `App.test.jsx`, `ui/e2e/journeys.spec.js`.
- **Replaces:** nothing about the palette's own behavior (Ctrl/Cmd+K focus, 350ms-debounced search, `/solve`/`/explore` slash routing) — only its shell: it now lives inside `IxApplicationHeader`'s left slot instead of a bespoke `TopBar` div, per the decided option (b).
- **Fixes:** nothing broken — this is a relocation, not a behavior change, but it still touches the header's DOM structure enough to matter for tests.
- **Could break:** **forces `SHELL-02/04`'s full rewrite regardless** — the exact selector (`getByPlaceholder(/search a startup/i)`) and the literal `Control+k`-to-`body` behavior need re-verifying against wherever the input now sits in the DOM, even though the palette's own logic is unchanged.
- **Size:** medium-large — not small, since it's the app's only keyboard-driven navigation shortcut and the rewrite must prove the shortcut still works, not just that the input renders.
- **Baselines invalidated:** both, if the header search box's position/appearance changes visibly once it's inside the header slot rather than the current `TopBar` div — verify against the built header. (Still inside the gate-RED exception.)
- **e2e rewrites:** `SHELL-02/04` (full rewrite).

### MIG-11 — `AssistantDock` → `IxPane`/`IxPaneLayout`
- **Files:** `components/AssistantDock.jsx`, `App.jsx` (`Shell` composition, the width-listener `useEffect`), `styles.css`.
- **Replaces:** the fixed 332px panel + manual `.content` margin math with `IxPane` (`composition="right"`, `size="360px"`, `variant` per mapping's open question #3) inside `IxPaneLayout`.
- **Fixes:** hands sizing/collapse semantics to iX instead of a hand-rolled fixed-panel + margin offset.
- **Could break:** `App.test.jsx`'s dock-breakpoint assertions (auto-open ≥1181px, one control reopens it) — `IxPane` has no breakpoint prop of its own, so the existing width-listener must keep driving `expanded` manually; re-verify the test against that wiring, not assume it just works.
- **Size:** medium.
- **Baselines invalidated:** both at desktop/laptop widths (1920/1440, both >1181px, dock likely auto-open and visible in the captured state) — tablet/mobile (1024/390, both <1181px) expected unaffected — verify against the actual fixture stabilise() behavior before relying on this split.
- **e2e rewrites:** none expected beyond re-verifying `X-05` at the two affected breakpoints.
- **Visual gate note: this row closes the MIG-06–MIG-11 exception.** A human runs `--update-snapshots` once, here, after this row merges — not before, and not per-row within the block. The gate is expected green again starting `MIG-12`.

### MIG-12 — Explore filter row → `IxCategoryFilter`
- **Files:** `pages/Explore.jsx`, `Explore.test.jsx`.
- **Replaces:** hand-rolled text filter + 4 pillar chips + active-filter chips + Clear-all with `IxCategoryFilter` (`categories`, `filterState`, built-in per-chip clear and reset).
- **Fixes:** one component instead of four independent hand-rolled pieces; per mapping, an unusually strong prop-shape match.
- **Could break:** `Explore.test.jsx`'s filter-interaction assertions need rewriting against `IxCategoryFilter`'s events instead of the current input/button DOM.
- **Size:** medium.
- **Baselines invalidated:** `explore-*` (filter row is above the fold).
- **e2e rewrites:** none of `SHELL-01/02/04`; spot-check any Explore-specific journey test that interacts with the filter row.

### MIG-13 — Explore page head/stats → `IxContentHeader` + `IxKpi`
- **Files:** `pages/Explore.jsx`.
- **Replaces:** hand-rolled page head + stats strip. **Depends on MIG-04** for the `IxKpi` primitive already being in place.
- **Fixes:** consistent header pattern with Profile's own `IxContentHeader` use (MIG-18).
- **Could break:** `UI-16`'s stats-vs-table mismatch (companies vs. runs) is a data bug, not fixed by this row — don't conflate the component swap with fixing the undercount.
- **Size:** small.
- **Baselines invalidated:** `explore-*`.
- **e2e rewrites:** none expected.

### MIG-14 — Explore column drawer → `IxPane`
- **Files:** `pages/Explore.jsx` (`ColumnDrawer`), `Explore.test.jsx`, `styles.css`.
- **Replaces:** hand-rolled `.drawer`/`.drawer-mask` with `IxPane` (`variant="floating"`, `composition="right"`, `closeOnClickOutside`).
- **Fixes:** `UI-04`'s backdrop click-handler site could move onto `closeOnClickOutside` instead of a bespoke `<div onClick>`.
- **Could break:** `UI-14`'s focus-trap gap may or may not be solved by this swap — `IxPane`'s prop list has no explicit `trapFocus`, so don't assume it's fixed until verified against the built component; also forces rewriting `Explore.test.jsx`'s open-focus/Escape-return assertions, and re-checking `EXP-02/08`'s `getByRole("complementary", ...)` selector against whatever role `IxPane` actually renders.
- **Size:** medium.
- **Baselines invalidated:** none expected — the drawer is closed by default in both captured screenshots.
- **e2e rewrites:** possibly `EXP-02/08` if `IxPane`'s ARIA role differs from `complementary` — verify when built, not assumed here.

### MIG-15 — Explore data grid → semantic `<table>` + iX tokens
- **Files:** `pages/Explore.jsx` (the entire table), `Explore.test.jsx`, likely `styles.css`.
- **Replaces:** re-skin only — sort/sticky/column-drawer logic stays exactly as today. Column colors, borders, hover/selected states, header styling move onto `--theme-color-*`/elevation tokens; zero iX components introduced (decided option (a) — dense column-wise comparison is the product, so a card-list alternative was rejected even for the simpler tables).
- **Fixes:** the last remaining raw-color/non-token surface on Explore, feeding directly into `UI-02`'s token-migration count.
- **Could break:** low behavioral risk since sort/sticky/drawer logic is unchanged — the risk is purely visual (contrast, density) given how many rows/columns are on screen at once.
- **Size:** **the largest row in the entire plan** — this is also the row that `MIG-23`'s Evidence-tab sub-part, `MIG-25`'s Alerts sub-part, and 4 of `MIG-27`'s Admin tables all reuse. One pattern, six dependent sites, but each site still needs its own pass since it's a re-skin, not a shared component.
- **Baselines invalidated:** `explore-*` at minimum; likely `profile-*` too if the Evidence tab's table shares the same CSS.
- **e2e rewrites:** any Explore journey test asserting on `<table>`/`<th>`/`<tr>` structure (sort, column headers) should be checked, but since the DOM shape is unchanged (only styling moves), most are expected to keep passing — verify rather than assume a rewrite is needed.

### MIG-16 — Explore toolbar toggles
- **Files:** `pages/Explore.jsx` (density toggle, portfolio-weighting toggle).
- **Replaces:** hand-rolled toggle buttons with `IxToggleButton`/`IxToggle` (already-verified core components, not gated on any open question).
- **Fixes:** consistent toggle affordance/state styling.
- **Could break:** low risk — isolated controls.
- **Size:** small.
- **Baselines invalidated:** `explore-*` (toolbar is above the fold).
- **e2e rewrites:** none expected.

### MIG-17 — Profile pipeline ribbon → delete (moved before the head row)
- **Files:** `pages/Profile.jsx:612-619` (`.ribbon`, `STEPS` array).
- **Replaces:** nothing — this is a deletion, not a re-skin. Verified at `Profile.jsx:613-618`: every step unconditionally renders `className="step done"` regardless of the run's actual state, and only ever renders after the run has finished (the earlier `!res` branch at `:561` shows a generic skeleton, not per-step progress) — there is no streaming-progress code anywhere in this component. A ribbon where all 7 steps are always "done" conveys zero information.
- **Fixes:** removes a widget that has never actually communicated anything, rather than shipping a correctly-styled version of it on `IxWorkflowSteps`.
- **Could break:** low risk — check nothing else reads `STEPS` or `.ribbon` before deleting. If a genuine streaming-progress view for in-flight evaluations is ever built, `IxWorkflowSteps`/`IxWorkflowStep` (`status` enum) is the right component for it *then* — this row does not preclude that, it just doesn't re-skin dead decoration today.
- **Size:** small.
- **Baselines invalidated:** `profile-*` (the ribbon disappears from the captured Overview view — this is an intentional, expected pixel change, not a regression).
- **e2e rewrites:** none expected — no journey test asserts on `.ribbon`/`.step` per the earlier grep of `journeys.spec.js`.
- **Sequencing:** deliberately ships **before** `MIG-18` (Profile head) rather than after — the ribbon sits in the same header region the next row rewrites, so deleting it first means `MIG-18` has one less element to carry through the swap.

### MIG-18 — Profile head → `IxContentHeader` + `IxPill`
- **Files:** `pages/Profile.jsx` (header region).
- **Replaces:** logo chip/name/pillar pill/summary/meta/tags/action row with `IxContentHeader` (`hasBackButton`, `headerTitle`, `headerSubtitle`, header-slot for pill/tags, action buttons). **Depends on MIG-01** for the pill, and on `MIG-17` having already removed the ribbon from this region.
- **Fixes:** near-literal match per mapping — consolidates a hand-built header region into one component.
- **Could break:** `UI-01`'s provenance-link accessible-name fix and `UI-06`'s provenance-badge fix both live in this region — re-verify both survive the swap, don't just trust the visual similarity.
- **Size:** medium.
- **Baselines invalidated:** `profile-*`.
- **e2e rewrites:** `PROF-04` only asserts tab-role/switching, not the header, so unaffected — verified by the earlier grep, not assumed.

### MIG-19 — Profile tab bar → `IxTabs`
- **Files:** `pages/Profile.jsx` (tab bar + `?tab=` sync).
- **Replaces:** hand-rolled sticky tab bar with `IxTabs`/`IxTabItem` (`activeTabKey`≈`tabKey` maps onto the existing query param with no semantic change).
- **Fixes:** nothing broken — direct match.
- **Could break:** **forces `PROF-04`'s rewrite** — its `tablist` role and `aria-selected` assertions must be re-verified against `IxTabs`'s actual rendered ARIA (likely compatible, since tabs are a native ARIA pattern, but not to be assumed without checking the built markup).
- **Size:** small-medium.
- **Baselines invalidated:** `profile-*` (tab bar is visible in the captured Overview state).
- **e2e rewrites:** `PROF-04`.

### MIG-20 — Profile Overview tab → `IxKeyValueList`, `IxCard`
- **Files:** `pages/Profile.jsx` (Overview tab body). **Depends on MIG-04** (`Spec`→`IxKeyValueList` already landed there).
- **Replaces:** panel wrappers around Spec/HeadcountTrend/Radar/Team/Customers/Signals with `IxCard`; HeadcountTrend and Radar chart internals stay custom (no chart primitive exists).
- **Fixes:** consistent card surface/elevation across Overview's many panels.
- **Could break:** low risk if MIG-04 already handled `Spec` correctly.
- **Size:** medium.
- **Baselines invalidated:** `profile-*` (this is exactly what's captured — full Overview tab, now also missing the deleted ribbon from MIG-17).
- **e2e rewrites:** none expected beyond what MIG-04/MIG-19 already cover.

### MIG-21 — Add Playwright visual baselines: Home + one non-default Profile tab
- **Files:** `ui/e2e/journeys.spec.js` (or a new spec alongside it), `ui/playwright.config.js` if new fixture/viewport setup is needed.
- **Replaces:** nothing — this row only **adds** visual-regression coverage, it changes no application code. Seven rows in this plan (`MIG-22` through `MIG-28`, i.e. everything after this point) currently carry "baselines invalidated: none of the current 8" — that phrase describes a coverage gap, not a clean bill of health: those screens have never had a captured baseline to invalidate.
- **Fixes:** closes that gap for two of the highest-traffic uncovered surfaces before the plan moves further into screen-content rows: Home (the landing screen) and Profile's Scoring & Fit tab (the next row, `MIG-22`, and the most complex non-default tab — sliders, gate rows, `ScoreBar`).
- **Could break:** nothing — additive test-authoring only, asserted against the *current*, pre-migration UI as ground truth, so it must land and get baselines captured before `MIG-22` changes that tab's contents.
- **Size:** small (test-authoring only).
- **Baselines invalidated:** none — this row is what *creates* the new baselines, not what invalidates existing ones.
- **e2e rewrites:** none — purely additive.
- **Human step required:** after this row's spec is written, a human runs `--update-snapshots` to actually capture the two new baseline images. Do not fabricate placeholder screenshots or mark this row done before that capture happens.

### MIG-22 — Profile Scoring & Fit tab
- **Files:** `pages/Profile.jsx` (Scoring & Fit tab), `components/WhatIfWeights.jsx`, `components/WeightSliders.jsx`.
- **Replaces:** `ScoreBar` per `MIG-02`'s decision (`role="meter"` or `IxKpi`, not `IxProgressIndicator`); `WhatIfWeights`' collapsible wrapper→`IxBlind`; `WeightSliders`' range inputs→`IxSlider` (not `IxRangeField` — verified as the wrong component for a single value); gate pass/fail rows→`IxMessageBar` per `MIG-03`'s outcome (only if that row shipped — otherwise these stay `ErrorBox`).
- **Fixes:** real slider semantics instead of hand-rolled range inputs; a scoring metric represented as a measurement, not a completion bar.
- **Could break:** the shared `se.whatIfWeights.v1` state contract between Profile's what-if and Explore's portfolio re-weighting (CLAUDE.md) — verify both consumers still agree on the value shape after `IxSlider` is wired in. Also: `MIG-21`'s new Scoring & Fit baseline is captured against the *pre*-this-row UI — this row is expected to invalidate it immediately, which is normal, not a sign `MIG-21` was pointless (it still covers `MIG-23` onward).
- **Size:** medium-large.
- **Baselines invalidated:** the new Scoring & Fit baseline from `MIG-21` (expected — verify against the actual diff).
- **e2e rewrites:** none expected.

### MIG-23 — Profile Evidence/Market&Risk/Ask tabs
- **Files:** `pages/Profile.jsx` (remaining tabs), local `EvidenceTab` definition.
- **Replaces:** claimed-program badges→`IxChip`/`IxPill` (open question #6, not picked here); prompt chips→`IxChip`; input bar→`IxInput`+`IxIconButton`; chat transcript stays custom (no chat-message component exists). **Evidence tab's fact table now uses `MIG-15`'s decided pattern** (semantic `<table>` + tokens) — no longer blocked, but still its own build since it's a different table.
- **Fixes:** consistent chip/input styling for the non-table parts of these tabs.
- **Could break:** low risk throughout — the table sub-part now has a decided pattern to follow instead of an open decision.
- **Size:** medium, split cleanly at the table boundary.
- **Baselines invalidated:** none of the current 8 or the two new ones from `MIG-21` (these tabs aren't captured by either).
- **e2e rewrites:** none expected.

### MIG-24 — Home
- **Files:** `pages/Home.jsx`.
- **Replaces:** stats strip→`IxKpi`; query composer→`IxCard`+`IxCardContent`; quick-prompt chips→`IxChip`; list panels (Solve results/Recent evaluations/Tracked companies/Saved views/Recent challenges)→`IxCardList`+`IxEventListItem`. **Depends on MIG-02/04.**
- **Fixes:** `UI-12`'s keyboard-unreachable row-click sites on Home (recent-evaluations, tracked-companies, saved-views rows) — `IxEventListItem`'s `chevron` affordance is a real interactive element, verify it's keyboard-reachable by default before calling `UI-12` closed by this row alone.
- **Could break:** low risk; existing Vitest for Home likely needs rewriting against the new component structure regardless. `MIG-21`'s new Home baseline is expected to be invalidated by this row's own changes — that's the point of having captured it first.
- **Size:** medium-large (Home has the most distinct panel types of any screen).
- **Baselines invalidated:** the new Home baseline from `MIG-21` (expected — verify against the actual diff).
- **e2e rewrites:** none expected.

### MIG-25 — Saved + Alerts
- **Files:** `pages/Saved.jsx`, `pages/Alerts.jsx`.
- **Replaces:** list rows→`IxCardList`+`IxEventListItem` (open question #8: no verified trailing-delete-action slot on `IxEventListItem`, resolve during this row, not before). **Alerts' watchlist table now uses `MIG-15`'s decided pattern** — no longer blocked.
- **Fixes:** `UI-12`'s Saved-view-row and Alerts-table-row keyboard-unreachable sites, same caveat as MIG-24 — verify, don't assume.
- **Could break:** low risk for Saved; Alerts' table sub-part follows `MIG-15`'s pattern directly.
- **Size:** small (Saved) + small-medium (Alerts table re-skin).
- **Baselines invalidated:** none of the current 8 or the two from `MIG-21`.
- **e2e rewrites:** none expected.

### MIG-26 — Settings
- **Files:** `pages/Settings.jsx` (`Row` component).
- **Replaces:** account panel→`IxKeyValueList` (depends on MIG-04); backend-status rows→open question #7 (`IxKpi` vs `IxEventListItem`, not picked here — resolve during this row).
- **Fixes:** nothing broken — component consolidation only.
- **Could break:** low risk.
- **Size:** small.
- **Baselines invalidated:** none of the current 8 or the two from `MIG-21`.
- **e2e rewrites:** none expected.

### MIG-27 — Admin
- **Files:** `pages/Admin.jsx`.
- **Replaces:** stats strip→`IxKpi`; grant form→`IxInput`/`IxButton`; Administrators/Reviewers/Most-searched/All-companies/Recent-activity tables **now use `MIG-15`'s decided pattern** (4 of Admin's tables, the largest concentration of the re-skin work on any single screen — no longer blocked, but still the biggest sub-part of this row by far).
- **Fixes:** the last four raw-`<table>` sites on the app, once re-skinned.
- **Could break:** low risk for stats/form; table parts carry `MIG-15`'s visual-risk profile fourfold, just no longer an open decision.
- **Size:** small (non-table parts) + medium (4 tables).
- **Baselines invalidated:** none of the current 8 or the two from `MIG-21`.
- **e2e rewrites:** none expected.

### MIG-28 — SignIn
- **Files:** `pages/SignIn.jsx` (or wherever it's defined).
- **Replaces:** full-bleed card + 10 CA-failure messages + correlation ID + sign-in button → `IxCard` + `IxMessageBar` per `MIG-03`'s outcome (type per failure severity — if `MIG-03` rejected the swap, this row keeps `ErrorBox` instead) + `IxButton`.
- **Fixes:** nothing broken — consistent message-severity styling across the 10 failure states instead of ad hoc text.
- **Could break:** low risk; **decided: SignIn stays outside `IxApplication`** — it has no header/menu/dock to host and a signed-out user has no shell to be inside, so none of `App.jsx`'s shell rows (`MIG-06` through `MIG-11`) touch it at all, not even indirectly.
- **Size:** small-medium.
- **Baselines invalidated:** none (SignIn isn't a captured screen, and `MIG-21` didn't add one for it).
- **e2e rewrites:** none expected — no journey test exercises the CA-failure states per `current-state-inventory.md`.

### MIG-29 — Consolidate the remaining `.pill.<Pillar>` renderers onto `PillarPill`
- **Why this exists / why it's out of number order:** `MIG-01` moved Profile's and Explore's pillar
  pills onto `IxPill` via a new `PillarPill` wrapper in `widgets.jsx`, but deliberately left the
  `.pill.Connect/.Collaborate/.Empower/.Pass` CSS class in place because four other sites still
  consume it directly and migrating them was unscoped for that row. `MIG-22` (WhatIfWeights),
  `MIG-24` (Home) and `MIG-25` (Alerts) each already touch one of those four files for other
  component swaps, but none of them mentions the pillar-pill delivery mechanism — so, left as
  written, the plan would finish with two live pillar-pill renderings side by side and no row ever
  reconciling them. This row closes that gap. Appended at the end rather than renumbered into
  sequence, per current branching convention: each row now branches off the merged main rather than
  stacking on the previous row's branch, so inserting a row mid-sequence and renumbering everything
  after it is exactly the costly, error-prone operation that convention exists to avoid.
- **Sequencing: ships BEFORE `MIG-22`/`MIG-24`/`MIG-25`, despite the higher number.** Those three
  rows each touch a file that still renders the old `.pill.*` markup — landing them first means each
  would either migrate that markup incidentally as a side effect of its own component swap, or work
  around it and leave it stranded, and this row would then have to consolidate something already
  half-changed by three different, unrelated diffs. Doing the pill swap first means `MIG-22`/`24`/`25`
  simply inherit `PillarPill` already in place at their file's pillar-pill site, with nothing left to
  collide with.
- **Files:** `ui/src/pages/Home.jsx:147`, `ui/src/pages/Alerts.jsx:57`, `ui/src/components/WhatIfWeights.jsx` (3 sites), `ui/src/components/widgets.jsx:30` (the routing-summary render of `scoring/routing.js`'s output — `scoring/routing.js` itself only computes the pillar name, it renders nothing). `ui/src/styles.css` (`.pill.Connect/.Collaborate/.Empower/.Pass` rules can only be deleted once all four are converted — `.pill.sfs`/`.pill.ghost` are a separate, non-pillar variant and stay).
- **`widgets.jsx:30` scope note:** this call site is on the browser what-if path — it renders the
  pillar `scoring/routing.js` computes for the *hypothetical* re-weighted state, not a stored run.
  Swap the rendering only (`<span className={...}>` → `<PillarPill pillar={...} />`); do not
  restructure the call site, its surrounding function, or how it's invoked from the what-if flow.
- **Replaces:** each site's `<span className={`pill ${pillar}`}>` with `<PillarPill pillar={...} />`, the same component `MIG-01` built — no new component work, just finishing the swap at the remaining call sites.
- **Fixes:** the two-renderings-of-the-same-concept drift this row exists to prevent; once done, `UI-09`'s contrast fix lives in exactly one place (`PillarPill`) instead of being duplicated across a CSS class and a component.
- **Could break:** low risk — `PillarPill` already handles the unknown-pillar fallback (bare span, no miscoloured pill) per `MIG-01`. Verify `WhatIfWeights.jsx`'s `ghost` modifier (a distinct opacity treatment for a "would-be" pillar) has an equivalent on `PillarPill`/`IxPill` before assuming a like-for-like swap — `IxPill`'s prop table has no direct `ghost` equivalent, this may need an `outline` or reduced-opacity wrapper decision made during the row, not before.
- **Size:** small.
- **Baselines invalidated:** depends on sequencing against `MIG-21` — Home's and Scoring & Fit's baselines (once `MIG-21` captures them) show a pillar pill in view, so this row is expected to invalidate whichever has landed by the time it ships; Alerts isn't captured by any baseline currently. Verify against whichever baselines actually exist when this row is picked up, don't assume the state described here still holds.
- **e2e rewrites:** none expected — no journey test asserts on `.pill` DOM structure at these four sites (only `PROF-15` did, and `MIG-01` already rewrote it).
- **Status:** proposed. Ships before `MIG-22`/`MIG-24`/`MIG-25` — see the sequencing note above.

## Notes

- **UI-02 and UI-05 overlap** with the iX token migration. Prefer doing them *as* that migration
  rather than twice — check with a human before starting either. Note that the migration (fb1568f)
  moved `tokens.css` onto iX but touched **no component**: `ix_lint` still reports the same 51
  findings, so both rows remain valid exactly as written.
- **UI-04 overstates its scope by 2x.** Only `Explore.jsx:65` (the drawer backdrop) is a real
  `<div onClick>` with no role. Lines 246–247 are lint false positives: the `<span className="fchip">`
  wraps a real `<button aria-label="Clear text filter">`, which is already labelled and keyboard
  reachable. `ix_lint.mjs:84-88` is line-based regex, so it matches any line containing both
  `onClick=` and `<span`. Fix the one real site; do not "fix" the other two.
- Every row above came from `node scripts/ix_lint.mjs` or a real test failure, not from opinion.
  Keep it that way: a finding without a `file:line` does not belong here.
- Sorting, filtering and column controls are **not** features (see `contract/feature-rubric.md`);
  if one is genuinely needed it belongs here as a UI row.
