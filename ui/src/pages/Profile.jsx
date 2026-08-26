import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import ProfileLayout from "./profile/ProfileLayout.jsx";
import OverviewTab from "./profile/OverviewTab.jsx";
import ScoringTab from "./profile/scoring/ScoringTab.jsx";
import MarketTab from "./profile/MarketTab.jsx";
import EvidenceTab from "./profile/EvidenceTab.jsx";
import { DEFAULT_VIEW } from "./profile/sections.js";

function SkeletonProfile({ name }) {
  return (
    <div>
      <div className="panel">
        <p style={{ margin: 0 }}><span className="spinner" /> Evaluating <strong>{name}</strong> —
          running Input → Enrich → Verify → Structure → Score → Review → Route. This can take a minute or two.</p>
      </div>
      <div className="skel" style={{ height: 84, marginBottom: 12 }} />
      <div className="grid2">
        <div className="skel" style={{ height: 200 }} />
        <div className="skel" style={{ height: 200 }} />
      </div>
    </div>
  );
}

/* ---------------- page ---------------- */
export default function Profile() {
  const { id } = useParams();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const { watchlist, toggleWatch, setDockCtx, setDockOpen } = useApp();
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const evalName = params.get("name") || "";
  const tab = params.get("tab") || DEFAULT_VIEW;
  const runId = id === "new" ? null : Number(id);

  const refreshData = async () => {
    if (!res || refreshing) return;
    setRefreshing(true);
    try {
      const r = await api.evaluate(res.company, true, true);   // refresh=true bypasses cache
      if (r.run_id) nav(`/startup/${r.run_id}`, { replace: true });
      else setRes(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setRefreshing(false);
    }
  };

  const ageDays = (() => {
    const ts = res?.run_created_at;
    if (!ts) return null;
    const d = (Date.now() - new Date(ts).getTime()) / 86400000;
    return d >= 0 ? d : null;
  })();

  useEffect(() => {
    setRes(null); setError("");
    if (id === "new" && evalName) {
      api.evaluate(evalName, true, params.get("refresh") === "1")
        .then((r) => {
          if (r.run_id) nav(`/startup/${r.run_id}`, { replace: true });
          else setRes(r);
        })
        .catch((e) => setError(e.message));
    } else if (runId) {
      api.run(runId).then(setRes).catch((e) => setError(e.message));
    }
  }, [id, evalName]);           // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (res) setDockCtx({ runId, company: res.company });
    return () => setDockCtx(null);
  }, [res]);                    // eslint-disable-line react-hooks/exhaustive-deps

  const p = res?.profile || {};
  const tags = useMemo(() => {
    const t = [];
    if (p["Business model"]) t.push(p["Business model"]);
    if (p["Development stage of your solution"]) t.push(p["Development stage of your solution"]);
    if (res?.routing?.sfs_relevant) t.push("SFS relevant");
    return t;
  }, [res]);                    // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <div className="empty">
        <div className="big">△</div>
        <h4>Could not load this startup</h4>
        <p>{error}</p>
        <button className="btn secondary" onClick={() => nav("/explore")}>Back to Explore</button>
      </div>
    );
  }
  if (!res) return <SkeletonProfile name={evalName || `run #${id}`} />;

  const rt = res.routing || {}, sc = res.score || {};

  return (
    <div>
      <div className="profile-head">
        <div className="ph-row">
          <div className="ph-logo">{(res.company || "?").slice(0, 1).toUpperCase()}</div>
          <div style={{ flex: 1, minWidth: 240 }}>
            <h1 className="ph-title">
              {res.company}
              <span className={`pill ${rt.pillar}`} style={{ marginLeft: 10, verticalAlign: "middle" }}>{rt.pillar}</span>{" "}
              {(rt.secondary || []).map((s) => <span key={s} className={`pill ghost ${s}`}>+{s}</span>)}
              {/* Only the competing case earns a place in the headline. A complementary or
                  adjacent startup is the ordinary situation and belongs in the fit panel; one
                  that does what a Siemens product already does is a different conversation
                  entirely — competitive watch, or buy-instead-of-build — and used to be visible
                  only as a quietly reduced fit score. */}
              {rt.portfolio_stance?.competes && (
                <span className="pill sfs" style={{ marginLeft: 6, verticalAlign: "middle" }}
                  title={rt.portfolio_stance.note}>Competes</span>
              )}
            </h1>
            <p className="ph-desc">{res.summary}</p>
            {/* HQ and funding moved to the metric row below, where they sit beside the other
                company facts instead of competing with the score for the same line. */}
            <div className="ph-meta">
              <span>Score <strong>{Number(sc.final_score || 0).toFixed(0)}</strong></span>
              <span>Confidence {Math.round((rt.confidence || 0) * 100)}%</span>
              <span className="muted">{res.engine}</span>
              {/* Rescued from the pipeline ribbon, which was the only place it appeared. A run
                  assembled from the web rather than the curated GlassDollar record is a caveat on
                  every figure below it, and dropping the caveat with the chrome would have been a
                  quiet loss of meaning. */}
              {res.source === "web" && <span className="badge">web-sourced — verify figures</span>}
            </div>
            {tags.length > 0 && (
              <div style={{ marginTop: 4 }}>
                {tags.map((t) => <span key={t} className="chip">{t}</span>)}
              </div>
            )}
          </div>
          <div className="ph-actions">
            {ageDays !== null && (
              <span className="badge" title={res.run_created_at}
                style={ageDays > 7 ? { color: "var(--warning)" } : {}}>
                {res.cached ? "cached · " : ""}
                {ageDays < 0.08 ? "just evaluated"
                  : ageDays < 1 ? `evaluated ${Math.round(ageDays * 24)}h ago`
                  : `evaluated ${Math.round(ageDays)}d ago`}
              </span>
            )}
            <button className="tool-btn" onClick={refreshData} disabled={refreshing}
              title="Re-run the full pipeline with fresh web data (old run is kept for history)">
              {refreshing ? "Refreshing…" : "⟳ Refresh Data"}
            </button>
            <button className={"tool-btn" + (watchlist.includes(res.company) ? " active" : "")}
              onClick={() => toggleWatch(res.company)}>
              {watchlist.includes(res.company) ? "★ Watching" : "☆ Watch"}
            </button>
            <button className="tool-btn" onClick={() => setDockOpen(true)}>✦ Assistant</button>
            <button className="tool-btn" onClick={() => nav("/explore")}>← Explore</button>
          </div>
        </div>
      </div>

      {/* Navigation is the rail alone. The pipeline ribbon that used to sit here rendered all
          seven steps as done on every finished run, so it reported nothing a reader could act on
          while costing sticky height on every profile; the Ask tab left with it because the ✦
          Assistant button above opens the same conversation in the dock, from any view. */}
      <ProfileLayout view={tab} onSelectView={(v) => setParams({ tab: v }, { replace: true })}>
        {tab === "Scoring & Fit" ? <ScoringTab res={res} runId={runId} />
          : tab === "Market & Risk" ? <MarketTab res={res} />
          : tab === "Evidence" ? <EvidenceTab res={res} />
          : <OverviewTab res={res} />}
      </ProfileLayout>
    </div>
  );
}
