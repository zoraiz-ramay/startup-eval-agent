import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { IxButton, IxDropdown, IxDropdownItem } from "@siemens/ix-react";
import { iconArrowRight, iconPlay, iconPlus, iconSearch } from "@siemens/ix-icons/icons";
import Icon from "../components/Icon.jsx";
import { useResearch } from "../research.jsx";
import TracxnConnection from "../components/TracxnConnection.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import DepartmentChooser from "../components/DepartmentChooser.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api.js";

export function parseStartups(text) {
  return [...new Map(text.split(/[\n;,]+/).map((s) => s.trim()).filter(Boolean).map((s) => [s.toLowerCase(), s])).values()];
}
export default function SearchHome() {
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [text, setText] = useState("");
  const [batch, setBatch] = useState(false);
  const [showSession, setShowSession] = useState(false);
  const inputRef = useRef(null);
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); inputRef.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { jobs, start } = useResearch();
  const { department, setDepartment } = useApp();
  const [departments, setDepartments] = useState([]);
  const [deptError, setDeptError] = useState("");
  useEffect(() => {
    let active = true;
    api.departments().then((r) => { if (active) setDepartments(r.departments || []); })
      .catch(() => { if (active) setDeptError("Departments could not be loaded, so a search cannot start. Reload to retry."); });
    return () => { active = false; };
  }, []);
  // A remembered department that no longer exists is no choice at all.
  const chosen = departments.some((d) => d.id === department) ? department : "";
  const nav = useNavigate();
  const names = batch ? parseStartups(text) : [text.trim()].filter(Boolean);
  const [needDept, setNeedDept] = useState(false);
  const submit = async () => {
    if (busy || !names.length || names.length > 10 || names.some((n) => n.length > 200)) return;
    if (!chosen) { setNeedDept(true); return; }
    setBusy(true); setError("");
    try {
      const rows = await start({ names, department_id: chosen });
      if (alive.current && rows.length > 1) setShowSession(true);
      if (alive.current && rows.length === 1) nav(`/startup/new?name=${encodeURIComponent(rows[0].query)}&job=${rows[0].id}`);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <div className="startup-home search-hero">
    <h1 className="search-hero-title">Explore a startup</h1>
    <p className="search-hero-sub">Find and evaluate companies against Siemens strategic needs.</p>
    <div className="search-department">
      <p className="search-step"><span className="search-step-num" aria-hidden="true">1</span>Assess for department</p>
      <DepartmentChooser departments={departments} value={chosen} disabled={busy} invalid={needDept && !chosen}
        onChange={(id) => { setDepartment(id); setNeedDept(false); }} />
    </div>
    {deptError && <ErrorBox message={deptError} />}
    {needDept && !chosen && <ErrorBox message="Choose a department before starting an evaluation." />}
    <p className="search-step"><span className="search-step-num" aria-hidden="true">2</span>Search a startup</p>
    {/* The Assess button appears once there is something to assess: an always-present button
        beside an empty field is a control that can only fail. Batch mode has its own below. */}
    <div className={`search-hero-field${!batch && text.trim() ? " has-assess" : ""}`}>
      <span className="lens"><Icon icon={iconSearch} size={18} /></span>
      <input ref={inputRef} value={text} onChange={(e) => setText(e.target.value)}
        disabled={busy} onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        placeholder={batch ? "Startup names, separated by commas…" : "e.g., Radical Dot"}
        aria-label={batch ? "Startup names or websites" : "Search a startup"} aria-describedby={batch ? "batch-help" : undefined} />
      {!batch && text.trim() && <button type="button" className="search-assess" disabled={busy} onClick={submit}>
        {busy ? "Starting…" : "Assess"}<Icon icon={iconArrowRight} size={16} /></button>}
      <button id="startup-search-options" className="batch-toggle" aria-label="Search options"
        title="Search options" aria-haspopup="menu"><Icon icon={iconPlus} size={20} /></button>
      <IxDropdown trigger="startup-search-options" placement="bottom-end">
        <IxDropdownItem label={batch ? "Single startup search" : "Mass search · up to 10 startups"}
          onClick={() => { setBatch(!batch); inputRef.current?.focus(); }} />
      </IxDropdown>
    </div>
    {batch && <div className="batch-search">
      <div className="problem-submit"><span id="batch-help" className="muted">Separate names with commas · {names.length}/10</span>
        <IxButton variant="primary" disabled={busy || !names.length || names.length > 10 || names.some((n) => n.length > 200)} onClick={submit}>
          {busy ? "Starting…" : `Evaluate ${names.length > 1 ? `${names.length} startups` : "startup"}`}</IxButton></div>
      {names.length > 10 && <ErrorBox message="Limit the batch to 10 startups." />}
    </div>}
    {names.some((n) => n.length > 200) && <ErrorBox message="Keep each startup name or website under 200 characters." />}
    {busy && !batch && <p className="muted" role="status">Starting evaluation…</p>}
    {error && <ErrorBox message={error} />}
    <TracxnConnection compact />
    {jobs.length > 0 && <details className="research-session" open={showSession} onToggle={(e) => setShowSession(e.currentTarget.open)}>
      <summary><Icon icon={iconPlay} size={14} /><span>Your research session ({jobs.length})</span></summary>
      <div className="research-list">{jobs.map((j) => <article className="panel research-item" key={j.id}>
        <div><strong>{j.query}</strong><p className="muted">{j.kind === "solve" ? "Problem search" : `Startup evaluation${j.department_id ? ` · ${departments.find((d) => d.id === j.department_id)?.label || j.department_id}` : ""}`} · {j.status}</p>
          {j.error && <ErrorBox message={j.error} />}</div>
        <Link to={j.kind === "solve" ? `/workspace?job=${j.id}` : `/startup/${j.result?.run_id || "new"}?name=${encodeURIComponent(j.query)}&job=${j.id}`}>Open research →</Link>
      </article>)}</div>
    </details>}
  </div>;
}
