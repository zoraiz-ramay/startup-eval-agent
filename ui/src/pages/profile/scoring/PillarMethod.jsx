import React from "react";
import { signals } from "./presentation.js";

const BANDS = [["no_match", "No match", "0–3", 4], ["review", "Review", "4–6", 3], ["strong", "Strong", "7–9", 3]];
const THIRD_LABEL = { Connect: "ecosystem value", Empower: "actionability", Collaborate: "actionability" };

/* The 0–9 total on the three bands the engine uses, one slot per point. The marker sits on the
   total and the highlighted band is the engine's, so a 7 held at Review by a weak third criterion
   shows as exactly that — a marker in Strong's range under a highlighted Review. */
function BandBar({ total, band, name }) {
  return (
    <div className="band-bar" role="img" aria-label={`${name} total ${total} of 9, band ${BANDS.find((b) => b[0] === band)?.[1] || band}`}>
      {BANDS.map(([id, label, range, slots]) => (
        <span key={id} className={`band-bar-seg${band === id ? " on" : ""}`} style={{ flexGrow: slots }}>
          <strong>{label}</strong> <span>{range}</span>
        </span>
      ))}
      <span className="band-bar-marker" style={{ left: `${((total + 0.5) * 100) / 10}%` }} />
    </div>
  );
}

/* How a pillar's score was built, for the detailed view: each criterion's level and anchor with a
   way into its full detail, then the band rule. The only place on the page that states the exact
   scores in a row, so it is the one to read when auditing a route. */
export default function PillarMethod({ pillar, row, name, onOpenCriterion }) {
  const words = Object.fromEntries(signals(pillar, name).map((s) => [s.id, s]));
  return (
    <section className="opp-method" aria-labelledby={`method-${name}`}>
      <h4 id={`method-${name}`}>Scoring method</h4>
      <table className="method-table">
        <thead><tr><th scope="col">Criterion</th><th scope="col">Score</th><th scope="col">Level reached</th>
          <th scope="col"><span className="sr-only">Detail</span></th></tr></thead>
        <tbody>
          {pillar.criteria.map((c) => (
            <tr key={c.id}>
              <th scope="row">{c.label}</th>
              <td className="method-score">
                <span className="strength-meter three" aria-hidden="true">{[1, 2, 3].map((i) => <span key={i} className={i <= c.score ? "on" : ""} />)}</span>
                {c.score}/3
              </td>
              <td className={words[c.id]?.weak ? "method-weak" : ""}>{c.anchor}{words[c.id]?.weak && <> · next step needs definition</>}</td>
              <td><button type="button" className="link-btn" onClick={() => onOpenCriterion(c.id)}
                aria-label={`How ${c.label} was scored`}>How it was scored</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <BandBar total={pillar.total} band={pillar.band} name={name} />
      <p className="muted">Total {pillar.total}/9 · {row.bandLabel} · shown as {row.value}/100. Strong needs 7 or more
        with {THIRD_LABEL[name]} at least 2.</p>
      {(pillar.notes || []).map((n) => <p key={n} className="crit-note">{n}</p>)}
      {pillar.catalog?.checksum && <p className="muted method-version">Catalog {pillar.catalog.name} · version {pillar.catalog.checksum.slice(0, 12)}</p>}
    </section>
  );
}
