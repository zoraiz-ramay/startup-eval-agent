import React from "react";
import { ExtLink } from "../../../components/widgets.jsx";
import { dedupeEvidence } from "./presentation.js";

/* Cited evidence, each record once, under a human label. The internal field path a record came
   from stays reachable — it is the audit trail — but only in the record's own disclosure, and
   only where a reader audits (`audit`); a criterion's detail panel is read for its reasoning and
   leaves it out, the full trail being one tab away under Evidence. */
export default function EvidenceList({ items, audit = true }) {
  const list = dedupeEvidence(items);
  if (!list.length) return <p className="muted">No startup evidence was cited for this item.</p>;
  return (
    <ul className="evidence-list">
      {list.map((e, i) => (
        <li key={`${e.id || i}-${i}`}>
          <blockquote>{e.quote || e.text}</blockquote>
          <span className="muted">{e.label}</span>{" "}
          {e.url && <ExtLink href={e.url}>Source</ExtLink>}
          {audit && <details className="evidence-audit"><summary>Record path</summary>
            <code>{e.refs.filter(Boolean).join(", ") || "—"}</code></details>}
        </li>
      ))}
    </ul>
  );
}
