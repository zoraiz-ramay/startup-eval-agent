import React from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state.jsx";

export default function Saved() {
  const nav = useNavigate();
  const { savedViews, setSavedViews } = useApp();
  return (
    <div>
      <div className="crumb">Workspace &gt; Saved views</div>
      <div className="page-head"><h1 className="page-title">Saved views</h1>
        <span className="page-meta">{savedViews.length} views</span></div>
      {savedViews.length === 0 ? (
        <div className="empty">
          <div className="big">▤</div>
          <h4>No saved views yet</h4>
          <p>Open Explore, customise the columns, and save the configuration as a view.</p>
          <button className="btn secondary" onClick={() => nav("/explore")}>Open Explore</button>
        </div>
      ) : (
        <div className="panel">
          {savedViews.map((v) => (
            <div key={v.name} className="list-row">
              <div className="list-main" style={{ cursor: "pointer" }}
                onClick={() => nav(`/explore?view=${encodeURIComponent(v.name)}`)}>
                <strong>{v.name}</strong>
                <div className="muted" style={{ fontSize: 12 }}>
                  {v.columns.length} columns{v.filters?.q ? ` · filter “${v.filters.q}”` : ""}
                  {v.filters?.pillar ? ` · ${v.filters.pillar}` : ""}
                </div>
              </div>
              <button className="btn danger"
                onClick={() => setSavedViews((s) => s.filter((x) => x.name !== v.name))}>
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
