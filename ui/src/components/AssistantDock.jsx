import React, { useRef, useState } from "react";
import { api } from "../api.js";
import { useApp } from "../state.jsx";

const GENERIC_SUGGESTIONS = [
  "Which evaluated startups best fit Siemens today?",
  "Summarise the current portfolio by routing pillar",
  "What sectors are we seeing the most traction in?",
];
const CONTEXT_SUGGESTIONS = [
  "Summarise why this startup matches the brief",
  "What are the top risks?",
  "Compare this startup with similar companies",
  "What evidence is weakest?",
];

export default function AssistantDock() {
  const { dockOpen, setDockOpen, dockCtx } = useApp();
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef(null);

  if (!dockOpen) return null;

  const send = async (text) => {
    const question = (text || q).trim();
    if (!question || busy) return;
    setQ("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: question }]);
    try {
      const r = await api.ask(question, dockCtx?.runId ?? null);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, source: r.source, evidence: r.evidence }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: `Request failed: ${e.message}`, source: "error" }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => bodyRef.current?.scrollTo(0, 1e6));
    }
  };

  const suggestions = dockCtx ? CONTEXT_SUGGESTIONS : GENERIC_SUGGESTIONS;

  return (
    <aside className="dock" aria-label="AI assistant">
      <div className="dock-head">
        <span style={{ color: "var(--ai)" }}>✦</span> Assistant
        {dockCtx && <span className="ctx" title={dockCtx.company}>on {dockCtx.company}</span>}
        <button className="icon-btn" style={{ color: "var(--text-2)" }}
          onClick={() => setDockOpen(false)} aria-label="Close assistant">✕</button>
      </div>
      <div className="dock-body" ref={bodyRef}>
        {msgs.length === 0 && (
          <>
            <p className="muted" style={{ fontSize: 12.5 }}>
              Answers combine AI knowledge with a targeted web check, grounded in
              {dockCtx ? ` ${dockCtx.company}` : " your evaluated portfolio"}.
            </p>
            <div className="dock-suggest">
              {suggestions.map((s) => (
                <button key={s} onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`dock-msg ${m.role}`}>
            {m.role === "assistant" && m.source && <div className="src">{m.source}</div>}
            {m.text}
            {m.evidence?.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {m.evidence.slice(0, 4).map((e, j) => (
                  <div key={j} style={{ fontSize: 11 }}>
                    <a href={e.url} target="_blank" rel="noopener noreferrer">[{j + 1}] {e.title || e.url}</a>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="muted"><span className="spinner" /> Drafting, searching, refining…</p>}
      </div>
      <div className="dock-input">
        <input className="input" placeholder="Ask about this workspace…" value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()} />
        <button className="btn ai" disabled={busy || !q.trim()} onClick={() => send()}>→</button>
      </div>
    </aside>
  );
}
