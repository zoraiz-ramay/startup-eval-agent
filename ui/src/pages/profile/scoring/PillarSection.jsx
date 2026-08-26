import React from "react";
import { ExtLink } from "../../../components/widgets.jsx";

/* One pillar, answered by both gates in one place.
 *
 * A pillar is decided twice and the two questions are different: the SCORE gate asks how strong
 * the startup is on that route's own weighting, the CRITERIA gate asks whether Siemens' published
 * programme would take it. Those used to live in two separate panels — a "Route scorecards" list
 * that only ever contained routes which had already qualified, and a "Siemens programme criteria"
 * checklist further down — so a reviewer wanting to know why Connect was not recommended had to
 * cross-reference by hand, and for a REJECTED pillar the scorecard list said nothing at all
 * because rejected routes were simply absent from it.
 *
 * Everything about one pillar is now in one section, and a failing gate names its own shortfall
 * and which clause is binding. "Connect: 47.2 / 70, traction 44 / 60 — traction is the binding
 * constraint" is a thing a reviewer can act on; the pillar's absence from a list is not.
 */
const VERDICT_TEXT = {
  eligible: "Meets every published criterion.",
  unproven: "Nothing disqualifies it — these still need evidence:",
  blocked: "Wrong programme for this company:",
};
const MARK = { met: "✓", unmet: "✕", unknown: "?" };

const CLAUSE_LABEL = {
  route_score: "Route scorecard",
  traction: "Traction",
  alignment: "Portfolio alignment",
};

function num(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(1).replace(/\.0$/, "") : "—";
}

/* One gate clause as a criterion row, so a score gate and a published criterion read on the same
   scale. The glyph is aria-hidden and the state repeated as a visually-hidden word: WCAG 1.4.1
   forbids colour as the only carrier, and a screen reader would otherwise announce "check mark"
   before every line. */
function GateRow({ clause, binding }) {
  const met = clause.passes;
  const isAlignment = clause.kind === "alignment";
  return (
    <div className={`crit ${met ? "met" : "unmet"}`}>
      <span className="mark" aria-hidden="true">{met ? MARK.met : MARK.unmet}</span>
      <span className="body">
        <span className="label">
          {CLAUSE_LABEL[clause.kind] || clause.kind}{" "}
          <span className="num">{num(clause.value)}</span> / {clause.threshold}
        </span>
        <span className="sr-only"> — {met ? "met" : "not met"}</span>
        {!met && (
          <span className="why">
            {isAlignment && !clause.aligned
              ? "No Siemens tool met the fit threshold, so no route is open. "
              : `${clause.shortfall} short. `}
            {binding && "This is the binding constraint — the gap to close first."}
          </span>
        )}
      </span>
    </div>
  );
}

export default function PillarSection({ pillar, assessment, gate, recommendation, routed,
                                        children }) {
  const status = assessment?.status;
  const criteria = assessment?.criteria || [];
  /* `assess_pillar` builds each blocker out of the NOTE of the criterion that blocked, so with the
     checklist and the blockers finally adjacent in one section, every blocker was printed twice.
     Invisible while the two lived in separate panels. Only a blocker whose text is not already on
     screen earns a second, louder line. */
  const shown = new Set(criteria.map((c) => String(c.note || c.label || "").trim()));
  const blockers = (assessment?.blockers || []).filter((b) => !shown.has(String(b).trim()));
  // Two gates decide a route and they answer different questions. A pillar can meet every
  // published criterion and still not be recommended — say so, or "Collaborate: eligible" beside
  // a gate it visibly failed reads as the page contradicting itself.
  const meetsButNotRouted = status === "eligible" && routed === false;

  return (
    <>
      <h3 style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span className={`pill ${pillar}`}>{pillar}</span>
        {status && <span className={`verdict ${status}`}>{status}</span>}
        {routed && <span className="badge">recommended route</span>}
      </h3>

      {gate ? (
        <>
          <p className="muted" style={{ fontSize: 12.5, margin: "0 0 4px" }}>
            {gate.clauses.length === 0
              ? "Empower has no score gate — once portfolio alignment passes it is always open, "
                + "which is why the published criteria below are what decide it."
              : gate.passes
                ? "Clears every score gate on this route's own weighting."
                : "Held below this route's score gate:"}
          </p>
          <GateRow clause={gate.alignment} binding={gate.binding?.kind === "alignment"} />
          {gate.clauses.map((c) => (
            <GateRow key={c.kind} clause={c} binding={gate.binding?.kind === c.kind} />
          ))}
        </>
      ) : (
        <p className="muted" style={{ fontSize: 12.5, margin: "0 0 4px" }}>
          Score gates cannot be shown for this run — it carries no dimension scores.
        </p>
      )}

      {status && (
        <p className="muted" style={{ fontSize: 12.5, margin: "10px 0 4px" }}>
          {VERDICT_TEXT[status]}
          {meetsButNotRouted && (
            <> Not a recommended route on this run, though — the {pillar} scorecard gate is what it
              has not cleared, not the programme&apos;s criteria.</>
          )}
        </p>
      )}
      {criteria.map((c) => (
        <div key={c.id} className={`crit ${c.status}`}>
          <span className="mark" aria-hidden="true">{MARK[c.status] || "?"}</span>
          <span className="body">
            <span className="label">{c.label}</span>
            <span className="sr-only"> — {c.status}</span>
            {/* Which ✕ is fatal. Some unmet criteria are things a startup can go and acquire (a
                certification, API docs) and some are what the company IS — and both rendered as
                the same cross, so the checklist could not say which one ends the conversation.
                This is also why the duplicate blocker list below could go: the blocking
                criterion now marks itself, in place. */}
            {c.blocking && c.status === "unmet" && (
              <span className="badge danger">blocks this route</span>
            )}
            {c.note && <span className="why">{c.note}</span>}
            {/^https?:\/\//.test(c.evidence_url || "") && (
              <ExtLink href={c.evidence_url}>{c.status === "met" ? "evidence" : "criterion"}</ExtLink>
            )}
          </span>
        </div>
      ))}
      {blockers.map((b, i) => (
        <div key={i} className="risk"
             style={{ borderLeftColor: "var(--danger)", background: "var(--danger-soft)" }}>{b}</div>
      ))}
      {recommendation?.recommendation && (
        <div className="reason" style={{ marginTop: 10 }}>{recommendation.recommendation}</div>
      )}
      {!status && !gate && (
        <p className="muted" style={{ margin: 0 }}>
          This run predates the programme criteria. Re-evaluate to assess it.
        </p>
      )}
      {children}
    </>
  );
}
