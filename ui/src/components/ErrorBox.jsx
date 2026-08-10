import React from "react";

/**
 * The app's single error surface.
 *
 * role="alert" makes a failure audible to a screen reader the moment it appears — errors here are
 * usually "the backend is unreachable", which a sighted user sees instantly and a non-sighted one
 * otherwise never learns. Styling lives in `.error-box` (styles.css) so the colours come from
 * design tokens; inline colours previously hard-coded `red`, which both fought the token system
 * and ignored the theme.
 */
export default function ErrorBox({ message, hint }) {
  if (!message) return null;
  return (
    <div role="alert" className="error-box">
      {message}{hint ? ` — ${hint}` : ""}
    </div>
  );
}
