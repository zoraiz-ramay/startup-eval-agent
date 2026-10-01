import React from "react";
import { IxContentHeader } from "@siemens/ix-react";
import { BandScale } from "../../../components/charts.jsx";
import { ExtLink } from "../../../components/widgets.jsx";
import Section from "../Section.jsx";
import StrengthRows from "./StrengthRows.jsx";
import { MARKET_SCALES } from "./presentation.js";

/* Market: size, growth and strategic relevance, 0–5 each, 15 points in all.

   Size and growth come from a cited market figure when the research found one — drawn as a
   marker on the rubric's own bands, so a reader sees how far the figure sits from the next band —
   otherwise they are the model's judgment, capped at 2, and labelled as that. */
function Scale({ c, figure }) {
  const spec = MARKET_SCALES[c.id];
  const value = c.id === "market_size" ? figure?.eur : figure?.pct;
  return (
    <div className="market-row">
      <div className="market-row-head">
        <strong>{c.label}</strong>
        <span>{c.anchor} <span className="muted">· {c.score}/5</span>
          {c.basis === "cited_figure"
            ? <> · {c.value} {c.source_url && <ExtLink href={c.source_url}>source</ExtLink>}</>
            : <span className="muted"> · model judgment, no figure cited (max 2)</span>}</span>
      </div>
      {spec && value != null
        ? <BandScale {...spec} value={value} active={c.score} label={`${c.label}: ${c.value}, ${c.anchor}, ${c.score} of 5`} />
        : <Segments c={c} />}
    </div>
  );
}

function Segments({ c }) {
  return (
    <div className="segment-meter" role="img" aria-label={`${c.label}: ${c.anchor}, ${c.score} of 5`}>
      {[1, 2, 3, 4, 5].map((i) => <span key={i} className={i <= c.score ? "on" : ""} />)}
    </div>
  );
}

export default function MarketScorePanel({ res, detailed = false }) {
  const m = res.market;
  const header = <IxContentHeader headerTitle="Market"
    headerSubtitle="Market size, market growth and strategic relevance, 0–5 each." />;
  if (!m) {
    return <Section id="scoring-market">{header}<p className="muted" role="status">
      {res.streaming ? "Market is being assessed…"
        : res.department ? "Not scored with the market rubric on this run; the total uses the model's market number. Re-evaluate to score it."
          : "Not assessed on this run."}</p></Section>;
  }
  if (m.status !== "assessed") {
    return <Section id="scoring-market">{header}
      <p role="status"><span className="verdict unassessed">Not assessed</span> <span className="muted">{m.message}</span></p>
    </Section>;
  }
  const figures = m.figures || {};
  const relevance = m.criteria.find((c) => c.id === "strategic_relevance");
  return (
    <Section id="scoring-market">
      {header}
      <p className="section-score"><strong className="big-num">{m.points}</strong><span className="muted">/15</span>
        <span className="badge">{m.band}</span><span className="muted">counts as {m.score_0_100.toFixed(0)}/100 in the total</span></p>
      {(m.industry || m.market) && <p className="muted">Industry: {m.industry || "—"} · Market: {m.market || "—"}</p>}
      {m.criteria.filter((c) => c.id !== "strategic_relevance").map((c) =>
        <Scale key={c.id} c={c} figure={c.id === "market_size" ? figures.size : figures.growth} />)}
      {relevance && <div className="market-row">
        <div className="market-row-head"><strong>{relevance.label}</strong>
          <span>{relevance.anchor} <span className="muted">· {relevance.score}/5 · model judgment</span></span></div>
        <Segments c={relevance} />
        {relevance.areas?.length > 0 && <div>{relevance.areas.map((a) => <span key={a} className="badge">{a}</span>)}</div>}
      </div>}
      {(m.notes || []).map((n) => <p key={n} className="muted">{n}</p>)}
      {detailed && <StrengthRows criteria={m.criteria} name="Market" />}
    </Section>
  );
}
