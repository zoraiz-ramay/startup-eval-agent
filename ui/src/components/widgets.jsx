import React from "react";
import { DIMENSIONS, DIMENSION_LABELS } from "../scoring/index.js";

export function PillarPills({ routing }) {
  if (!routing) return null;
  return (
    <span>
      <span className={`pill ${routing.pillar}`}>{routing.pillar}</span>{" "}
      {(routing.secondary || []).map((s) => (
        <span key={s} className={`pill ghost ${s}`}>+ {s}</span>
      ))}{" "}
      {routing.sfs_relevant && (
        <span className="pill sfs" title={routing.sfs_rationale || ""}>💶 SFS financing</span>
      )}
    </span>
  );
}

export function ScoreBar({ label, value }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div>
      <div className="bar-label"><span>{label}</span><span>{v.toFixed(0)}</span></div>
      <div className="bar-track"><div className="bar-fill" style={{ width: `${v}%` }} /></div>
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

export function Spec({ k, children }) {
  return (
    <div className="spec">
      <div className="k">{k}</div>
      <div className="v">{children || <span className="muted">—</span>}</div>
    </div>
  );
}

export function ExtLink({ href, children }) {
  if (!href || !/^https?:\/\//i.test(String(href))) return children || null;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children || String(href).replace(/^https?:\/\//, "")}
    </a>
  );
}

export function Loading({ text }) {
  // role="status" + aria-live="polite" so a screen reader announces that work started and
  // finished. Evaluations run for tens of seconds; without this the page is silent the whole
  // time and a non-sighted reviewer cannot tell a slow run from a broken one. The spinner is
  // decorative and hidden, or it gets read out as meaningless content alongside the message.
  return (
    <p className="muted" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" /> {text}
    </p>
  );
}
