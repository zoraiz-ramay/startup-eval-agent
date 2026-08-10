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
| UI-08 | Five orphaned page stubs ("Superseded by the enterprise redesign") remain in `ui/src/pages/`: Dashboard, Evaluate, Challenges, Solve, RunDetail. Nothing imports them; they inflate `docs/ui-inventory.json` and give agents dead surface to reason about. | `ui/src/pages/{Dashboard,Evaluate,Challenges,Solve,RunDetail}.jsx` | med | — | proposed |
| UI-09 | The iX token migration (fb1568f) dropped text contrast on two of the four pillar pills — the control that displays the routing decision. `.pill.Pass` resolves to `rgba(0,10,20,.4)` on `#f0f2f5` = **2.69:1**; `.pill.Collaborate` resolves to `#009999` on `#e7f4f8` = **3.11:1**. 11px bold text needs 4.5:1 (AA). Pre-migration: 4.22:1 and 4.77:1 — a measured regression, not inherited debt. Root cause is `--theme-color-weak-text`, an iX token intended for de-emphasised text on the page background, used as a label colour on a filled pill. | `ui/src/styles.css:178,180` resolving `ui/src/tokens.css:60,63` | high | X-06 | done |
| UI-11 | The visual gate does not notice a whole new panel. Adding the PROF-12 "Headcount trend" panel to the Overview tab left `profile-desktop/laptop/tablet.png` **passing** — a white panel on the near-white canvas falls under Playwright's per-pixel colour threshold, so only its thin border and heading text count, staying below `maxDiffPixelRatio: 0.02` (`ui/playwright.config.js:27`). The baselines catch geometry shifts and text reflow, but not low-contrast additions or removals — so "the Tracxn layout still works" is a weaker guarantee than it reads. Consider a structural assertion (panel count / DOM shape per tab) alongside the pixel diff. | `ui/playwright.config.js:24-30`, `ui/e2e/journeys.spec.js:215-221` | med | X-05 | proposed |
| UI-10 | Four components are imported by nothing: `pages/EvidenceTab.jsx`, `components/{ClaimEvidenceMatrix,FitScoreHistogram,ScoreBar}.jsx` (Profile.jsx defines its own local `EvidenceTab` and takes `ScoreBar` from `widgets.jsx`). They carry 17 of the 51 `ix_lint` findings, so a third of UI-02/UI-05's effort would be spent on code no user renders. `EvidenceTab.jsx` additionally calls `useState`/`useMemo` after two conditional early returns — a Rules-of-Hooks violation that would throw if it were ever wired up. | `ui/src/pages/EvidenceTab.jsx:44-57` and three component files | med | — | proposed |
| UI-12 | Eight primary-navigation controls across five files are `onClick` on a non-interactive element with no `role`, `tabIndex` or key handler, and — unlike Explore's row click, which offers a real `aria-label="Open …"` button as the keyboard path (`Explore.jsx:334-335`) — none has any keyboard equivalent at all: Home's recent-evaluations, tracked-companies and saved-views rows; Saved's view row; Alerts' table row; and the SideNav saved-views item and page logo, both in the persistent shell on every page. The primary action on those pages (open a company) is unreachable without a mouse. | `ui/src/pages/Home.jsx:139-140,160-161,174-175` · `ui/src/pages/Saved.jsx:23-25` · `ui/src/pages/Alerts.jsx:50` · `ui/src/App.jsx:85,146-148` | high | X-04 | proposed |
| UI-13 | Explore's column-sort headers (`<th onClick>`, both the pinned company column and every configured column) have no keyboard path — no `tabIndex`, no Enter/Space handler. Sorting is mouse-only. | `ui/src/pages/Explore.jsx:293,297-303` | med | X-04 | proposed |
| UI-14 | The column drawer gained a keyboard entry and exit (UI-04) but no focus **trap**: no `role="dialog"`/`aria-modal`, so Tab from the last control moves focus behind the 28%-opacity mask onto dimmed content the panel visually implies is unreachable. `Explore.test.jsx:78-93` covers open-focus and Escape-return but never Tab-cycling, so the gap is untested as well as unfixed. | `ui/src/pages/Explore.jsx:41-115`, `ui/src/styles.css:272-277` | med | X-04 | proposed |
| UI-15 | `ix_lint`'s `a11y/clickable-non-interactive` rule has three independent blind spots in five lines, so its finding count understates real debt: it matches `onClick=` and `<div\|span` **on the same source line** only (missing four sites where `onClick` sits on the next line), checks `div`/`span` but never `tr`/`th` (missing UI-12's Alerts row and all of UI-13), and treats any `role=` as sufficient without checking tabbability (missing `App.jsx:85`, a `role="link"` with no `tabIndex`). Fixing the linter is higher leverage than patching the sites it happens to catch — UI-04 already established it produces false positives too, so it is wrong in both directions. | `scripts/ix_lint.mjs:84-88` | high | X-04 | proposed |

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
