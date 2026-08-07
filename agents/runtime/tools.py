"""Deterministic verifier tools used as real quality gates.

These are the "tools" the pipeline runs against LLM-authored code. They are NOT
LLM prompts: they execute the real checkers so that gates stay honest (a model
cannot merely claim that tests passed). Each returns a small structured dict.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys


def _run(cmd: list, cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def run_pytest(target: pathlib.Path) -> dict:
    """Run pytest on a tests dir/file. Pass if there are no tests to run."""
    if not target.exists():
        return {"status": "pass", "detail": "no tests directory", "output": ""}
    proc = _run([sys.executable, "-m", "pytest", "-q", str(target)], target.parent)
    out = (proc.stdout + proc.stderr).strip()
    # exit code 5 == "no tests collected" -> treat as pass
    ok = proc.returncode in (0, 5)
    return {"status": "pass" if ok else "fail", "returncode": proc.returncode,
            "output": out[-4000:]}


def run_flake8(files: list, cwd: pathlib.Path, max_line: int = 100) -> dict:
    py = [f for f in files if str(f).endswith(".py")]
    if not py:
        return {"status": "pass", "detail": "no python files", "output": ""}
    proc = _run([sys.executable, "-m", "flake8", f"--max-line-length={max_line}", *py], cwd)
    out = (proc.stdout + proc.stderr).strip()
    return {"status": "pass" if proc.returncode == 0 else "fail", "output": out[-4000:]}


def run_mypy(files: list, cwd: pathlib.Path) -> dict:
    py = [f for f in files if str(f).endswith(".py")]
    if not py:
        return {"status": "pass", "detail": "no python files", "output": ""}
    # --explicit-package-bases + --namespace-packages avoid the
    # "Source file found twice under different module names" error when an
    # authored package (e.g. features/x/) has no top-level __init__.py.
    proc = _run([sys.executable, "-m", "mypy", "--ignore-missing-imports",
                 "--explicit-package-bases", "--namespace-packages", *py], cwd)
    out = (proc.stdout + proc.stderr).strip()
    return {"status": "pass" if proc.returncode == 0 else "fail", "output": out[-4000:]}


_SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                         # AWS access key
    r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",  # private key
    r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9]{16,}['\"]",
    r"(?i)secret\s*[:=]\s*['\"][A-Za-z0-9]{16,}['\"]",
    r"gh[pousr]_[A-Za-z0-9]{36,}",               # GitHub token
]


def scan_secrets(files: list) -> dict:
    """Cross-platform regex secret scan over the given files."""
    hits = []
    for f in files:
        p = pathlib.Path(f)
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in _SECRET_PATTERNS:
            if re.search(pat, text):
                hits.append({"file": str(p), "pattern": pat})
    return {"status": "pass" if not hits else "fail", "findings": hits}


# coarse dev-cycle token budgets by engineering effort
_BUDGETS = {
    "small": 150000,
    "medium": 400000,
    "large": 1000000,
}


def check_budget(effort: str, tokens_estimated: int) -> dict:
    limit = _BUDGETS.get((effort or "small").lower(), _BUDGETS["small"])
    status = "within_budget" if tokens_estimated <= limit else "exceeded"
    return {"budget_status": status, "limit": limit, "tokens_estimated": tokens_estimated}
