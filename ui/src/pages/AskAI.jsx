import React, { useEffect } from "react";
import { useApp } from "../state.jsx";

export default function AskAI() {
  const { setDockOpen } = useApp();
  useEffect(() => { setDockOpen(true); }, [setDockOpen]);
  return (
    <div>
      <div className="crumb">Workspace &gt; Ask AI</div>
      <div className="page-head"><h1 className="page-title">Ask AI</h1></div>
      <div className="panel" style={{ maxWidth: 720 }}>
        <h3>How the assistant works</h3>
        <p style={{ marginTop: 0 }}>
          The assistant panel (right) combines AI knowledge with a targeted web check: it drafts an
          answer, writes precise search queries, verifies against live results, and cites its sources.
          Open any startup profile first to ground the conversation in that company — otherwise it
          answers across your evaluated portfolio.
        </p>
        <p className="muted" style={{ marginBottom: 0 }}>
          Tip: use the ✦ AI button in the top bar from any screen. On a profile, the Ask tab offers
          startup-specific prompts like “What evidence is weakest?”.
        </p>
      </div>
    </div>
  );
}
