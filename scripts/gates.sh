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
