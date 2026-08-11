import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { ScoreBar, ExtLink, Loading } from "../components/widgets.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

const QUICK_PROMPTS = [
  "Predictive maintenance for legacy PLCs",
  "Grid-scale battery analytics",
  "AI visual inspection for electronics",
  "Industrial cybersecurity for OT networks",
];

export default function Home() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { watchlist, savedViews } = useApp();
  const [runs, setRuns] = useState(null);
  const [challenges, setChallenges] = useState([]);
  const [problem, setProblem] = useState("");
  const [solving, setSolving] = useState(false);
  const [solveRes, setSolveRes] = useState(null);
  const [error, setError] = useState("");
  const composeRef = useRef(null);

  useEffect(() => {
    api.runs().then((d) => setRuns(d.runs)).catch((e) => setError(e.message));
    api.challenges().then((d) => setChallenges(d.challenges || [])).catch(() => {});
  }, []);
  useEffect(() => {
    if (params.get("compose")) composeRef.current?.focus();
  }, [params]);

  const stats = useMemo(() => {
    if (!runs?.length) return null;
    return {
      total: runs.length,
      avg: (runs.reduce((s, r) => s + (r.final_score || 0), 0) / runs.length).toFixed(0),
      aligned: runs.filter((r) => r.pillar !== "Pass").length,
      watched: watchlist.length,
      challenges: challenges.length,
    };
  }, [runs, watchlist, challenges]);

  const solve = async (text) => {
    const prob = (text || problem).trim();
    if (prob.length < 3 || solving) return;
    setSolving(true); setSolveRes(null); setError("");
    try {
      setSolveRes(await api.solve(prob));
    } catch (e) {
      setError(e.message);
    } finally { setSolving(false); }
  };

  const recent = (runs || []).slice(0, 6);
  const watched = [];
  {
    const seen = new Set();
    for (const r of runs || []) {
      if (watchlist.includes(r.company) && !seen.has(r.company.toLowerCase()) && watched.length < 6) {
        seen.add(r.company.toLowerCase());
        watched.push(r);
      }
    }
  }

  return (
    <div>
      <div className="crumb">Command Centre</div>
      <div className="page-head">
        <h1 className="page-title">Home</h1>
        <span className="page-meta">Scouting workspace</span>
      </div>

      {stats && (
        <div className="stats-strip">
          <div className="stat"><span className="v">{stats.total}</span><span className="k">Companies evaluated</span></div>
          <div className="stat"><span className="v">{stats.avg}</span><span className="k">Avg Fit Score</span></div>
          <div className="stat"><span className="v">{stats.aligned}</span><span className="k">Siemens-aligned</span></div>
          <div className="stat"><span className="v">{stats.watched}</span><span className="k">Watching</span></div>
          <div className="stat"><span className="v">{stats.challenges}</span><span className="k">Challenges recorded</span></div>
        </div>
      )}
      {error && <ErrorBox message={error} hint="is the API running?" />}

      {/* scouting query composer — compact, integrated */}
      <div className="panel">
        <h3>Start a scouting query</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input ref={composeRef} className="input"
            placeholder="Describe a problem to solve — e.g. predictive maintenance for legacy PLCs…"
            value={problem} maxLength={2000}
            onChange={(e) => setProblem(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && solve()} />
          <button className="btn" disabled={solving || problem.trim().length < 3} onClick={() => solve()}>
            {solving ? "Searching…" : "Run query"}
          </button>
        </div>
        <div style={{ marginTop: 8 }}>
          {QUICK_PROMPTS.map((qp) => (
            <button key={qp} className="chip action" onClick={() => { setProblem(qp); solve(qp); }}>{qp}</button>
          ))}
        </div>
        {solving && <Loading text="Deriving capabilities, searching applications + GlassDollar + web…" />}
        {solveRes && (
          <div style={{ marginTop: 10 }}>
            {(solveRes.candidates || []).length === 0 && (
              <p className="muted">No credible solver startups found — try rephrasing.</p>
            )}
            {(solveRes.candidates || []).map((c, i) => (
              <div key={i} className="list-row">
                <div className="list-main">
                  <strong>{c.name}</strong>
                  <span className="badge">{c.source === "applications" ? "Applications" : c.source === "glassdollar" ? "GlassDollar" : "Web"}</span>
                  {c.website && <> · <ExtLink href={c.website} /></>}
                  <div className="muted" style={{ fontSize: 12.5 }}>{c.rationale || c.description}</div>
                </div>
                <div style={{ width: 120 }}><ScoreBar label="relevance" value={c.relevance} /></div>
                <button className="btn secondary"
                  onClick={() => nav(`/startup/new?name=${encodeURIComponent(c.name)}`)}>
                  Evaluate
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid2">
        <div className="panel">
          <h3>Recent evaluations</h3>
          {!runs && <Loading text="Loading…" />}
          {runs && recent.length === 0 && (
            <p className="muted" style={{ margin: 0 }}>Nothing yet — search a startup (Ctrl K) to evaluate it.</p>
          )}
          {recent.map((r) => (
            <div key={r.id} className="list-row" style={{ cursor: "pointer" }}
              onClick={() => nav(`/startup/${r.id}`)}>
              <span className="logo-chip">{r.company.slice(0, 1).toUpperCase()}</span>
              <div className="list-main">
                <strong>{r.company}</strong>
                <div className="muted" style={{ fontSize: 12 }}>{(r.summary || "").slice(0, 90)}</div>
              </div>
              <span className="num">{Number(r.final_score).toFixed(0)}</span>
              <span className={`pill ${r.pillar}`}>{r.pillar}</span>
            </div>
          ))}
          {runs?.length > 0 && <Link to="/explore" style={{ fontSize: 12.5 }}>Open Explore →</Link>}
        </div>

        <div>
          <div className="panel">
            <h3>Tracked companies</h3>
            {watched.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>Star companies in Explore to track them here.</p>
            )}
            {watched.map((r) => (
              <div key={r.id} className="list-row" style={{ cursor: "pointer" }}
                onClick={() => nav(`/startup/${r.id}`)}>
                <span style={{ color: "var(--warning)" }}>★</span>
                <div className="list-main"><strong>{r.company}</strong></div>
                <span className="num">{Number(r.final_score).toFixed(0)}</span>
              </div>
            ))}
          </div>
          <div className="panel">
            <h3>Saved views</h3>
            {savedViews.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>Save a column set from Explore to reuse it.</p>
            )}
            {savedViews.map((v) => (
              <div key={v.name} className="list-row" style={{ cursor: "pointer" }}
                onClick={() => nav(`/explore?view=${encodeURIComponent(v.name)}`)}>
                <div className="list-main"><strong>{v.name}</strong>
                  <span className="muted" style={{ fontSize: 11.5 }}> · {v.columns.length} columns</span></div>
              </div>
            ))}
          </div>
          <div className="panel">
            <h3>Recent challenges</h3>
            {challenges.map((c, idx) => ({ ...c, idx })).slice(-4).reverse().map((c) => (
              <div key={c.idx} className="list-row">
                <div className="list-main" style={{ fontSize: 12.5 }}>
                  {c.problem}
                  <span className="badge" style={c.status === "approved" ? { color: "var(--success)" }
                    : c.status === "rejected" ? { color: "var(--danger)" } : {}}>
                    {c.status || "pending"}
                  </span>
                </div>
                {(c.status || "pending") === "pending" && (
                  <span style={{ display: "flex", gap: 4 }}>
                    <button className="tool-btn" title="Approve"
                      onClick={() => api.setChallengeStatus(c.idx, "approved")
                        .then(() => api.challenges().then((d) => setChallenges(d.challenges || [])))}>✓</button>
                    <button className="tool-btn" title="Reject"
                      onClick={() => api.setChallengeStatus(c.idx, "rejected")
                        .then(() => api.challenges().then((d) => setChallenges(d.challenges || [])))}>✕</button>
                  </span>
                )}
              </div>
            ))}
            {challenges.length === 0 && <p className="muted" style={{ margin: 0 }}>No challenges recorded yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
