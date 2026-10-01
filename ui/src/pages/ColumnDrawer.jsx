import React, { useEffect, useRef, useState } from "react";
import { IxButton, IxPane } from "@siemens/ix-react";
import { COLUMNS } from "./exploreColumns.jsx";

/* The Database grid's column chooser and "save view" form, in a side pane. */
export default function ColumnDrawer({ open, onClose, cols, setCols, onSaveView }) {
  const [viewName, setViewName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const asideRef = useRef(null);
  // MIG-14: IxPane's own Escape handler (pane.js's registerEscapeListener) is attached to the
  // host element itself, and only fires while focus is inside it — kept here too, on window,
  // as a second path that doesn't depend on where focus happens to be. Both call the same
  // onClose, which is idempotent, so there is no double-close to guard against.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  // IxPane moves focus into itself on its own (pane.js's focusFirstSlottedElement), but only
  // after its open animation's completion callback fires — real in a browser, not guaranteed in
  // a test environment that doesn't run animation frames the same way. Doing it here too, plain
  // and synchronous, means the "focus lands inside" contract holds regardless of the pane's own
  // animation timing.
  useEffect(() => {
    if (open) asideRef.current?.focus();
  }, [open]);
  if (!open) return null;
  const move = (i, d) => {
    const next = [...cols];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    setCols(next);
  };
  const inactive = Object.keys(COLUMNS).filter((k) => !cols.includes(k));
  return (
    // variant="floating" + composition="right" is the same overlay shape AssistantDock (MIG-11)
    // already uses; .explore-drawer-pane forces position:fixed the same way .assistant-pane
    // does, since IxPane defaults every composition to position:relative (verified against
    // pane.css). closeOnClickOutside replaces the old bare `.drawer-mask` div outright — X-04's
    // complaint was a mouse-only control invisible to assistive tech, and there is now no
    // backdrop element at all for that problem to attach to; a plain window click listener
    // (pane.js's onExpandedChange, gated on event.composedPath()) closes it instead.
    <IxPane
      className="explore-drawer-pane"
      variant="floating"
      composition="right"
      size="320px"
      expanded
      closeOnClickOutside
      heading="Customise columns"
      ariaLabelCollapseCloseButton="Close customise columns"
      onExpandedChanged={(e) => { if (!e.detail.expanded) onClose(); }}
    >
      {/* IxPane's <aside> carries no aria-labelledby/aria-label wired to `heading` (verified
          against the compiled source, same gap AssistantDock's own comment documents) — the
          "Customise columns" landmark name has to come from a light-DOM wrapper we slot in. */}
      <div ref={asideRef} tabIndex={-1} role="complementary" aria-label="Customise columns">
        <form className="save-view-form" onSubmit={async (e) => {
          e.preventDefault(); if (saving || !viewName.trim()) return;
          setSaving(true); setSaveError("");
          try { await onSaveView(viewName.trim(), cols); setViewName(""); }
          catch (error) { setSaveError(error.message); }
          finally { setSaving(false); }
        }}>
          <label htmlFor="saved-view-name">Save these columns and filters</label>
          <input id="saved-view-name" className="input" placeholder="View name…" maxLength={80} value={viewName} onChange={(e) => setViewName(e.target.value)} />
          <IxButton type="submit" disabled={saving || !viewName.trim()}>{saving ? "Saving…" : "Save view"}</IxButton>
          {saveError && <p role="alert">{saveError}</p>}
        </form>
        <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>Reorder, remove, or add columns.</p>
        {cols.map((k, i) => (
          <div key={k} className="drow">
            <input type="checkbox" checked readOnly aria-label={`Remove ${COLUMNS[k].label}`}
              onClick={() => setCols(cols.filter((c) => c !== k))} />
            {COLUMNS[k].label}
            <span className="mv">
              <button onClick={() => move(i, -1)} aria-label="Move up">↑</button>
              <button onClick={() => move(i, 1)} aria-label="Move down">↓</button>
            </span>
          </div>
        ))}
        {inactive.length > 0 && <h4 className="muted" style={{ margin: "14px 0 4px", fontSize: 11 }}>AVAILABLE</h4>}
        {inactive.map((k) => (
          <div key={k} className="drow">
            <input type="checkbox" checked={false} readOnly aria-label={`Add ${COLUMNS[k].label}`}
              onClick={() => setCols([...cols, k])} />
            {COLUMNS[k].label}
          </div>
        ))}
        <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
          <button className="btn secondary" onClick={() => setCols(DEFAULT_COLS)}>Restore defaults</button>
        </div>

      </div>
    </IxPane>
  );
}
