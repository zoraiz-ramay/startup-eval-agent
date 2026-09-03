import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { IxEmptyState } from "@siemens/ix-react";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import { PillarPill } from "../components/widgets.jsx";

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
        <IxEmptyState
          header="Nothing tracked yet"
          subHeader="Star companies in Explore or on a profile to build your watchlist. Re-evaluate any time to refresh scores and signals."
          icon="star"
          action="Open Explore"
          onActionClick={() => nav("/explore")}
        />
      )}
      {watched.length > 0 && (
        <div className="panel" style={{ padding: 0 }}>
          <table className="dtable">
            <thead>
              <tr><th /><th>Company</th><th>Score</th><th>Route</th><th>Last evaluated</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {watched.map((r) => (
                // tabIndex + onKeyDown make the row itself keyboard-reachable (UI-12) — a plain
                // <tr onClick> has no keyboard path, and MIG-15's re-skin pattern for this table
                // keeps the DOM a semantic <table> rather than introducing a row component.
                <tr key={r.id} tabIndex={0} onClick={() => nav(`/startup/${r.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav(`/startup/${r.id}`); }
                  }}>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className="star-btn on" onClick={() => toggleWatch(r.company)}
                      aria-label={`Unwatch ${r.company}`}>★</button>
                  </td>
                  <td><strong>{r.company}</strong></td>
                  <td className="num">{Number(r.final_score).toFixed(0)}</td>
                  <td><PillarPill pillar={r.pillar} /></td>
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
