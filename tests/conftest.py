"""Test environment, set before anything imports the app.

`api.store` and `api.security` both read configuration at module scope, so these have to
land in os.environ before the first import of either — which is why this is module-level
code and not a fixture.

APP_ENV is deliberately left unset: it is what arms the production seal in api/auth.py, and
the suite should exercise the same code path a developer's laptop does, not a special one.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

os.environ["AUTH_MODE"] = "stub"
os.environ["SESSION_BACKEND"] = "memory"
os.environ.setdefault("RUNS_DB", str(pathlib.Path(tempfile.gettempdir()) / "sea_test_runs.db"))
os.environ.pop("APP_ENV", None)
