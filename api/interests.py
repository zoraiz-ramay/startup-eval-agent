"""Department shortlists with replaceable database-backed demo interest profiles."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import Principal, current_user, require_admin
from api import store, workspace

router = APIRouter(prefix="/api/departments", tags=["departments"])
DEMO = [
    ("di", "Digital Industries", ["automation", "digital twin", "manufacturing", "inspection", "industrial software"]),
    ("si", "Smart Industries", ["buildings", "energy", "grid", "electrification", "storage"]),
    ("mobility", "Siemens Mobility", ["rail", "transport", "signalling", "fleet", "maintenance"]),
]


def _db():
    con = store._conn()
    con.executescript('''CREATE TABLE IF NOT EXISTS department_profiles (
      id TEXT PRIMARY KEY, label TEXT NOT NULL, interests TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE IF NOT EXISTS department_shortlists (
      department_id TEXT NOT NULL, company TEXT NOT NULL, added_by TEXT NOT NULL,
      PRIMARY KEY(department_id, company));''')
    con.executemany("INSERT OR IGNORE INTO department_profiles VALUES (?,?,?,1)",
                    [(key, label, json.dumps(terms)) for key, label, terms in DEMO])
    # Update only the mock labels; preserve configured department profiles.
    con.executemany("UPDATE department_profiles SET label=? WHERE id=? AND is_demo=1",
                    [(label, key) for key, label, _ in DEMO])
    con.commit()
    return con


class ProfileBody(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    interests: list[str] = Field(..., min_length=1, max_length=30)


class CompanyBody(BaseModel):
    company: str = Field(..., min_length=1, max_length=200)


def interest_score(run, profile):
    if not run:
        return {"score": None, "matched": [], "missing": profile["interests"], "status": "not_evaluated"}
    text = (str(run.get("summary", "")) + " " + str(run.get("profile", {}).get("short_description", ""))).casefold()
    terms = profile["interests"]
    matched = [t for t in terms if t.casefold() in text]
    # Relevance is deliberately separate from the canonical score and admission criteria.
    relevance = 100 * len(matched) / len(terms) if terms else 0
    base = run.get("score", {}).get("dimensions", {}).get("siemens_fit")
    if base is None: base = run.get("fit", {}).get("rubric", {}).get("score")
    return {"score": round(.6 * relevance + .4 * base, 1) if base is not None else None,
        "relevance": round(relevance, 1), "siemens_fit": base, "matched": matched,
        "missing": [t for t in terms if t not in matched], "status": "assessed" if base is not None else "refresh_required",
        "formula": "60% stated-interest coverage + 40% evidence-based Siemens fit",
        "method": "explicit term matching; screening aid, not semantic proof"}


@router.get("")
def profiles(user: Principal = Depends(current_user)):
    with _db() as con:
        rows = con.execute("SELECT * FROM department_profiles ORDER BY CASE id WHEN 'di' THEN 0 WHEN 'si' THEN 1 WHEN 'mobility' THEN 2 ELSE 3 END, id").fetchall()
    return {"departments": [{"id": r[0], "label": r[1], "interests": json.loads(r[2]), "demo": bool(r[3])} for r in rows]}


@router.put("/{department_id}")
def configure(department_id: str, body: ProfileBody, user: Principal = Depends(require_admin)):
    terms = list(dict.fromkeys(t.strip() for t in body.interests if t.strip()))
    if not terms or any(len(t) > 100 for t in terms):
        raise HTTPException(422, "Provide interests of 1–100 characters.")
    with _db() as con:
        if not con.execute("SELECT 1 FROM department_profiles WHERE id=?", (department_id,)).fetchone():
            raise HTTPException(404, "Unknown department")
        con.execute("UPDATE department_profiles SET label=?,interests=?,is_demo=0 WHERE id=?",
                    (body.label, json.dumps(terms), department_id))
    store._upload_to_s3()
    return {"updated": department_id}


@router.get("/{department_id}")
def board(department_id: str, user: Principal = Depends(current_user)):
    profile = next((p for p in profiles(user)["departments"] if p["id"] == department_id), None)
    if not profile:
        raise HTTPException(404, "Unknown department")
    with _db() as con:
        rows = con.execute("SELECT company,added_by FROM department_shortlists WHERE department_id=? ORDER BY company", (department_id,)).fetchall()
    companies = []
    for name, added_by in rows:
        run = workspace.private_latest(user.oid, name) or store.latest_run_for_company(name)
        companies.append({"company": name, "can_remove": added_by == user.oid,
                          "run_id": run.get("run_id") if run else None,
                          "assessment": interest_score(run, profile)})
    return {**profile, "companies": companies}


@router.post("/{department_id}/companies")
def add(department_id: str, body: CompanyBody, user: Principal = Depends(current_user)):
    if not any(p["id"] == department_id for p in profiles(user)["departments"]):
        raise HTTPException(404, "Unknown department")
    name = body.company.strip()
    if not name:
        raise HTTPException(422, "Provide a company name")
    with _db() as con:
        con.execute("INSERT OR IGNORE INTO department_shortlists VALUES (?,?,?)", (department_id, name, user.oid))
    store._upload_to_s3()
    return {"added": name}


@router.delete("/{department_id}/companies/{company}")
def remove(department_id: str, company: str, user: Principal = Depends(current_user)):
    with _db() as con:
        cur = con.execute("DELETE FROM department_shortlists WHERE department_id=? AND company=? AND added_by=?",
                          (department_id, company, user.oid))
        if not cur.rowcount:
            raise HTTPException(404, "Only the reviewer who added this entry can remove it.")
    store._upload_to_s3()
    return {"deleted": company}
