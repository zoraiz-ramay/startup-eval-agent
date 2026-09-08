import React, { useState } from "react";
import { ScoreBar, Radar } from "../../../components/widgets.jsx";

import Section from "../Section.jsx";
import { useApp } from "../../../state.jsx";
import { contributionProfile, DEFAULT_WEIGHTS, DIMENSIONS, DIMENSION_LABELS }
  from "../../../scoring/index.js";

// Derived, not written out: these percentages used to be literals, which quietly became a claim
// the code could contradict. They are the engine's weights and say so.
const DIM_META = Object.fromEntries(
  DIMENSIONS.map((k) => [k, `${DIMENSION_LABELS[k]} (${Math.round(DEFAULT_WEIGHTS[k])}%)`]),
);

/* The six dimensions, the radar, and the what-if — one section, because they are one question.
   The radar used to sit in a second column beside a column of unrelated panels; in a single-column
   reading order that put it a screen away from the bars it plots. */
export default function BreakdownPanel({ score, fit, routing }) {
  const dims = score.dimensions || {};

  return (
    <Section id="scoring-breakdown" className="">
      <div className="panel">
        <h3>Score breakdown</h3>
        <div className="score-split">
          <div>
            {Object.entries(DIM_META).map(([k, label]) =>
              k in dims ? <ScoreBar key={k} label={label} value={dims[k]} /> : null)}
            <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
              Raw {score.raw_score} × data confidence {score.data_confidence} (completeness{" "}
              {Math.round((score.data_completeness || 0) * 100)}%) ={" "}
              <strong>{Number(score.final_score || 0).toFixed(0)}</strong>.
              Effective traction {score.effective_traction} (verified {score.verified_customers} /
              unverified {score.unverified_customers}).
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <Radar dimensions={dims} />
          </div>
        </div>
      </div>
    </Section>
  );
}
