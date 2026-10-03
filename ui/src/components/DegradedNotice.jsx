import React from "react";

/* Which parts of this evaluation ran without the model (result.degraded, core/pipeline.py).

   A failed model call does not fail the run: each stage falls back — fit to keyword overlap, the
   profile to keyword extraction, a pillar to "unassessed". That kept pages rendering, and also hid
   the weaker answer: 11 of 52 stored runs had keyword-only fit with nothing on screen saying so.
   Saying which stage and why is what tells a reviewer to refresh rather than trust the result. */

const STAGE = {
  input: "Company lookup", enrich: "Enrichment", verification: "Fact verification",
  summary: "Summary", fit: "Siemens tool fit", profile: "Deep profile", trend: "Market trend",
  score: "Model score", pillars: "Pillar assessment", team_ecosystem: "Team & Ecosystem",
  market: "Market rubric",
};
const REASON = {
  rate_limited: "the model's rate limit was hit",
  timeout: "the model timed out",
  error: "the model call failed",
};

export default function DegradedNotice({ degraded }) {
  if (!degraded?.length) return null;
  return (
    <div className="degraded-notice" role="alert">
      <strong>Part of this evaluation ran without the model.</strong>{" "}
      Those sections used their fallback and may be thinner than usual — refresh to retry them.
      <ul>
        {degraded.map((d) => (
          <li key={`${d.stage}-${d.reason}`}>
            {STAGE[d.stage] || d.stage}: {REASON[d.reason] || REASON.error}
            {d.calls > 1 ? ` (${d.calls} calls)` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
