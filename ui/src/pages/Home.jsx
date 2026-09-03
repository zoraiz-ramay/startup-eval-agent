import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  IxKpi, IxCard, IxCardContent, IxChip, IxCardList, IxEventListItem, IxInput, IxButton,
} from "@siemens/ix-react";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { ScoreBar, ExtLink, Loading, PillarPill } from "../components/widgets.jsx";
import ErrorBox from "../components/ErrorBox.jsx";

// MIG-24: IxEventListItem's own click listener (event-list-item.js) is bound to the whole host
// element and fires on mouse click only -- there is no tabindex and no keydown handling anywhere
// in the compiled component, so its `chevron` affordance is NOT keyboard-reachable by default
// (verified against ui/node_modules/@siemens/ix/dist/collection/components/event-list-item/
// event-list-item.js). This wrapper is what actually closes UI-12 for the row-click sites below:
// it makes the item a real keyboard target (tabIndex + Enter/Space -> the same handler as click).
function Row({ onActivate, children, ...rest }) {
  return (
    <IxEventListItem
      chevron
      tabIndex={0}
      onClick={onActivate}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onActivate(); }
      }}
      {...rest}
    >
      {children}
    </IxEventListItem>
  );
}

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
    api.myRuns().then((d) => setRuns(d.runs)).catch((e) => setError(e.message));
    api.challenges().then((d) => setChallenges(d.challenges || [])).catch(() => {});
  }, []);
  useEffect(() => {
    // IxInput's ref is the <ix-input> host, not the native <input> — .focus() on the host
    // wouldn't move focus into the field, so this calls the component's own focusInput() method.
    if (params.get("compose")) composeRef.current?.focusInput?.();
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
          <IxKpi label="Companies evaluated" value={stats.total} />
          <IxKpi label="Avg Fit Score" value={stats.avg} />
          <IxKpi label="Siemens-aligned" value={stats.aligned} />
          <IxKpi label="Watching" value={stats.watched} />
          <IxKpi label="Challenges recorded" value={stats.challenges} />
        </div>
      )}
      {error && <ErrorBox message={error} hint="is the API running?" />}

      {/* scouting query composer — compact, integrated */}
      <IxCard>
        <IxCardContent>
          <h3>Start a scouting query</h3>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <div style={{ flex: 1 }}>
              <IxInput ref={composeRef}
                placeholder="Describe a problem to solve — e.g. predictive maintenance for legacy PLCs…"
                value={problem} maxLength={2000}
                onValueChange={(e) => setProblem(e.detail ?? e.target?.value ?? "")}
                onKeyDown={(e) => e.key === "Enter" && solve()} />
            </div>
            <IxButton disabled={solving || problem.trim().length < 3} onClick={() => solve()}>
              {solving ? "Searching…" : "Run query"}
            </IxButton>
          </div>
          <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            {QUICK_PROMPTS.map((qp) => (
              <IxChip key={qp} onClick={() => { setProblem(qp); solve(qp); }}>{qp}</IxChip>
            ))}
          </div>
          {solving && <Loading text="Deriving capabilities, searching applications + GlassDollar + web…" />}
          {solveRes && (
            <div style={{ marginTop: 10 }}>
              {(solveRes.candidates || []).length === 0 && (
                <p className="muted">No credible solver startups found — try rephrasing.</p>
              )}
              {(solveRes.candidates || []).length > 0 && (
                <IxCardList>
                  {(solveRes.candidates || []).map((c, i) => (
                    <Row key={i} onActivate={() => nav(`/startup/new?name=${encodeURIComponent(c.name)}`)}>
                      <strong>{c.name}</strong>{" "}
                      <span className="badge">{c.source === "applications" ? "Applications" : c.source === "glassdollar" ? "GlassDollar" : "Web"}</span>
                      {c.website && <> · <ExtLink href={c.website} /></>}
                      <div className="muted" style={{ fontSize: 12.5 }}>{c.rationale || c.description}</div>
                      <div style={{ width: 120, marginTop: 4 }}><ScoreBar label="relevance" value={c.relevance} /></div>
                    </Row>
                  ))}
                </IxCardList>
              )}
            </div>
          )}
        </IxCardContent>
      </IxCard>

      <div className="grid2">
        <div className="panel">
          <h3>Recent evaluations</h3>
          {!runs && <Loading text="Loading…" />}
          {runs && recent.length === 0 && (
            <p className="muted" style={{ margin: 0 }}>Nothing yet — search a startup (Ctrl K) to evaluate it.</p>
          )}
          {recent.length > 0 && (
            <IxCardList>
              {recent.map((r) => (
                <Row key={r.id} onActivate={() => nav(`/startup/${r.id}`)}>
                  <span className="logo-chip">{r.company.slice(0, 1).toUpperCase()}</span>{" "}
                  <strong>{r.company}</strong>
                  <div className="muted" style={{ fontSize: 12 }}>{(r.summary || "").slice(0, 90)}</div>
                  <span className="num">{Number(r.final_score).toFixed(0)}</span>{" "}
                  <PillarPill pillar={r.pillar} />
                </Row>
              ))}
            </IxCardList>
          )}
          {runs?.length > 0 && <Link to="/explore" style={{ fontSize: 12.5 }}>Open Explore →</Link>}
        </div>

        <div>
          <div className="panel">
            <h3>Tracked companies</h3>
            {watched.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>Star companies in Explore to track them here.</p>
            )}
            {watched.length > 0 && (
              <IxCardList>
                {watched.map((r) => (
                  <Row key={r.id} onActivate={() => nav(`/startup/${r.id}`)}>
                    <span style={{ color: "var(--warning)" }}>★</span>{" "}
                    <strong>{r.company}</strong>{" "}
                    <span className="num">{Number(r.final_score).toFixed(0)}</span>
                  </Row>
                ))}
              </IxCardList>
            )}
          </div>
          <div className="panel">
            <h3>Saved views</h3>
            {savedViews.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>Save a column set from Explore to reuse it.</p>
            )}
            {savedViews.length > 0 && (
              <IxCardList>
                {savedViews.map((v) => (
                  <Row key={v.name} onActivate={() => nav(`/explore?view=${encodeURIComponent(v.name)}`)}>
                    <strong>{v.name}</strong>
                    <span className="muted" style={{ fontSize: 11.5 }}> · {v.columns.length} columns</span>
                  </Row>
                ))}
              </IxCardList>
            )}
          </div>
          <div className="panel">
            <h3>Recent challenges</h3>
            {challenges.length > 0 && (
              <IxCardList>
                {challenges.map((c, idx) => ({ ...c, idx })).slice(-4).reverse().map((c) => (
                  <IxEventListItem key={c.idx}>
                    <div style={{ fontSize: 12.5 }}>
                      {c.problem}{" "}
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
                  </IxEventListItem>
                ))}
              </IxCardList>
            )}
            {challenges.length === 0 && <p className="muted" style={{ margin: 0 }}>No challenges recorded yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
