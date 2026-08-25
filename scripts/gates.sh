#!/usr/bin/env bash
# The single verification entry point. Every change — human or agent — must leave this green.
#
# It exists because the previous agent system's gates reported `tests: pass` and `ui_approved:
# true` while checking nothing real: its "tests" were substring matches on JSX, one of them read a
# stale copy of the source that lived inside tests/, and its UI reviewer had no browser. The rule
# here is that each gate can actually fail, and each failure names something a user would notice.
#
#   bash scripts/gates.sh            # all gates
#   bash scripts/gates.sh --fast     # skip Playwright (no browser needed)
set -uo pipefail
cd "$(dirname "$0")/.."

FAST=0
[[ "${1:-}" == "--fast" ]] && FAST=1

PY=${PY:-py -3}
failed=()
run() {
  local name="$1"; shift
  printf '\n\033[1m── %s\033[0m\n' "$name"
  if "$@"; then
    printf '\033[32m   PASS\033[0m %s\n' "$name"
  else
    printf '\033[31m   FAIL\033[0m %s\n' "$name"
    failed+=("$name")
  fi
}

run "backend tests"        $PY -m pytest tests/ -q
# Regenerated, not hand-maintained: agents read this to know what the app contains, so a stale
# copy is a hallucination waiting to happen.
run "ui inventory current" $PY scripts/ui_inventory.py --check
run "ix conformance"       node scripts/ix_lint.mjs
# Corpus health, not a code regression, so it reports rather than blocks: it reads data/runs.db,
# and a dimension can only be shown to have gone flat once enough runs exist that were scored by
# the CURRENT engine. Blocking on it would fail every build until someone re-ran the corpus, which
# is how a useful check gets deleted. Read it — three dimensions had silently collapsed to
# constants at once, and the test suite was green throughout. Drop --report to make it blocking
# once the stored runs are current.
printf '\n\033[1m── dimension variance (advisory)\033[0m\n'
$PY scripts/dimension_variance.py --report || true
# Also advisory, and deliberately noisy while unlabelled: routing quality is the one thing here
# that no amount of unit testing establishes, and the labels can only come from a reviewer. A
# silent reminder is one nobody acts on. Once benchmarks/labels.json is filled in, swap this for
# `--min-f1 <floor>` and drop the `|| true` to make a routing regression fail the build.
printf '\n\033[1m── routing benchmark (advisory)\033[0m\n'
$PY -m benchmarks.routing_eval --brief || true
run "ui component tests"   bash -c 'cd ui && npx vitest run --reporter=dot'

if [[ $FAST -eq 0 ]]; then
  if [[ -d ui/node_modules/@playwright ]]; then
    # E2E + visual regression. Baselines in ui/e2e/__screenshots__ are the record that the Tracxn
    # layout survived; agents must never regenerate them.
    run "e2e + visual"     bash -c 'cd ui && npx playwright test'
  else
    printf '\n\033[33m── e2e + visual: SKIPPED (playwright not installed)\033[0m\n'
    printf '   install with: cd ui && npm i -D @playwright/test && npx playwright install chromium\n'
  fi
fi

printf '\n════════════════════════════════════════\n'
if [[ ${#failed[@]} -eq 0 ]]; then
  printf '\033[32mAll gates passed.\033[0m\n'
  exit 0
fi
printf '\033[31mFAILED: %s\033[0m\n' "${failed[*]}"
exit 1
