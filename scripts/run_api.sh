#!/usr/bin/env bash
# Local API with automatic reload; production starts through start.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-.venv_mac/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN=python3; fi
export AUTH_MODE="${AUTH_MODE:-stub}"
export SESSION_BACKEND="${SESSION_BACKEND:-memory}"
exec "$PYTHON_BIN" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
