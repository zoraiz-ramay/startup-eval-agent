import React from "react";
import { IxButton } from "@siemens/ix-react";
import { iconArrowRight, iconInfo } from "@siemens/ix-icons/icons";
import ErrorBox from "../components/ErrorBox.jsx";
import Icon from "../components/Icon.jsx";

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
    body: "Venture Lens requires a Siemens-managed device that passes a compliance check. Open Company Portal, run a sync, then try again.",
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
    body: "A Siemens Conditional Access policy blocked this sign-in. Venture Lens needs a compliant Siemens device on the corporate network or VPN. If you're already on VPN, disconnect and reconnect so your location is recognised.",
  },
  mfa_required: {
    title: "Multifactor setup is incomplete",
    body: "Finish multifactor-authentication setup in My Account, then try again.",
  },
  not_assigned: {
    title: "Your account isn't approved yet",
    body: "Your Siemens account isn't approved for Venture Lens. Request access from the app owner.",
  },
  tenant_mismatch: {
    title: "Wrong account",
    body: "That isn't a Siemens tenant account. Sign out of the other account, then sign in with your Siemens one.",
  },
  missing_oid: {
    title: "Wrong account",
    body: "That account is missing the directory details Venture Lens needs. Sign in with your standard Siemens account.",
  },
  cancelled: { title: "Sign-in cancelled", body: "You closed the sign-in before it finished." },
  expired: { title: "Sign-in timed out", body: "The sign-in took too long to complete. Please try again." },
  // Our bug, not the user's. Saying so stops someone re-running a compliance check for an
  // hour over an expired client secret.
  config_error: {
    title: "Sign-in is misconfigured",
    body: "Venture Lens's sign-in configuration is wrong or its credentials have expired. This is not something you can fix — please contact the app owner.",
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

  /* The device requirement sits above the button as a notice, not in small print under it:
     it is the reason most refused sign-ins fail, so it has to be read before the click. A
     failure (ErrorBox, role="alert") takes the same place and says what to do next. */
  return (
    <div className="signin">
      <main className="signin-card" aria-labelledby="signin-title">
        <div className="signin-brand">
          <span className="signin-mark" aria-hidden="true">SI</span>
          <h1 id="signin-title" className="signin-title">Venture Lens</h1>
        </div>
        <p className="signin-lede">Startup evaluation for Siemens partnership decisions.</p>
        <p className="signin-sub">Sign in with your official Siemens account to access the grid.</p>

        {failure
          ? <ErrorBox message={failure.title} hint={failure.body} />
          : (
            <div className="signin-notice">
              <Icon icon={iconInfo} size={16} />
              <p>Requires a Siemens-managed device on the corporate network or VPN.</p>
            </div>
          )}

        <IxButton className="signin-button" iconRight={iconArrowRight} onClick={signIn}>Sign in with Siemens</IxButton>

        {correlationId && <p className="signin-foot">Reference for IT: <code>{correlationId}</code></p>}
      </main>
    </div>
  );
}
