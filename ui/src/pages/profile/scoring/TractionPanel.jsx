import React, { useState } from "react";
import { IxContentHeader } from "@siemens/ix-react";
import { ExtLink, Loading } from "../../../components/widgets.jsx";
import Section from "../Section.jsx";
import { MiniBar, RingGauge } from "../../../components/charts.jsx";
import TractionDetail, { barId, flagsOf, pts } from "./TractionDetail.jsx";
import { divisionDisplay } from "./presentation.js";

const VERSION = "traction-rubric-v2";
// pts: 7.5 and 11.25 are real rubric values; "7.50" and "11" would each misstate one.

/* A division with no evidence is excluded from the total, and the row has to say so in words:
   "0 / 30" beside it would read as a finding that the company has no revenue, when nobody found
   out either way. An evidenced zero (a sourced "pre-revenue") keeps its 0 and its link. */
function DivisionRow({ d }) {
  const unknown = d.status === "unknown";
  return (
    <tr>
      <th scope="row">{d.label}</th>
      <td>{unknown ? "—" : pts(d.points)} <span className="muted">/ {d.max}</span>
        {!unknown && <span className="mini-bar" aria-hidden="true"><span style={{ width: `${(100 * d.points) / d.max}%` }} /></span>}</td>
      <td className="traction-value">{unknown ? <span className="muted">Not found</span> : <span title={String(d.value || "")}>{divisionDisplay(d)}</span>}
        {flagsOf(d).map((f) => <span key={f} className="badge">{f}</span>)}</td>
      <td>{unknown ? <span className="muted">excluded from total</span> : d.band || "—"}</td>
      <td>{d.source_url ? <ExtLink href={d.source_url}>source</ExtLink>
        : <span className="muted">{d.origin || "—"}</span>}</td>
    </tr>
  );
}

/* One bar per division, earned against its maximum; a division with no evidence is a hatched,
   empty track that says "excluded" — it was left out of the total, not scored zero. Each row is a
   button that opens its division's detail, one at a time, like the Siemens Fit criteria. */
function DivisionBars({ divisions, open, onToggle }) {
  return (
    <ul className="division-bars" aria-label="Traction divisions">
      {divisions.map((d) => {
        const unknown = d.status === "unknown";
        const on = open === d.id;
        const said = unknown ? `${d.label}: no evidence, excluded from the total` : `${d.label}: ${pts(d.points)} of ${d.max} points`;
        return (
          <li key={d.id}>
            <button id={barId(d.id)} type="button" className={`division-bar${on ? " open" : ""}`} aria-expanded={on}
              aria-controls={on ? "traction-division" : undefined} onClick={() => onToggle(d.id)}
              aria-label={`${said}${unknown ? "" : `, ${divisionDisplay(d)}`}`}>
              <strong>{d.label}</strong>
              <MiniBar value={unknown ? null : d.points} max={d.max} color="var(--chart-traction)" label={said} />
              {unknown ? <span className="badge">No evidence · excluded</span>
                : <span><strong>{pts(d.points)}</strong><span className="muted">/{d.max} · {divisionDisplay(d)}</span></span>}
              <span className="division-more" aria-hidden="true">{on ? "Hide" : "Details"}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function TractionPanel({ res, runId = null, detailed = false }) {
  const [open, setOpen] = useState(null);
  const t = res.traction;
  const header = <IxContentHeader headerTitle="Traction"
    headerSubtitle="Points rubric from sourced facts: Funding 30 · Customers 30 · Revenue 30 · Employees 10. Select a division to see how it was scored." />;
  if (!t) {
    return <Section id="scoring-traction">{header}
      {res.streaming ? <Loading text="Computing traction…" />
        : <p className="muted" role="status">Traction was not computed for this run. Re-evaluate to score it.</p>}
    </Section>;
  }
  if (t.version !== VERSION || !Array.isArray(t.divisions)) {
    return <Section id="scoring-traction">{header}
      <p role="alert">This traction breakdown was produced by a version this page cannot read.</p>
    </Section>;
  }
  const known = t.divisions.filter((d) => d.status !== "unknown").map((d) => d.label);
  const opened = t.divisions.find((d) => d.id === open);
  const close = () => { const back = open; setOpen(null); document.getElementById(barId(back))?.focus(); };
  return (
    <Section id="scoring-traction">
      {header}
      <div className="traction-overview">
        <div className="traction-rings">
          <RingGauge value={t.score_0_100} size={112} color="var(--chart-traction)" sub="of 100"
            label={t.score_0_100 != null ? `Traction ${Math.round(t.score_0_100)} of 100` : "Traction not scored"} />
          <div><strong className="big-num">{Math.round(t.confidence * 100)}%</strong>
            <span className="muted">of the 100 points had evidence</span></div>
        </div>
        {/* Escape closes an opened division from its bar too, where focus stays while reading. */}
        <div onKeyDown={(e) => { if (e.key === "Escape" && open) { e.stopPropagation(); close(); } }}>
          <DivisionBars divisions={t.divisions} open={open} onToggle={(id) => setOpen((o) => (o === id ? null : id))} />
        </div>
      </div>
      {opened && <TractionDetail d={opened} rungs={res.traction_ladders?.[opened.id]} res={res} runId={runId ?? res.run_id ?? null}
        fxAsOf={t.fx_as_of} onClose={close} />}
      {t.status === "no_evidence"
        ? <p role="status">No traction evidence was found for any division, so there is no score — not a score of zero.</p>
        : <p className="muted">{pts(t.earned)} of {t.available_max} available points, scaled to 100 — {known.join(", ")} evidenced;
          divisions with no evidence are left out rather than scored zero.</p>}
      {detailed && <><div className="table-scroll">
        <table className="dtable static" aria-label="Traction points by division">
          <thead><tr><th scope="col">Division</th><th scope="col">Points</th><th scope="col">Value</th>
            <th scope="col">Band</th><th scope="col">Source</th></tr></thead>
          <tbody>{t.divisions.map((d) => <DivisionRow key={d.id} d={d} />)}</tbody>
        </table>
      </div>
      <p className="muted traction-footnote">Amounts converted to EUR at reference rates as of {t.fx_as_of}.</p></>}
    </Section>
  );
}
