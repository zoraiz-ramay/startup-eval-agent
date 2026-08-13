"""SQLite persistence for evaluation runs with S3 backup.

Stored per run: summary columns for fast listing + the full result JSON blob.
DB lives at DATA_DIR/runs.db (override with RUNS_DB).

On first connection the DB is restored from S3 if a remote copy exists and no
local file is present. After every write (save_run, delete_run, add_override)
the DB is uploaded back to S3 in a background thread so it survives container
restarts and redeployments.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from core.config import BASE_DIR

log = logging.getLogger(__name__)

DB_PATH = os.getenv("RUNS_DB", str(pathlib.Path(BASE_DIR) / "runs.db"))

# ----------------------------------------------------------------- S3 sync
_S3_DB_KEY = "data/runs.db"
_s3_lock = threading.Lock()
_restored = False


def _s3_client():
    import boto3
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        aws_access_key_id=os.environ.get("HYDRA_DATA_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("HYDRA_DATA_AWS_SECRET_ACCESS_KEY"),
    )


def _s3_available() -> bool:
    return bool(
        os.environ.get("HYDRA_DATA_AWS_ACCESS_KEY_ID")
        and os.environ.get("HYDRA_DATA_AWS_SECRET_ACCESS_KEY")
    )


def _s3_bucket() -> str:
    return os.getenv("S3_BUCKET", "hydra-data-app-startup-evaluation-agent-hydra-pdfs")


def _restore_from_s3() -> None:
    """Download runs.db from S3 if no local copy exists yet."""
    global _restored
    if _restored or not _s3_available():
        _restored = True
        return
    _restored = True
    if os.path.exists(DB_PATH):
        log.info("[store] Local DB already exists at %s, skipping S3 restore", DB_PATH)
        return
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        tmp = DB_PATH + ".s3tmp"
        _s3_client().download_file(_s3_bucket(), _S3_DB_KEY, tmp)
        shutil.move(tmp, DB_PATH)
        log.info("[store] Restored DB from s3://%s/%s -> %s", _s3_bucket(), _S3_DB_KEY, DB_PATH)
    except Exception as exc:
        log.info("[store] No DB in S3 (starting fresh): %s", exc)
        if os.path.exists(DB_PATH + ".s3tmp"):
            os.remove(DB_PATH + ".s3tmp")


def _upload_to_s3() -> None:
    """Upload the current runs.db to S3 in a background thread."""
    if not _s3_available():
        return

    def _do_upload():
        with _s3_lock:
            try:
                _s3_client().upload_file(DB_PATH, _s3_bucket(), _S3_DB_KEY)
                log.debug("[store] Synced DB to s3://%s/%s", _s3_bucket(), _S3_DB_KEY)
            except Exception as exc:
                log.warning("[store] S3 upload failed: %s", exc)

    threading.Thread(target=_do_upload, daemon=True).start()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    pillar      TEXT,
    secondary   TEXT,
    final_score REAL,
    sfs         INTEGER DEFAULT 0,
    engine      TEXT,
    created_at  TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS overrides (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL,
    prev_pillar   TEXT,
    new_pillar    TEXT NOT NULL,
    reason        TEXT NOT NULL,
    evidence_note TEXT,
    reviewer      TEXT,
    created_at    TEXT NOT NULL
);

-- ---------------- normalized entities: everything fetched from APIs/searches ----------------
CREATE TABLE IF NOT EXISTS companies (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    website        TEXT, domain TEXT, hq TEXT, founded_year TEXT,
    parent_group   TEXT, employees TEXT, funding TEXT, stage TEXT,
    latest_run_id  INTEGER,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS people (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    kind       TEXT NOT NULL,           -- founder | advisor | key_team
    name       TEXT NOT NULL,
    role       TEXT, background TEXT, affiliation TEXT,
    linkedin   TEXT, source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS programs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name       TEXT NOT NULL,
    type       TEXT,                    -- incubator | accelerator | corporate_program
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reference_customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name       TEXT NOT NULL,
    status     TEXT,                    -- verified | partial | unverified | contradicted | ''
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    company_id  INTEGER REFERENCES companies(id),
    key         TEXT, value TEXT, source_url TEXT,
    method      TEXT, source_type TEXT,
    confidence  REAL, verified INTEGER, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS tool_matches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    company_id INTEGER REFERENCES companies(id),
    tool       TEXT NOT NULL,
    division   TEXT, relation TEXT, confidence REAL, rationale TEXT
);
CREATE TABLE IF NOT EXISTS web_cache (
    key        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- ---------------- per-reviewer workspace (keyed on the Entra oid) ----------------
-- One row per /api/evaluate call, whether or not it re-ran the pipeline. This is BOTH the
-- reviewer's own list of startups and the admin activity log, which is why it records
-- served_from: the difference between the two is the whole point of the shared cache.
CREATE TABLE IF NOT EXISTS searches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_oid     TEXT NOT NULL,
    user_upn     TEXT,
    query        TEXT NOT NULL,           -- what the reviewer typed, before resolution
    company_id   INTEGER,                 -- nullable: delete_run does not cascade
    company_name TEXT,                    -- resolved name, denormalized so the list survives deletes
    run_id       INTEGER,                 -- nullable for the same reason
    served_from  TEXT,                    -- cache | fresh
    created_at   TEXT NOT NULL
);
-- Sign-ins are recorded here rather than counted from Redis: sessions there expire after
-- SESSION_TTL (8h by default), so Redis can answer "who is online" but never "how many
-- sessions this month", which is what the admin dashboard asks.
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_oid   TEXT NOT NULL,
    user_upn   TEXT,
    started_at TEXT NOT NULL
);
-- Every string that has ever been used to reach a company: the name a reviewer typed, the
-- name the pipeline resolved it to, and its domain. Without this the cache-first lookup in
-- /api/evaluate misses its own writes -- it searches on the typed name while save_run stores
-- the RESOLVED one, so "phena" never finds the run filed under "Phena Technologies" and the
-- whole external pipeline runs again for a company already in the database.
CREATE TABLE IF NOT EXISTS company_aliases (
    alias      TEXT PRIMARY KEY COLLATE NOCASE,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saved_views (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_oid     TEXT NOT NULL,
    name         TEXT NOT NULL COLLATE NOCASE,
    columns_json TEXT NOT NULL,
    filters_json TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (user_oid, name)
);
-- Admins granted from inside the app. This is the SECOND source of admin rights, never the
-- only one: ADMIN_UPNS stays the seed (see is_admin in api/auth.py), because a system with no
-- "not configured, so allow" branch anywhere would otherwise have no way to make its first
-- grant once this table is empty. Keyed on UPN rather than oid because you grant access to a
-- colleague by typing their sign-in name, before they have ever signed in and been given one.
CREATE TABLE IF NOT EXISTS admins (
    upn        TEXT PRIMARY KEY COLLATE NOCASE,
    granted_by TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_id);
CREATE INDEX IF NOT EXISTS idx_facts_run ON evidence_facts(run_id);
CREATE INDEX IF NOT EXISTS idx_web_cache_created ON web_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_searches_user ON searches(user_oid, created_at);
CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_oid);
CREATE INDEX IF NOT EXISTS idx_saved_views_user ON saved_views(user_oid);
-- latest_run_for_company scans runs on every evaluate; it is the hot path of the cache.
CREATE INDEX IF NOT EXISTS idx_runs_company ON runs(company);
"""


def _conn() -> sqlite3.Connection:
    _restore_from_s3()
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    for col, typ in (("summary", "TEXT"), ("parent_group", "TEXT"), ("company_id", "INTEGER")):
        try:
            con.execute(f"ALTER TABLE runs ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    # Verified reviewer identity, added when the app moved to Entra ID sign-in. These stay
    # NULL on rows written before that, which is the honest record: the `reviewer` string
    # on those rows was free text the client supplied and nothing checked it. Backfilling
    # them would make unverified history indistinguishable from verified history, which is
    # the one thing an audit trail must never do.
    for col in ("reviewer_oid", "reviewer_upn", "reviewer_tid", "reviewer_source"):
        try:
            con.execute(f"ALTER TABLE overrides ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    return con


# ---------------------------------------------------------------------- web cache
# Search results and fetched site pages are cached so a re-evaluation is both fast and
# REPRODUCIBLE: DuckDuckGo returns a different mix of results run to run, which is the main
# reason two evaluations of the same startup used to disagree.
#
# Cache writes deliberately DO NOT call _upload_to_s3(): that ships the whole runs.db in a
# background thread and would fire dozens of times per evaluation (~41 searches). The rows are
# written locally and ride along on the next save_run upload, which sends the entire file
# anyway.
WEB_CACHE_TTL_DAYS = float(os.getenv("WEB_CACHE_TTL_DAYS", "7"))
_cache_lock = threading.Lock()


def _cache_conn() -> sqlite3.Connection:
    """Short-lived connection for cache access.

    Searches run in _ddg_many's daemon threads, so every cache call may come from a different
    thread; sqlite3 connections are not shareable across threads. WAL lets the readers proceed
    while a writer holds the lock."""
    con = _conn()
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
    except sqlite3.OperationalError:
        pass
    return con


def cache_get(kind: str, key: str) -> "object | None":
    """Cached payload for this key, or None when absent or older than the TTL."""
    try:
        with _cache_lock, _cache_conn() as con:
            row = con.execute(
                "SELECT payload, created_at FROM web_cache WHERE key=? AND kind=?",
                (key, kind)).fetchone()
        if not row:
            return None
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(row[1])).total_seconds() / 86400
        if age > WEB_CACHE_TTL_DAYS or age < 0:
            return None
        return json.loads(row[0])
    except Exception:
        return None            # a cache fault must never break an evaluation


def cache_put(kind: str, key: str, payload) -> None:
    try:
        with _cache_lock, _cache_conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO web_cache (key, kind, payload, created_at) "
                "VALUES (?,?,?,?)",
                (key, kind, json.dumps(payload), _now()))
    except Exception:
        pass


def cache_purge_expired() -> int:
    """Drop rows past the TTL; returns how many were removed."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=WEB_CACHE_TTL_DAYS)).isoformat(timespec="seconds")
    try:
        with _cache_lock, _cache_conn() as con:
            return int(con.execute("DELETE FROM web_cache WHERE created_at < ?",
                                   (cutoff,)).rowcount or 0)
    except Exception:
        return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _upsert_company(con: sqlite3.Connection, result: dict, run_id: int) -> int:
    """Create/update the canonical company row from an evaluation result."""
    p = result.get("profile", {}) or {}
    dp = result.get("deep_profile", {}) or {}
    name = str(result.get("company", "")).strip()
    vals = (str(p.get("website", "")), str(p.get("domain", "")), str(p.get("hq", "")),
            str(p.get("founded_year", "")), str(dp.get("parent_group", "")),
            str(dp.get("employees", "") or p.get("employees_count", "")),
            str(p.get("funding", "")), str(p.get("Development stage of your solution", "")))
    row = con.execute("SELECT id FROM companies WHERE name=? COLLATE NOCASE", (name,)).fetchone()
    if row:
        cid = int(row[0])
        con.execute(
            "UPDATE companies SET website=?, domain=?, hq=?, founded_year=?, parent_group=?, "
            "employees=?, funding=?, stage=?, latest_run_id=?, updated_at=? WHERE id=?",
            (*vals, run_id, _now(), cid))
    else:
        cur = con.execute(
            "INSERT INTO companies (name, website, domain, hq, founded_year, parent_group, "
            "employees, funding, stage, latest_run_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (name, *vals, run_id, _now(), _now()))
        cid = int(cur.lastrowid)
    return cid


def _replace_children(con: sqlite3.Connection, cid: int, run_id: int, result: dict) -> None:
    """Persist the fetched entities. People/programs/customers reflect the LATEST
    evaluation (replaced per company); evidence facts and tool matches are per-run
    history (appended, keyed by run_id)."""
    dp = result.get("deep_profile", {}) or {}
    ts = _now()
    # people / programs / customers — snapshot of current knowledge
    con.execute("DELETE FROM people WHERE company_id=?", (cid,))
    for kind, key in (("founder", "founders"), ("advisor", "advisors"), ("key_team", "key_team")):
        for x in dp.get(key, []) or []:
            if isinstance(x, dict) and str(x.get("name", "")).strip():
                con.execute(
                    "INSERT INTO people (company_id, kind, name, role, background, affiliation, "
                    "linkedin, source_url, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (cid, kind, str(x.get("name", ""))[:120], str(x.get("role", ""))[:120],
                     str(x.get("background", ""))[:400], str(x.get("affiliation", ""))[:200],
                     str(x.get("linkedin", ""))[:300], str(x.get("source_url", ""))[:500], ts))
    con.execute("DELETE FROM programs WHERE company_id=?", (cid,))
    for x in dp.get("programs", []) or []:
        if isinstance(x, dict) and str(x.get("name", "")).strip():
            con.execute("INSERT INTO programs (company_id, name, type, source_url, updated_at) "
                        "VALUES (?,?,?,?,?)",
                        (cid, str(x.get("name", ""))[:120], str(x.get("type", ""))[:40],
                         str(x.get("source_url", ""))[:500], ts))
    # customers with their verification status from this run
    ver = {str(c.get("value", "")).strip().lower(): str(c.get("status", ""))
           for c in (result.get("verification", {}) or {}).get("claims", [])
           if c.get("field") == "reference_customer"}
    con.execute("DELETE FROM reference_customers WHERE company_id=?", (cid,))
    for c in dp.get("reference_customers", []) or []:
        s = str(c).strip()
        if s:
            con.execute("INSERT INTO reference_customers (company_id, name, status, updated_at) "
                        "VALUES (?,?,?,?)", (cid, s[:120], ver.get(s.lower(), ""), ts))
    # per-run history tables
    for f in result.get("facts", []) or []:
        if isinstance(f, dict):
            con.execute(
                "INSERT INTO evidence_facts (run_id, company_id, key, value, source_url, method, "
                "source_type, confidence, verified, retrieved_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, cid, str(f.get("key", ""))[:120], str(f.get("value", ""))[:500],
                 str(f.get("source_url", ""))[:500], str(f.get("method", ""))[:40],
                 str(f.get("source_type", ""))[:20], float(f.get("confidence", 0) or 0),
                 1 if f.get("verified") in (True, "True", "true") else 0,
                 str(f.get("retrieved_at", ""))[:32]))
    for m in (result.get("fit", {}) or {}).get("matches", []) or []:
        if isinstance(m, dict) and m.get("tool"):
            con.execute(
                "INSERT INTO tool_matches (run_id, company_id, tool, division, relation, "
                "confidence, rationale) VALUES (?,?,?,?,?,?,?)",
                (run_id, cid, str(m.get("tool", ""))[:120], str(m.get("division", ""))[:80],
                 str(m.get("relation", ""))[:20], float(m.get("confidence", 0) or 0),
                 str(m.get("rationale", ""))[:400]))


def _norm_alias(value: str) -> str:
    """Reduce a typed query, a resolved name or a URL to the string aliases are matched on.

    Hosts and URLs collapse to a bare domain so "https://www.phena.ai/about", "phena.ai" and
    "www.phena.ai" are one alias. Company names are left alone apart from trimming — the
    column is COLLATE NOCASE, so case needs no handling here.
    """
    s = str(value or "").strip()
    if not s:
        return ""
    if "://" in s:
        s = s.split("://", 1)[1]
    if "." in s and " " not in s:            # looks like a host, not a company name
        s = s.split("/", 1)[0]
        if s.lower().startswith("www."):
            s = s[4:]
    return s.strip().strip(".,")[:200]


def _record_alias(con: sqlite3.Connection, alias: str, cid: int) -> None:
    key = _norm_alias(alias)
    if not key:
        return
    # First writer wins: an alias already pointing somewhere is not repointed here, because
    # two companies can legitimately share a typed prefix and silently stealing the alias
    # would serve the wrong company's evaluation from cache.
    con.execute("INSERT OR IGNORE INTO company_aliases (alias, company_id, created_at) "
                "VALUES (?,?,?)", (key, cid, _now()))


def save_run(result: dict, aliases: Iterable[str] = ()) -> int:
    """Persist an evaluation. `aliases` are extra strings this company should be findable
    by — in practice the query the reviewer actually typed, which is usually NOT the name
    the pipeline resolved and stores."""
    rt = result.get("routing", {}) or {}
    sc = result.get("score", {}) or {}
    dp = result.get("deep_profile", {}) or {}
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO runs (company, pillar, secondary, final_score, sfs, engine, created_at, "
            "result_json, summary, parent_group) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(result.get("company", "")), str(rt.get("pillar", "")),
             ",".join(rt.get("secondary", []) or []), float(sc.get("final_score", 0) or 0),
             1 if rt.get("sfs_relevant") else 0, str(result.get("engine", "")),
             datetime.now(timezone.utc).isoformat(timespec="seconds"),
             json.dumps(result, default=str),
             str(result.get("summary", ""))[:300], str(dp.get("parent_group", ""))[:120]))
        run_id = int(cur.lastrowid)
        cid = _upsert_company(con, result, run_id)
        con.execute("UPDATE runs SET company_id=? WHERE id=?", (cid, run_id))
        _replace_children(con, cid, run_id, result)
        p = result.get("profile", {}) or {}
        for a in (result.get("company", ""), p.get("domain", ""), p.get("website", ""), *aliases):
            _record_alias(con, a, cid)
    _upload_to_s3()
    return run_id


def backfill_entities() -> int:
    """Idempotent migration: populate the normalized tables from runs saved before
    the schema existed. Returns the number of runs backfilled."""
    n = 0
    with _conn() as con:
        rows = con.execute(
            "SELECT id, result_json FROM runs WHERE company_id IS NULL ORDER BY id").fetchall()
        for run_id, blob in rows:
            try:
                result = json.loads(blob or "{}")
                if not str(result.get("company", "")).strip():
                    continue
                cid = _upsert_company(con, result, run_id)
                con.execute("UPDATE runs SET company_id=? WHERE id=?", (cid, run_id))
                _replace_children(con, cid, run_id, result)
                n += 1
            except Exception:
                continue
    return n


def list_companies() -> list[dict]:
    """Canonical company records with their people/programs/customers rolled up."""
    with _conn() as con:
        comps = con.execute(
            "SELECT id, name, website, hq, founded_year, parent_group, employees, funding, "
            "stage, latest_run_id, updated_at FROM companies ORDER BY updated_at DESC").fetchall()
        out = []
        for c in comps:
            cid = c[0]
            people = con.execute(
                "SELECT kind, name, role, background, linkedin FROM people WHERE company_id=?",
                (cid,)).fetchall()
            progs = con.execute(
                "SELECT name, type FROM programs WHERE company_id=?", (cid,)).fetchall()
            custs = con.execute(
                "SELECT name, status FROM reference_customers WHERE company_id=?", (cid,)).fetchall()
            out.append({
                "id": cid, "name": c[1], "website": c[2], "hq": c[3], "founded_year": c[4],
                "parent_group": c[5], "employees": c[6], "funding": c[7], "stage": c[8],
                "latest_run_id": c[9], "updated_at": c[10],
                "founders": [{"name": p[1], "role": p[2], "background": p[3], "linkedin": p[4]}
                             for p in people if p[0] == "founder"],
                "advisors": [{"name": p[1], "role": p[2]} for p in people if p[0] == "advisor"],
                "programs": [{"name": p[0], "type": p[1]} for p in progs],
                "reference_customers": [{"name": x[0], "status": x[1]} for x in custs],
            })
    return out


def list_runs(limit: int = 100) -> list[dict]:
    """Summary rows enriched with explore-grid columns parsed from the stored result JSON
    (fine at this scale; switch to real columns if runs grow past a few thousand)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, company, pillar, secondary, final_score, sfs, engine, created_at, "
            "summary, parent_group, result_json FROM runs ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        overridden = {r[0] for r in con.execute("SELECT DISTINCT run_id FROM overrides").fetchall()}
    out = []
    for r in rows:
        item = {"id": r[0], "company": r[1], "pillar": r[2],
                "secondary": [s for s in (r[3] or "").split(",") if s],
                "final_score": r[4], "sfs_relevant": bool(r[5]),
                "engine": r[6], "created_at": r[7],
                "summary": r[8] or "", "parent_group": r[9] or "",
                "overridden": r[0] in overridden}
        try:
            res = json.loads(r[10] or "{}")
            p, sc = res.get("profile", {}) or {}, res.get("score", {}) or {}
            dims = sc.get("dimensions", {}) or {}
            facts = res.get("facts", []) or []
            item.update({
                "hq": str(p.get("hq", "")),
                "funding": str(p.get("funding", "")),
                "founded_year": str(p.get("founded_year", "")),
                "stage": str(p.get("Development stage of your solution", "")),
                "siemens_fit": dims.get("siemens_fit", ""),
                "traction": dims.get("traction", ""),
                "evidence_count": len(facts),
                "verified_facts": sum(1 for f in facts if f.get("verified") in (True, "True", "true")),
                "confidence": (res.get("routing", {}) or {}).get("confidence", ""),
                "trend": (res.get("trend", {}) or {}).get("label", ""),
                "founders": ", ".join(f.get("name", "") for f in
                                      (res.get("deep_profile", {}) or {}).get("founders", [])
                                      if isinstance(f, dict))[:120],
                # Everything the browser needs to re-score this row under a reviewer's own
                # weighting (ui/src/scoring). Eight numbers, parsed from JSON already being
                # read here, so the grid can answer "who would we be talking to under my
                # priorities" without a round trip per row.
                "dimensions": {k: v for k, v in dims.items() if isinstance(v, (int, float))},
                "data_completeness": sc.get("data_completeness", 0),
                "fit_aligned": bool((res.get("fit", {}) or {}).get("aligned")),
            })
        except Exception:
            pass
        out.append(item)
    return out


def get_run(run_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT result_json, created_at FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        return None
    res = json.loads(row[0])
    res["run_id"] = run_id
    res["run_created_at"] = row[1]        # lets the UI show freshness + Refresh
    return res


def latest_run_for_company(company: str) -> dict | None:
    """Most recent stored evaluation for a company (case-insensitive exact name match).
    Powers the cache-first evaluate flow."""
    if not str(company).strip():
        return None
    with _conn() as con:
        row = con.execute(
            "SELECT id, created_at, result_json FROM runs WHERE LOWER(company)=LOWER(?) "
            "ORDER BY id DESC LIMIT 1", (company.strip(),)).fetchone()
    if not row:
        return None
    res = json.loads(row[2])
    res["run_id"] = row[0]
    res["run_created_at"] = row[1]
    return res


def latest_run_for_alias(name: str) -> dict | None:
    """Cache-first lookup that also resolves the strings a company is *known by*.

    `latest_run_for_company` matches the stored name exactly, which means it misses its own
    writes: /api/evaluate searches on what the reviewer typed while save_run files the run
    under the name the pipeline resolved. Aliases close that gap; the exact-name match stays
    as the fallback so runs written before company_aliases existed are still served.
    """
    key = _norm_alias(name)
    if not key:
        return None
    with _conn() as con:
        row = con.execute(
            "SELECT r.id, r.created_at, r.result_json FROM company_aliases a "
            "JOIN companies c ON c.id = a.company_id "
            "JOIN runs r ON r.id = c.latest_run_id "
            "WHERE a.alias = ?", (key,)).fetchone()
    if row:
        res = json.loads(row[2])
        res["run_id"] = row[0]
        res["run_created_at"] = row[1]
        return res
    return latest_run_for_company(name)


# ------------------------------------------------- per-reviewer searches & sessions
def record_search(user: dict, query: str, *, company_name: str = "", company_id: int | None = None,
                  run_id: int | None = None, served_from: str = "fresh") -> None:
    """Log one evaluate call against the signed-in principal.

    Uploads to S3 like the other write paths: unlike web_cache this is an audit record and
    cannot be regenerated, so it must not sit only on a container's local disk waiting for
    someone else to trigger a save_run.
    """
    oid = str((user or {}).get("oid", "")).strip()
    if not oid:
        return
    with _conn() as con:
        con.execute(
            "INSERT INTO searches (user_oid, user_upn, query, company_id, company_name, run_id, "
            "served_from, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (oid, str((user or {}).get("upn", "") or ""), str(query)[:200], company_id,
             str(company_name or "")[:200], run_id, served_from, _now()))
    _upload_to_s3()


def record_session(user: dict) -> None:
    """One row per successful sign-in — see the schema comment on `sessions`."""
    oid = str((user or {}).get("oid", "")).strip()
    if not oid:
        return
    with _conn() as con:
        con.execute("INSERT INTO sessions (user_oid, user_upn, started_at) VALUES (?,?,?)",
                    (oid, str((user or {}).get("upn", "") or ""), _now()))
    _upload_to_s3()


def list_user_runs(user_oid: str, limit: int = 200) -> list[dict]:
    """The reviewer's own list: one grid row per company THEY searched, newest search first.

    Built by intersecting `searches` with `list_runs` rather than by a join, so the grid rows
    stay byte-identical to the ones Explore already renders and there is one place that
    decides what a grid row contains.
    """
    oid = str(user_oid or "").strip()
    if not oid:
        return []
    with _conn() as con:
        rows = con.execute(
            "SELECT company_name, MAX(created_at) FROM searches "
            "WHERE user_oid=? AND company_name<>'' GROUP BY LOWER(company_name) "
            "ORDER BY MAX(created_at) DESC LIMIT ?", (oid, limit)).fetchall()
    if not rows:
        return []
    order = {str(r[0]).lower(): i for i, r in enumerate(rows)}
    searched_at = {str(r[0]).lower(): r[1] for r in rows}
    mine = []
    seen = set()
    # list_runs is per-RUN and a re-evaluated company has several; this list is per-company, so
    # take the first (newest — list_runs is id DESC) and drop the rest. History stays in the DB
    # and is still reachable from the profile.
    for item in list_runs(limit=max(limit * 5, 500)):
        k = str(item.get("company", "")).lower()
        if k in order and k not in seen:
            seen.add(k)
            item["searched_at"] = searched_at[k]
            mine.append(item)
    mine.sort(key=lambda i: order[str(i["company"]).lower()])
    return mine


def admin_overview(recent_days: int = 30, top: int = 10) -> dict:
    """Usage metrics for the admin dashboard. One connection, small aggregate queries."""
    since = (datetime.now(timezone.utc) - timedelta(days=recent_days)).isoformat(timespec="seconds")
    with _conn() as con:
        q = lambda sql, args=(): con.execute(sql, args).fetchone()[0] or 0   # noqa: E731
        sessions_total = q("SELECT COUNT(*) FROM sessions")
        sessions_recent = q("SELECT COUNT(*) FROM sessions WHERE started_at>=?", (since,))
        searches_total = q("SELECT COUNT(*) FROM searches")
        searches_recent = q("SELECT COUNT(*) FROM searches WHERE created_at>=?", (since,))
        users_total = q("SELECT COUNT(DISTINCT user_oid) FROM sessions")
        users_recent = q("SELECT COUNT(DISTINCT user_oid) FROM searches WHERE created_at>=?", (since,))
        companies_searched = q("SELECT COUNT(DISTINCT LOWER(company_name)) FROM searches "
                               "WHERE company_name<>''")
        cache_hits = q("SELECT COUNT(*) FROM searches WHERE served_from='cache'")
        runs_total = q("SELECT COUNT(*) FROM runs")
        companies_total = q("SELECT COUNT(*) FROM companies")
        top_companies = [{"company": r[0], "searches": r[1]} for r in con.execute(
            "SELECT company_name, COUNT(*) c FROM searches WHERE company_name<>'' "
            "GROUP BY LOWER(company_name) ORDER BY c DESC, company_name LIMIT ?", (top,)).fetchall()]
        per_user = [{"upn": r[0] or r[1], "oid": r[1], "searches": r[2], "companies": r[3],
                     "last_seen": r[4]} for r in con.execute(
            "SELECT MAX(user_upn), user_oid, COUNT(*), COUNT(DISTINCT LOWER(company_name)), "
            "MAX(created_at) FROM searches GROUP BY user_oid "
            "ORDER BY COUNT(*) DESC LIMIT ?", (top,)).fetchall()]
    return {
        "window_days": recent_days,
        "sessions": {"total": sessions_total, "recent": sessions_recent},
        "searches": {"total": searches_total, "recent": searches_recent},
        "users": {"total": users_total, "recent": users_recent},
        "companies": {"searched": companies_searched, "evaluated": companies_total},
        "runs": runs_total,
        # The share of searches answered from the database instead of the pipeline — the
        # number that says whether the shared cache is actually earning its keep.
        "cache_hit_rate": round(cache_hits / searches_total, 3) if searches_total else 0.0,
        "top_companies": top_companies,
        "per_user": per_user,
    }


def list_searches(limit: int = 200) -> list[dict]:
    """The full activity log, newest first. Admin-only — see require_admin in api/auth.py."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, user_oid, user_upn, query, company_name, run_id, served_from, created_at "
            "FROM searches ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
    return [{"id": r[0], "user_oid": r[1], "user_upn": r[2] or "", "query": r[3],
             "company": r[4] or "", "run_id": r[5], "served_from": r[6] or "",
             "created_at": r[7]} for r in rows]


# ------------------------------------------------------------------- saved views
def list_views(user_oid: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT name, columns_json, filters_json, updated_at FROM saved_views "
            "WHERE user_oid=? ORDER BY updated_at DESC", (str(user_oid),)).fetchall()
    out = []
    for r in rows:
        try:
            out.append({"name": r[0], "columns": json.loads(r[1]),
                        "filters": json.loads(r[2]), "updated_at": r[3]})
        except ValueError:
            continue
    return out


def save_view(user_oid: str, name: str, columns: list, filters: dict) -> dict:
    """Upsert by (owner, name) — saving over a name replaces that view, as the UI implies."""
    name = str(name).strip()[:80]
    ts = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO saved_views (user_oid, name, columns_json, filters_json, created_at, "
            "updated_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_oid, name) DO UPDATE SET columns_json=excluded.columns_json, "
            "filters_json=excluded.filters_json, updated_at=excluded.updated_at",
            (str(user_oid), name, json.dumps(columns), json.dumps(filters), ts, ts))
    _upload_to_s3()
    return {"name": name, "columns": columns, "filters": filters, "updated_at": ts}


def delete_view(user_oid: str, name: str) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM saved_views WHERE user_oid=? AND name=?",
                          (str(user_oid), str(name).strip()))
        deleted = cur.rowcount > 0
    if deleted:
        _upload_to_s3()
    return deleted


def delete_run(run_id: int) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM runs WHERE id=?", (run_id,))
        deleted = cur.rowcount > 0
    if deleted:
        _upload_to_s3()
    return deleted


# ----------------------------------------------------------------- reviewer overrides
def add_override(run_id: int, new_pillar: str, reason: str,
                 evidence_note: str = "", *, reviewer: dict | None = None) -> dict | None:
    """Record a reviewer override of the routing decision. The automated result stays
    untouched in result_json (auditability); the runs row reflects the effective pillar.

    `reviewer` is the authenticated principal (see api/auth.py), not a name the caller
    chose. It is keyword-only and optional so the scripts and tests that drive the engine
    without a web request keep working; those rows are then indistinguishable from the
    pre-SSO ones, which is correct — nobody verified them either.
    """
    r = reviewer or {}
    with _conn() as con:
        row = con.execute("SELECT pillar FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        prev = row[0]
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute(
            "INSERT INTO overrides (run_id, prev_pillar, new_pillar, reason, evidence_note, "
            "reviewer, reviewer_oid, reviewer_upn, reviewer_tid, reviewer_source, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, prev, new_pillar, reason, evidence_note, r.get("name", ""),
             r.get("oid"), r.get("upn"), r.get("tid"), r.get("source"), ts))
        con.execute("UPDATE runs SET pillar=? WHERE id=?", (new_pillar, run_id))
    _upload_to_s3()
    return {"run_id": run_id, "prev_pillar": prev, "new_pillar": new_pillar,
            "reason": reason, "evidence_note": evidence_note,
            "reviewer": r.get("name", ""), "verified": r.get("source") == "entra",
            "created_at": ts}


def list_overrides(run_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT prev_pillar, new_pillar, reason, evidence_note, reviewer, created_at, "
            "reviewer_oid, reviewer_source FROM overrides WHERE run_id=? ORDER BY id",
            (run_id,)).fetchall()
    return [{"prev_pillar": r[0], "new_pillar": r[1], "reason": r[2],
             "evidence_note": r[3] or "", "reviewer": r[4] or "", "created_at": r[5],
             "reviewer_oid": r[6] or "",
             # Only an Entra-issued identity counts as verified. Rows written by the stub,
             # by a script, or before sign-in existed all read as unverified.
             "verified": r[7] == "entra"}
            for r in rows]


# ------------------------------------------------------------------ admins

def list_admins() -> list[dict]:
    """Admins granted in-app, oldest first. Read-only, so no S3 upload."""
    with _conn() as con:
        rows = con.execute(
            "SELECT upn, granted_by, granted_at, note FROM admins ORDER BY granted_at, upn"
        ).fetchall()
    return [{"upn": r[0], "granted_by": r[1], "granted_at": r[2], "note": r[3] or "",
             "source": "db"} for r in rows]


def admin_upns_from_db() -> set[str]:
    """Just the names, lowercased, for the is_admin check on every admin request.

    Separate from list_admins so the hot path does not build dicts it throws away, and so a
    caller that only needs membership cannot accidentally leak the grant metadata.
    """
    with _conn() as con:
        rows = con.execute("SELECT upn FROM admins").fetchall()
    return {str(r[0]).strip().lower() for r in rows if str(r[0]).strip()}


def grant_admin(upn: str, granted_by: str, note: str = "") -> dict | None:
    """Add an admin. Returns the new row, or None if that UPN already had a grant.

    Audit record, so it uploads like the other write paths — losing it would leave a
    privilege change on one container's local disk.
    """
    u = str(upn or "").strip().lower()
    if not u:
        return None
    ts = _now()
    with _conn() as con:
        existing = con.execute("SELECT 1 FROM admins WHERE upn=?", (u,)).fetchone()
        if existing:
            return None
        con.execute(
            "INSERT INTO admins (upn, granted_by, granted_at, note) VALUES (?,?,?,?)",
            (u, str(granted_by or "").strip().lower(), ts, str(note or "")[:200]))
    _upload_to_s3()
    return {"upn": u, "granted_by": str(granted_by or "").strip().lower(),
            "granted_at": ts, "note": str(note or "")[:200], "source": "db"}


def revoke_admin(upn: str) -> bool:
    """Remove an in-app grant. False if there was nothing to remove.

    Cannot touch an ADMIN_UPNS-seeded admin — those live in the environment, not here, which
    is exactly what makes them the recovery path.
    """
    u = str(upn or "").strip().lower()
    if not u:
        return False
    with _conn() as con:
        cur = con.execute("DELETE FROM admins WHERE upn=?", (u,))
        removed = cur.rowcount > 0
    if removed:
        _upload_to_s3()
    return removed
