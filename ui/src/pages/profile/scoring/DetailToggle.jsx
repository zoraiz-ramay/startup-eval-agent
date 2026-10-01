import React, { useEffect, useId, useRef, useState } from "react";

/* The one way a reader opens reasoning and sources, everywhere on Scoring & Fit.

   An inline region rather than a side pane: the pane would compete with the assistant dock for
   the same edge of a desktop screen, and a phone has no edge to spare, so one behaviour at every
   width. Opening moves focus into the region; Escape closes it and returns focus to the button. */
export default function DetailToggle({ label = "View reasoning and sources", title, children }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const button = useRef(null);
  const heading = useRef(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) heading.current?.focus();
    else if (wasOpen.current) button.current?.focus();
    wasOpen.current = open;
  }, [open]);
  return (
    <div className="detail-toggle">
      <button ref={button} type="button" className="link-btn" aria-expanded={open} aria-controls={id}
        onClick={() => setOpen((o) => !o)}>{open ? "Hide reasoning and sources" : label}</button>
      {open && (
        <div id={id} className="detail-region" role="region" aria-label={title || label}
          onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setOpen(false); } }}>
          <h4 ref={heading} tabIndex={-1}>{title || "Reasoning and sources"}</h4>
          {children}
        </div>
      )}
    </div>
  );
}
