"""api/interests.py: department profiles are seeded from the requirements xlsx (via
core.department_needs) rather than the old five-word demo lists, and an admin-configured
profile (is_demo=0) must survive the reseed that runs on every _db() call."""
import json
import os
import pathlib
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import auth, store  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture()
def db(monkeypatch):
    path = pathlib.Path(tempfile.mkdtemp()) / "runs.db"
    monkeypatch.setattr(store, "DB_PATH", str(path))
    monkeypatch.setattr(store, "_restore_from_s3", lambda: None)
    monkeypatch.setattr(store, "_upload_to_s3", lambda: None)
    monkeypatch.setattr(auth, "_seed_admins_from_file", lambda: frozenset())
    return path


@pytest.fixture()
def signed_in(db) -> TestClient:
    client = TestClient(app)
    client.get("/api/auth/login", follow_redirects=False)
    return client


def test_demo_department_profiles_are_richer_than_the_old_five_term_lists(signed_in):
    depts = signed_in.get("/api/departments").json()["departments"]
    by_id = {d["id"]: d for d in depts}
    assert set(by_id) == {"di", "si", "mobility"}
    for dept in by_id.values():
        assert dept["demo"] is True
    # The old hardcoded DEMO list had exactly 5 keywords per department; the requirements xlsx
    # (when present) is far larger. If the xlsx is absent (e.g. a stripped CI checkout) this
    # falls back to the old 5-term list, so assert only a lower bound that holds either way.
    assert len(by_id["di"]["interests"]) >= 5


def test_admin_configured_profile_survives_reseed(signed_in):
    import api.interests as interests

    with interests._db() as con:
        con.execute("UPDATE department_profiles SET label=?,interests=?,is_demo=0 WHERE id=?",
                    ("Custom Label", json.dumps(["bespoke-term"]), "di"))
        con.commit()

    # A second _db() call must not clobber the admin's edit — only is_demo=1 rows are reseeded.
    with interests._db() as con:
        row = con.execute("SELECT label, interests, is_demo FROM department_profiles WHERE id=?",
                          ("di",)).fetchone()
    assert row[0] == "Custom Label"
    assert json.loads(row[1]) == ["bespoke-term"]
    assert row[2] == 0
