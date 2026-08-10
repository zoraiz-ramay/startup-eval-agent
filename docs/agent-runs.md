# Agent run log

Append-only record of what the agent cycles actually did. Newest run first.

Written at the end of every cycle so an unattended loop leaves a reviewable trail — the previous
agent system ran 59 cycles and left nothing anyone could reconstruct, which is why it was deleted
wholesale rather than untangled.

**One entry per cycle.** Each records the agent flow, the commit, the gate results, and anything
left for a human. A cycle that produced nothing still gets an entry saying so — "no worthwhile
finding" is a real outcome and hiding it makes the log a highlight reel.

## The two flows

```
/ui-improve                          /feature-cycle
───────────                          ──────────────
ui-auditor      (read-only)          feature-scout    (read-only, no write access)
    ↓ returns ranked rows                ↓ returns scored proposals
[caller records to ui-backlog.md]    [caller records to feature-proposals.md]
    ↓                                    ↓
HUMAN picks one                      HUMAN sets Status: approved
    ↓                                    ↓
ui-implementer  (one row only)       feature-builder  (engine + API + pytest, never ui/)
    ↓                                    ↓
scripts/gates.sh                     ui-integrator    (states placement plan, then codes)
    ↓                                    ↓
pr-author       (branch + PR)        scripts/gates.sh
                                         ↓
                                     pr-author        (branch + PR)
```

Both auditing roles have **no write access** by design: an auditor that can edit the code it audits
can make its own findings true, and its report stops being independent evidence.

`pr-author` never pushes to `main` and never merges. A human merges, always.

## Human-owned, never an agent

- `ui/e2e/__screenshots__/` — visual baselines. An agent that can regenerate a baseline can prove
  any layout change was safe.
- `contract/feature-inventory.md` — the behaviour contract. Scope comes from a human.
- `Status: approved` in `contract/feature-proposals.md`.

---

## 2026-08-11 · UI-01 · provenance badge accessible names

**Flow**: caller-directed single-item implementation (no ui-auditor re-run this cycle; the row was
handed over directly, already flagged as higher priority since UI-06 gave the Overview tab a
second `WebSourced` badge with the same accessible name).

**Selected**: UI-01 (`high`) — the provenance badge's accessible name was the literal string "web"
regardless of which field it sourced. After UI-06, Employees and Founded sit adjacent in the same
metric row, so a screen reader announced "web", "web" with no way to tell them apart. `title` is
not exposed as the accessible name (link text wins), which was the actual bug.

**Changed**
- `ui/src/pages/Profile.jsx` — `WebSourced` now takes a `field` prop and, on the linked branch,
  sets `aria-label={`web — ${field} source`}`. Visible text stays the literal word "web" per the
  design constraint (dense Tracxn canvas, no room to grow the label) and per WCAG 2.5.3 Label in
  Name — the accessible name still starts with the visible word, so speech-input users saying
  "click web" keep matching. All three call sites updated: Employees (`field="employees"`),
  Founded (`field="founded year"`), Funding (`field="funding"`).
- The non-link branch (`<span className="chip">`, no URL captured) got **no aria-label**. Decision:
  it renders no role and is never in the tab order, so it isn't a "control" a screen reader
  presents as actionable — giving it an accessible name would announce affordance that doesn't
  exist. Its visible "web" text plus the `title` tooltip already say everything a sighted user
  gets; there is no interaction to name.
- `ui/src/pages/Profile.test.jsx` — updated the two existing tests that queried
  `getByRole("link", { name: /^web$/i })` (now field-specific), and added one new test that
  renders Employees and Founded sourced simultaneously and asserts they resolve to two distinct
  links by accessible name — the case a single-badge test would miss.
- `ui/e2e/journeys.spec.js` — the PROF-02/X-01 journey queried the same generic `/^web$/i` link
  name; updated to the new field-specific name (`web — founded year source`), matching the
  `founded_year` fixture it actually exercises.
- `contract/ui-backlog.md` — UI-01 → `done`.
- `docs/ui-inventory.json` — regenerated.

**Verified independently of the agent's report**: reverted the `Profile.jsx` change with the new
tests in place — the added disambiguation test and both updated tests failed (couldn't find a link
named `web — employees source` / `web — founded year source`, since both badges were still named
plain "web"). Restored — all pass.

**Gates**: pytest 190 passed · vitest 17 passed (16 pre-existing + 1 new) · ix_lint no new findings
(51 known, unchanged) · ui inventory current · e2e 54 passed, 2 failed — `explore-mobile.png`
(7617px diff) and `profile-mobile.png` (12534px diff), the same two mobile baselines already
failing at HEAD before this change (inherited from the iX migration, unchanged pixel counts from
the prior cycle's log). No new visual diff caused by this change.

**Left for a human**: the two mobile visual baselines remain unresolved from the iX migration —
not touched here per the harness rule against re-baselining. Also worth a second look: I chose the
suffix "source" in the accessible name (e.g. "web — employees source") for readability; a human
reviewing screen-reader output first-hand may prefer a shorter form.

---

## 2026-08-11 · UI-06 · employees provenance badge

**Flow**: `/ui-improve` → ui-implementer → gates. Audit skipped: the backlog had been audited
hours earlier in the same session and still had ten `proposed` rows, so re-running ui-auditor would
have re-derived a fresh list rather than draining the one that existed.

**Selected**: UI-06 (`high`) — chosen by the model, not a human. The operator enabled full-auto
self-selection for this loop. Picked over UI-01 and UI-02, also `high`, because it is the row that
touches the product's one rule: a number that *is* web-researched was rendering with no provenance
badge, two lines above Founded which had one, so a reviewer could not tell which figures were
sourced.

**Changed**
- `ui/src/pages/Profile.jsx` — Employees metric now renders `<WebSourced src={psrc.employees_count} />`,
  mirroring how Founded renders its own. Reused the existing component rather than adding a second
  provenance idiom.
- `ui/src/pages/Profile.test.jsx` — two tests, both directions: badge present when
  `profile_sources.employees_count` exists, absent when it does not.
- `contract/ui-backlog.md` — UI-06 → `done`.
- `docs/ui-inventory.json` — regenerated.

`WebSourced` already returns `null` on a falsy `src`, so the badge cannot appear on an unsourced
number. That direction is the one that matters: a provenance badge on an unevidenced figure asserts
evidence that does not exist, which is worse than no badge at all.

**Verified independently of the agent's report**: reverted `Profile.jsx`, re-ran the suite — 1
failed. Restored — 16 passed. The test bites.

**Gates**: pytest 190 · vitest 16 · ix_lint no new findings (51 known) · inventory current ·
e2e 2 failed, the same two mobile baselines inherited from the iX migration at unchanged pixel
counts. No new visual diff.

**Left for a human**: nothing new from this cycle.

---

## 2026-08-10 · PROF-12 · headcount trend

**Flow**: `/feature-cycle` → feature-scout → *human approved* → feature-builder → ui-integrator →
gates. Commits `de5c2df`, `14a31ba`.

**Scout** verified the rubric's three named candidates and found **two of the three were stale** —
`route_scorecards` already renders at `Profile.jsx:228-231`, and `search_stats.timed_out` already
surfaces via `core/pipeline.py:177-180`. Only `employees_over_time` was genuinely unexposed. It
proposed one feature rather than three, and the rubric was corrected in `c28715f` so the next scout
does not propose shipped work.

**Builder** found the backend already complete — the series reached the API intact and survived
persistence. It wrote characterisation tests instead of inventing engine work. Verified they bite:
mutating `save_run` to drop the field failed 3 of them.

**Integrator** placed the panel on the Overview tab under Executive summary, not in Scoring & Fit —
filing it under scoring would imply it feeds `final_score`, and `core/score.py` has no headcount
term. Each year carries its own `ExtLink` labelled `source (2021)` rather than a repeated generic
"source".

**Gates**: pytest 190 · vitest 14 · ix_lint clean · e2e 50 passed, 2 failed (inherited).

**Finding raised — UI-11**: the desktop/laptop/tablet baselines **passed with an entire new panel
present**. A white panel on the near-white canvas falls under Playwright's per-pixel colour
threshold, so only its border and heading text count, staying under `maxDiffPixelRatio: 0.02`. The
baselines catch geometry and reflow but not low-contrast additions. Caught only because the pixel
counts came back byte-identical, which should not happen when a panel is added.

**Left for a human**: `PROF-12` row in `contract/feature-inventory.md`.

---

## 2026-08-10 · UI-09 · pillar pill contrast

**Flow**: `/ui-improve` → ui-auditor → *human picked* → ui-implementer → gates. Commit `d44d72c`.

The auditor found a contrast regression introduced by the iX migration earlier the same session:
`--pillar-pass` had been mapped onto `--theme-color-weak-text`, an iX token meant for de-emphasised
text on the page background, not a label on a filled pill.

Auditing all four pills rather than the two the row named turned up a third failure.

```
Connect      4.13 -> 5.80    was failing, not in the original row
Collaborate  3.11 -> 5.64
Pass         2.69 -> 5.16
Empower      4.98 -> 4.98    already passing, left alone
```

The test measures what the browser actually painted — composites the ancestor background chain and
text alpha, then computes the WCAG ratio — so it survives a theme swap and cannot be satisfied by a
literal in a comment.

**Gates**: pytest 181 · vitest 12 · ix_lint clean · e2e 46 passed, 2 failed (inherited).

---

## 2026-08-10 · iX token migration

**Flow**: manual, not an agent cycle. Commit `fb1568f`.

`tokens.css` moved onto Siemens iX. Token names unchanged, so no component was touched.

The work was in what iX brought along uninvited: a Bootstrap-style reset whose `body` rule
outranks `:root`, silently adopting metrics sized for touch panels at ~2px per table row, and an
`h1`–`h6` rule that put every heading in Arial beside Segoe UI body text. Both countered
explicitly. That reset also names Siemens Sans, which had quietly defeated the precaution
`tokens.css` already documented — the font is licensed and not bundled, so any machine with it
installed would render different screenshots and the visual gate would stop meaning anything.

**Left for a human**: two mobile baselines (`explore-mobile.png` 7617px, `profile-mobile.png`
12534px). The diff is the intended colour change plus form controls now inheriting the app font
instead of the browser's Arial default. Still unresolved — every cycle since has inherited them,
and `pr-author` refuses to package while gates are red.
