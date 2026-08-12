import React, { useEffect, useState } from "react";
import { api } from "../api.js";

/* Claim-Evidence Matrix
 * Shows each evaluated claim, its Tracxn benchmark dimension, verdict, source
 * quality and a citation. Benchmarked against the Tracxn profile schema
 * (https://tracxn.com). Follows Siemens iX table + badge conventions. */

const VERDICT_STYLE = {
  supported: { label: "Supported", bg: "#e6f4ea", fg: "#137333" },
  partially_supported: { label: "Partial", bg: "#fef7e0", fg: "#a56300" },
  unsupported: { label: "Unsupported", bg: "#f1f3f4", fg: "#5f6368" },
  contradicted: { label: "Contradicted", bg: "#fce8e6", fg: "#c5221f" },
  unclear: { label: "Unclear", bg: "#f1f3f4", fg: "#5f6368" },
};

const QUALITY_STYLE = {
  high: { label: "High", bg: "#d4edda", fg: "#155724" },
  medium: { label: "Medium", bg: "#fff3cd", fg: "#856404" },
  low: { label: "Low", bg: "#f8d7da", fg: "#721c24" },
};

function Verdict({ verdict }) {
  const s = VERDICT_STYLE[verdict] || VERDICT_STYLE.unclear;
  return (
    <span className="badge" style={{ background: s.bg, color: s.fg }}>
      {s.label}
    </span>
  );
}

function QualityBadge({ quality }) {
  const key = (quality || "").toString().toLowerCase();
  const s = QUALITY_STYLE[key] || { label: quality, bg: "#e0e0e0", fg: "#000000" };
  return (
    <span className="badge" style={{ background: s.bg, color: s.fg }}>
      {s.label}
    </span>
  );
}

export default function ClaimEvidenceMatrix({ startup }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!startup) return;
    setLoading(true);
    setError("");
    api
      .evidence(startup)
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load evidence."))
      .finally(() => setLoading(false));
  }, [startup]);

  if (!startup) return null;
  if (loading)
    return (
      <div className="cem-state" role="status" aria-live="polite">
        Loading claim-evidence matrix…
      </div>
    );
  if (error)
    return (
      <div className="cem-state cem-error" role="alert">
        {error}
      </div>
    );
  if (!data || !data.matrix || data.matrix.length === 0)
    return <div className="cem-state">No claims to display yet.</div>;

  const b = data.benchmark || {};
  const pct = Math.round((b.coverage_ratio || 0) * 100);

  return (
    <section className="cem" aria-label="Claim-evidence matrix">
      <header className="cem-head">
        <h3>Claim-Evidence Matrix</h3>
        <p className="sub">
          Benchmarked against{" "}
          <a href={b.source} target="_blank" rel="noreferrer">
            {b.benchmark || "Tracxn"}
          </a>{" "}
          — coverage {pct}% ({(b.covered || []).length}/{(b.dimensions || []).length} dimensions)
        </p>
      </header>
      <div className="cem-scroll">
        <table className="cem-table" role="table">
          <thead>
            <tr>
              <th>Claim</th>
              <th>Benchmark dimension</th>
              <th>Verdict</th>
              <th>Quality</th>
              <th>Confidence</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {data.matrix.map((r, i) => (
              <tr key={i}>
                <td>{r.claim || r.field}</td>
                <td>{r.benchmark_dimension}</td>
                <td>
                  <Verdict verdict={r.verdict} />
                </td>
                <td>
                  <QualityBadge quality={r.source_quality} />
                </td>
                <td>{Math.round((r.confidence || 0) * 100)}%</td>
                <td>
                  {r.evidence_url ? (
                    <a href={r.evidence_url} target="_blank" rel="noreferrer">
                      citation
                    </a>
                  ) : (
                    <span className="sub">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
