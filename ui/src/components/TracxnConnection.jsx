import React, { useEffect, useState } from "react";
import { IxButton } from "@siemens/ix-react";
import { iconLogIn, iconDisconnected } from "@siemens/ix-icons/icons";
import { api } from "../api.js";
import ErrorBox from "./ErrorBox.jsx";

export default function TracxnConnection({ compact = false }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.tracxnStatus().then(setState).catch((e) => setError(e.message)); }, []);
  const connect = async () => {
    setBusy(true); setError("");
    try {
      if (state?.connected) setState(await api.tracxnDisconnect());
      else window.location.assign((await api.tracxnConnect("home")).url);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <div className={compact ? "connection-compact" : "connection-strip"}>
    {!compact && <div><strong>Tracxn {state?.connected ? "connected" : "company intelligence"}</strong>
      <p className="muted">{state?.connected ? "Your account is used automatically for each new evaluation." : "Connect your MCP-enabled account. Otherwise, research uses GlassDollar and the web."}</p></div>}
    {compact && state?.connected && <span className="muted">Tracxn connected</span>}
    <IxButton variant="secondary" icon={state?.connected ? iconDisconnected : iconLogIn} disabled={busy || !state} onClick={connect}>{busy ? "Please wait…" : state?.connected ? "Disconnect Tracxn" : compact ? "Log in to Tracxn" : "Connect Tracxn"}</IxButton>
    {compact && !state?.connected && <span className="tracxn-optional muted">Optional · search works without Tracxn</span>}
    {error && <ErrorBox message={error} />}
  </div>;
}
