import React from "react";

/**
 * Simple horizontal progress‑bar that is accessible.
 * Props:
 *   - label: text shown next to the bar
 *   - value: current numeric value
 *   - max: maximum possible value (default 100)
 */
export default function ScoreBar({ label, value, max = 100 }) {
  const percent = max ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className="score-bar" style={{ width: "30%", minWidth: "200px" }}>
      <div style={{ marginBottom: "0.25rem", fontSize: "0.9rem" }}>{label}</div>
      <div
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        style={{
          background: "#e0e0e0",
          borderRadius: "4px",
          height: "1rem",
          width: "100%",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            background: "#3b82f6",
            height: "100%",
            transition: "width 0.3s"
          }}
        />
      </div>
      <div style={{ marginTop: "0.25rem", fontSize: "0.8rem", textAlign: "right" }}>
        {value}/{max}
      </div>
    </div>
  );
}
