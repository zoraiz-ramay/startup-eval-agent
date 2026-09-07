import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, evaluateStream } from "../api.js";
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

/* A branch of the pipeline that has not finished yet.
   Deliberately distinct from every view's own empty state: "no competitors found" and "we have
   not looked yet" are opposite readings, and while an evaluation streams the second one is true. */
function StillRunning({ what }) {
  return (
    <div className="panel">
      <p className="muted" style={{ margin: 0 }} role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" /> {what} is still running. This section fills
        in as soon as it finishes — the profile beside it is already complete.
      </p>
    </div>
  );
}

/* ---------------- page ---------------- */
export default function Profile() {
  const { id } = useParams();
  const nav = useNavigate();
  const [params] = useSearchParams();
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

  /* The run already on screen. When a streamed evaluation finishes we rewrite the URL from
     /startup/new to /startup/:run_id, which changes `id` and re-runs this effect — and without
     this guard that would throw away a complete profile and re-fetch it from the API. */
  const loadedRunId = useRef(null);

  useEffect(() => {
    if (runId && loadedRunId.current === runId) return;
    setRes(null); setError("");
    if (id === "new" && evalName) {
      /* Streamed, so the profile appears as soon as the engine has assembled it rather than
         when routing finishes a minute later. Each partial merges into the same object the
         non-streaming path produces, so every view below reads one shape and none of them know
         this happened. `evaluateStream` falls back to api.evaluate on any stream failure. */
      evaluateStream(evalName, {
        refresh: params.get("refresh") === "1",
        onPartial: (section, data) => setRes((prev) => ({
          ...(prev || { found: true, streaming: true }),
          // `identity` and `profile` each arrive as a BUNDLE of top-level keys — company/source,
          // and the three the Overview reads — so they spread. Everything else is its own key.
          // Wrapping identity instead left res.company undefined and the page headed by a blank
          // <h1> for the whole run.
          ...(section === "identity" || section === "profile" ? data : { [section]: data }),
        })),
      })
        .then((r) => {
          setRes(r);
          if (r.run_id) {
            loadedRunId.current = r.run_id;
            nav(`/startup/${r.run_id}`, { replace: true });
          }
        })
        .catch((e) => setError(e.message));
    } else if (runId) {
      api.run(runId).then((r) => { loadedRunId.current = runId; setRes(r); })
        .catch((e) => setError(e.message));
    }
  }, [id, evalName]);           // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (res) setDockCtx({ runId, company: res.company });
    return () => setDockCtx(null);
  }, [res]);                    // eslint-disable-line react-hooks/exhaustive-deps

  // Re-observed whenever the run changes, because the anchors are conditional on what it found.
  const active = useScrollSpy([res]);

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
        <button className="btn secondary" onClick={() => nav("/explore")}>Back to Databases</button>
      </div>
    );
  }
  /* The profile is the first thing worth reading and the first thing the engine finishes, so the
     skeleton holds until it lands rather than flashing a page of em dashes for the seconds
     between the company being resolved and its profile being assembled. */
  if (!res || (res.streaming && !res.profile)) {
    return <SkeletonProfile name={res?.company || evalName || `run #${id}`} />;
  }

  const rt = res.routing || {}, sc = res.score || {};
  // A section the run has not produced YET, which is not the same as a section it produced empty.
  const pending = (section) => Boolean(res.streaming) && !res[section];

  return (
    <div>
      <div className="profile-head">
        <div className="ph-row">
          <div className="ph-logo">{(res.company || "?").slice(0, 1).toUpperCase()}</div>
          <div style={{ flex: 1, minWidth: 240 }}>
            <h1 className="ph-title">
              {res.company}
              {/* No pillar until routing has run. An empty pill would read as a verdict of
                  nothing rather than as a verdict not yet reached. */}
              {rt.pillar && (
                <span className={`pill ${rt.pillar}`} style={{ marginLeft: 10, verticalAlign: "middle" }}>{rt.pillar}</span>
              )}{" "}
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
              {pending("score") ? (
                <span className="muted" role="status" aria-live="polite">
                  <span className="spinner" aria-hidden="true" /> scoring…
                </span>
              ) : (
                <>
                  <span>Score <strong>{Number(sc.final_score || 0).toFixed(0)}</strong></span>
                  <span>Confidence {Math.round((rt.confidence || 0) * 100)}%</span>
                </>
              )}
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
      {/* Merged into the existing query, not replacing it. `setParams({tab})` dropped every other
          parameter — including the `name=` that /startup/new is evaluating — so selecting a group
          mid-run reset the page to a skeleton. Unreachable before, because /startup/new used to
          redirect to /startup/:id before anything was clickable. */}
      <ProfileLayout view={tab} onSelectView={(v) => setParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", v);
        return next;
      }, { replace: true })}>
        {/* A view whose branch of the pipeline is still running says so. Rendering its empty
            state instead would report an absence of findings for work that has not happened —
            the same mistake `employees_history_status` exists to prevent, one level up. */}
        {tab === "Scoring & Fit"
          ? (pending("score") ? <StillRunning what="Scoring and routing" />
            : <ScoringTab res={res} runId={runId} />)
          : tab === "Market & Risk"
            ? (pending("trend") ? <StillRunning what="Market analysis" /> : <MarketTab res={res} />)
            : tab === "Evidence"
              ? (pending("facts") ? <StillRunning what="Evidence collection" />
                : <EvidenceTab res={res} />)
              : <OverviewTab res={res} />}
      </ProfileLayout>
    </div>
  );
}
