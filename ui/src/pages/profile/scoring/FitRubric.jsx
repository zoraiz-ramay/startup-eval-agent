import ScoreTile from "./ScoreTile.jsx";
import React, { useEffect, useRef, useState } from "react";
import { IxButton, IxSelect, IxSelectItem, IxContentHeader, IxCard, IxCardContent } from "@siemens/ix-react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../../api.js";
import { ExtLink, Loading } from "../../../components/widgets.jsx";
import Section from "../Section.jsx";
import BreakdownPanel from "./BreakdownPanel.jsx";

import { sameDepartment } from "../../../scoring/department.js";

export default function FitRubric({ res, runId, onAssessment }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get("department") || "di";
  const [departments, setDepartments] = useState([]);
  const [assessment, setAssessment] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useRef(0);
  useEffect(() => {
    let active = true;
    api.departments().then((r) => { if (active) setDepartments(r.departments || []); })
      .catch(() => { if (active) setError("Department profiles could not be loaded."); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    request.current++; setBusy(false); setAssessment(null); setError("");
    return () => { request.current++; };
  }, [runId, selected]);
  const department = departments.find((d) => d.id === selected);
  const stored = res.department_assessments?.[selected];
  const fit = assessment?.department_fit || (stored?.status === "assessed" && sameDepartment(stored.department, department) && typeof stored.score === "number" ? stored : null);
  const currentScore = assessment?.score?.status === "assessed" ? assessment.score : res.score;
  const scored = currentScore?.version === "llm-judgment-v1" && currentScore.status === "assessed";
  const assess = async () => {
    if (busy || !runId || !department) return;
    const id = ++request.current; setBusy(true); setError("");
    try {
      const result = await api.assessRun(runId, selected);
      if (request.current === id) setAssessment(result);
      onAssessment?.(result);
    } catch (e) { if (request.current === id) setError(e.message); }
    finally { if (request.current === id) setBusy(false); }
  };
  return <>
    <Section id="scoring-department">
      <IxContentHeader headerTitle="Department fit" headerSubtitle="Choose a team and assess the opportunity against its needs." />
      <div className="department-selector">
        <IxSelect label="Choose your department" value={selected} disabled={busy}
          onValueChange={(e) => setParams((old) => { const next = new URLSearchParams(old); next.set("department", e.detail); return next; }, { replace: true })}>
          {departments.map((d) => <IxSelectItem key={d.id} value={d.id} label={d.label} />)}
        </IxSelect>
        {!fit || fit.status !== "assessed" || !scored ? <IxButton onClick={assess} disabled={busy || !runId || !department}>
          {busy ? "Assessing…" : fit?.status === "assessed" ? "Update startup scores" : "Assess department fit"}</IxButton> : <span className="badge">Saved to Database</span>}
      </div>
      {department && <div className="department-needs"><span className="muted">{department.demo ? "Example interests" : "Department interests"}</span>
        {department.interests.map((t) => <span className="badge" key={t}>{t}</span>)}</div>}
      {!fit && !busy && <p className="muted">Start an assessment when you’re ready. Existing startup research will be reused.</p>}
      {busy && <Loading text="Assessing the opportunity…" />}
      {(error || fit?.status === "unavailable" || assessment?.score?.status === "unavailable") && <p role="status">{error || (fit?.status === "unavailable" ? fit.message : assessment.score.message)}</p>}
      {fit?.status === "assessed" && <>
        <div className="department-summary">
          <ScoreTile label={`${department?.label} fit`} value={fit.score} />
          <div><h2>Why this startup fits {department?.label}</h2><p>{fit.summary}</p></div>
        </div>
        <div className="fit-card-grid">{(fit.criteria || []).map((c) => <IxCard key={c.id}><IxCardContent>
          <h3>{c.label}</h3><p>{c.rationale}</p>
          <details><summary>Evidence · {c.evidence?.length || 0} sources</summary>
            {(c.evidence || []).map((e, i) => <div key={`${e.id}-${i}`}><blockquote>{e.quote}</blockquote>
              <small className="muted">{e.source} {e.url && <ExtLink href={e.url}>Source</ExtLink>}</small></div>)}
          </details>
        </IxCardContent></IxCard>)}</div>
      </>}
    </Section>
    <BreakdownPanel score={assessment?.score?.status === "assessed" ? assessment.score : res.score || {}} busy={busy} />
  </>;
}
