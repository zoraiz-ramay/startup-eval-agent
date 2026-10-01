import React from "react";
import DetailToggle from "./DetailToggle.jsx";
import EvidenceList from "./EvidenceList.jsx";

/* Criteria scored 0–5, as aligned rows: the anchor's own words, a five-step meter, and the
   reasoning behind the shared detail control. The meter carries the level for sighted readers
   and its label says it in words, so colour is never the only signal. */
export default function StrengthRows({ criteria, extra, name }) {
  return (
    <>
      <ul className="strength-rows" aria-label={`${name} criteria`}>
        {criteria.map((c) => (
          <li key={c.id} className="strength-row">
            <span className="strength-label">{c.label}</span>
            <span className="strength-meter" role="img" aria-label={`${c.label}: ${c.anchor}, level ${c.score} of 5`}>
              {[1, 2, 3, 4, 5].map((i) => <span key={i} className={i <= c.score ? "on" : ""} />)}
            </span>
            <span className="strength-anchor">{c.anchor}{extra?.(c)}</span>
            <DetailToggle title={`${c.label}: reasoning and sources`}>
              {c.rationale ? <p>{c.rationale}</p> : <p className="muted">No rationale was recorded.</p>}
              <EvidenceList items={c.evidence} />
            </DetailToggle>
          </li>
        ))}
      </ul>
      <details className="fit-method"><summary>Scoring method</summary>
        <ul>{criteria.map((c) => <li key={c.id}>{c.label}: {c.score}/5 — {c.anchor}</li>)}</ul>
      </details>
    </>
  );
}
