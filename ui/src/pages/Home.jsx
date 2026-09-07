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
  const [problem, setProblem] = useState("");
  const [solving, setSolving] = useState(false);
  const [solveRes, setSolveRes] = useState(null);
  const [error, setError] = useState("");
  const composeRef = useRef(null);

  useEffect(() => {
    api.myRuns().then((d) => setRuns(d.runs)).catch((e) => setError(e.message));
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
    };
  }, [runs, watchlist]);

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
        <h1 className="page-title">Explore</h1>
        <span className="page-meta">Scouting workspace</span>
      </div>

      {stats && (
        <div className="stats-strip">
          <IxKpi label="Companies evaluated" value={stats.total} />
          <IxKpi label="Avg Fit Score" value={stats.avg} />
          <IxKpi label="Siemens-aligned" value={stats.aligned} />
          <IxKpi label="Watching" value={stats.watched} />
        </div>
      )}
      {error && <ErrorBox message={error} hint="is the API running?" />}

      {/* scouting query composer — compact, integrated */}
      <IxCard className="composer-card">
        <IxCardContent>
          <h3>Start a scouting query</h3>
          <div className="composer-row">
            <div className="composer-input">
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
                // The score and pillar used to be slotted after the description <div>, which put
                // them on a third line and left the row reading as a stack rather than an entry.
                // They belong with the name — a run is "company, score, pillar" — so the headline
                // is one flex line and the summary sits under it. The initial logo-chip is gone:
                // a generated letter tile is not information, and it pushed the name off the row
                // start where the eye scans for it.
                <Row key={r.id} onActivate={() => nav(`/startup/${r.id}`)}>
                  {/* One wrapper, not two sibling <div>s: IxEventListItem lays its slotted
                      children out in a flex ROW inside its shadow DOM, so two siblings sit side
                      by side rather than stacking — which is what put the summary beside the
                      name instead of under it. */}
                  <div className="run-cell">
                    <div className="run-row">
                      <strong className="run-name">{r.company}</strong>
                      <span className="num">{Number(r.final_score).toFixed(0)}</span>
                      <PillarPill pillar={r.pillar} />
                    </div>
                    <div className="muted run-desc">{(r.summary || "").slice(0, 90)}</div>
                  </div>
                </Row>
              ))}
            </IxCardList>
          )}
          {runs?.length > 0 && <Link to="/explore" style={{ fontSize: 12.5 }}>Open Databases →</Link>}
        </div>

        <div>
          <div className="panel">
            <h3>Tracked companies</h3>
            {watched.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>Star companies in Databases to track them here.</p>
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
              <p className="muted" style={{ margin: 0 }}>Save a column set from Databases to reuse it.</p>
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
        </div>
      </div>
    </div>
  );
}
