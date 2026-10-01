import React from "react";
import { DetailPanel } from "./CriterionDetail.jsx";
import { FundingLookup, HeadcountLookup, Sources } from "./TractionLookup.jsx";
import { divisionDisplay } from "./presentation.js";

/* One traction division, opened from its bar: where it sits on the rubric ladder, what was found
   and where, and how it was scored. Each division answers the question a reviewer actually asks
   of it — who funded them, who the customers are, where the revenue figure comes from, where the
   headcount comes from — and every figure carries its source or says it has none. */

export const barId = (id) => `traction-bar-${id}`;
export const pts = (n) => (Number.isFinite(n) ? String(Math.round(n * 100) / 100) : "—");
export const flagsOf = (d) => [
  d.basis === "stage_only" && "stage only, amount undisclosed",
  d.currency_assumed && "currency assumed €",
  d.conflict && "sources disagree",
  d.stale && "figure older than 3 years",
].filter(Boolean);

// Where a value came from, in words. A value from a database has no page to link to, so its
// origin is the source and it is named as such.
const ORIGIN = { application: "Application form", glassdollar: "GlassDollar database", glassdollar_api: "GlassDollar database",
  database: "Database", profile: "Company profile", web: "Web research", linkedin: "LinkedIn", verified: "Verified claim",
  research: "Research" };
const originOf = (o) => ORIGIN[o] || (o ? String(o) : "Unknown");
// A web-researched value with no link says so: "Web research" alone would read as a source.
const src = (url, origin) => (url ? [{ title: "", url }]
  : origin ? [{ title: origin === "web" ? "Web research · no link captured" : originOf(origin), url: "" }] : []);

/* Which rung of the rubric a division reached. Bands are matched on the string the engine
   reported, never recomputed here; customer rungs are counts, so the counted big-name and SME
   customers each mark the highest tier they reach — the two tiers add up. */
function reached(d, rung) {
  if (d.status === "unknown") return false;
  if (rung.kind) {
    if (d.basis !== "named") return false;
    const n = (d.items || []).filter((i) => i.counted && (rung.kind === "big") === (i.size === "large_enterprise")).length;
    return n >= rung.min;
  }
  return rung.match === d.band || Boolean(rung.prefix && String(d.band || "").startsWith(rung.prefix));
}

function Ladder({ d, rungs }) {
  const groups = [];
  for (const r of rungs) {
    let g = groups.find((x) => x.name === r.group);
    if (!g) { g = { name: r.group, rungs: [] }; groups.push(g); }
    g.rungs.push(r);
  }
  // Only the top reached rung in each group is marked: 3 big-name customers reach "2+" as well,
  // but it is the 3+ tier that scores.
  const marked = new Set(groups.map((g) => g.rungs.find((r) => reached(d, r))).filter(Boolean));
  return (
    <>
      <h5>Where this startup sits</h5>
      {d.status === "unknown" && <p className="crit-note">No evidence was found, so this division is left out of the total — not scored zero.</p>}
      {groups.map((g) => (
        <div key={g.name || "all"} className="ladder-group">
          {g.name && <p className="ladder-group-name">{g.name}</p>}
          <ol className="crit-scale" aria-label={`${d.label} rubric${g.name ? `: ${g.name}` : ""}`}>
            {g.rungs.map((r) => {
              const on = marked.has(r);
              return (
                <li key={r.label} className={on ? "on" : ""} aria-current={on ? "true" : undefined}>
                  <span className="crit-level ladder-points">{pts(r.points)}</span>
                  <span>{r.label}{on && <strong className="crit-here">This startup</strong>}</span>
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </>
  );
}

/* The fact the division scored, in one line, with its source. */
function Found({ d }) {
  if (d.status === "unknown") return <p className="muted">Nothing the rubric could score was evidenced for {d.label.toLowerCase()}.</p>;
  const raw = String(d.value || "");
  return (
    <div className="division-found">
      <p><strong className="division-value">{divisionDisplay(d)}</strong>
        {raw && raw !== divisionDisplay(d) && <span className="muted"> · “{raw.slice(0, 180)}”</span>}</p>
      <Sources items={src(d.source_url, d.origin)} label="Source" />
      {flagsOf(d).length > 0 && <p>{flagsOf(d).map((f) => <span key={f} className="badge">{f}</span>)}</p>}
    </div>
  );
}

function Customers({ d, res }) {
  const dp = res.deep_profile || {};
  const items = d.items || [];
  const grade = dp.customer_segment_grade || {};
  return (
    <>
      <h5>Named customers {d.basis === "named" && <span className="scored-tag">scored</span>}</h5>
      {items.length ? (
        <ul className="division-list">{items.map((c, i) => (
          <li key={`${c.name}-${i}`} className={c.counted ? "" : "not-counted"}>
            <span className="division-list-main"><strong>{c.name}</strong>
              {c.counted && <span className="kind-tag">{c.size === "large_enterprise" ? "Big name" : "SME"}</span>}</span>
            <span className="muted">{c.counted ? "counted" : `not counted · ${c.reason}`}</span>
            <Sources items={src(c.source_url, c.origin)} label="Source" />
          </li>))}</ul>
      ) : <p className="muted">No customer is named in the research.</p>}
      <h5>Customer base, described {d.basis === "generic" && <span className="scored-tag">scored</span>}</h5>
      {dp.customer_segment ? (
        <div className="division-found">
          <p>“{dp.customer_segment}”{grade.level ? <span className="muted"> · level {grade.level} of 3</span> : null}</p>
          <Sources items={src(dp.customer_segment_source || grade.source_url, "")} label="Source" />
        </div>
      ) : <p className="muted">No description of the customer base was found.</p>}
    </>
  );
}

const METRIC = { revenue: "Revenue", arr: "Annual recurring revenue", mrr: "Monthly recurring revenue", estimate: "Revenue estimate" };
const SIGNAL = { recurring: "Recurring revenue (subscriptions or contracts)", contracted: "Contracted revenue", customers: "Paying customers" };

function Revenue({ res }) {
  const com = res.deep_profile?.commercial || {};
  const rev = com.revenue || {};
  return (
    <>
      <h5>Revenue figure</h5>
      {rev.source_url ? (
        <div className="division-found">
          <p><strong>{METRIC[String(rev.metric || "").toLowerCase()] || "Revenue"}</strong>
            {rev.fiscal_year && <span className="muted"> · {rev.fiscal_year}</span>}</p>
          {rev.quote && <p className="division-quote">“{rev.quote}”</p>}
          <Sources items={src(rev.source_url, "")} label="Source" />
        </div>
      ) : <p className="muted">No revenue figure with a source was found.</p>}
      <h5>Revenue signal</h5>
      {SIGNAL[com.revenue_signal]
        ? <div className="division-found"><p>{SIGNAL[com.revenue_signal]}</p><Sources items={src(com.revenue_source, "")} label="Source" /></div>
        : <p className="muted">No evidence of how the company earns was found.</p>}
      {com.pricing_public === true && <><h5>Pricing</h5>
        <div className="division-found"><p>Pricing is published</p><Sources items={src(com.pricing_source, "")} label="Source" /></div></>}
    </>
  );
}

function Employees({ d, res }) {
  const series = (res.deep_profile?.employees_over_time || []).filter((p) => p?.source_url);
  const candidates = (d.candidates || []).filter((c) => c.value);
  return (
    <>
      <h5>Headcount on record</h5>
      {candidates.length ? (
        <ul className="division-list">{candidates.map((c, i) => (
          <li key={i}>
            <span className="division-list-main"><strong>{c.value}</strong>{c.used && <span className="scored-tag">used</span>}</span>
            <span className="muted">{c.reason || originOf(c.origin)}</span>
            <Sources items={src(c.source_url, c.origin)} label="Source" />
          </li>))}</ul>
      ) : <p className="muted">No headcount was found.</p>}
      {series.length > 0 && <><h5>Headcount history</h5>
        <ul className="division-list">{series.map((p, i) => (
          <li key={i}><span className="division-list-main"><strong>{p.count}</strong><span className="muted">{p.year}</span></span>
            <Sources items={src(p.source_url, "")} label="Source" /></li>))}</ul></>}
    </>
  );
}

export default function TractionDetail({ d, rungs, res, runId, fxAsOf, onClose }) {
  const candidates = (d.candidates || []).filter((c) => c.value);
  return (
    <DetailPanel id="traction-division" anchorId={barId(d.id)} context="Traction" title={d.label}
      score={d.status === "unknown" ? "—" : pts(d.points)} max={d.max} onClose={onClose}
      scale={rungs?.length ? <Ladder d={d} rungs={rungs} /> : null}>
      <h5>What scored</h5>
      <Found d={d} />
      <h5>How it was scored</h5>
      {d.rationale ? <p>{d.rationale}</p> : <p className="muted">No rationale was recorded.</p>}
      {d.id === "funding" && <>
        {candidates.length > 1 && <><h5>Figures found</h5>
          <ul className="division-list">{candidates.map((c, i) => (
            <li key={i}><span className="division-list-main"><strong>{c.value}</strong>{c.used && <span className="scored-tag">used</span>}</span>
              <span className="muted">{c.reason || originOf(c.origin)}</span>
              <Sources items={src(c.source_url, c.origin)} label="Source" /></li>))}</ul></>}
        <FundingLookup runId={runId} known={(res.deep_profile?.commercial?.investors || []).filter((i) => i?.name)} />
      </>}
      {d.id === "customers" && <Customers d={d} res={res} />}
      {d.id === "revenue" && <Revenue res={res} />}
      {d.id === "employees" && <><Employees d={d} res={res} /><HeadcountLookup runId={runId} /></>}
      {d.value_eur != null && fxAsOf && <p className="muted traction-footnote">Converted to EUR at reference rates as of {fxAsOf}.</p>}
    </DetailPanel>
  );
}
