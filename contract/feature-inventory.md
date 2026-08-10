# Behaviour contract

Every user-visible behaviour that must keep working. This is what **"no feature was changed"** is
measured against — not an opinion, not a diff review. Each entry maps to a test, and the ID is
cited in that test's name so a failure names the broken behaviour directly.

Derived from the source (`ui/src/`), not from memory. When a behaviour genuinely changes, this file
and its test change **in the same commit**, and the reason goes in the commit message.

Legend: **L** = Vitest component test · **E** = Playwright E2E · **V** = visual baseline

---

## Shell — `ui/src/App.jsx`

| ID | Behaviour | Layer |
|---|---|---|
| SHELL-01 | Icon rail lists Home, Explore, Saved, Alerts, Ask, Settings; the active route is marked | L, V |
| SHELL-02 | Command bar is focusable with **Ctrl/Cmd-K** from anywhere | L, E |
| SHELL-03 | Typing ≥1 char queries `/api/search` (debounced ~350 ms) and shows suggestions | L |
| SHELL-04 | Enter on a query navigates to `/startup/new?name=…` | L, E |
| SHELL-05 | `/solve` and `/explore` command prefixes route to Home-compose and Explore | L |
| SHELL-06 | Suggestions dismiss on blur without swallowing the click on a suggestion | L |
| SHELL-07 | Assistant dock is reachable and dismissible | L |

## Home — `ui/src/pages/Home.jsx`

| ID | Behaviour | Layer |
|---|---|---|
| HOME-01 | Problem box: Enter or the button submits; disabled under 3 characters or while solving | L |
| HOME-02 | Example chips populate the box and submit | L |
| HOME-03 | Solve results list candidate companies; clicking one opens its profile | E |
| HOME-04 | Recent runs list navigates to `/startup/:id` | L, E |
| HOME-05 | Saved views navigate to `/explore?view=…` | L |
| HOME-06 | Challenges can be approved/rejected; the row reflects the new status | L |
| HOME-07 | Loading, empty and error states are all visible and distinguishable | L, V |

## Explore — `ui/src/pages/Explore.jsx`

| ID | Behaviour | Layer |
|---|---|---|
| EXP-01 | Table renders companies with the configured columns | L, V |
| EXP-02 | Column drawer opens from "Customise columns" | L |
| EXP-03 | Columns can be added, removed and reordered (↑/↓), each with an accessible name | L |
| EXP-04 | "Restore defaults" returns the default column set | L |
| EXP-05 | A named view can be saved and reappears on Home | L, E |
| EXP-06 | Select-all toggles every row; individual selection persists | L |
| EXP-07 | Density toggle switches compact/comfortable via the `density` URL param | L |
| EXP-08 | Drawer closes on **Escape** and on mask click | L |
| EXP-09 | Filters/params survive a reload (URL is the state) | E |

## Profile — `ui/src/pages/Profile.jsx`

| ID | Behaviour | Layer |
|---|---|---|
| PROF-01 | Header shows company, score, pillar, and the spec grid (HQ, founded, employees, funding) | L, V |
| PROF-02 | A web-sourced field shows its provenance badge linking to the real source URL | L |
| PROF-03 | A field with no evidence renders "—" and never a guess | L |
| PROF-04 | Tabs switch between Overview / Evidence / Ask without losing run context | L, E |
| PROF-05 | Ecosystem lists programs; self-asserted ones are labelled company-claimed | L |
| PROF-06 | Evidence tab filters by text via the labelled filter input | L |
| PROF-07 | Ask tab: suggestion chips and Enter both submit; answer renders with sources | L, E |
| PROF-08 | "Override routing…" requires a reason, records the override, and shows it in audit | L, E |
| PROF-09 | "Refresh data" re-evaluates with `refresh: true` and disables while running | L |
| PROF-10 | "Back to Explore" returns to `/explore` | L |
| PROF-11 | Long evaluations show a loading state, not a blank page | L, V |

## Saved · Alerts · Ask · Settings

| ID | Behaviour | Layer |
|---|---|---|
| MISC-01 | Saved lists saved runs/views and opens them | L |
| MISC-02 | Alerts renders its list with empty state | L |
| MISC-03 | Ask page answers a standalone question | E |
| MISC-04 | Settings renders and reflects backend health | L |

## Cross-cutting — these are the product, not decoration

| ID | Behaviour | Layer |
|---|---|---|
| X-01 | **Provenance**: any fact sourced from the web carries a resolvable link; a non-URL source renders no link | L |
| X-02 | **No fabrication**: absent data renders "—"; the UI never substitutes a plausible value | L |
| X-03 | Every data view has a distinct loading, empty and error state | L, V |
| X-04 | Keyboard: all interactive controls reachable by Tab, visible focus ring | L, E |
| X-05 | Layout holds at 1920 / 1440 / 1024 / 390 px with no horizontal body scroll | V |
| X-06 | Tracxn information architecture intact: icon rail + top command bar + dense data canvas | V |

---

## Rules

1. **A red contract test blocks the change.** No exceptions for "the test is outdated" — if it is
   outdated, update this file and the test deliberately, in the same commit.
2. **Agents may not edit this file.** Scope changes come from a human-approved spec.
3. **Visual baselines are the evidence for V rows.** Agents may not regenerate them
   (`ui/e2e/__screenshots__/`); a human runs `--update-snapshots` after reviewing the intent.
4. **Never assert on source text.** `assert "sticky-header" in file` proves nothing and rots — the
   previous agent system left three such tests failing for months. Render it and assert behaviour.
