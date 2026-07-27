import React from "react";

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

const DIM_LABELS = {
  traction: "Traction", siemens_fit: "Siemens Fit", product: "Product",
  market: "Market", founder: "Founder", ecosystem: "Ecosystem",
};

export function Radar({ dimensions, size = 260 }) {
  const keys = Object.keys(DIM_LABELS).filter((k) => k in (dimensions || {}));
  if (!keys.length) return null;
  const cx = size / 2, cy = size / 2, r = size / 2 - 34;
  const pt = (i, val) => {
    const a = (Math.PI * 2 * i) / keys.length - Math.PI / 2;
    return [cx + Math.cos(a) * r * (val / 100), cy + Math.sin(a) * r * (val / 100)];
  };
  const poly = keys.map((k, i) => pt(i, dimensions[k]).join(",")).join(" ");
  const ring = (frac) => keys.map((_, i) => pt(i, frac * 100).join(",")).join(" ");
  return (
    <svg width={size} height={size} role="img" aria-label="Score radar">
      {[0.33, 0.66, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke="var(--border, #e4e8ee)" strokeWidth="1" />
      ))}
      <polygon points={poly} fill="rgba(36,87,197,.15)" stroke="var(--accent, #2457c5)" strokeWidth="2" />
      {keys.map((k, i) => {
        const [x, y] = pt(i, 118);
        return (
          <text key={k} x={x} y={y} fill="var(--text-2, #5a6472)" fontSize="11" textAnchor="middle">
            {DIM_LABELS[k]}
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
  return (
    <p className="muted"><span className="spinner" /> {text}</p>
  );
}
