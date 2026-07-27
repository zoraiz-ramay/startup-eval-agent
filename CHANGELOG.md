# Changelog

## Delta release — problem-led, evidence-led, route-specific engine

### Extended (existing features upgraded in place)
- **Evidence model** (`core/provenance.py`): `Fact` gains `source_type`
  (self_reported / public / inferred / private, auto-derived from method) and
  `freshness_days`. No schema migration needed — facts live in the result JSON.
- **Scoring** (`core/score.py`): route-aware scorecards (`ROUTE_WEIGHTS` per pillar)
  alongside the backwards-compatible universal `final_score`; output gains
  `red_flags` (negative evidence only) and `missing_evidence` (absence of data,
  explicitly separated); corporate-program points now require an evidence URL
  (supporting signal, not automatic credit).
- **Routing** (`core/route.py`): pillar eligibility now driven by each route's own
  scorecard; `route_recommendations` emits per-route recommendation text + score.
- **Deep profile** (`core/profile.py`): `key_team` (early/core non-founder roles)
  added to the research schema and evidence facts.
- **Challenge intake** (`core/solve.py`): challenges gain `status`
  (pending/approved/rejected) + `reviewer`; rejected challenges are excluded from
  fit scoring (`core/fit.py`).

### New
- **Reviewer override + audit log** (`api/store.py` `overrides` table — additive
  migration via `CREATE TABLE IF NOT EXISTS`): `POST /api/runs/{id}/override`,
  `GET /api/runs/{id}/audit`. Automated result preserved; effective pillar updated;
  who/why/evidence logged. Explanation surfaced in the Profile → Scoring & Fit tab.
- **Challenge approval control**: `PATCH /api/challenges/{index}` + approve/reject
  actions on the Home command centre.
- **UI**: route scorecard panel, red-flags & gaps panel, reviewer-decision panel
  with audit trail (`ui/src/pages/Profile.jsx`); challenge status chips (`Home.jsx`).

### Skipped (already implemented and working)
Problem intake + matching, expanded startup profile (founders/advisors/programs/
customers/parent group), multi-pillar Siemens routing, corporate-program capture,
claim verification with contradiction status, provenance timestamps, challenge
library, AI ask flow, run persistence.
