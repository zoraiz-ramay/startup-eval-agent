import React, { useEffect, useState } from "react";
import ErrorBox from "../../../components/ErrorBox.jsx";
import { api } from "../../../api.js";

/* The reviewer's own decision, and the audit trail behind it.
   Unchanged by the move into its own file — it is here because it is the one part of this view
   that WRITES, and mixing a mutation into the panel composition made both harder to follow. */
export default function OverridePanel({ runId, currentPillar }) {
  const [audit, setAudit] = useState([]);
  const [open, setOpen] = useState(false);
  const [pillar, setPillar] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (runId) api.audit(runId).then((d) => setAudit(d.overrides || [])).catch(() => {});
  }, [runId]);

  const submit = async () => {
    if (!pillar || reason.trim().length < 5 || busy) return;
    setBusy(true); setError("");
    try {
      const rec = await api.override(runId, pillar, reason.trim(), note.trim());
      setAudit((a) => [...a, rec]);
      setOpen(false); setPillar(""); setReason(""); setNote("");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  if (!runId) return null;
  return (
    <>
      <h3>Reviewer decision</h3>
      {audit.length === 0 && !open && (
        <p className="muted" style={{ margin: "0 0 8px" }}>
          Automated recommendation stands — no reviewer override recorded.
        </p>
      )}
      {audit.map((o, i) => (
        <div key={i} className="risk" style={{ borderLeftColor: "var(--accent)", background: "var(--accent-soft)" }}>
          <strong>{o.prev_pillar} → {o.new_pillar}</strong>
          {o.reviewer && <span className="badge">{o.reviewer}</span>}
          <span className="badge">{String(o.created_at).slice(0, 10)}</span>
          <div style={{ fontSize: 12.5 }}>{o.reason}</div>
          {o.evidence_note && <div className="muted" style={{ fontSize: 12 }}>Evidence: {o.evidence_note}</div>}
        </div>
      ))}
      {!open ? (
        <button className="tool-btn" onClick={() => setOpen(true)}>Override routing…</button>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 460 }}>
          <select className="input" value={pillar} onChange={(e) => setPillar(e.target.value)}
            aria-label="New route">
            <option value="">New route…</option>
            {["Connect", "Collaborate", "Empower", "Pass"].filter((p) => p !== currentPillar)
              .map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <input className="input" placeholder="Reason (required)" value={reason}
            onChange={(e) => setReason(e.target.value)} />
          <input className="input" placeholder="Supporting evidence (optional)" value={note}
            onChange={(e) => setNote(e.target.value)} />
          {error && <ErrorBox message={error} />}
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn" disabled={busy || !pillar || reason.trim().length < 5}
              onClick={submit}>{busy ? "Saving…" : "Record override"}</button>
            <button className="btn secondary" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </>
  );
}
