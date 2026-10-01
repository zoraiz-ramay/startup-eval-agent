import React, { useEffect, useRef, useState } from "react";
import { IxButton, IxIconButton, IxPane } from "@siemens/ix-react";
import { iconAi, iconLogIn, iconSendRight, iconTrashcan } from "@siemens/ix-icons/icons";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Loading } from "./widgets.jsx";

const GENERIC_SUGGESTIONS = [
  "Which startups are working on industrial AI inspection?",
  "Who are the leading players in chemical recycling?",
  "What is happening in the battery-materials market?",
];
const CONTEXT_SUGGESTIONS = [
  "What does this startup do, and who funds it?",
  "Who are its closest competitors?",
  "How big is its market, and how fast is it growing?",
  "What are the top risks?",
];
const HISTORY_TURNS = 10;
// How each answer was sourced, in words a reviewer can weigh. "unverified" is kept loud on
// purpose: an answer from the model's memory must never read like a searched one.
const PROVIDER = {
  tracxn: { label: "Tracxn", tone: "ok" },
  web: { label: "Web search", tone: "ok" },
  model: { label: "AI knowledge · unverified", tone: "warn" },
  none: { label: "Not answered", tone: "warn" },
};

function hostOf(url, fallback) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return fallback || url; }
}

/* The little markdown a model writes — **bold**, "- " bullets, blank-line paragraphs — as React
   elements. Never HTML: the answer is model output, so it is only ever rendered as text. */
const inline = (line) => line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
  /^\*\*[^*]+\*\*$/.test(part) ? <strong key={i}>{part.slice(2, -2)}</strong> : part);

function RichText({ text }) {
  return String(text || "").split(/\n{2,}/).map((block, i) => {
    const lines = block.split("\n");
    if (lines.every((l) => /^\s*[-*•]\s+/.test(l))) {
      return <ul key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*•]\s+/, ""))}</li>)}</ul>;
    }
    return <p key={i}>{lines.map((l, j) => <React.Fragment key={j}>{j > 0 && <br />}{inline(l)}</React.Fragment>)}</p>;
  });
}

function Answer({ m }) {
  const p = PROVIDER[m.provider] || { label: m.source || "Assistant", tone: "ok" };
  return (
    <div className="dock-msg assistant">
      <span className={`dock-src ${p.tone}`}>{p.label}</span>
      <div className="dock-text"><RichText text={m.text} /></div>
      {m.note && <p className="dock-note">{m.note}</p>}
      {m.evidence?.length > 0 && (
        <ol className="dock-sources" aria-label="Sources">
          {m.evidence.slice(0, 8).map((e, j) => (
            <li key={j}>{e.url
              ? <a href={e.url} target="_blank" rel="noopener noreferrer">{/* Grounding links are redirects; the title is the real site. */}
                  {e.title && !/^https?:/.test(e.title) ? e.title : hostOf(e.url)}</a>
              : e.title}</li>
          ))}
        </ol>
      )}
    </div>
  );
}

/* The assistant: a chat about startups, their competitors and their markets.

   Answers come from the reviewer's own Tracxn connection when there is one, and from the
   model's own web search when there is not (core/chat.py::chat_assistant). The header says
   which, before the first question, so a reviewer knows what a reply will be worth; each reply
   carries its own source label, since a Tracxn miss falls back to the web mid-conversation. */
export default function AssistantDock() {
  const { dockOpen, setDockOpen, dockCtx } = useApp();
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [tracxn, setTracxn] = useState(null);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!dockOpen) return undefined;
    let live = true;
    // Any failure to learn the status reads as "not connected": the web-search answer is the
    // honest default, and a claimed Tracxn connection that is not there would mislabel replies.
    Promise.resolve().then(() => api.tracxnStatus())
      .then((s) => { if (live) setTracxn(s || { connected: false }); })
      .catch(() => { if (live) setTracxn({ connected: false }); });
    return () => { live = false; };
  }, [dockOpen]);

  // The field grows with what is typed, up to a few lines, then scrolls.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [q]);

  if (!dockOpen) return null;

  const send = async (text) => {
    const question = (text || q).trim();
    if (!question || busy) return;
    const history = msgs.filter((m) => m.role === "user" || m.provider !== "none")
      .slice(-HISTORY_TURNS).map((m) => ({ role: m.role, text: m.text }));
    setQ("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: question }]);
    try {
      const r = await api.ask(question, dockCtx?.runId ?? null, history);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, source: r.source, provider: r.provider,
        note: r.note, evidence: r.evidence }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: `Request failed: ${e.message}`, provider: "none" }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight; });
      inputRef.current?.focus();
    }
  };

  const connectTracxn = async () => {
    // Connecting fails only when the server has no Tracxn callback configured; hide the offer then.
    try { window.location.assign((await api.tracxnConnect("home")).url); } catch { setTracxn({ connected: false, configured: false }); }
  };
  const suggestions = dockCtx ? CONTEXT_SUGGESTIONS : GENERIC_SUGGESTIONS;

  return (
    // IxPane owns the title bar and its close button; the pane mounts and unmounts on `dockOpen`
    // (state.jsx), and .assistant-pane in styles.css keeps it a fixed overlay sized to the space
    // under the top bar. See the MIG-11 note there.
    <IxPane className="assistant-pane" composition="right" variant="floating" size="360px"
      expanded noPadding icon={iconAi} heading="Assistant"
      ariaLabelCollapseCloseButton="Close assistant"
      onExpandedChanged={(e) => { if (!e.detail.expanded) setDockOpen(false); }}>
      {dockCtx && <span slot="header" className="ctx" title={dockCtx.company}>on {dockCtx.company}</span>}
      {/* IxPane's own <aside> has no label wiring, so the landmark name comes from this content. */}
      <div className="dock" role="complementary" aria-label="AI assistant">
        <div className="dock-provider" role="status">
          {tracxn == null ? <span className="muted">Checking Tracxn…</span>
            : tracxn.connected ? <span><strong>Tracxn connected.</strong> Answers come from Tracxn first, then web search.</span>
            : <>
                <span><strong>Tracxn not connected.</strong> Answers use AI web search.</span>
                {tracxn.configured !== false && <IxButton variant="subtle-primary" icon={iconLogIn} onClick={connectTracxn}>Connect Tracxn</IxButton>}
              </>}
        </div>
        <div className="dock-body" ref={bodyRef}>
          {msgs.length === 0 && (
            <>
              <p className="muted dock-intro">
                Ask about {dockCtx ? dockCtx.company : "a startup"}, its competitors or its market.
              </p>
              <div className="dock-suggest">
                {suggestions.map((s) => <button key={s} type="button" onClick={() => send(s)}>{s}</button>)}
              </div>
            </>
          )}
          {msgs.map((m, i) => (m.role === "user"
            ? <div key={i} className="dock-msg user">{m.text}</div>
            : <Answer key={i} m={m} />))}
          {busy && <Loading text={tracxn?.connected ? "Checking Tracxn…" : "Searching the web…"} />}
        </div>
        <div className="dock-input">
          <textarea ref={inputRef} className="input dock-field" rows={1} value={q} aria-label="Message the assistant"
            placeholder={dockCtx ? `Ask about ${dockCtx.company}…` : "Ask about a startup or market…"}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
          <div className="dock-actions">
            <IxIconButton icon={iconSendRight} variant="primary" disabled={busy || !q.trim()} aria-label="Send"
              onClick={() => send()} />
            {msgs.length > 0 && <IxIconButton icon={iconTrashcan} variant="subtle-tertiary" disabled={busy}
              aria-label="Clear conversation" onClick={() => setMsgs([])} />}
          </div>
        </div>
      </div>
    </IxPane>
  );
}
