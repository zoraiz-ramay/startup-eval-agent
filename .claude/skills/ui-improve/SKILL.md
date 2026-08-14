---
name: ui-improve
description: Run one UI improvement cycle - audit the React UI against Siemens iX and the Tracxn layout contract, implement the single highest-impact finding, prove nothing broke, and open a PR. Use when asked to improve the UI, work the UI backlog, or continue iX adoption.
---

# UI improvement cycle

One finding, implemented and proven, per run. Bounded on purpose: the previous agent system in this
repo ran 59 unbounded cycles and produced churn nobody could review.

## Preconditions

```bash
bash scripts/gates.sh --fast
```

Green before you start, or stop and fix that first. Never begin work on a red tree — you will not
be able to tell your breakage from the one already there.

## Steps

### 1. Audit
Launch `ui-auditor`. It grounds itself in `docs/ui-inventory.json`, `contract/ui-backlog.md` and
`node scripts/ix_lint.mjs --json`, then **returns** ranked, cited rows.

It has no write access on purpose: an auditor that can edit the code it audits can make its own
findings true. **You append its rows to `contract/ui-backlog.md`**, preserving existing rows and
their status.

If it reports nothing worth doing, **stop and say so**. That is a successful run.

### 2. Choose — with the human
Present the top 3 findings with their impact, and ask which to take (`AskUserQuestion`). Do not
self-select on the first few cycles: the choice is where taste enters, and it is how the user
teaches the system what "worth it" means here.

### 3. Implement
Launch `ui-implementer` with the chosen backlog row. Exactly one item.

### 4. Verify
```bash
bash scripts/gates.sh
```
All five gates. A failing **visual baseline is a stop**, not an obstacle — surface the diff and let
the human decide whether the layout change was intended. Agents cannot update baselines, by design.

### 5. Package
Launch `pr-author` for a branch + PR with gate results and before/after screenshots.

## Rules

- One finding per cycle. If the implementer wants to fix something adjacent, that is a new backlog
  row, not scope creep.
- Never update visual baselines. Never edit `contract/feature-inventory.md`.
- Never re-baseline `ix_lint` to silence a new violation — the baseline only ratchets down.
- If a cycle ends with nothing merged, that is fine. Reporting "no worthwhile finding" beats
  manufacturing work to look busy.

## Running unattended

Once you trust the output, `/loop 6h /ui-improve` will run it on a cadence. Do not start there:
watch several supervised cycles first and confirm the findings are ones you would have picked.
