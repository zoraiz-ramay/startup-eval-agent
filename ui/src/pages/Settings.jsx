import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Loading } from "../components/widgets.jsx";

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(e.message));
  }, []);
  const Row = ({ k, ok, val }) => (
    <div className="spec">
      <div className="k">{k}</div>
      <div className="v">
        <span className="status-dot" style={{ background: ok ? "var(--success)" : "var(--warning)" }} />
        {val}
      </div>
    </div>
  );
  return (
    <div>
      <div className="crumb">Workspace &gt; Settings</div>
      <div className="page-head"><h1 className="page-title">Settings</h1></div>
      <div className="panel" style={{ maxWidth: 640 }}>
        <h3>Backend status</h3>
        {error && <div className="error-box">{error}</div>}
        {!health && !error && <Loading text="Checking backend…" />}
        {health && (
          <>
            <Row k="API" ok={health.status === "ok"} val={health.status} />
            <Row k="LLM reasoning" ok={health.llm} val={health.llm ? "enabled" : "offline fallback (set OPENAI_API_KEY)"} />
            <Row k="GlassDollar API" ok={health.glassdollar_key} val={health.glassdollar_key ? "key configured" : "no key (web fallback)"} />
            <Row k="Applications file" ok={!!health.applications_file}
              val={health.applications_file ? `${health.applications_file} · ${health.applications_count} rows` : "not found"} />
          </>
        )}
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
          Keys and data paths are configured server-side in <code>.env</code> — never in the browser.
        </p>
      </div>
    </div>
  );
}
