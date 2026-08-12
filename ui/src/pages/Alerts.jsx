import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

export default function Alerts() {
  const nav = useNavigate();
  const { watchlist, toggleWatch } = useApp();
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.myRuns().then((d) => setRuns(d.runs)).catch((e) => setError(e.message));
  }, []);

  // watchlist is keyed by company; show the LATEST run per watched company
  const watched = [];
  const seen = new Set();
  for (const r of runs || []) {
    if (watchlist.includes(r.company) && !seen.has(r.company.toLowerCase())) {
      seen.add(r.company.toLowerCase());
      watched.push(r);
    }
  }

  return (
    <div>
      <div className="crumb">Workspace &gt; Tracking</div>
      <div className="page-head"><h1 className="page-title">Tracking</h1>
        <span className="page-meta">{watched.length} companies watched</span></div>
      {error && <ErrorBox message={error} />}
      {runs && watched.length === 0 && (
        <div className="empty">
          <div className="big">◉</div>
          <h4>Nothing tracked yet</h4>
          <p>Star companies in Explore or on a profile to build your watchlist. Re-evaluate any
            time to refresh scores and signals.</p>
          <button className="btn secondary" onClick={() => nav("/explore")}>Open Explore</button>
        </div>
      )}
      {watched.length > 0 && (
        <div className="panel" style={{ padding: 0 }}>
          <table className="dtable">
            <thead>
              <tr><th /><th>Company</th><th>Score</th><th>Route</th><th>Last evaluated</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {watched.map((r) => (
                <tr key={r.id} onClick={() => nav(`/startup/${r.id}`)}>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className="star-btn on" onClick={() => toggleWatch(r.company)}
                      aria-label={`Unwatch ${r.company}`}>★</button>
                  </td>
                  <td><strong>{r.company}</strong></td>
                  <td className="num">{Number(r.final_score).toFixed(0)}</td>
                  <td><span className={`pill ${r.pillar}`}>{r.pillar}</span></td>
                  <td className="muted">{String(r.created_at).slice(0, 10)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className="tool-btn"
                      onClick={() => nav(`/startup/new?name=${encodeURIComponent(r.company)}`)}>
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
