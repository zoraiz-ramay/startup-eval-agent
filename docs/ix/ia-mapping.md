# IA mapping — Tracxn-modelled screens → iX-authoritative replacement

Phase 2 deliverable. Every component name below is verified against `docs/ix/components.md`
(the installed `@siemens/ix-react` 5.1.1 export list — zero invented names) and cited to a rule in
`docs/ix/guidance.md` where one exists. Where a mapping rests on a component's props alone (no
fetched guidance page covers it — it's on `guidance.md`'s deferred/unverified-slug list), that's
marked **[props-only, fetch JIT before building]** rather than cited as if verified usage advice
exists. Nothing here is committed to; it's the input to the migration plan below.

Screen sections follow `docs/ix/current-state-inventory.md`'s ordering exactly.

**Decided, not re-opened below:** command bar → option (b), fully custom inside the
`IxApplicationHeader` left slot (not (a) `IxExpandingSearch`, not (c) repurposing
`IxCategoryFilter`). Dense/sortable tables (Explore, Alerts, Profile's Evidence tab, 3 of Admin's 4
tables) → option (a), semantic `<table>` re-skinned entirely with iX tokens, zero iX components,
sort/sticky/column-drawer logic unchanged — not (b) `IxCardList` for the simpler tables: dense
column-wise comparison is the product, and a card list can't be scanned that way regardless of how
simple the table looks. Dark-chrome-over-light-canvas → option (b), drop it — light/iX-native
everywhere, `colorSchema='light'` globally, no per-region override. The dark-chrome seam **is** the
Tracxn look; keeping it as a "documented exception" would mean the migration changed the styling
authority on paper without changing it in the browser.

---

## App shell (`ui/src/App.jsx`)

| Current | Replacement | Verified via |
|---|---|---|
| `Shell` fragment (`TopBar`+`Rail`+`SideNav`+`<main class="content">`) | `IxApplication` as single root, `IxContent` as the content host nested inside it | components.md: `IxApplication`, `IxContent`. guidance.md "Application shell": "Use `ix-application` as the single top-level wrapper... nest the application header, application menu, and content component inside `ix-application` rather than placing them as siblings." — this directly forbids the current fixed-position-siblings structure. |
| `TopBar` (brand/logo, `CommandBar`, advanced-search icon button, tracking bell, avatar) | `IxApplicationHeader`, `companyLogo`/`appIcon` for brand, `name="ScoutGrid"`, right-aligned slot for advanced-search + tracking bell + avatar | components.md: `IxApplicationHeader` props (`companyLogo`, `appIcon`, `name`, `nameSuffix`). guidance.md "Application header": "Use the right-aligned slot for high-level info/actions... left-aligned slot for lean, compact toolbars"; "Only add the avatar slot if the application actually has user profiles/login." |
| Avatar button (`.avatar-btn`, initials, → Settings) | `IxAvatar` (`initials`, `image`, `username`, `extra`) placed in the header's avatar slot | components.md: `IxAvatar` — note `username`/`extra` "only working if avatar is part of the ix-application-header," so this only works as a header-slotted avatar, not standalone. |
| Tracking bell with unread-count badge | **No verified match.** `IxMenuItem.notifications` exists but only inside a menu, not a header action. No badge-on-icon-button primitive found in the header/feedback component groups. | Flag for Phase 3: either move "Tracking" entirely into the nav (where `IxMenuItem.notifications` works) and drop it from the header, or keep a custom badge on a plain `IxIconButton`. |
| `Rail` (Home/Explore/Views/Tracking/Ask AI button/Settings/Admin) | `IxMenu` populated with `IxMenuItem` per entry (`icon`, `label`, `href` for the routed ones) | components.md: `IxMenu`, `IxMenuItem`. This is the corrected slug from the earlier `menu`→`application-menu` miss — the *component* is `IxMenu`, its *docs page* lives at `/application-menu/guide`. |
| "Ask AI" rail button (toggles dock, not a route) | `IxMenuItem` in `IxMenu`'s bottom slot | guidance.md "Application menu": "Reserve the bottom section for settings/theme-toggle and other state-toggling or overlay-opening items only — never for navigation." Ask AI is exactly that: state-toggling, non-navigational. Clean fit. |
| "Settings" rail link (a real route, not a panel) | **Open question**, not settled here: guidance's bottom-section rule is written for *panel-opening* items (its own `IxMenuSettings`/`IxMenuAbout` sub-panels), not route navigation. Putting a routed Settings link in the bottom slot conflicts with "never for navigation" read literally; leaving it in the main nav list keeps it consistent with Home/Explore/Views/Tracking but loses the visual "utility vs. primary nav" separation the current rail has. | Two options for Phase 3, not picked: (a) main list, same tier as Home/Explore; (b) bottom slot anyway, accepting the rule's spirit (state/settings) over its letter (navigation). |
| `SideNav` (Quick access links + dynamic Saved-views list, hidden on Profile, hidden <1180px) | Fold into the same `IxMenu` as second-level items under an `IxMenuCategory` (e.g. a "Saved views" category), rather than a second fixed chrome layer | components.md: `IxMenuCategory` (`icon`, `label`, `notifications`). guidance.md: "Use icons in second-level navigation items only when they aid recognition, and never mix icon and non-icon items within the same second-level category" — implies `IxMenu` supports exactly this second-level grouping. **This collapses two chrome layers into one** — the single biggest structural change in the shell mapping, not a re-skin. |
| `AssistantDock` (fixed 332px right panel, auto-opens ≥1181px) | `IxPane` inside `IxPaneLayout`, `composition="right"`, `size` closest fixed value to 332px (`'360px'`), `variant` TBD (`'floating'` doesn't reflow content the way today's dock does via `.content` margin; `'inline'` does — closer to current behavior) | components.md: `IxPane` (`composition`, `size` enum incl. `'360px'`, `variant: 'floating'|'inline'`, `hideOnCollapse`, `isMobile`), `IxPaneLayout` (`layout`, `variant`). **[props-only, fetch JIT]** — `pane`/`pane-layout` are on guidance.md's unverified-slug list; no fetched usage rule yet. |
| `Icon.jsx` (inline-SVG repaint wrapper) | Unchanged. iX components take icon names as props and paint their own chrome; anything rendered inside a custom card/panel still needs this wrapper. Not part of the IA change. | — |

---

## `/` — Home

| Current | Replacement | Verified via |
|---|---|---|
| Stats strip (5 tiles) | `IxKpi` per tile (`label`, `value`, `unit`, `orientation`, `state`) | components.md: `IxKpi`. **[props-only, fetch JIT]** — `kpi` unverified slug. |
| Query composer panel | `IxCard` + `IxCardContent` wrapping the existing input/button | components.md: `IxCard`, `IxCardContent`. **[props-only, fetch JIT]**. |
| Quick-prompt chips | `IxChip` (`variant`, `icon`, non-`closable`) | components.md: `IxChip`. **[props-only, fetch JIT]** — `chip` unverified slug. |
| Solve results / Recent evaluations / Tracked companies / Saved views / Recent challenges panels (`.list-row` rows) | `IxCardList` wrapping `IxEventListItem` per row (`chevron`, `itemColor`, `selected`) — a closer fit than `IxActionCard` for "click a row to open something" | components.md: `IxCardList` (`listStyle`, `maxVisibleCards`, `hideShowAll`), `IxEventListItem`, `IxEventList` (`compact`, `itemHeight`). **[props-only, fetch JIT]**. |
| Challenge approve/reject buttons | `IxButton` pair, unchanged behavior | components.md: `IxButton` (generic, not itemized here since it's the one component already implicitly assumed everywhere). |

---

## `/explore` — Explore (densest screen)

| Current | Replacement | Verified via |
|---|---|---|
| Page head + stats strip | `IxContentHeader` (`headerTitle`, header-slot for the KPI tiles/active-view chip) | guidance.md "Content header": "an optional header-slot for status pills/counters." |
| Filter row (text filter + 4 pillar chips + active-filter chips + Clear all) | `IxCategoryFilter` — near 1:1: `categories` config object, `filterState`, chip rendering with per-chip clear built in, reset via `ariaLabelResetButton` | components.md: `IxCategoryFilter` (`categories`, `filterState`, `nonSelectableCategories`, `staticOperator`). **[props-only, fetch JIT]** — `category-filter` unverified slug, but the prop shape is an unusually strong match, worth calling out. |
| Toolbar (density/portfolio-weighting toggles) | `IxToggleButton`/`IxToggle` | components.md: `IxToggleButton`, `IxToggle` (both already-verified core form components, not on the deferred list). |
| Weighting panel (conditional, collapsible) | `IxBlind` (`collapsed`, `label`, `sublabel`, `variant`) | components.md: `IxBlind`. **[props-only, fetch JIT]** — `blind` unverified slug. |
| **Data grid** (sticky header + sticky first column + row select + 13-column registry + inline reorder drawer + CSV export + saved views + sort) | **No iX equivalent exists.** Confirmed by grepping all 104 `@siemens/ix-react` 5.1.1 exports in `docs/ix/components.md` — no `IxTable`, `IxBasicTable`, or any table/grid primitive of any kind. | See options below. This is the single highest-leverage open decision in the whole migration — it recurs at Alerts, Profile's Evidence tab, and three of Admin's four tables (6 sites total, one decision). |
| Skeleton / empty / error states | `IxSpinner` (loading), `IxEmptyState` (`header`, `subHeader`, `icon`, `action`), `IxMessageBar` (`type='alarm'`) **candidate, not cleared** for the error box | components.md's `IxMessageBar` prop table (`persistent`, `type`) documents no ARIA role at all — `role="alert"` is not confirmed by the docs, only by inspecting the rendered component. This matters beyond styling: `scripts/ix_lint.mjs:96-99` names `ErrorBox` as **the only sanctioned error surface** precisely so `role="alert"` is guaranteed, and flags any other `className="error-box"` site as a lint failure. Before this swap enters any row: build `IxMessageBar`, inspect its rendered DOM for `role="alert"`, and if present, update `ix_lint.mjs`'s rule to sanction `IxMessageBar` instead of (or alongside) `ErrorBox`. If `IxMessageBar` does not emit `role="alert"`, keep `ErrorBox` and do not swap it — a visually-consistent error surface that silently drops screen-reader announcement is a regression, not a migration. |
| Column drawer (right overlay, reorder ↑/↓, add/remove, restore defaults, save view) | `IxPane` (`variant='floating'`, `composition='right'`, `closeOnClickOutside`) as the overlay container; reorder controls stay custom (no drag/sort component exists in the list) | components.md: `IxPane`. **[props-only, fetch JIT]**. |

### No iX equivalent — decided

**1. Ctrl+K command bar with slash commands** (`App.jsx:23-85`, `CommandBar`) — **decided: (b)**,
fully custom code inside `IxApplicationHeader`'s left slot. iX explicitly allows custom content in
header slots, so this doesn't fight the shell — it just isn't "an iX component." `IxExpandingSearch`
(option a) was rejected because it has no slash-command routing; repurposing `IxCategoryFilter`
(option c) was rejected as an awkward reuse of a filter component for navigation.

**2. Dense, sortable, sticky-column, customisable data table** (Explore, Alerts, Profile's Evidence
tab, 3 of Admin's 4 tables) — **decided: (a)**, semantic HTML `<table>` styled entirely with iX
tokens (`--theme-color-*`, elevation tokens), zero iX components — sort/sticky/column-drawer logic
unchanged, only re-skinned. `IxCardList`+`IxEventListItem` (option b) was rejected even for the
"simpler" tables: dense column-wise comparison is the product across all these screens, and a card
list can't be scanned that way regardless of how few columns a given table happens to have — this
is not a case where two different problems happen to share a `<table>`.

**3. Dark chrome over a light canvas** — **decided: (b)**, drop it. Rail/menu/header go light like
the rest of the app; `IxApplication`'s `colorSchema` applies globally, `'light'` everywhere, no
per-region override. Keeping the seam as a "documented exception" (option a) was rejected: the
dark-chrome-over-light seam **is** the Tracxn look this migration exists to retire, not a neutral
detail that survives it. Running the whole app in dark schema (option c) was never a live option —
listed originally only for completeness.

---

## `/startup/:id` — Profile (most complex screen)

| Current | Replacement | Verified via |
|---|---|---|
| Profile head (logo chip, name+pillar pill, summary, meta row, tag chips, action row) | `IxContentHeader` (`hasBackButton`, `headerTitle`, `headerSubtitle`, header-slot for pillar pill/tags, right-side action buttons) | guidance.md "Content header": back button/title/subtitle/header-slot/action-buttons is a near-literal match for this region's current field list. |
| Pillar pill(s) (Connect/Collaborate/Empower/Pass) | `IxPill` `variant='custom'` + `background`/`pillColor` (none of iX's 7 semantic variants map 1:1 to the 4-way pillar vocabulary) | components.md: `IxPill` (`variant` enum, `background`, `pillColor` — the two props exist specifically for a case exactly like this one). Ties directly to current-state-inventory §4's flagged "pillar ramp has no iX anchor" — this is the *mechanism*, not a resolution of whether the 4 literal colors themselves should change (they don't, in this mapping). |
| Pipeline ribbon (7 steps, Input→Route) | **Not a re-skin — delete it.** Verified against `Profile.jsx:613-618`: every step unconditionally renders `className="step done"` regardless of the run's actual state, and this render path only exists after the run has finished (`Profile.jsx:561`'s earlier `!res` branch shows a generic skeleton, not per-step progress — there is no streaming-progress code anywhere in this component). A ribbon where all 7 steps are always "done" conveys zero information on every render it's ever shown in; re-skinning it onto `IxWorkflowSteps` would ship a correctly-styled version of a widget that has never done anything. `IxWorkflowSteps`/`IxWorkflowStep` (`status`: open/success/done/warning/error) is the right component **for a streaming run** — the "running Input → Enrich → …" copy at `Profile.jsx:23` describes exactly that state, which today only exists as static text, not a rendered step sequence. If a real streaming-progress view is ever built for an in-flight evaluation, `IxWorkflowStep`'s per-step `status` is the component for it then. | components.md: `IxWorkflowSteps`/`IxWorkflowStep` remain a correct match for a genuine step-status use — this row is about deleting dead decoration, not about the component being wrong. |
| Tab bar (Overview/Scoring & Fit/Market & Risk/Evidence/Ask, sticky, `?tab=`-synced) | `IxTabs` + `IxTabItem` (`activeTabKey`, `tabKey`, `keyboardNavigation`, `layout`, `placement`) | components.md: direct match — `tabKey` maps onto the existing `?tab=` query value with no semantic change. |
| Metric row (6 tiles) | `IxKpi` | Same as Home's stats strip. |
| Executive summary panel (Spec rows: HQ/stage/business model/funding/website/LinkedIn/parent group) | `IxKeyValueList` + `IxKeyValue` (`label`, `value`, `icon`, `labelPosition`) | components.md: `IxKeyValueList`/`IxKeyValue` — direct structural match for the existing `.spec .k/.v` pattern. **[props-only, fetch JIT]** — `key-value`/`key-value-list` unverified slugs. |
| HeadcountTrend panel, Radar chart | Stay fully custom (SVG) — no chart primitive exists in the component list — wrapped in `IxCard` for surface/elevation consistency only | components.md has no chart component in any group. |
| Team & ecosystem / Reference customers / Recent signals panels | `IxCard` + `IxCardContent`; self-asserted "claimed" programs need a decision on which primitive carries the trust distinction | **Open question, not picked:** `IxChip` with a distinct `variant` for claimed-vs-corroborated, vs. `IxPill variant='neutral'` with literal text, vs. keeping the current custom "claimed" badge unstyled by either. No guidance page covers a verification/trust marker specifically. |
| Score breakdown (`ScoreBar` per dimension) | **Not `IxProgressIndicator` — rejected.** `IxProgressIndicator`'s `role="progressbar"` semantics mean *task completion*; a score of 62 is not 62% done toward something, and reusing a completion widget for a static score misrepresents what the number means. **Decided: two options, not further narrowed here** — (a) keep `ScoreBar` custom but correct its role to `role="meter"` (the correct ARIA pattern for "a fixed-range measurement," which is what a score actually is), or (b) `IxKpi` (`value`, `label`, `state`), which already avoids the completion framing entirely. | components.md (`IxProgressIndicator`'s `type`/`value`/`max` props are real, but the component's semantic contract is wrong for this use, not just its styling) |
| `WhatIfWeights` collapsible panel | `IxBlind` wrapping the panel | Same as Explore's weighting panel — same **[props-only, fetch JIT]** caveat. |
| `WeightSliders` (6 range inputs) | `IxSlider` (single 0-100 value per dimension) — not `IxRangeField`, which is for range *pairs*, not a single value | components.md: `IxSlider` vs `IxRangeField` — verified the two are different components before picking; `IxSlider`'s prop shape (single value) is the correct one for this. |
| Routing rationale / Red flags & gaps / `OverridePanel` | `IxCard`s; gate pass/fail rows → `IxMessageBar` (`type` mapped to alarm/warning/success/info per gate severity); reviewer decision form → `IxSelect`/`IxTextarea`/`IxButton` (all already-verified core form components); audit history → `IxEventList`/`IxEventListItem` | components.md, all core/verified components except `IxMessageBar`'s exact role semantics (flagged above under Explore's error box). |
| Evidence tab (locally-defined filterable fact table) | Same no-table-primitive gap as Explore's grid — **do not solve twice**, this is the same open decision applied a second time | See "No iX equivalent" options above. |
| Ask tab (chat transcript, prompt chips, input bar) | Prompt chips → `IxChip`; input bar → `IxInput` + `IxIconButton` (send); transcript itself has no "chat message" component in the list — stays custom, wrapped in `IxCard`/`IxCardList` | components.md: no chat/message-thread component in any group. |
| Loading state (`SkeletonProfile`) | `IxSpinner` + text; no dedicated skeleton-loader component exists (no `IxSkeleton`), so the 2-block placeholder shapes stay custom | components.md has no skeleton-loader component. |
| Error state | `IxEmptyState` | Same as Explore. |

---

## `/saved`, `/alerts`, `/ask`, `/settings`, `/admin`, `/signin`

| Screen | Region | Replacement | Verified via |
|---|---|---|---|
| Saved | List of saved views | `IxCardList` + `IxEventListItem`; **open question:** `IxEventListItem` has no documented trailing-action-button slot in its prop list, so the per-row delete button needs either a custom row wrapper or `IxActionCard`'s icon+chevron combo instead — not resolved here. | components.md |
| Saved | Empty state | `IxEmptyState` | components.md |
| Alerts | Watchlist table | Same no-table-primitive gap as Explore (site 2 of 6) | — |
| Alerts | Empty state | `IxEmptyState` | components.md |
| Ask AI | Static explainer panel | `IxEmptyState` or `IxCard`+`IxTypography`; the page's actual behavior (force `dockOpen=true` on mount) is unaffected by the component swap | components.md |
| Settings | Account panel (name/email/stub warning/sign-out) | `IxKeyValueList`/`IxKeyValue` | Same as Profile's Spec panel |
| Settings | Backend status rows (label + status dot + value) | **Open question, not picked:** `IxKpi`'s `state` enum (neutral/warning/alarm) is a real fit for "status dot + value," but `IxEventListItem`'s `itemColor` is also a plausible fit for a labelled status row — no guidance page covers either specifically. | components.md |
| Admin | Forbidden state | `IxEmptyState` | components.md |
| Admin | Administrators panel table, Reviewers table, Most-searched table, All-companies table, Recent-activity table | Same no-table-primitive gap as Explore (sites 3-6 of 6 — four separate tables on one screen, all one decision) | — |
| Admin | Grant form, stats strip | `IxInput`+`IxButton`; `IxKpi` | components.md |
| SignIn | Full-bleed card, 10 CA-failure messages, correlation ID, sign-in button | `IxCard` + `IxMessageBar` (`type` per failure severity, same not-cleared caveat as above) + `IxButton`. **Decided: SignIn stays outside `IxApplication`**, as a documented exception to guidance's "single top-level wrapper for the whole app" rule — it has no header/menu/dock to host, and a signed-out user has no application shell to be inside. | components.md; the exception itself, not the components, deviates from guidance.md "Application shell." |

---

## Summary of undecided items carried into Phase 3

Resolved this round: command bar (→ custom in header slot), dense/sortable tables (→ semantic
`<table>` + tokens), dark chrome (→ dropped, light everywhere), ScoreBar (→ `role="meter"` or
`IxKpi`, not further narrowed), pipeline ribbon (→ delete, don't re-skin), SignIn/`IxApplication`
(→ stays outside, documented exception). Still open:

1. Tracking bell badge placement (header action vs. moved into nav).
2. Settings: main-nav item vs. `IxMenu` bottom slot.
3. AssistantDock's `IxPane` variant (`floating` vs `inline`) and exact `size`.
4. `ScoreBar`'s exact replacement — `role="meter"` custom bar vs. `IxKpi` (both cleared of the
   `IxProgressIndicator` mistake; neither picked over the other).
5. `IxMessageBar`'s `role="alert"` status — unverified against the built component; may mean
   `ErrorBox` doesn't move at all, pending that check and an `ix_lint.mjs` update either way.
6. "Claimed" program trust-marker primitive (`IxChip` vs `IxPill` vs custom).
7. Settings status-row primitive (`IxKpi` vs `IxEventListItem`).
8. Saved-view row's trailing delete action (no verified `IxEventListItem` slot for it).

None of these block starting the migration plan below — they block specific rows, which are marked
accordingly.
