import React from "react";

/* Small SVG/CSS charts for Scoring & Fit, coloured with the iX chart tokens (tokens.css).

   No chart library: iX ships no chart component, its ECharts theme would add a large dependency
   and draw to a canvas, and these five shapes are each a few dozen lines of SVG. Every chart is a
   `role="img"` with an aria-label that states its numbers, so the picture is never the only way
   to read them, and a missing value is drawn as missing — never as a zero. */

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** A 0–max ring with the value in the middle. */
export function RingGauge({ value, max = 100, size = 120, stroke = 10, color = "var(--accent)", label, center, sub }) {
  const v = num(value);
  const r = (size - stroke) / 2 - 2;
  const c = 2 * Math.PI * r;
  const h = size / 2;
  const filled = v == null ? 0 : (c * clamp(v, 0, max)) / max;
  return (
    <svg className="ring-gauge" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={label || (v == null ? "not scored" : `${v} of ${max}`)}>
      <circle cx={h} cy={h} r={r} fill="none" stroke="var(--chart-track)" strokeWidth={stroke}
        strokeDasharray={v == null ? "4 5" : undefined} />
      {filled > 0 && <circle cx={h} cy={h} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={`${filled} ${c}`} transform={`rotate(-90 ${h} ${h})`} />}
      <text x={h} y={sub ? h + 2 : h + size * 0.08} textAnchor="middle" className="ring-value"
        style={{ fontSize: Math.round(size * 0.22) }}>{center ?? (v == null ? "—" : Math.round(v))}</text>
      {sub && <text x={h} y={h + size * 0.17} textAnchor="middle" className="ring-sub"
        style={{ fontSize: Math.max(10, Math.round(size * 0.09)) }}>{sub}</text>}
    </svg>
  );
}

/** One bar split into parts of a whole (the weighted contributions that sum to the total). A part
    that is not scored is a hatched block the width of what it could have added. */
export function StackedBar({ segments, max = 100, label }) {
  return (
    <div className="stacked-bar" role="img" aria-label={label}>
      <div className="stacked-track">
        {segments.map((s) => (
          <div key={s.key} className={`stacked-seg${s.value == null ? " pending" : ""}`}
            style={{ width: `${(100 * (s.value == null ? s.capacity || 0 : s.value)) / max}%`, background: s.value == null ? undefined : s.color }} />
        ))}
      </div>
      <div className="stacked-axis" aria-hidden="true">{[0, 25, 50, 75, 100].map((t) => <span key={t}>{Math.round((t * max) / 100)}</span>)}</div>
    </div>
  );
}

/** A thin 0–max bar with a colour; null is a hatched, empty track. */
export function MiniBar({ value, max = 100, color = "var(--accent)", label }) {
  const v = num(value);
  return (
    <div className={`mini-track${v == null ? " pending" : ""}`} role="img" aria-label={label}>
      {v != null && v > 0 && <div style={{ width: `${(100 * clamp(v, 0, max)) / max}%`, background: color }} />}
    </div>
  );
}

/** N-axis radar, 0–max on every axis. Axis order is the caller's. Labels sit outside the outer
    ring and read outward (left of centre anchored at their end, right at their start), with side
    margins wide enough that a label never lands on a data point. Labels carry names only — the
    values are in the aria-label and in whatever the caller puts beside the chart. `active`
    marks the axis the reader has opened. */
export function RadarChart({ axes, max = 5, size = 240, color = "var(--chart-team)", label, active = -1 }) {
  const n = axes.length;
  const pad = 70;
  const w = size + 2 * pad;
  const cx = w / 2, cy = size / 2, r = size / 2 - 30;
  const pt = (i, v) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    return [cx + Math.cos(a) * r * (v / max), cy + Math.sin(a) * r * (v / max)];
  };
  const ring = (lvl) => axes.map((_, i) => pt(i, lvl).join(",")).join(" ");
  const shape = axes.map((a, i) => pt(i, clamp(num(a.value) ?? 0, 0, max)).join(",")).join(" ");
  return (
    <svg className="radar-chart" width={w} height={size} viewBox={`0 0 ${w} ${size}`} role="img"
      aria-label={label || axes.map((a) => `${a.label} ${a.value} of ${max}`).join(", ")}>
      {Array.from({ length: max }, (_, k) => <polygon key={k} points={ring(k + 1)} fill="none" stroke="var(--chart-grid)" />)}
      {axes.map((_, i) => { const [x, y] = pt(i, max); return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--chart-axes)" />; })}
      <polygon points={shape} fill={color} fillOpacity=".25" stroke={color} strokeWidth="2" />
      {axes.map((a, i) => { const [x, y] = pt(i, clamp(num(a.value) ?? 0, 0, max)); return <circle key={i} cx={x} cy={y} r={i === active ? 5.5 : 3.5} fill={color} />; })}
      {axes.map((a, i) => {
        const [x, y] = pt(i, max);
        const side = Math.abs(x - cx) < 4 ? 0 : x > cx ? 1 : -1;
        const tx = x + side * 10;
        const ty = side === 0 ? (y < cy ? y - 10 : y + 18) : y + 4;
        return <text key={a.label} x={tx} y={ty} textAnchor={side === 0 ? "middle" : side > 0 ? "start" : "end"}
          className={`chart-label${i === active ? " on" : ""}`}>{a.short || a.label}</text>;
      })}
    </svg>
  );
}

/** A scale divided into rubric bands, with a marker where a cited value falls. `edges` are the
    band boundaries; `active` is the band the engine scored, highlighted so the picture and the
    score cannot disagree. */
export function BandScale({ edges, min, max, value, log = false, active, color = "var(--chart-market)", format = String, label }) {
  const f = (v) => (log ? Math.log10(v) : v);
  const pos = (v) => (100 * (f(clamp(v, min, max)) - f(min))) / (f(max) - f(min));
  const stops = [min, ...edges, max];
  const v = num(value);
  return (
    <div className="band-scale" role="img" aria-label={label}>
      <div className="band-track">
        {stops.slice(0, -1).map((s, i) => (
          <div key={i} className={`band-seg${i === active ? " on" : ""}`}
            style={{ left: `${pos(s)}%`, width: `${pos(stops[i + 1]) - pos(s)}%`, background: i === active ? color : undefined }} />
        ))}
        {v != null && <div className="band-marker" style={{ left: `${pos(v)}%`, background: color }} />}
      </div>
      <div className="band-ticks" aria-hidden="true">
        {edges.map((e) => <span key={e} style={{ left: `${pos(e)}%` }}>{format(e)}</span>)}
      </div>
    </div>
  );
}

/** One cell per criterion, shaded by level, each a disclosure button for that criterion's detail.
    Pressing an open cell closes it and pressing another switches to it, so criteria are read one
    at a time. `idPrefix` names each cell so a detail panel can point back at the one it belongs to. */
export function HeatStrip({ cells, max = 3, name, openId = null, onToggle, idPrefix, controls }) {
  return (
    <span className="heat-strip" role="group" aria-label={`${name} criteria`}>
      {cells.map((c) => {
        const open = openId === c.id;
        return (
          <button key={c.id} id={`${idPrefix}-${c.id}`} type="button" className={`heat-item${open ? " open" : ""}`}
            aria-expanded={open} aria-controls={open ? controls : undefined} onClick={() => onToggle(c.id)}
            aria-label={`${c.label}: ${c.score} of ${max}, ${c.anchor}`}>
            <span className={`heat-cell l${clamp(c.score, 0, max)}`}>{c.score}</span>
            <span className="heat-label">{c.short || c.label}</span>
          </button>
        );
      })}
    </span>
  );
}
