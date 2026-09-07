import React, { useState } from "react";
import { ExtLink } from "../../components/widgets.jsx";
import Section from "./Section.jsx";

/* Age of a piece of evidence, computed against the reader's clock rather than read from the run.
   The engine deliberately does not store an age (core/provenance.py::as_dict explains why: it was
   a frozen zero that decayed into a lie). `retrieved_at` is the durable fact, and for a search
   replayed from cache it is the timestamp of the search that actually produced the result — so a
   re-evaluation shows genuinely older evidence as older instead of inheriting its own clock. */
function evidenceAge(retrievedAt) {
  if (!retrievedAt) return null;
  const ms = Date.now() - new Date(retrievedAt).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const days = Math.floor(ms / 86400000);
  if (days >= 1) return { text: `${days}d ago`, stale: days > 7 };
  const hours = Math.floor(ms / 3600000);
  return { text: hours >= 1 ? `${hours}h ago` : "just now", stale: false };
}

function EvidenceTab({ res }) {
  const [filter, setFilter] = useState("");
  const facts = (res.facts || []).filter((f) =>
    !filter || `${f.key} ${f.value} ${f.method}`.toLowerCase().includes(filter.toLowerCase()));
  const dot = (v) => (
    <span className="status-dot" style={{ background: v ? "var(--success)" : "var(--border-2)" }} />
  );
  // One section, because the table is one thing. It is still wrapped so the rail can address it
  // and so a permalink to #evidence-table lands with the header clear of the sticky chrome.
  return (
    <Section id="evidence-table" className="panel flush">
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)" }}>
        <input className="input" style={{ maxWidth: 280 }} placeholder="Filter evidence…"
          value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter evidence" />
        <span className="muted" style={{ marginLeft: 10, fontSize: 12 }}>{facts.length} facts</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="dtable dense">
          <thead>
            <tr><th>Status</th><th>Claim</th><th>Value</th><th>Method</th><th>Retrieved</th><th>Source</th></tr>
          </thead>
          <tbody>
            {facts.slice(0, 120).map((f, i) => {
              const age = evidenceAge(f.retrieved_at);
              return (
                <tr key={i} style={{ cursor: "default" }}>
                  <td>{dot(f.verified === true || f.verified === "True")}
                    {f.verified === true || f.verified === "True" ? "verified" : "unverified"}</td>
                  <td>{f.key}</td>
                  <td style={{ whiteSpace: "normal", maxWidth: 380, overflowWrap: "anywhere" }}>{f.value}</td>
                  <td className="muted">{f.method}</td>
                  <td className="muted" title={f.retrieved_at || ""}
                    style={age?.stale ? { color: "var(--warning)" } : undefined}>
                    {age ? age.text : "—"}
                  </td>
                  <td>{/^https?:\/\//.test(f.source_url || "")
                    ? <ExtLink href={f.source_url}>link</ExtLink>
                    : <span className="muted">{f.source_url || "—"}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

export default EvidenceTab;
