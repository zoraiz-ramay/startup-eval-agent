import { api } from "../../../api.js";
import { ExtLink } from "../../../components/widgets.jsx";
import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import FitRubric from "./FitRubric.jsx";
import { ScoreBar } from "../../../components/widgets.jsx";
import Section from "../Section.jsx";
import SfsPanel from "./SfsPanel.jsx";
import { IxButton, IxContentHeader, IxTabs, IxTabItem } from "@siemens/ix-react";

const PILLARS = ["Empower", "Connect", "Collaborate"];

export default function ScoringTab({ res, runId, onAssessment }) {
  const [params, setParams] = useSearchParams();
  const activePillar = PILLARS.includes(params.get("pillar")) ? params.get("pillar") : "Empower";
  const setActivePillar = (p) => setParams((old) => { const next = new URLSearchParams(old); next.set("pillar", p); return next; }, { replace: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const decide = async () => {
    setBusy(true); setError("");
    try { const result = await api.decideRun(runId);
      if (result.routing?.status === "assessed") onAssessment?.(result);
      else setError(result.routing?.message || "Recommendation unavailable. Please retry.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const fit = res.fit || {}, rt = res.routing || {};

  return (
    <>
      <Section id="scoring-decision">
        <IxContentHeader headerTitle="Decision" headerSubtitle="Recommended partnership route and practical next steps, based on collected research." />
        {rt.version === "llm-decision-v2" && rt.status === "assessed" ? <>
          <p><span className={`pill ${rt.pillar}`}>{rt.pillar}</span> <span className="muted">LLM recommendation · {Math.round(rt.confidence * 100)}% confidence</span></p>
          {(rt.reasons || []).map((reason, i) => <p key={i}>{reason}</p>)}
          <h4>How to proceed</h4>
          <ol className="decision-next-steps">{(rt.next_steps || []).map((step, i) => <li key={i}>{step}</li>)}</ol>
          <details><summary>Supporting evidence</summary>{(rt.evidence || []).map((e, i) => <div key={i}><blockquote>{e.quote}</blockquote><small>{e.source} {e.url && <ExtLink href={e.url}>Source</ExtLink>}</small></div>)}</details>
        </> : <>
          <p className="muted">Generate an evidence-based recommendation for Empower, Collaborate, Connect, Pass or Defer, including what to do next.</p>
          <IxButton disabled={busy || !runId} onClick={decide}>{busy ? "Assessing partnership…" : "Generate recommendation"}</IxButton>
        </>}
        {error && <p role="alert">{error}</p>}
      </Section>

      <Section id="scoring-routes">
        <IxTabs aria-label="Partnership routes" activeTabKey={activePillar} layout="stretched"
          onTabChange={(e) => { if (PILLARS.includes(e.detail)) setActivePillar(e.detail); }}>
          {PILLARS.map((p) => <IxTabItem key={p} tabKey={p} id={`pillar-tab-${p}`} label={p} />)}
        </IxTabs>
        {PILLARS.map((p) => <div key={p} role="tabpanel" id={`pillar-panel-${p}`}
          aria-labelledby={`pillar-tab-${p}`} hidden={activePillar !== p}
          className={p === "Collaborate" ? undefined : "partnership-placeholder"}>
          {p === "Collaborate"
            ? <FitRubric res={res} runId={runId} onAssessment={onAssessment} />
            : <p className="muted">Under development</p>}
        </div>)}
      </Section>

      <Section id="scoring-portfolio">
        <h3>Siemens portfolio fit</h3>
        {rt.portfolio_stance?.label && (
          <p style={{ margin: "0 0 8px" }}>
            <span className={`verdict ${rt.portfolio_stance.competes ? "blocked" : "eligible"}`}>
              {rt.portfolio_stance.label}
            </span>{" "}
            <span className="muted" style={{ fontSize: 12.5 }}>{rt.portfolio_stance.note}</span>
          </p>
        )}
        {fit.aligned && (fit.matches || []).length ? fit.matches.map((m, i) => (
          <div key={i} style={{ marginBottom: 10 }}>
            <strong>{m.tool}</strong>
            <span className="badge">{m.division}</span>
            {m.relation && <span className="badge">{m.relation}</span>}
            <ScoreBar label="match confidence" value={m.confidence} />
            <p className="muted" style={{ margin: "3px 0 0", fontSize: 12.5 }}>{m.rationale}</p>
          </div>
        )) : <p className="muted">No tool met the fit threshold.</p>}
        <p className="muted" style={{ fontSize: 11.5, marginBottom: 0 }}>method: {fit.method || "—"}</p>
      </Section>

      <Section id="scoring-sfs"><SfsPanel rt={rt} /></Section>

    </>
  );
}
