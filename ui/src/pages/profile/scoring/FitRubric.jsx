import React from "react";
import { ScoreBar, ExtLink } from "../../../components/widgets.jsx";

export default function FitRubric({ rubric }) {
  if (!rubric) return <div className="info-box">This saved evaluation predates the evidence-based Siemens fit rubric. Refresh Data to calculate it.</div>;
  return <div className="panel fit-rubric">
    <h2>Why this startup fits Siemens</h2>
    <ScoreBar label="Siemens fit" value={rubric.score} />
    <p className="muted">{rubric.notice} · {Math.round(rubric.evidence_coverage * 100)}% of the rubric has cited evidence.</p>
    {(rubric.criteria || []).map((c) => <details key={c.id} className="rubric-criterion" open>
      <summary><strong>{c.label}</strong><span>{c.points} / {c.weight} points</span></summary>
      <p>{c.rationale}</p>
      {c.quote && <blockquote>{c.quote}</blockquote>}
      {(c.evidence || []).map((e) => <p className="muted" key={e.id}>{e.source} · {e.verified ? "Verified evidence" : "Unverified evidence; points capped"} {e.url && <ExtLink href={e.url}>Source</ExtLink>}</p>)}
      <p className="muted"><strong>Next check:</strong> {c.gap}</p>
    </details>)}
    <small className="muted">Rubric {rubric.version} · {rubric.method} · each criterion is graded 0–4, then converted to its stated points.</small>
  </div>;
}
