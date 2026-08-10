# UI backlog

Durable, evidence-cited findings. `ui-auditor` appends; `ui-implementer` takes **one** at a time.

Status is the memory that stops the system re-proposing what you already declined — the previous
agent system had no such record and re-litigated the same ideas across 59 cycles. A `rejected` row
stays here forever, with its reason.

Impact: **high** = a user is misled or blocked · **med** = friction or inconsistency ·
**low** = polish.

| ID | Finding | Where | Impact | Contract | Status |
|----|---------|-------|--------|----------|--------|
| UI-01 | Provenance link's accessible name is just "web" — a screen-reader user hears "web" with no indication of what it sources or where it goes. The `title` is ignored because link text wins. | `ui/src/pages/Profile.jsx:38` | high | X-01, X-04 | proposed |
| UI-02 | 47 raw colour literals outside `tokens.css`. Each is a site the iX theme cannot reach, so the token migration cannot fully land while they exist. | 12 files, see `contract/ix-lint-baseline.json` | high | X-06 | proposed |
| UI-03 | `var(--bg)` is referenced but never declared, so it resolves to nothing and the rule silently does nothing. | `ui/src/pages/Explore.css:4` | med | — | proposed |
| UI-04 | Three `onClick` handlers on `<div>`/`<span>` with no role — not keyboard reachable and invisible to assistive tech. | `ui/src/pages/Explore.jsx:65,246,247` | high | X-04 | proposed |
| UI-05 | `ClaimEvidenceMatrix` hard-codes its entire palette (9 literals) rather than using the pillar/semantic tokens that already exist for exactly this. | `ui/src/components/ClaimEvidenceMatrix.jsx:10-34` | med | X-06 | proposed |
| UI-06 | Employees is web-researched and `profile_sources.employees_count` is populated (`core/pipeline.py:27`), but the metric renders with no provenance badge — while Founded, two lines below, has one. A reviewer cannot tell which figures are sourced. | `ui/src/pages/Profile.jsx:55` vs `:57` | high | X-01, PROF-02 | proposed |
| UI-07 | Alerts has an error state and an empty state but no loading state, so the list appears empty while it is still fetching — indistinguishable from "you are tracking nothing". | `ui/src/pages/Alerts.jsx` | med | X-03, MISC-02 | proposed |
| UI-08 | Five orphaned page stubs ("Superseded by the enterprise redesign") remain in `ui/src/pages/`: Dashboard, Evaluate, Challenges, Solve, RunDetail. Nothing imports them; they inflate `docs/ui-inventory.json` and give agents dead surface to reason about. | `ui/src/pages/{Dashboard,Evaluate,Challenges,Solve,RunDetail}.jsx` | med | — | proposed |

## Notes

- **UI-02 and UI-05 overlap** with the iX token migration. Prefer doing them *as* that migration
  rather than twice — check with a human before starting either.
- Every row above came from `node scripts/ix_lint.mjs` or a real test failure, not from opinion.
  Keep it that way: a finding without a `file:line` does not belong here.
- Sorting, filtering and column controls are **not** features (see `contract/feature-rubric.md`);
  if one is genuinely needed it belongs here as a UI row.
