"""SQLite persistence for evaluation runs (replaces session-only history).

Stored per run: summary columns for fast listing + the full result JSON blob.
DB lives at DATA_DIR/runs.db (override with RUNS_DB).
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
from datetime import datetime, timezone

from core.config import BASE_DIR

DB_PATH = os.getenv("RUNS_DB", str(pathlib.Path(BASE_DIR) / "runs.db"))

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
CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_id);
CREATE INDEX IF NOT EXISTS idx_facts_run ON evidence_facts(run_id);
"""


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    # lightweight migrations for DBs created before these columns existed
    for col, typ in (("summary", "TEXT"), ("parent_group", "TEXT"), ("company_id", "INTEGER")):
        try:
            con.execute(f"ALTER TABLE runs ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass                                   # column already present
    return con


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


def save_run(result: dict) -> int:
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
        # normalized persistence of everything the pipeline fetched
        cid = _upsert_company(con, result, run_id)
        con.execute("UPDATE runs SET company_id=? WHERE id=?", (cid, run_id))
        _replace_children(con, cid, run_id, result)
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


def delete_run(run_id: int) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM runs WHERE id=?", (run_id,))
        return cur.rowcount > 0


# ----------------------------------------------------------------- reviewer overrides
def add_override(run_id: int, new_pillar: str, reason: str,
                 evidence_note: str = "", reviewer: str = "") -> dict | None:
    """Record a reviewer override of the routing decision. The automated result stays
    untouched in result_json (auditability); the runs row reflects the effective pillar."""
    with _conn() as con:
        row = con.execute("SELECT pillar FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        prev = row[0]
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute(
            "INSERT INTO overrides (run_id, prev_pillar, new_pillar, reason, evidence_note, "
            "reviewer, created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, prev, new_pillar, reason, evidence_note, reviewer, ts))
        con.execute("UPDATE runs SET pillar=? WHERE id=?", (new_pillar, run_id))
    return {"run_id": run_id, "prev_pillar": prev, "new_pillar": new_pillar,
            "reason": reason, "evidence_note": evidence_note,
            "reviewer": reviewer, "created_at": ts}


def list_overrides(run_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT prev_pillar, new_pillar, reason, evidence_note, reviewer, created_at "
            "FROM overrides WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [{"prev_pillar": r[0], "new_pillar": r[1], "reason": r[2],
             "evidence_note": r[3] or "", "reviewer": r[4] or "", "created_at": r[5]}
            for r in rows]
