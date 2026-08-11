import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../state.jsx";
import { Loading } from "../components/widgets.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const { user, mode, signOut } = useAuth();
  useEffect(() => {
    // /health is public and now reports nothing but liveness; the diagnostics below live
    // behind the session guard.
    api.status().then(setHealth).catch((e) => setError(e.message));
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
        <h3>Account</h3>
        {user && (
          <>
            <Row k="Signed in as" ok val={user.name} />
            <Row k="Email" ok val={user.email} />
          </>
        )}
        {mode === "stub" && (
          <ErrorBox message="Stubbed sign-in"
            hint="This session is a fixed test identity, not a real one. Overrides recorded now are marked unverified." />
        )}
        <button className="btn secondary" onClick={signOut} style={{ marginTop: 8 }}>
          Sign out
        </button>
      </div>
      <div className="panel" style={{ maxWidth: 640 }}>
        <h3>Backend status</h3>
        {error && <ErrorBox message={error} />}
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
