---
name: feature-cycle
description: Run one feature delivery cycle - scout a worthwhile feature against the value rubric, get human approval, build the backend, place it in the UI, prove nothing broke, and open a PR. Use when asked to propose, build or ship a new feature.
---

# Feature delivery cycle

Spec → **human approval** → backend → UI placement → gates → PR.

The approval step is the highest-leverage gate in the system. Its absence is why the previous
agent system shipped `company-name-sort-accessibility` and called it a feature.

## Preconditions

```bash
bash scripts/gates.sh --fast
```

## Steps

### 1. Scout
Launch `feature-scout`. It scores proposals against `contract/feature-rubric.md` and **returns**
them. It has no write access — a scout that records its own proposals is one step from a system
that approves its own work. **You append them to `contract/feature-proposals.md`** with
`Status: proposed`.

It is instructed to look first at evidence the engine **already computes but the UI never shows** —
`employees_over_time`, `route_scorecards`, `search_stats.timed_out` — because that is where real
value is cheapest.

If it proposes nothing above the bar, stop. That is a valid outcome.

### 2. Approve — human only
Present each proposal with its score and the decision it would change. Use `AskUserQuestion`.

**No agent may approve a proposal, including by inferring approval from enthusiasm.** A human edits
`Status: approved`, or nothing gets built.

### 3. Build the backend
Launch `feature-builder`. Engine + API + pytest. It does not touch `ui/`.

Non-negotiable: any new displayed fact carries a source or renders "—". Never fill a gap from model
knowledge — that is how `SAR 3.75 million` was invented for makkook.ai before that path was removed.

### 4. Place it in the UI
Launch `ui-integrator`. It states a placement plan — which surface, what it displaces, which
existing pattern it reuses, its loading/empty/error states, where the provenance link sits —
**before** writing code. Review the plan; a good feature in the wrong place is invisible.

### 5. Verify
```bash
bash scripts/gates.sh
```
A new panel legitimately changes the page, so a failing visual baseline is expected here. It is
still a **stop**: the human confirms the change is the intended one and updates baselines
themselves.

### 6. Package
Launch `pr-author`. Add the new behaviour IDs to `contract/feature-inventory.md` — **the human does
this**, as part of accepting the feature.

## Rules

- One feature per cycle.
- Backend and UI are separate agents on purpose: computing a thing and knowing where it belongs are
  different skills, and bundling them produces diffs nobody can review.
- No agent approves its own work at any stage.
- If a proposal cannot clear the rubric honestly, it does not get built. Do not lower the score to
  fit an idea you like.
