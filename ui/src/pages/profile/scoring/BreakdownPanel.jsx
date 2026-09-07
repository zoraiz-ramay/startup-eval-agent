import React, { useState } from "react";
import { ScoreBar, Radar } from "../../../components/widgets.jsx";
import WhatIfWeights from "../../../components/WhatIfWeights.jsx";
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
  const { whatIfWeights } = useApp();
  // Lifted so the radar overlay appears only while the panel is open. A second polygon beside a
  // collapsed panel would be an unexplained line on the chart — exactly the
  // mistaking-a-what-if-for-the-evaluation risk this feature has to avoid.
  const [whatIfOpen, setWhatIfOpen] = useState(false);
  const contribution = whatIfOpen ? contributionProfile(dims, whatIfWeights || DEFAULT_WEIGHTS) : null;

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
            <Radar dimensions={dims} overlay={contribution ? contribution.values : null} />
            {contribution && (
              <p className="muted" style={{ fontSize: 11.5, margin: "6px 0 0", textAlign: "center" }}>
                Solid = evidence scores · dashed = each dimension&apos;s share of the score under
                your weighting. They coincide only when all six are weighted equally; the
                engine&apos;s own weights lean on traction and Siemens fit.
              </p>
            )}
          </div>
        </div>
      </div>
      <WhatIfWeights score={score} fit={fit} routing={routing}
                     open={whatIfOpen} setOpen={setWhatIfOpen} />
    </Section>
  );
}
