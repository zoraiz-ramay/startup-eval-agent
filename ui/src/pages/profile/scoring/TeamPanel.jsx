import React, { useState } from "react";
import { IxContentHeader } from "@siemens/ix-react";
import { RadarChart } from "../../../components/charts.jsx";
import Section from "../Section.jsx";
import CriterionDetail from "./CriterionDetail.jsx";
import TeamEvidence, { EvidencePreview } from "./TeamEvidence.jsx";
import { CRITERION_QUESTIONS } from "./presentation.js";

const SHORT = { founder_experience: "Founder", domain_expertise: "Domain", external_validation: "Validation",
  strategic_network: "Network" };
const boxId = (id) => `team-box-${id}`;

/* Team & Ecosystem: four criteria, 0–5 each, 20 points in all. A radar because the four are
   facets of one team whose overall shape matters; the four boxes beside it carry each criterion's
   level in words and open its reasoning, one at a time — the same interaction as a Siemens Fit
   criterion cell. The same whatever department the run is for, so switching department reuses it. */
export default function TeamPanel({ res }) {
  const [open, setOpen] = useState(null);
  const t = res.assessment?.team_ecosystem || res.team_ecosystem;
  const header = <IxContentHeader headerTitle="Team & Ecosystem"
    headerSubtitle="Founder experience, domain expertise, external validation and strategic network, 0–5 each. Select one to see how it was scored." />;
  if (!t) {
    return <Section id="scoring-team">{header}<p className="muted" role="status">
      {res.streaming ? "Team & Ecosystem is being assessed…" : "Not assessed on this run."}</p></Section>;
  }
  if (t.status !== "assessed") {
    return <Section id="scoring-team">{header}<p role="status"><span className="verdict unassessed">Not assessed</span> <span className="muted">{t.message}</span></p></Section>;
  }
  const index = t.criteria.findIndex((c) => c.id === open);
  const close = () => { const back = open; setOpen(null); document.getElementById(boxId(back))?.focus(); };
  return (
    <Section id="scoring-team">
      {header}
      <p className="section-score"><strong className="big-num">{t.points}</strong><span className="muted">/20</span>
        <span className="badge">{t.band}</span><span className="muted">counts as {t.score_0_100}/100 in the total</span></p>
      <div className="team-chart">
        <RadarChart axes={t.criteria.map((c) => ({ label: c.label, short: SHORT[c.id], value: c.score }))} max={5} active={index}
          label={`Team and ecosystem: ${t.criteria.map((c) => `${c.label} ${c.score} of 5`).join(", ")}`} />
        <div className="team-boxes" role="group" aria-label="Team and ecosystem criteria"
          onKeyDown={(e) => { if (e.key === "Escape" && open) { e.stopPropagation(); close(); } }}>
          {t.criteria.map((c) => {
            const on = open === c.id;
            return (
              <button key={c.id} id={boxId(c.id)} type="button" className={`team-box${on ? " open" : ""}`}
                aria-expanded={on} aria-controls={on ? "team-criterion" : undefined}
                aria-label={`${c.label}: ${c.score} of 5, ${c.anchor}`} onClick={() => setOpen(on ? null : c.id)}>
                <span className="team-box-head"><strong>{c.label}</strong>
                  <span className="team-box-score">{c.score}<small>/5</small></span></span>
                <span className="strength-meter" aria-hidden="true">
                  {[1, 2, 3, 4, 5].map((i) => <span key={i} className={i <= c.score ? "on" : ""} />)}</span>
                <span className="team-box-anchor">{c.anchor}</span>
                <EvidencePreview criterion={c} res={res} />
                <span className="team-box-more" aria-hidden="true">{on ? "Hide details" : "Show details"}</span>
              </button>
            );
          })}
        </div>
      </div>
      {index >= 0 && (
        <CriterionDetail id="team-criterion" anchorId={boxId(open)} max={5} context="Team & Ecosystem"
          criterion={t.criteria[index]} scale={res.assessment?.scales?.team_ecosystem?.[open]}
          question={CRITERION_QUESTIONS.team_ecosystem[open]} onClose={close}
          evidenceView={<TeamEvidence criterion={t.criteria[index]} res={res} />} />
      )}
    </Section>
  );
}
