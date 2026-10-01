import React, { useState } from "react";
import { IxButton } from "@siemens/ix-react";
import { api } from "../../../api.js";
import { RingGauge } from "../../../components/charts.jsx";
import Section from "../Section.jsx";
import EvidenceList from "./EvidenceList.jsx";
import { contributions, pillarRows } from "./presentation.js";

const KEY = { traction: "var(--chart-traction)", siemens_fit: "var(--chart-fit)",
  team_ecosystem: "var(--chart-team)", market: "var(--chart-market)" };

/* The four components as tiles, colour-keyed to the total chart below. A component not scored
   says so — "pending" while the run streams, "not scored" after — never 0. */
function KpiStrip({ res }) {
  const c = contributions(res);
  return (
    <ul className="kpi-strip" aria-label="Score components">
      {c.rows.map((r) => (
        <li key={r.key} className="kpi-tile">
          <span className="kpi-label"><span className="key" style={{ background: KEY[r.key] }} />{r.label}</span>
          <strong className="kpi-value">{r.value != null ? Math.round(r.value) : <span className="muted">{res.streaming ? "pending" : "not scored"}</span>}</strong>
          <span className="muted">{r.earned != null ? `${r.earned} of ${r.max} points` : `up to ${r.max} points`}</span>
        </li>
      ))}
    </ul>
  );
}

/* The top of Scoring & Fit: one recommendation, one opportunity and one next step, beside the two
   numbers a reader looks for first. Built from the winning pillar's own statement and next step
   rather than the route's reason strings, which restate every criterion score; those stay in the
   audit disclosure of the detailed view. */
export default function FitSummary({ res, runId, onAssessment, detailed = false }) {
  const rt = res.routing || {};
  const a = res.assessment;
  const fit = a?.siemens_fit;
  const pillarRoute = rt.version === "pillar-route-v1";
  const winner = pillarRoute ? a?.pillars?.[rt.pillar] : null;
  const rows = pillarRows(res);
  const best = rows.find((r) => r.role === "Recommended")?.value;
  const alternatives = rows.filter((r) => r.role === "Alternative");
  const equal = alternatives.length > 0 && alternatives.every((r) => r.value === best);
  const others = rows.filter((r) => r.role !== "Recommended" && r.role !== "Alternative")
    .map((r) => `${r.name}: ${r.role.toLowerCase()}`);
  const total = typeof a?.total === "number" ? a.total : null;
  const next = winner?.next_step || rt.next_steps?.[0];
  return (
    <Section id="scoring-summary">
      <span id="scoring-decision" className="anchor-alias" aria-hidden="true" />
      {pillarRoute ? (
        <div className="fit-hero">
          <div className="fit-hero-text">
            <p className="fit-hero-route">
              <span className={`pill ${rt.pillar === "Defer" ? "pill-warn" : rt.pillar === "Pass" ? "pill-neutral" : "pill-ok"}`}>{rt.pillar === "Pass" || rt.pillar === "Defer" ? rt.pillar : `Recommended · ${rt.pillar}`}</span>
              {others.length > 0 && <span className="muted">{others.join(" · ")}</span>}
            </p>
            <h2 className="fit-opportunity">{winner?.statement || (rt.pillar === "Pass"
              ? "No pillar matched this department's criteria."
              : rt.pillar === "Defer" ? "Not enough to decide yet." : `${rt.pillar} is the strongest route.`)}</h2>
            {alternatives.length > 0 && <p className="muted">{alternatives.map((r) => r.name).join(" and ")} {alternatives.length > 1 ? "are" : "is"} {equal ? "an equally strong" : "also a strong"} alternative in this assessment.</p>}
            {next && <div className="next-step-box"><svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10h11M11 6l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <div><span className="eyebrow">Next step</span>{next}</div></div>}
          </div>
          <div className="fit-hero-rings">
            <figure>
              <RingGauge value={total} sub={total != null ? "of 100" : "pending"}
                center={total != null ? total.toFixed(1) : "—"}
                label={total != null ? `Total score ${total.toFixed(1)} out of 100` : "Total score pending"} />
              <figcaption className="eyebrow">Total score</figcaption>
            </figure>
            <figure>
              <RingGauge value={fit?.score ?? null} color="var(--chart-fit)"
                sub={fit?.winner ? `from ${fit.winner}` : res.streaming ? "pending" : "not assessed"}
                label={fit?.score != null ? `Siemens Fit ${fit.score} out of 100` : "Siemens Fit not available"} />
              <figcaption className="eyebrow">Siemens Fit{fit?.partial ? " · partial" : ""}</figcaption>
            </figure>
          </div>
        </div>
      ) : res.streaming ? (
        <p className="muted" role="status">The route is decided once all three pillars are assessed.</p>
      ) : <LegacyDecision rt={rt} runId={runId} onAssessment={onAssessment} />}
      {(pillarRoute || res.streaming) && <KpiStrip res={res} />}
      {pillarRoute && detailed && (
        <details className="blind"><summary>Route reasoning (audit)</summary>
          <div className="blind-body">
            {(rt.reasons || []).map((r, i) => <p key={i}>{r}</p>)}
            {rt.next_steps?.length > 1 && <ol>{rt.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>}
            <EvidenceList items={rt.evidence} />
          </div>
        </details>
      )}
    </Section>
  );
}

function LegacyDecision({ rt, runId, onAssessment }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const decide = async () => {
    setBusy(true); setError("");
    try { const result = await api.decideRun(runId);
      if (result.routing?.status === "assessed") onAssessment?.(result);
      else setError(result.routing?.message || "Recommendation unavailable. Please retry.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  if (rt.version === "llm-decision-v2" && rt.status === "assessed") {
    return <div className="fit-headline"><div>
      <span className={`pill ${rt.pillar}`}>{rt.pillar}</span> <span className="muted">Legacy model recommendation</span>
      {(rt.reasons || []).map((r, i) => <p key={i}>{r}</p>)}
      {rt.next_steps?.[0] && <p className="fit-next"><span className="eyebrow">Next step</span>{rt.next_steps[0]}</p>}
    </div></div>;
  }
  return <div>
    <p className="muted">This run predates department assessments. Assess it for a department with the department switch above, or generate a legacy recommendation.</p>
    <IxButton variant="secondary" disabled={busy || !runId} onClick={decide}>{busy ? "Assessing partnership…" : "Generate legacy recommendation"}</IxButton>
    {error && <p role="alert">{error}</p>}
  </div>;
}
