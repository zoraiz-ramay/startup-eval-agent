import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { IxContentHeader } from "@siemens/ix-react";
import Section from "../Section.jsx";
import CriterionDetail from "./CriterionDetail.jsx";
import OpportunityDetail from "./OpportunityDetail.jsx";
import { HeatStrip, RingGauge } from "../../../components/charts.jsx";
import { CRITERION_QUESTIONS, PILLAR_ORDER, criterionNotes, pillarRows } from "./presentation.js";

const SHORT = { tool_fit: "Tool", benefit_fit: "Benefit", actionability: "Action", capability_fit: "Capability",
  need_fit: "Need", ecosystem_gap: "Gap", industry_topic_fit: "Fit", ecosystem_value: "Ecosystem",
  // Connect's criteria before rubric v2, for stored runs.
  industry_fit: "Industry", topic_fit: "Topic" };
const ROLE_PILL = { Recommended: "pill-ok", Alternative: "pill-ok", Review: "pill-warn" };
const cellId = (pillar, id) => `fit-cell-${pillar}-${id}`;
const CATALOG_LABEL = { Empower: "Siemens tools", Connect: "Xcelerator catalog entries", Collaborate: "department needs" };

/* Empower, Connect and Collaborate side by side on the Siemens Fit 0–100 scale.

   Alternatives, not parts of a whole — so a ring per route, not a pie. Each card has two kinds of
   control, kept apart because a button cannot hold buttons: its header selects the route (opening
   its opportunity below and recording it in `?pillar=`, the parameter shared links already
   carry), and each criterion cell opens that criterion's detail. Selecting a route explores it;
   the recommendation above does not change. */
function RouteCard({ r, pillar, selected, onSelect, onKey, openId, onCell }) {
  const cells = r.state === "assessed" ? (pillar.criteria || []).map((c) => ({ ...c, short: SHORT[c.id] })) : [];
  return (
    <div className={`route-card${selected ? " on" : ""}`}>
      <button id={`fit-choice-${r.name}`} type="button" className="route-card-head"
        aria-pressed={selected} aria-controls="fit-opportunity" onClick={onSelect} onKeyDown={onKey}
        aria-label={`${r.name}: ${r.value != null ? `${r.value} out of 100, ${r.role}` : r.role}${r.provisional ? ", provisional" : ""}`}>
        <RingGauge value={r.value} size={60} stroke={7} label={`${r.name} ${r.value ?? "not assessed"}`} />
        <span className="route-card-title"><strong>{r.name}</strong>
          <span className={`pill ${ROLE_PILL[r.role] || "pill-neutral"}`}>{r.role}{r.provisional ? " · provisional" : ""}</span></span>
      </button>
      {cells.length > 0
        ? <HeatStrip cells={cells} name={r.name} openId={openId} onToggle={onCell} idPrefix={`fit-cell-${r.name}`} controls="fit-criterion" />
        : <span className="route-card-empty">{r.state === "pending" ? "Assessing…" : "Not assessed"}</span>}
      {r.lowActionability && <small className="route-card-warn">Next step needs definition</small>}
      {r.state === "assessed" && r.band === "no_match" && r.provisional && <small className="muted">Against example needs</small>}
    </div>
  );
}

export default function FitComparison({ res, detailed = false }) {
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(null);                       // { pillar, id } of the opened criterion
  const rows = pillarRows(res);
  const pillars = res.assessment?.pillars || {};
  const selected = PILLAR_ORDER.includes(params.get("pillar")) ? params.get("pillar") : "Empower";
  const select = (p) => {
    if (open && open.pillar !== p) setOpen(null);
    setParams((old) => { const next = new URLSearchParams(old); next.set("pillar", p); return next; }, { replace: true });
  };
  // A criterion opens beside its own route: opening Connect's Industry also explores Connect.
  const toggle = (pillar, id) => {
    if (open?.pillar === pillar && open?.id === id) { setOpen(null); return; }
    setOpen({ pillar, id });
    if (pillar !== selected) setParams((old) => { const next = new URLSearchParams(old); next.set("pillar", pillar); return next; }, { replace: true });
  };
  const close = () => { const back = open && cellId(open.pillar, open.id); setOpen(null); document.getElementById(back)?.focus(); };
  const move = (e, i) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = rows[(i + step + rows.length) % rows.length].name;
    select(next);
    document.getElementById(`fit-choice-${next}`)?.focus();
  };
  const criteria = open ? pillars[open.pillar]?.criteria || [] : [];
  const index = criteria.findIndex((c) => c.id === open?.id);
  const fit = res.assessment?.siemens_fit;
  return (
    <Section id="scoring-routes">
      <IxContentHeader headerTitle="Siemens Fit"
        headerSubtitle={`${fit?.score != null ? `${fit.score}/100 from ${fit.winner}${fit.partial ? " · partial: not every pillar could be assessed" : ""}. `
          : "Empower, Connect and Collaborate on one 0–100 scale. "}Choose a route to explore it, or a criterion score to see how it was scored.`} />
      {/* Escape closes an opened criterion from its cell too, where focus stays while reading it. */}
      <div className="route-cards" role="group" aria-label="Compare and explore partnership routes"
        onKeyDown={(e) => { if (e.key === "Escape" && open) { e.stopPropagation(); close(); } }}>
        {rows.map((r, i) => (
          <RouteCard key={r.name} r={r} pillar={pillars[r.name]} selected={selected === r.name}
            onSelect={() => select(r.name)} onKey={(e) => move(e, i)}
            openId={open?.pillar === r.name ? open.id : null} onCell={(id) => toggle(r.name, id)} />
        ))}
      </div>
      {index >= 0 && (
        <CriterionDetail id="fit-criterion" anchorId={cellId(open.pillar, open.id)} max={3}
          context={`${open.pillar} · criterion ${index + 1} of 3`} criterion={criteria[index]}
          scale={res.assessment?.scales?.pillars?.[open.pillar]?.[open.id]}
          question={CRITERION_QUESTIONS[open.pillar]?.[open.id]}
          notes={criterionNotes(pillars[open.pillar], criteria[index])} catalogLabel={CATALOG_LABEL[open.pillar]} onClose={close} />
      )}
      <div id="fit-opportunity" aria-live="polite">
        <OpportunityDetail res={res} name={selected} row={rows.find((r) => r.name === selected)} detailed={detailed}
          onOpenCriterion={(id) => { if (!(open?.pillar === selected && open?.id === id)) toggle(selected, id); }} />
      </div>
    </Section>
  );
}
