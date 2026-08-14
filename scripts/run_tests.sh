#!/usr/bin/env bash
# Run the test suite for the current (work)tree.
# Usage: bash scripts/run_tests.sh [path]
set -euo pipefail

TARGET="${1:-tests}"

if [ ! -d "$TARGET" ]; then
  echo "No tests directory at '$TARGET' - nothing to run."
  exit 0
fi

python -m pytest -q "$TARGET"
