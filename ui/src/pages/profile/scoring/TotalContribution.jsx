import React from "react";
import { IxContentHeader } from "@siemens/ix-react";
import { MiniBar, StackedBar } from "../../../components/charts.jsx";
import Section from "../Section.jsx";
import { contributions } from "./presentation.js";

const COLOR = { traction: "var(--chart-traction)", siemens_fit: "var(--chart-fit)",
  team_ecosystem: "var(--chart-team)", market: "var(--chart-market)" };
const SECTION = { traction: "scoring-traction", siemens_fit: "scoring-routes", team_ecosystem: "scoring-team",
  market: "scoring-market" };

/* What the total is made of. The weighted contributions add up to the total, so one stacked bar
   is honest here (unlike the pillars, which are alternatives). A component that is not scored is
   a hatched block the size of what it could add, and while any is missing the total is pending —
   a partial sum would be a different measurement under the same label. */
export default function TotalContribution({ res, detailed = false }) {
  const header = <IxContentHeader headerTitle="Total score"
    headerSubtitle="Four weighted components: 30% traction · 35% Siemens Fit · 20% Team & Ecosystem · 15% market." />;
  if (!res.department && !res.streaming) {
    return <Section id="scoring-total">{header}
      <p className="muted" role="status">Legacy run: the weighted total is computed for a department assessment only.</p></Section>;
  }
  const c = contributions(res);
  const a = res.assessment;
  const segments = c.rows.map((r) => ({ key: r.key, label: r.label, value: r.earned, capacity: r.max, color: COLOR[r.key] }));
  const label = `Total ${c.total != null ? c.total.toFixed(1) : "pending"} of 100: `
    + c.rows.map((r) => (r.earned != null ? `${r.label} ${r.earned} of ${r.max}` : `${r.label} not scored`)).join(", ");
  return (
    <Section id="scoring-total">
      {header}
      <div className="contrib-head">
        {c.total != null
          ? <p className="contrib-total"><strong className="num">{c.total.toFixed(1)}</strong> <span className="muted">/ 100</span></p>
          : <p className="contrib-pending" role="status">Total pending · {c.missing.length ? `${c.missing.join(", ")} not scored yet` : "waiting for the assessment"}</p>}
      </div>
      <StackedBar segments={segments} label={label} />
      {/* Each component is a link to the section that scores it — plain anchors, the same
          navigation the section rail uses, so the scroll-spy follows the jump. */}
      <ul className="contrib-legend">
        {c.rows.map((r) => {
          const said = r.earned != null ? `${r.earned} of ${r.max} points` : `not scored, up to ${r.max} points`;
          return (
            <li key={r.key}>
              <a className="contrib-link" href={`#${SECTION[r.key]}`} aria-label={`${r.label}: ${said}. Go to ${r.label}`}>
                <span className="legend-name"><span className="key" style={{ background: COLOR[r.key] }} /><strong>{r.label}</strong>
                  <span className="muted">{r.max}%</span></span>
                <MiniBar value={r.value} color={COLOR[r.key]}
                  label={r.earned != null ? `${r.label}: ${r.earned} of ${r.max} points (score ${Math.round(r.value)}/100)` : `${r.label}: not scored, up to ${r.max} points`} />
                <span className="contrib-foot"><span className="muted">{r.earned != null ? `${r.earned} of ${r.max} pts` : `${res.streaming ? "pending" : "not scored"} · ${r.max} possible`}</span>
                  <span className="contrib-go" aria-hidden="true">See breakdown</span></span>
              </a>
            </li>
          );
        })}
      </ul>
      {detailed && <details className="blind"><summary>How the total is calculated</summary><div className="blind-body">
        <p>Total = 0.30 × Traction + 0.35 × Siemens Fit + 0.20 × Team &amp; Ecosystem + 0.15 × Market, each on 0–100.
          It is only calculated when all four are scored.</p>
        <div className="table-scroll">
          <table className="dtable static" aria-label="Total score components">
            <thead><tr><th scope="col">Component</th><th scope="col">Score</th><th scope="col">Weight</th><th scope="col">Contribution</th></tr></thead>
            <tbody>{c.rows.map((r) => <tr key={r.key}>
              <th scope="row">{r.label}{r.key === "market" && a?.market_method === "llm_judgment" ? " · model judgment (run predates the market rubric)" : ""}</th>
              <td>{r.value != null ? r.value.toFixed(1) : "—"}</td><td>{r.max}%</td><td>{r.earned != null ? r.earned : "—"}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </div></details>}
    </Section>
  );
}
