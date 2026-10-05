import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { IxDropdownButton, IxDropdownItem, IxMessageBar, IxToggleButton } from "@siemens/ix-react";
import DepartmentPanel from "./DepartmentPanel.jsx";
import DepartmentRanking, { viewAs } from "./DepartmentRanking.jsx";
import FitComparison from "./FitComparison.jsx";
import FitSummary from "./FitSummary.jsx";
import MarketScorePanel from "./MarketScorePanel.jsx";
import Supplementary from "./Supplementary.jsx";
import TeamPanel from "./TeamPanel.jsx";
import TotalContribution from "./TotalContribution.jsx";
import TractionPanel from "./TractionPanel.jsx";
import { scoringNotices } from "./presentation.js";

export const VIEW_KEY = "se.scoringView.v1";

/* Summary or detailed, remembered per browser. How much of the reasoning a reviewer wants on
   screen is a reading preference, not part of the run, so it lives beside the page and never in
   the URL a reviewer shares. */
function useView() {
  const [view, setView] = useState(() => {
    try { return localStorage.getItem(VIEW_KEY) === "detailed" ? "detailed" : "summary"; } catch { return "summary"; }
  });
  const change = (next) => {
    setView(next);
    try { localStorage.setItem(VIEW_KEY, next); } catch { /* storage off: the choice lasts the visit */ }
  };
  return [view, change];
}

/* Scoring & Fit, in the order a reviewer decides: what we recommend and why, what the total is
   made of, then its components by weight — Siemens Fit (35%, as three routes), Traction (30%),
   Team & Ecosystem (20%), Market (15%) — then supporting detail. The order here and in sections.js is the same list; the rail reads the latter. */
export default function ScoringTab({ res: run, runId, onAssessment, onRefresh }) {
  const [view, setView] = useView();
  const [params, setParams] = useSearchParams();
  // `?dept=` picks which department's assessment the panels show; absent, the recommended one.
  // In the URL rather than state, so a link a reviewer shares opens on the same department.
  const res = viewAs(run, params.get("dept"));
  const selectDept = (id) => setParams((old) => { const next = new URLSearchParams(old); next.set("dept", id); return next; });
  const detailed = view === "detailed";
  const copyLink = () => { try { navigator.clipboard?.writeText(window.location.href); } catch { /* no clipboard */ } };
  const openEvidence = () => setParams((old) => { const next = new URLSearchParams(old); next.set("tab", "Evidence"); return next; });
  return (
    <>
      <div className="scoring-toolbar">
        {run.departments ? <DepartmentRanking res={run} selected={params.get("dept")} onSelect={selectDept} />
          : <DepartmentPanel res={res} runId={runId} />}
        <div className="view-toggle" role="group" aria-label="View">
          <IxToggleButton pressed={!detailed} variant="subtle-primary" onClick={() => setView("summary")}>Summary</IxToggleButton>
          <IxToggleButton pressed={detailed} variant="subtle-primary" onClick={() => setView("detailed")}>Detailed</IxToggleButton>
        </div>
        <IxDropdownButton label="Actions" variant="secondary" ariaLabelDropdownButton="Actions">
          {onRefresh && <IxDropdownItem label="Re-evaluate with fresh data" onClick={onRefresh} />}
          <IxDropdownItem label="Copy link to this view" onClick={copyLink} />
          <IxDropdownItem label="Open evidence" onClick={openEvidence} />
        </IxDropdownButton>
      </div>
      {scoringNotices(res).map((n) => (
        <IxMessageBar key={n.id} type={n.type} persistent className="scoring-notice">
          <strong>{n.title}</strong> {n.text}
        </IxMessageBar>
      ))}
      <FitSummary res={res} runId={runId} onAssessment={onAssessment} detailed={detailed} />
      <TotalContribution res={res} detailed={detailed} />
      <FitComparison res={res} runId={runId} detailed={detailed} />
      <TractionPanel res={res} runId={runId} detailed={detailed} />
      <TeamPanel res={res} />
      <MarketScorePanel res={res} detailed={detailed} />
      <Supplementary res={res} />
    </>
  );
}
