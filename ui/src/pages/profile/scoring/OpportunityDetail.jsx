import React from "react";
import { iconBuilding1, iconBuildingBlock, iconBulb, iconConnections, iconGlobe, iconRocket, iconTrendUpward } from "@siemens/ix-icons/icons";
import ExpandableList from "../../../components/ExpandableList.jsx";
import Icon from "../../../components/Icon.jsx";
import { ExtLink } from "../../../components/widgets.jsx";
import PillarMethod from "./PillarMethod.jsx";
import { opportunity } from "./presentation.js";

const MAX_ITEMS = 3;
const ICONS = { "Startup activity": iconRocket, "Startup offering": iconRocket, "Startup capability": iconRocket,
  "Siemens tool": iconBuildingBlock, "Xcelerator industry & topic": iconGlobe, "Department needs": iconBuilding1, "Potential benefit": iconTrendUpward, "Ecosystem audience": iconConnections,
  "Proposed pilot": iconBulb };
const RELATION_PILL = { complement: "pill-ok", integration: "pill-ok", substitute: "pill-warn" };

/* A term or catalog entry: what it is (the tag), and in the detailed view where it came from — the
   sentence a startup term was grounded in, or the catalog's own description of a Siemens entry. */
function Item({ item, detailed }) {
  return (
    <li className="opp-item">
      <span className="opp-item-top">
        <span className="opp-item-text">{item.url && !item.quote ? <ExtLink href={item.url}>{item.text}</ExtLink> : item.text}</span>
        {item.tag && <span className="kind-tag">{item.tag}</span>}
      </span>
      {item.verified && <span className="tool-verified" title="A web search found this as a Siemens offering">Verified Siemens offering</span>}
      {item.detail && <span className="opp-item-detail">{item.detail}</span>}
      {detailed && item.quote && <span className="opp-item-detail">“{item.quote.slice(0, 110)}{item.quote.length > 110 ? "…" : ""}”</span>}
    </li>
  );
}

function Node({ node, step, detailed }) {
  const items = node.items || [];
  return (
    <div className="opp-node">
      <span className="opp-node-head">
        <span className="opp-node-icon"><Icon icon={ICONS[node.label]} size={16} /></span>
        <span><span className="opp-step">Step {step}</span><strong>{node.label}</strong></span>
      </span>
      <p className="opp-hint">{node.hint}</p>
      <ExpandableList items={items} max={MAX_ITEMS} className="opp-items" itemKey={(t) => t.text}
        renderItem={(t) => <Item item={t} detailed={detailed} />} />
      {node.statement && <p className="opp-statement">{node.statement}</p>}
      {!items.length && !node.statement && <p className="opp-empty">{node.empty}</p>}
    </div>
  );
}

/* An arrow for a proposed link, a dashed line with no head for "no supported link" — the shape
   says which, not only the words under it. */
function Connector({ gap, text }) {
  return (
    <span className="opp-connector" aria-hidden="true">
      <svg width="44" height="14" viewBox="0 0 44 14">
        <path d={gap ? "M2 7h40" : "M2 7h36M32 2l6 5-6 5"} fill="none" stroke="currentColor" strokeWidth="1.6"
          strokeDasharray={gap ? "3 4" : undefined} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <small>{text}</small>
    </span>
  );
}

/* Empower keeps what used to be a separate portfolio section: the other Siemens tools the
   startup relates to, with their relation. Their old match confidence is a different, older
   measure than the pillar rubric, so it is labelled as such. */
function OtherTools({ res }) {
  const matches = res.fit?.matches || [];
  const stance = res.routing?.portfolio_stance;
  if (!matches.length && !stance?.label) return null;
  return (
    <section className="opp-other" aria-labelledby="other-tools">
      <h4 id="other-tools">Other Siemens tools</h4>
      {stance?.label && <p><span className={`verdict ${stance.competes ? "blocked" : "eligible"}`}>{stance.label}</span> <span className="muted">{stance.note}</span></p>}
      <ul className="tool-cards">{matches.map((m, i) => (
        <li key={`${m.tool}-${i}`} className="tool-card">
          <span className="tool-card-head"><strong>{m.tool}</strong>
            {m.division && <span className="kind-tag">{m.division}</span>}
            {m.relation && <span className={`pill ${RELATION_PILL[m.relation] || "pill-neutral"}`}>{m.relation}</span>}</span>
          {m.rationale && <p>{m.rationale}</p>}
          {typeof m.confidence === "number" && <small className="muted">Earlier portfolio-match confidence {m.confidence}/100 · not part of the pillar rubric</small>}
        </li>))}</ul>
    </section>
  );
}

export default function OpportunityDetail({ res, name, row, detailed = false, onOpenCriterion }) {
  const pillar = res.assessment?.pillars?.[name];
  if (!row || row.state === "pending") return <div className="opp-skeleton" role="status" aria-label={`${name} is being assessed`}><span /><span /><span /></div>;
  if (row.state === "legacy") return <p className="muted" role="status">Legacy run: routes are assessed for a department. Assess this run for a department above.</p>;
  if (row.state === "unassessed") {
    return <div role="status"><p><span className="verdict unassessed">Not assessed</span> <span className="muted">{row.message || `${name} was not assessed on this run.`}</span></p>
      <p className="muted">Refresh the evaluation from the page header to try again.</p>
      {name === "Empower" && <OtherTools res={res} />}</div>;
  }
  const opp = opportunity(res, name);
  return (
    <div className="opp">
      <div className="opp-head">
        <div><h3>{opp.title}</h3><p className="muted">{opp.note}</p></div>
        <span className="opp-score"><strong>{name}</strong> {pillar.total}/9 · {row.bandLabel}</span>
      </div>
      <div className={`opp-flow${opp.gap ? " gap" : ""}`} role="group" aria-label={`${name} opportunity map`}>
        {/* Keyed by route, so a list opened on one route is not still open on the next. */}
        <Node key={`${name}-1`} node={opp.nodes[0]} step={1} detailed={detailed} />
        <Connector gap={opp.gap} text={opp.connector} />
        <Node key={`${name}-2`} node={opp.nodes[1]} step={2} detailed={detailed} />
        <Connector gap={opp.gap} text={opp.connector} />
        <Node key={`${name}-3`} node={opp.nodes[2]} step={3} detailed={detailed} />
      </div>
      {/* The recommended route's next step is already the hero's; repeating it here adds nothing. */}
      {opp.nextStep && name !== res.routing?.pillar && <p className="fit-next"><span className="eyebrow">{opp.gap ? "Review action" : "Next step"}</span>{opp.nextStep}</p>}
      {detailed && <>
        <PillarMethod pillar={pillar} row={row} name={name} onOpenCriterion={onOpenCriterion} />
        {name === "Empower" && <OtherTools res={res} />}
      </>}
    </div>
  );
}
