"""The S3 copy of runs.db is complete, and a burst of writes uploads it once.

The database runs in WAL mode, so a fresh commit lives in runs.db-wal until a checkpoint. The old
upload sent runs.db alone — a copy that could lack the newest runs, which is exactly the copy a
redeployed container restores from.
"""
import os
import shutil
import sqlite3
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import store  # noqa: E402


@pytest.fixture
def wal_db(tmp_path, monkeypatch):
    path = str(tmp_path / "runs.db")
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")      # keep commits in the WAL, as between checkpoints
    con.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, company TEXT)")
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # the schema is in runs.db; new rows are not
    monkeypatch.setattr(store, "DB_PATH", path)
    yield path, con
    con.close()


def _companies(path):
    con = sqlite3.connect(path)
    try:
        return [r[0] for r in con.execute("SELECT company FROM runs")]
    finally:
        con.close()


def test_a_bare_file_copy_misses_a_wal_commit_and_the_snapshot_does_not(wal_db, tmp_path):
    path, con = wal_db
    con.execute("INSERT INTO runs (company) VALUES ('Wandelbots')")
    con.commit()
    bare = str(tmp_path / "bare.db")
    shutil.copy(path, bare)                          # what upload_file(DB_PATH) used to send
    assert _companies(bare) == []
    snap = str(tmp_path / "snap.db")
    store._snapshot(snap)
    assert _companies(snap) == ["Wandelbots"]


@pytest.fixture
def fake_s3(monkeypatch, tmp_path):
    uploads = []

    class Client:
        def upload_file(self, src, bucket, key):
            uploads.append(_companies(src))

    monkeypatch.setattr(store, "_s3_available", lambda: True)
    monkeypatch.setattr(store, "_s3_client", lambda: Client())
    monkeypatch.setattr(store, "_upload_scheduled", False)
    return uploads


def test_a_burst_of_writes_is_uploaded_once_and_completely(wal_db, fake_s3, monkeypatch):
    path, con = wal_db
    monkeypatch.setattr(store, "S3_UPLOAD_DELAY", 0.1)
    for name in ("A", "B", "C", "D", "E"):
        con.execute("INSERT INTO runs (company) VALUES (?)", (name,))
        con.commit()
        store._upload_to_s3()
    deadline = time.time() + 5
    while not fake_s3 and time.time() < deadline:
        time.sleep(0.02)
    time.sleep(0.2)
    assert fake_s3 == [["A", "B", "C", "D", "E"]]


def test_a_pending_upload_is_flushed_at_shutdown(wal_db, fake_s3, monkeypatch):
    path, con = wal_db
    monkeypatch.setattr(store, "S3_UPLOAD_DELAY", 3600)
    con.execute("INSERT INTO runs (company) VALUES ('Celonis')")
    con.commit()
    store._upload_to_s3()
    assert fake_s3 == []
    store._flush_pending_upload()
    assert fake_s3 == [["Celonis"]]
