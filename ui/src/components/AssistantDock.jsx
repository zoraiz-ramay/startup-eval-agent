import React, { useRef, useState } from "react";
import { IxPane } from "@siemens/ix-react";
import { iconAi } from "@siemens/ix-icons/icons";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Loading } from "./widgets.jsx";

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
    // MIG-11: IxPane replaces the hand-rolled <aside class="dock">. `expanded` stays hard-wired
    // true rather than mirroring IxPane's own collapse mechanism — this component still mounts
    // and unmounts on `dockOpen` (state.jsx's width-listener-driven default, and the rail's
    // toggle), which is what "no breakpoint prop" in the backlog row means IxPane can't own
    // itself. Its built-in title-bar close/collapse button is what closes it instead of a
    // hand-rolled one: two controls that both mean "close" would repeat the exact duplicate-
    // control problem MIG-08's rail already fixed for the command bar. `variant="floating"` is
    // the closest built-in match to the old fixed-position overlay (assistant-pane in styles.css
    // still has to force `position: fixed` itself — IxPane defaults every composition to
    // `position: relative`, in flow, verified against the compiled source's pane.css).
    <IxPane className="assistant-pane" composition="right" variant="floating" size="360px"
      expanded noPadding icon={iconAi} heading="Assistant"
      ariaLabelCollapseCloseButton="Close assistant"
      onExpandedChanged={(e) => { if (!e.detail.expanded) setDockOpen(false); }}>
      {dockCtx && (
        <span slot="header" className="ctx" title={dockCtx.company}>on {dockCtx.company}</span>
      )}
      {/* IxPane's own <aside> has no aria-label/aria-labelledby wiring (verified against the
          compiled source) — the "AI assistant" landmark name has to come from content we slot
          in, not a prop on IxPane itself. */}
      <div className="dock" role="complementary" aria-label="AI assistant">
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
          {/* MIG-30: consolidated onto widgets.jsx's Loading (IxSpinner) rather than the
              hand-rolled `.spinner` span, so this dock's busy state gets the same
              role="status"/aria-live treatment as every other loading indicator in the app. */}
          {busy && <Loading text="Drafting, searching, refining…" />}
        </div>
        <div className="dock-input">
          <input className="input" placeholder="Ask about this workspace…" value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()} />
          <button className="btn ai" disabled={busy || !q.trim()} onClick={() => send()}>→</button>
        </div>
      </div>
    </IxPane>
  );
}
