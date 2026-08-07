import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Loading } from "../components/widgets.jsx";

export default function Alerts() {
  const nav = useNavigate();
  const { watchlist, toggleWatch } = useApp();
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState("");

  const loadRuns = useCallback(() => {
    setError("");
    setRuns(null);
    return api
      .runs()
      .then((d) => setRuns(d.runs))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // watchlist is keyed by company; show the LATEST run per watched company
  const watched = [];
  const seen = new Set();
  for (const r of runs || []) {
    if (watchlist.includes(r.company) && !seen.has(r.company.toLowerCase())) {
      seen.add(r.company.toLowerCase());
      watched.push(r);
    }
  }

  // Export the currently watched companies as a CSV file
  const handleExportCsv = () => {
    if (watched.length === 0) {
      return;
    }
    const header = ["company", "score", "pillar", "last_evaluated"];
    const rows = watched.map((r) => [
      r.company,
      Number(r.final_score).toFixed(0),
      r.pillar,
      String(r.created_at).slice(0, 10)
    ]);
    const csvContent = [header, ...rows]
      .map((row) => row.join(","))
      .join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tracked_companies.csv";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="crumb">Workspace &gt; Tracking</div>
      <div className="page-head">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h1 className="page-title">Tracking</h1>
          <button
            type="button"
            className="tool-btn"
            onClick={loadRuns}
            aria-label="Refresh tracked companies"
            title="Refresh tracked companies"
          >
            ↻
          </button>
          <button
            type="button"
            className="tool-btn"
            onClick={handleExportCsv}
            disabled={watched.length === 0}
            aria-label="Export tracked companies as CSV"
            title="Export CSV"
          >
            Export CSV
          </button>
        </div>
        <span className="page-meta">{watched.length} companies watched</span>
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      {(!runs && !error) && (
        <Loading aria-label="Loading runs" description="Fetching tracked companies…" />
      )}
      {runs && watched.length === 0 && (
        <div className="empty">
          <div className="big">◉</div>
          <h4>Nothing tracked yet</h4>
          <p>
            Star companies in Explore or on a profile to build your watchlist.
            Re-evaluate any time to refresh scores and signals.
          </p>
          <button className="btn secondary" onClick={() => nav("/explore")}>Open Explore</button>
        </div>
      )}
      {watched.length > 0 && (
        <div className="panel" style={{ padding: 0 }}>
          <table className="dtable">
            <thead>
              <tr>
                <th />
                <th>Company</th>
                <th>Score</th>
                <th>Route</th>
                <th>Last evaluated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {watched.map((r) => (
                <tr
                  key={r.id}
                  tabIndex="0"
                  onClick={() => nav(`/startup/${r.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      nav(`/startup/${r.id}`);
                    }
                  }}
                >
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      className="star-btn on"
                      onClick={() => toggleWatch(r.company)}
                      aria-label={`Unwatch ${r.company}`}
                    >
                      ★
                    </button>
                  </td>
                  <td><strong>{r.company}</strong></td>
                  <td className="num">{Number(r.final_score).toFixed(0)}</td>
                  <td><span className={`pill ${r.pillar}`}>{r.pillar}</span></td>
                  <td className="muted">{String(r.created_at).slice(0, 10)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      className="tool-btn"
                      onClick={() =>
                        nav(
                          `/startup/new?name=${encodeURIComponent(r.company)}`
                        )
                      }
                    >
                      Re-evaluate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
