# Feature value rubric

The bar a proposal must clear before anyone writes code. It exists because the previous agent
system had no bar and shipped things like **`company-name-sort-accessibility`** — a sort control,
counted as a feature, across 59 cycles.

`feature-scout` scores every proposal here and **auto-rejects** anything that fails a gate. A human
approves the survivors before implementation starts.

---

## Hard gates — fail any one and the proposal is rejected

| # | Gate | Why |
|---|---|---|
| G1 | **Changes a decision.** A Siemens reviewer would route, prioritise or reject a startup differently because of it. | If the decision is identical either way, it is decoration. |
| G2 | **Cites its evidence.** Names the backend field, API response key, or user journey it serves, with a `file:line`. | Stops invented features and invented justifications. |
| G3 | **Not a control or a restyle.** Sorting, filtering, toggling, spacing, colour and copy tweaks are UI backlog items, not features. | This is the exact trap the old system fell into. |
| G4 | **Preserves provenance.** Any new fact displayed carries a source, or renders "—". | The product's one rule (see CLAUDE.md). |
| G5 | **Fits the Tracxn information architecture.** Extends the icon rail / command bar / dense data canvas rather than introducing a new paradigm. | The layout is deliberate and not up for redesign. |

## Scored dimensions — 2 points each, **≥ 7 of 10 required**

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| **Decision impact** | cosmetic | adds context | changes the routing call |
| **Evidence readiness** | needs new data source | needs new engine work | **data already computed, just unexposed** |
| **Reviewer frequency** | rare edge case | occasional | every evaluation |
| **Trust/defensibility** | neutral | some | makes a claim auditable |
| **Cost to build** | multi-week | several days | ≤ 1–2 days behind the gates |

## Where the strongest candidates already are

The engine computes evidence today that the UI never shows. These score highly on *evidence
readiness* because the hard part is done — verified against the current source:

| Data | Computed in | Shown? | Why it matters |
|---|---|---|---|
| `employees_over_time` | `core/profile.py::_employee_history` | **no** | Evidence-cited headcount series, every point carrying a source URL. Growth trajectory is a routing signal, and the series is discarded today. |
| `route_scorecards` | `core/score.py` | **partly** | Already reaches the UI: `core/route.py:57-67` turns it into `routing.route_recommendations`, rendered at `ui/src/pages/Profile.jsx:228-231`. Only *eligible* routes are included (`route.py:24-34`), so a Pass-routed startup still sees zero or one card. Narrow completion gap, not a fresh feature. |
| `search_stats` (`timed_out`) | `core/enrich.py` | **yes** | Already surfaced: `core/pipeline.py:177-180` appends `"· N/M web queries timed out"` to `engine`, rendered at `ui/src/pages/Profile.jsx:520`. Under-emphasised (muted text, absent from Explore where many companies are scanned) — a presentation fix for `contract/ui-backlog.md`, not a feature. |

Anything scoring ≥ 7 that is *not* in this table needs a stronger `G2` citation, because the
cheapest real value in this product is currently sitting unexposed.

**Verify this table against source before citing it.** Two of its three rows were stale by the
first scouting run (2026-08-10) — they described work that had since shipped. A scout that trusts
the table blindly proposes something already built, which is exactly the churn this rubric exists
to prevent. Re-check and correct it as part of scouting; the correction is worth more than the
proposal.

## Rejected patterns (do not re-propose)

- A sort, filter or column control of any kind — that is `contract/ui-backlog.md`.
- "Export to CSV/PDF" without a named reviewer workflow that needs it.
- Dashboards of counts that do not change a decision.
- Anything requiring a paid data source (the engine is deliberately free-tier).
- Re-skinning that the iX token migration will handle anyway.

## Output format

`feature-scout` writes proposals to `contract/feature-proposals.md`:

```markdown
## <name>
- **Gates**: G1 ✓ · G2 ✓ (core/profile.py:640) · G3 ✓ · G4 ✓ · G5 ✓
- **Score**: 9/10 (impact 2, readiness 2, frequency 2, trust 2, cost 1)
- **Problem**: the reviewer decision it changes, in one sentence
- **Evidence**: the field/journey, cited
- **Sketch**: where it lands in the Tracxn layout
- **Contract rows**: new IDs to add to feature-inventory.md
- **Status**: proposed | approved | rejected — <who/when>
```

Nothing is built until `Status: approved` is set by a human.
