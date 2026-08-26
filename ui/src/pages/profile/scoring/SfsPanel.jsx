import React from "react";
import { ExtLink } from "../../../components/widgets.jsx";

/* Which SFS line applies, not merely whether one does.
   `unassessed` is a real state: a run from before the commercial posture was extracted knows
   nothing either way, and showing that as "not relevant" would be a negative finding the evidence
   does not support. */
export default function SfsPanel({ rt }) {
  const lines = rt.sfs_lines || [];
  const blockers = rt.sfs_blockers || [];
  const status = lines.length ? (rt.sfs_relevant ? "relevant" : "conditional")
    : (blockers.length ? "not relevant" : "not assessed");
  return (
    <>
      <h3>Siemens Financial Services</h3>
      <p style={{ margin: "0 0 8px" }}>
        <span className={`verdict ${rt.sfs_relevant ? "eligible" : blockers.length ? "blocked" : "unassessed"}`}>
          {status}
        </span>
        {rt.sfs_line && <span className="pill sfs" style={{ marginLeft: 8 }}>{rt.sfs_line}</span>}
      </p>
      {lines.map((l, i) => (
        <div key={i} className="spec">
          <div className="k">{l.line}</div>
          <div className="v">
            <span className="badge">{l.fit}</span>
            <div className="muted" style={{ fontSize: 12.5 }}>{l.rationale}</div>
            {l.missing?.length > 0 && (
              <div className="muted" style={{ fontSize: 12.5 }}>Still needed: {l.missing.join("; ")}</div>
            )}
            {/^https?:\/\//.test(l.evidence_url || "") && <ExtLink href={l.evidence_url}>evidence</ExtLink>}
          </div>
        </div>
      ))}
      {lines.length === 0 && blockers.length === 0 && (
        <p className="muted" style={{ margin: 0 }}>{rt.sfs_rationale
          || "Commercial posture was not established on this run. Re-evaluate to assess it."}</p>
      )}
      {blockers.map((b, i) => (
        <p key={i} className="muted" style={{ fontSize: 12.5, margin: "4px 0 0" }}>{b}</p>
      ))}
    </>
  );
}
