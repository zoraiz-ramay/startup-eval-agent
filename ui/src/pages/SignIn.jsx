import React from "react";
import ErrorBox from "../components/ErrorBox.jsx";

/**
 * The sign-in screen, and the only surface an unauthenticated visitor ever sees.
 *
 * Renders outside the app shell: `.content` offsets itself by the icon rail, so anything
 * inside it would sit in a column with an empty rail beside it.
 *
 * The failure copy matters more than it looks. Sign-in is gated by Conditional Access at
 * Siemens' highest tier, which means a perfectly valid Siemens account is still refused
 * from a non-compliant device or an unrecognised network — and Entra's own message for
 * that is developer prose about policy evaluation. Whoever hits this is trying to do their
 * job, so each case names the specific next action.
 */
const MESSAGES = {
  device_not_compliant: {
    title: "This device isn't compliant",
    body: "ScoutGrid requires a Siemens-managed device that passes a compliance check. Open Company Portal, run a sync, then try again.",
  },
  device_not_trusted: {
    title: "This device isn't registered",
    body: "This device isn't registered to Siemens. Sign in from your Siemens laptop, or register this device in Company Portal.",
  },
  // A trusted-location failure comes back as the same Conditional Access code as a device
  // failure, so this copy has to name both. Claiming it was the network specifically would
  // send everyone whose device was the real problem down the wrong path.
  access_blocked: {
    title: "Sign-in was blocked by policy",
    body: "A Siemens Conditional Access policy blocked this sign-in. ScoutGrid needs a compliant Siemens device on the corporate network or VPN. If you're already on VPN, disconnect and reconnect so your location is recognised.",
  },
  mfa_required: {
    title: "Multifactor setup is incomplete",
    body: "Finish multifactor-authentication setup in My Account, then try again.",
  },
  not_assigned: {
    title: "Your account isn't approved yet",
    body: "Your Siemens account isn't approved for ScoutGrid. Request access from the app owner.",
  },
  tenant_mismatch: {
    title: "Wrong account",
    body: "That isn't a Siemens tenant account. Sign out of the other account, then sign in with your Siemens one.",
  },
  missing_oid: {
    title: "Wrong account",
    body: "That account is missing the directory details ScoutGrid needs. Sign in with your standard Siemens account.",
  },
  cancelled: { title: "Sign-in cancelled", body: "You closed the sign-in before it finished." },
  expired: { title: "Sign-in timed out", body: "The sign-in took too long to complete. Please try again." },
  // Our bug, not the user's. Saying so stops someone re-running a compliance check for an
  // hour over an expired client secret.
  config_error: {
    title: "Sign-in is misconfigured",
    body: "ScoutGrid's sign-in configuration is wrong or its credentials have expired. This is not something you can fix — please contact the app owner.",
  },
  unknown: { title: "Sign-in failed", body: "Something went wrong signing you in. Please try again." },
};

export default function SignIn() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("e") || "";
  // Entra's correlation ID is the one string Siemens IT will ask for. Sanitised because it
  // arrives in a query string and lands in the DOM.
  const correlationId = (params.get("cid") || "").replace(/[^\w-]/g, "").slice(0, 64);
  const failure = code ? MESSAGES[code] || MESSAGES.unknown : null;

  const signIn = () => {
    const next = window.location.pathname.startsWith("/signin")
      ? "/"
      : window.location.pathname + window.location.search;
    window.location.href = `/api/auth/login?next=${encodeURIComponent(next)}`;
  };

  return (
    <div className="signin">
      <div className="panel signin-card">
        <h1 className="signin-title">ScoutGrid</h1>
        <p className="muted signin-lede">
          Startup evaluation for Siemens partnership decisions. Sign in with your Siemens
          account to continue.
        </p>

        {failure && <ErrorBox message={failure.title} hint={failure.body} />}

        <button className="btn" onClick={signIn}>Sign in with Siemens</button>

        <p className="muted signin-foot">
          Requires a Siemens-managed device on the corporate network or VPN.
          {correlationId && (
            <>
              <br />
              Reference for IT: <code>{correlationId}</code>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
