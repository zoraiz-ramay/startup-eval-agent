# Feature proposals

Scored against `contract/feature-rubric.md`. `feature-scout` writes nothing here — it has no write
access, deliberately, because a scout that can record its own proposals is one step from a system
that approves its own work. The caller pastes its output; a **human** sets `Status: approved`.

Nothing is built from a row that reads `proposed`. `feature-builder` is instructed to refuse.

A `rejected` row stays here forever with its reason, so the same idea is not re-litigated. That
record is what the previous agent system lacked across 59 cycles.

---

## profile-headcount-trend

- **Gates**: G1 ✓ · G2 ✓ (core/profile.py:814-847, :920; core/pipeline.py:154,196) · G3 ✓ · G4 ✓ · G5 ✓
- **Score**: 8/10 (impact 1, readiness 2, frequency 1, trust 2, cost 2)
- **Problem**: The engine researches a source-cited headcount-over-time series for every web-enabled
  evaluation, but the Profile page shows only a single current-headcount number
  (`ui/src/pages/Profile.jsx:55`, `dp.employees`). Traction is the highest-weighted scoring
  dimension (28%, `Profile.jsx:11`) yet `score_startup` never uses employee count at all
  (`core/score.py:50-119` has no headcount term) — the growth trajectory that would tell a reviewer
  "3 to 60 employees in 18 months" vs. "flat at 5" is computed and then discarded, leaving that
  judgment entirely to a single static number. A reviewer weighing a borderline Connect/Collaborate
  call, or deciding whether to override a Pass, currently has no way to see momentum — only a
  snapshot.
- **Evidence**: `deep_profile.employees_over_time` — `[{year, count, source_url}]`, every point
  guaranteed an `http(s)` source and the series guaranteed either empty or ≥2 points by
  `_clean_employee_series` (`core/profile.py:782-811`). Reaches the API untouched via
  `core/pipeline.py:196`, persisted whole in `api/store.py:354`, rehydrated at
  `api/store.py:462,479`. Zero references anywhere in `ui/src` — independently confirmed by grep.
- **Sketch**: New panel in the Overview tab (`OverviewTab`, `Profile.jsx:42-`), beside "Executive
  summary", titled "Headcount trend": one row per cited year (`year · count`), each linking out via
  the same `ExtLink` evidence-list pattern already used by `MarketTab`'s "Market evidence" panel
  (`Profile.jsx:312-323`) — no new visual language. Renders only when
  `employees_over_time.length >= 2`, mirroring the engine's own bar; otherwise shows a one-line
  "Insufficient cited headcount history" state (X-03). No sort/filter controls, no new nav.
- **Contract rows**: `PROF-12` — Overview tab renders a headcount-trend panel from
  `deep_profile.employees_over_time` with a source link per point; panel shows its declared empty
  state (not "—", since it is a section rather than a single field) when fewer than two cited points
  exist (L, V).
- **Status**: approved — Zoraiz Mahmood, 2026-08-10

---

## Corrections to `contract/feature-rubric.md`

The rubric's "Where the strongest candidates already are" table is **stale on two of its three
rows**. Verified against current source during the first scouting run (2026-08-10):

| Rubric claim | Actual state |
|---|---|
| `employees_over_time` — not shown | **Correct.** Zero references in `ui/src`. |
| `route_scorecards` — not shown | **Wrong.** `core/route.py:57-67` turns it into `routing.route_recommendations`, rendered at `ui/src/pages/Profile.jsx:228-231` under a "Route scorecards" heading. The residual gap is narrow: `route_recommendations` only includes routes the startup is *eligible* for (`route.py:24-34`), so a Pass-routed startup sees zero or one card. Partial-completion problem, not a fresh feature. |
| `search_stats.timed_out` — not shown | **Wrong.** `core/pipeline.py:177-180` appends `"· N/M web queries timed out"` to `engine`, rendered verbatim at `ui/src/pages/Profile.jsx:520`. It is under-emphasised (small muted text, absent from Explore where a reviewer scans many companies) — that is a presentation fix for `contract/ui-backlog.md`, not a feature. |

Fix the rubric table before the next scouting run, or the next scout will propose work that is
already done.
