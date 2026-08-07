import React, { useState, useMemo } from "react";

// Mapping from source quality string to badge background color
const qualityColors = {
  high: "green",
  medium: "orange",
  low: "red",
};

function getBadgeColor(quality) {
  const q = String(quality).toLowerCase();
  return qualityColors[q] || "gray";
}

function SourceQualityLegend() {
  return (
    <div
      className="source-quality-legend"
      aria-label="Source quality legend"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        margin: "0.75rem 0",
        flexWrap: "wrap",
      }}
    >
      <span style={{ fontWeight: 600 }}>Source quality:</span>
      <span className="badge" style={{ backgroundColor: qualityColors.high }}>
        High
      </span>
      <span className="badge" style={{ backgroundColor: qualityColors.medium }}>
        Medium
      </span>
      <span className="badge" style={{ backgroundColor: qualityColors.low }}>
        Low
      </span>
    </div>
  );
}

export default function EvidenceTab({ evidenceList }) {
  // Loading state when data is not yet available
  if (evidenceList == null) {
    return (
      <div role="status" aria-live="polite" className="loading">
        Loading...
      </div>
    );
  }

  // Empty state when the list is present but contains no items
  if (evidenceList.length === 0) {
    return <div className="empty">No evidence found for this startup.</div>;
  }

  const [filter, setFilter] = useState("");

  const filteredEvidence = useMemo(() => {
    const lowered = filter.toLowerCase();
    return evidenceList.filter((e) =>
      Object.values(e).some((value) => String(value).toLowerCase().includes(lowered))
    );
  }, [filter, evidenceList]);

  const handleClear = () => {
    setFilter("");
  };

  return (
    <div className="evidence-tab">
      <div
        className="filter-container"
        style={{ position: "relative", display: "inline-block" }}
      >
        <input
          type="text"
          placeholder="Filter evidence..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Evidence filter"
          style={{ paddingRight: "1.5rem" }}
        />
        {filter && (
          <button
            type="button"
            aria-label="Clear evidence filter"
            onClick={handleClear}
            style={{
              position: "absolute",
              right: "0.25rem",
              top: "50%",
              transform: "translateY(-50%)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "1rem",
            }}
          >
            ✕
          </button>
        )}
      </div>

      <SourceQualityLegend />

      {filter && filteredEvidence.length === 0 && (
        <div className="empty">No evidence matches filter</div>
      )}

      <table className="evidence-table">
        <thead>
          <tr>
            {evidenceList[0] &&
              Object.keys(evidenceList[0]).map((key) => <th key={key}>{key}</th>)}
          </tr>
        </thead>
        <tbody>
          {filteredEvidence.map((e, idx) => (
            <tr key={idx}>
              {Object.entries(e).map(([key, val], i) => (
                <td key={i}>
                  {key === "source_quality" ? (
                    <span className="badge" style={{ backgroundColor: getBadgeColor(val) }}>
                      {val}
                    </span>
                  ) : (
                    val
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
