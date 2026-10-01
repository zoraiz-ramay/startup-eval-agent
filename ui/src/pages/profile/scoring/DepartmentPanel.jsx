import React, { useEffect, useRef, useState } from "react";
import { IxButton } from "@siemens/ix-react";
import { useNavigate } from "react-router-dom";
import { api } from "../../../api.js";
import { Loading } from "../../../components/widgets.jsx";
import DepartmentPicker from "../../../components/DepartmentPicker.jsx";
import ErrorBox from "../../../components/ErrorBox.jsx";

/* The department row: which department this run was assessed for, and the switch to another.

   Each department's result is its own saved run. Switching opens that run; when the department
   has none at the current rubric and catalog version, the page offers to create one — it never
   shows another department's scores under this department's name. */
export default function DepartmentPanel({ res, runId }) {
  const nav = useNavigate();
  const dep = res.department;
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [target, setTarget] = useState(dep?.id || "");
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    setTarget(dep?.id || "");
    if (!runId) return undefined;
    let active = true;
    api.runDepartments(runId).then((r) => { if (active) setInfo(r); })
      .catch(() => { if (active) setError("Saved department runs could not be loaded."); });
    return () => { active = false; };
  }, [runId, dep?.id]);
  const departments = info?.departments || [];
  const choice = departments.find((d) => d.id === target);
  const open = (id) => nav(`/startup/${id}?tab=Scoring+%26+Fit`);
  const change = (id) => {
    setTarget(id); setError("");
    const d = departments.find((x) => x.id === id);
    if (d && d.current && d.run_id && d.run_id !== runId) open(d.run_id);
  };
  const assess = async () => {
    setBusy(true); setError("");
    try {
      const run = await api.assessDepartment(runId, target);
      if (alive.current && run?.run_id) open(run.run_id);
    } catch (e) { if (alive.current) setError(e.message); }
    finally { if (alive.current) setBusy(false); }
  };
  const other = choice && target !== dep?.id;
  return (
    <div className="fit-context" id="scoring-department">
      <div className="fit-context-row">
        {!dep && <span className="muted" role="status">Legacy run: assessed before departments existed.</span>}
        {runId && (info ? <DepartmentPicker departments={departments} value={target} disabled={busy} label="Department" onChange={change} />
          : !error && <Loading text="Loading saved department runs…" />)}
        {other && (!choice.current || !choice.run_id) &&
          <IxButton onClick={assess} disabled={busy}>{busy ? "Assessing…" : `Assess for ${choice.label}`}</IxButton>}
      </div>
      {!dep && <p className="muted">It stays as history. Assess it for a department to get Siemens Fit, a total and a route.</p>}
      {other && !choice.run_id && !busy &&
        <p className="muted">No saved run for {choice.label} yet. Assessing reuses this startup's research and saves a new run for that department.</p>}
      {other && choice.run_id && !choice.current && !busy &&
        <p className="muted">{choice.label} has an older run from a previous rubric or catalog version. Assess again for a current result; the older run stays as history.</p>}
      {busy && <Loading text="Assessing Siemens Fit for the department…" />}
      {error && <ErrorBox message={error} />}
    </div>
  );
}
