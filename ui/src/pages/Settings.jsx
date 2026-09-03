import React, { useEffect, useState } from "react";
import { IxKeyValueList, IxKeyValue, IxButton } from "@siemens/ix-react";
import { api } from "../api.js";
import { useAuth } from "../state.jsx";
import { Loading } from "../components/widgets.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

// MIG-26: both the account panel and backend-status list are exactly what IxKeyValue names itself
// for -- a label and a value, one row each -- so this replaces the old hand-rolled `Row` (`.spec`
// markup) rather than the IxKpi alternative floated in the backlog: IxKpi's prop table (label/
// value/unit/state) has no notion of a status dot next to the value, and "LLM reasoning: enabled"
// isn't a measurement with a unit, it's a label/status pair. IxKeyValue's `value` prop only takes a
// string, but the component (key-value.js) exposes a `custom-value` slot -- rendered automatically
// whenever `value` is left undefined -- which is exactly the "icon/dot + text" shape these rows
// need, so the status dot goes there instead of a fabricated prop.
function StatusRow({ k, ok, val }) {
  return (
    <IxKeyValue label={k} labelPosition="left">
      <span slot="custom-value" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <span className="status-dot" style={{ background: ok ? "var(--success)" : "var(--warning)" }} />
        {val}
      </span>
    </IxKeyValue>
  );
}

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const { user, mode, signOut } = useAuth();
  useEffect(() => {
    // /health is public and now reports nothing but liveness; the diagnostics below live
    // behind the session guard.
    api.status().then(setHealth).catch((e) => setError(e.message));
  }, []);
  return (
    <div>
      <div className="crumb">Workspace &gt; Settings</div>
      <div className="page-head"><h1 className="page-title">Settings</h1></div>
      <div className="panel" style={{ maxWidth: 640 }}>
        <h3>Account</h3>
        {user && (
          <IxKeyValueList>
            <StatusRow k="Signed in as" ok val={user.name} />
            <StatusRow k="Email" ok val={user.email} />
          </IxKeyValueList>
        )}
        {mode === "stub" && (
          <ErrorBox message="Stubbed sign-in"
            hint="This session is a fixed test identity, not a real one. Overrides recorded now are marked unverified." />
        )}
        <IxButton variant="secondary" onClick={signOut} style={{ marginTop: 8 }}>
          Sign out
        </IxButton>
      </div>
      <div className="panel" style={{ maxWidth: 640 }}>
        <h3>Backend status</h3>
        {error && <ErrorBox message={error} />}
        {!health && !error && <Loading text="Checking backend…" />}
        {health && (
          <IxKeyValueList>
            <StatusRow k="API" ok={health.status === "ok"} val={health.status} />
            <StatusRow k="LLM reasoning" ok={health.llm} val={health.llm ? "enabled" : "offline fallback (set OPENAI_API_KEY)"} />
            <StatusRow k="GlassDollar API" ok={health.glassdollar_key} val={health.glassdollar_key ? "key configured" : "no key (web fallback)"} />
            <StatusRow k="Applications file" ok={!!health.applications_file}
              val={health.applications_file ? `${health.applications_file} · ${health.applications_count} rows` : "not found"} />
          </IxKeyValueList>
        )}
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
          Keys and data paths are configured server-side in <code>.env</code> — never in the browser.
        </p>
      </div>
    </div>
  );
}
