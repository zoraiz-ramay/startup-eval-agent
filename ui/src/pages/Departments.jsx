import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { ScoreBar, Loading } from "../components/widgets.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

export default function Departments() {
  const [departments, setDepartments] = useState([]);
  const [selected, setSelected] = useState("");
  const [board, setBoard] = useState(null);
  const [company, setCompany] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.departments().then((r) => { setDepartments(r.departments); setSelected(r.departments[0]?.id || ""); }).catch((e) => setError(e.message)); }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true; setBoard(null); setError("");
    api.department(selected).then((r) => { if (active) setBoard(r); }).catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [selected]);
  const mutate = async (name, remove = false) => {
    setBusy(true); setError("");
    try {
      await (remove ? api.removeDepartmentCompany(selected, name) : api.addDepartmentCompany(selected, name));
      setBoard(await api.department(selected)); setCompany("");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <div>
    <h1 className="page-title">Department interests</h1>
    <p className="muted">Build a shortlist and compare startups against the needs of a business unit.</p>
    <label>Business unit <select value={selected} disabled={busy} onChange={(e) => setSelected(e.target.value)}>
      {departments.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
    </select></label>
    {error && <ErrorBox message={error} />}
    {!board && !error && <Loading text="Loading department interests…" />}
    {board && <>
      {board.demo && <div className="info-box"><strong>Demo interest profile</strong> · These example industries are placeholders, not approved Siemens department priorities.</div>}
      <div className="panel"><h2>{board.label}</h2><div className="problem-source-status">{board.interests.map((t) => <span className="badge" key={t}>{t}</span>)}</div>
        <p className="muted">Interest score: 60% stated-interest coverage + 40% Siemens fit. This screening score does not change the company’s canonical evaluation.</p>
        <form onSubmit={(e) => { e.preventDefault(); if (company.trim() && !busy) mutate(company.trim()); }} className="department-add">
          <label>Add a startup <input value={company} maxLength={200} onChange={(e) => setCompany(e.target.value)} placeholder="Company name" /></label>
          <button className="btn" disabled={busy || !company.trim()}>Add to shortlist</button>
        </form>
      </div>
      {!board.companies.length && <p className="muted">No startups on this shortlist yet. Add one above; evaluate it to see an evidence-based score.</p>}
      <div className="solution-grid">{board.companies.map((c) => <article className="panel" key={c.company}>
        <h3>{c.company}</h3>
        {c.assessment.score != null ? <ScoreBar label="Department interest score" value={c.assessment.score} /> : <p className="muted">{c.assessment.status === "refresh_required" ? "Refresh the evaluation to apply the new Siemens fit rubric." : "Not evaluated yet"}</p>}
        <p>Matched interests: {c.assessment.matched.join(", ") || "None evidenced in the company summary"}</p>
        <p className="muted">Still to establish: {c.assessment.missing.join(", ") || "—"}</p>
        <div className="solution-actions"><Link to={`/startup/${c.run_id || "new"}?name=${encodeURIComponent(c.company)}`}>{c.run_id ? "Open evaluation" : "Evaluate startup"} →</Link>
          {c.can_remove && <button className="tool-btn" disabled={busy} onClick={() => mutate(c.company, true)} aria-label={`Remove ${c.company}`}>Remove</button>}</div>
      </article>)}</div>
    </>}
  </div>;
}
