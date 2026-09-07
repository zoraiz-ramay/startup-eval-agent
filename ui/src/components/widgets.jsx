import React from "react";
import { IxKeyValue, IxPill, IxSpinner } from "@siemens/ix-react";
import { DIMENSIONS, DIMENSION_LABELS } from "../scoring/index.js";

// MIG-01: the four pillar colours themselves are unchanged (see tokens.css) — only the delivery
// mechanism moves, from a `.pill.<Pillar>` CSS class to IxPill's `variant="custom"` background/
// pillColor props, which is the only way to hand it a colour from JS rather than a class name.
const PILLAR_PILL_STYLE = {
  Connect: { background: "var(--pillar-connect-bg)", pillColor: "var(--pillar-connect)" },
  Collaborate: { background: "var(--pillar-collaborate-bg)", pillColor: "var(--pillar-collaborate)" },
  Empower: { background: "var(--pillar-empower-bg)", pillColor: "var(--pillar-empower)" },
  Pass: { background: "var(--pillar-pass-bg)", pillColor: "var(--pillar-pass)" },
};

export function PillarPill({ pillar, ghost = false, children, ...rest }) {
  const style = PILLAR_PILL_STYLE[pillar];
  // Absence renders the bare pillar name rather than a mis-coloured pill for an unknown value.
  if (!style) return <span {...rest}>{children ?? pillar}</span>;
  return (
    <IxPill variant="custom" background={style.background} pillColor={style.pillColor} outline={ghost} {...rest}>
      {children ?? pillar}
    </IxPill>
  );
}

// MIG-29: both the primary pillar and each `secondary` pillar carried a `.pill.<Pillar>` class
// (the secondary span's class list was `pill ghost <Pillar>`, which the CSS selector matches
// regardless of the extra `ghost` class) — so both go through PillarPill now, and PillarPill's own
// `ghost` prop (an outline treatment, see the component above) is what the secondary pillars use
// in place of the old bespoke `.pill.ghost` rule.
export function PillarPills({ routing }) {
  if (!routing) return null;
  return (
    <span>
      <PillarPill pillar={routing.pillar} />{" "}
      {(routing.secondary || []).map((s) => (
        <span key={s}>+ <PillarPill pillar={s} ghost /></span>
      ))}{" "}
      {routing.sfs_relevant && (
        <span className="pill sfs" title={routing.sfs_rationale || ""}>💶 SFS financing</span>
      )}
    </span>
  );
}

// MIG-02: not IxProgressIndicator — its role="progressbar" (verified: no ARIA override in
// components.md) means task completion, and a score of 62 is not 62% done toward anything.
// role="meter" is the correct native ARIA pattern for a fixed-range measurement, so this stays a
// custom widget rather than moving to IxKpi, whose prop table (label/value/unit/state) has no
// notion of a range or a visual fill and would drop the 0-100 scale the bar-track exists to show.
export function ScoreBar({ label, value }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div>
      <div className="bar-label"><span>{label}</span><span>{v.toFixed(0)}</span></div>
      <div
        className="bar-track"
        role="meter"
        aria-valuenow={v}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className="bar-fill" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}

export function Radar({ dimensions, overlay = null, overlayLabel = "", size = 260 }) {
  // Axis order comes from the shared registry so the radar and the score breakdown cannot end up
  // listing the dimensions differently.
  const keys = DIMENSIONS.filter((k) => k in (dimensions || {}));
  if (!keys.length) return null;
  const cx = size / 2, cy = size / 2, r = size / 2 - 34;
  const pt = (i, val) => {
    const a = (Math.PI * 2 * i) / keys.length - Math.PI / 2;
    return [cx + Math.cos(a) * r * (val / 100), cy + Math.sin(a) * r * (val / 100)];
  };
  // Plotted values are pinned to the outer ring. A contribution can exceed 100 (an emphasised
  // dimension carries more than its even share), and without this it would be drawn outside the
  // viewport as a shape that reads as broken rather than as "off the scale".
  const plot = (i, val) => pt(i, Math.min(100, val));
  const shape = (vals) => keys.map((k, i) => plot(i, vals[k]).join(",")).join(" ");
  const ring = (frac) => keys.map((_, i) => pt(i, frac * 100).join(",")).join(" ");

  const overlayKeys = overlay ? keys.filter((k) => typeof overlay[k] === "number") : [];
  const hasOverlay = overlayKeys.length === keys.length;
  const clamped = keys.filter((k) => dimensions[k] > 100 || (hasOverlay && overlay[k] > 100));
  const label = "Score radar. " + (hasOverlay
    ? `Solid outline: evidence scores. Dashed outline: ${overlayLabel || "contribution under your what-if weighting"}. `
    : "") + (clamped.length
    ? `${clamped.map((k) => DIMENSION_LABELS[k]).join(" and ")} reach past the outer ring and are drawn at the edge.`
    : "");

  return (
    <svg width={size} height={size} role="img" aria-label={label.trim()}>
      {[0.33, 0.66, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke="var(--border, #e4e8ee)" strokeWidth="1" />
      ))}
      <polygon points={shape(dimensions)} fill="rgba(36,87,197,.15)" stroke="var(--accent, #2457c5)" strokeWidth="2" />
      {hasOverlay && (
        // Dashed rather than a second colour: it needs no new token, adds no ix_lint finding, and
        // distinguishes the series without relying on colour vision.
        <polygon points={shape(overlay)} fill="none" stroke="var(--text-2)" strokeWidth="2" strokeDasharray="4 3" />
      )}
      {keys.map((k, i) => {
        const [x, y] = pt(i, 118);
        return (
          <text key={k} x={x} y={y} fill="var(--text-2, #5a6472)" fontSize="11" textAnchor="middle">
            {DIMENSION_LABELS[k]}
          </text>
        );
      })}
    </svg>
  );
}

// MIG-20: IxKeyValue's `value` prop only takes a string (components.md), but Spec's callers pass
// arbitrary JSX — links, chips, muted placeholders. Its compiled source (key-value.js) renders
// the `custom-value` slot whenever `value` is left undefined, which is the only way to hand it a
// React node rather than text, so `value` itself is never set here.
export function Spec({ k, children }) {
  return (
    <IxKeyValue label={k}>
      <div slot="custom-value">{children || <span className="muted">—</span>}</div>
    </IxKeyValue>
  );
}

/* A stored value without a scheme is still a link.
   `core/data.py::web_profile_row` derives the website from a search result and can store a bare
   host ("bliro.io"). Every such profile rendered the Website row EMPTY — the value was there the
   whole time, and a strict `^https?://` test dropped it on the floor. Upgrading here is what
   rescues the runs already in the database; the engine normalises new ones at the source.

   The bar is deliberately narrow, because `source_url` legitimately carries non-URL labels:
   "GlassDollar" for a database fact, a filename for a pitch deck. Prefixing those would
   manufacture a link to a host that does not exist, which is worse than showing plain text. */
const _BARE_DOMAIN = /^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}(\/\S*)?$/i;
const _FILE_EXT = /\.(pdf|docx?|xlsx?|pptx?|csv|txt|zip|png|jpe?g|gif|svg)$/i;

export function toHref(value) {
  const s = String(value || "").trim();
  if (!s) return "";
  if (/^https?:\/\//i.test(s)) return s;
  // Any other scheme (mailto:, javascript:, data:) is never turned into an external link.
  if (/^[a-z][a-z0-9+.-]*:/i.test(s)) return "";
  return _BARE_DOMAIN.test(s) && !_FILE_EXT.test(s) ? `https://${s}` : "";
}

export function ExtLink({ href, children }) {
  const url = toHref(href);
  if (!url) return children || null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {children || String(href).replace(/^https?:\/\//i, "")}
    </a>
  );
}

export function Loading({ text }) {
  // role="status" + aria-live="polite" so a screen reader announces that work started and
  // finished. Evaluations run for tens of seconds; without this the page is silent the whole
  // time and a non-sighted reviewer cannot tell a slow run from a broken one. IxSpinner claims
  // role="status"/aria-busy="true" on its own host unconditionally (ix/spinner.js) regardless of
  // what's passed in, so leaving it unhidden would give this region two competing status
  // announcers. aria-hidden="true" is preserved through that (only role/aria-busy get
  // overwritten), which removes the whole element from the accessibility tree per spec — so the
  // spinner stays purely decorative and the outer <p> is the one and only thing a screen reader
  // hears.
  return (
    <p className="muted" role="status" aria-live="polite">
      <IxSpinner size="xx-small" aria-hidden="true" /> {text}
    </p>
  );
}
