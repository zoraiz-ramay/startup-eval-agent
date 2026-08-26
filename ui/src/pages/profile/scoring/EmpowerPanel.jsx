import React from "react";
import { ExtLink } from "../../../components/widgets.jsx";

/* Empower, past the verdict: what to offer, why it is worth the week, and how to open.
 *
 * "Qualifies for Empower" is not an action. This is the pillar Siemens can offer the same day —
 * no business unit to line up, no procurement — so it is the one where the profile most owes a
 * reviewer something concrete. Everything here is derived from evidence the run already holds
 * (core/empower.py); nothing is researched, so nothing here can outrun its sources.
 *
 * The approach angles are labelled as suggestions and kept visually apart from the signals above
 * them. Signals are findings with citations; angles are composed sentences. Rendering them alike
 * would let one borrow the other's authority.
 */
const STRENGTH_CLASS = { strong: "met", moderate: "unknown", weak: "unknown" };

export default function EmpowerPanel({ empower, tool }) {
  const signals = empower?.signals || [];
  const rel = empower?.relevance || {};
  const approach = empower?.approach || [];
  const bundles = rel.bundles || [];
  if (!signals.length && !bundles.length && !approach.length) {
    return (
      <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
        No investment signals were derived for this run — it was evaluated before this panel
        existed, or nothing in the evidence bears on it. Re-evaluate to populate it.
      </p>
    );
  }

  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 4px", fontSize: 13 }}>What to offer</h4>
      {bundles.length ? bundles.map((b) => (
        <div key={b.id} className="spec">
          <div className="k">{b.label}</div>
          <div className="v muted" style={{ fontSize: 12.5 }}>{b.offer}</div>
        </div>
      )) : (
        <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
          Nothing the startup builds maps to a named Xcelerator bundle.
        </p>
      )}
      {(rel.division || tool) && (
        <div className="spec">
          <div className="k">Sponsoring unit</div>
          <div className="v">{rel.division || "—"}
            {(rel.tool || tool) && <span className="muted"> · closest tool {rel.tool || tool}</span>}
          </div>
        </div>
      )}

      <h4 style={{ margin: "14px 0 4px", fontSize: 13 }}>Investment signals</h4>
      {signals.length ? signals.map((s) => (
        <div key={s.id} className={`crit ${STRENGTH_CLASS[s.strength] || "unknown"}`}>
          {/* The glyph carries strength; the word repeats it for anyone not seeing colour. */}
          <span className="mark" aria-hidden="true">{s.strength === "strong" ? "▲" : "•"}</span>
          <span className="body">
            <span className="label">{s.label}</span>
            <span className="sr-only"> — {s.strength} signal</span>
            <span className="why">{s.detail}</span>
            {/^https?:\/\//.test(s.source_url || "") && <ExtLink href={s.source_url}>source</ExtLink>}
          </span>
        </div>
      )) : (
        <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
          Nothing in this run&apos;s evidence bears on investment readiness.
        </p>
      )}

      {approach.length > 0 && (
        <>
          <h4 style={{ margin: "14px 0 4px", fontSize: 13 }}>How to approach</h4>
          <p className="muted" style={{ fontSize: 12, margin: "0 0 6px" }}>
            Suggested openings, composed from the evidence above — not findings.
          </p>
          {approach.map((a, i) => <div key={i} className="info-box">{a}</div>)}
        </>
      )}
    </div>
  );
}
