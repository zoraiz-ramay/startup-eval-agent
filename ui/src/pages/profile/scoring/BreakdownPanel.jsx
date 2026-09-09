import ScoreTile from "./ScoreTile.jsx";
import React from "react";
import { IxContentHeader, IxCard, IxCardContent } from "@siemens/ix-react";
import { ScoreBar, ExtLink } from "../../../components/widgets.jsx";
import Section from "../Section.jsx";
import { DIMENSION_LABELS } from "../../../scoring/index.js";

export default function BreakdownPanel({ score, busy }) {
  const current = score.version === "llm-judgment-v1" && score.status === "assessed";
  return <Section id="scoring-breakdown">
    <IxContentHeader headerTitle="Startup score breakdown" headerSubtitle="Overall startup quality and Siemens relevance, shared across departments." />
    {!current ? <p className="muted" role="status">{busy ? "Preparing startup scores…" : "Start a department assessment above to update this startup’s scores in Database."}</p> : <>
      <div className="score-headline">
        <ScoreTile label="Overall score" value={score.final_score} />
        <ScoreTile label="Siemens fit" value={score.dimensions.siemens_fit} />
        <p>{score.overall?.rationale}</p>
      </div>
      <p className="muted">These are the same Overall score and Siemens fit values shown in Database. Department fit is saved separately for each team.</p>
      <div className="fit-card-grid score-card-grid">
        {Object.entries(DIMENSION_LABELS).map(([k, label]) => <IxCard key={k}><IxCardContent>
          <ScoreBar label={label} value={score.dimensions[k]} />
          <p>{score.judgments?.[k]?.rationale}</p>
          <details><summary>Supporting evidence</summary>
            {(score.judgments?.[k]?.evidence || []).map((e, i) => <div key={`${e.id}-${i}`}><blockquote>{e.quote}</blockquote>
              <small className="muted">{e.source} {e.url && <ExtLink href={e.url}>Source</ExtLink>}</small></div>)}
          </details>
        </IxCardContent></IxCard>)}
      </div>
    </>}
  </Section>;
}
