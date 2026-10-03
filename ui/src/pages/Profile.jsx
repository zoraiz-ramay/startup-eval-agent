import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { IxButton } from "@siemens/ix-react";
import { iconArrowLeft, iconRefresh, iconStar, iconStarFilled } from "@siemens/ix-icons/icons";
import { useResearch } from "../research.jsx";
import { api, evaluateStream } from "../api.js";
import { useApp } from "../state.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import DegradedNotice from "../components/DegradedNotice.jsx";
import ProfileLayout from "./profile/ProfileLayout.jsx";
import OverviewTab from "./profile/OverviewTab.jsx";
import ScoringTab from "./profile/scoring/ScoringTab.jsx";
import MarketTab from "./profile/MarketTab.jsx";
import EvidenceTab from "./profile/EvidenceTab.jsx";
import { DEFAULT_VIEW } from "./profile/sections.js";

/* `position` is this run's place in the shared evaluation queue (api/flight.py): set while other
   reviewers' runs hold every slot, 0 once it has started. Waiting in line and running are different
   states, and a spinner that says "evaluating" while nothing has started yet hides the queue. */
function SkeletonProfile({ name, position }) {
  return (
    <div>
      <div className="panel">
        <p style={{ margin: 0 }} role="status" aria-live="polite"><span className="spinner" aria-hidden="true" />{" "}
          {position > 0
            ? <>Queued: <strong>{name}</strong> is {position === 1 ? "next to start" : `number ${position} in line`}.
                Other evaluations are running; this one starts automatically.</>
            : <>Evaluating <strong>{name}</strong> —
                running Input → Enrich → Verify → Structure → Score → Review → Route. This can take a minute or two.</>}
        </p>
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
  const [params, setParams] = useSearchParams();
  const { watchlist, toggleWatch, setDockCtx, setDockOpen } = useApp();
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const research = useResearch();
  const jobId = params.get("job");
  const job = research.jobs.find((j) => j.id === jobId);
  const evalName = params.get("name") || "";
  const tab = params.get("tab") || DEFAULT_VIEW;
  const runId = id === "new" ? job?.result?.run_id || null : Number(id);

  const refreshData = async () => {
    if (!res || refreshing) return;
    setRefreshing(true);
    try {
      // A refresh re-evaluates for every department, legacy runs included, and carries the
      // earlier runs' sourced evidence forward (core/carry_forward.py).
      const [j] = await research.start({ names: [res.company], refresh: true });
      nav(`/startup/new?name=${encodeURIComponent(res.company)}&job=${j.id}`, { replace: true });
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
    let active = true;
    setRes(null); setError("");
    if (id === "new" && evalName) {
      /* Streamed, so the profile appears as soon as the engine has assembled it rather than
         when routing finishes a minute later. Each partial merges into the same object the
         non-streaming path produces, so every view below reads one shape and none of them know
         this happened. `evaluateStream` falls back to api.evaluate on any stream failure. */
      if (!jobId) {
        research.start({ names: [evalName], refresh: params.get("refresh") === "1" })
          .then(([j]) => { if (active) nav(`/startup/new?name=${encodeURIComponent(evalName)}&job=${j.id}`, { replace: true }); })
          .catch((e) => setError(e.message));
      }
    } else if (runId) {
      api.run(runId).then((r) => { if (active) { loadedRunId.current = runId; setRes(r); } })
        .catch((e) => setError(e.message));
    }
    return () => { active = false; };
  }, [id, evalName, jobId]);           // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!job) return;
    let active = true;
    if (job.status === "error") setError(job.error);
    else if (job.result) {
      setRes(job.result);
      if (job.result.run_id) api.run(job.result.run_id).then((r) => { if (active) setRes(r); }).catch(() => {});
    }
    else if (job.partial) setRes(job.partial);
    return () => { active = false; };
  }, [job]);

  useEffect(() => {
    if (res) setDockCtx({ runId, company: res.company });
    return () => setDockCtx(null);
  }, [res]);                    // eslint-disable-line react-hooks/exhaustive-deps

  const p = res?.profile || {};

  if (error) {
    return (
      <div className="empty">
        <div className="big">△</div>
        <h4>Could not load this startup</h4>
        <p>{error}</p>
        <button className="btn secondary" onClick={() => nav("/explore")}>Back to Companies</button>
      </div>
    );
  }
  /* The profile is the first thing worth reading and the first thing the engine finishes, so the
     skeleton holds until it lands rather than flashing a page of em dashes for the seconds
     between the company being resolved and its profile being assembled. */
  if (!res || (res.streaming && !res.profile)) {
    return <SkeletonProfile name={res?.company || evalName || `run #${id}`} position={res?.queue?.position} />;
  }

  const rt = res.routing || {};
  const compactHead = tab === "Scoring & Fit";
  // A section the run has not produced YET, which is not the same as a section it produced empty.
  const pending = (section) => Boolean(res.streaming) && !res[section];

  /* The sticky head says what the company is and nothing else: name and route, one line of facts,
     a short summary that opens on request, and where the data came from. The score has its own
     page (Scoring & Fit), the confidence figure was "not available" on every pillar-routed run,
     and the model name was an engine detail — all three left the head. */
  const watching = watchlist.includes(res.company);
  const age = ageDays === null ? "" : ageDays < 0.08 ? "just now" : ageDays < 1 ? `${Math.round(ageDays * 24)}h ago` : `${Math.round(ageDays)}d ago`;
  const stage = String(p["Development stage of your solution"] || "").replace(/\s*\(.*$/s, "").trim();
  // An all-departments run names the department it recommends; a one-department run names the
  // department it was assessed for.
  const deptFact = res.departments ? (res.departments.recommended ? `Best fit: ${res.department?.label}` : "All departments")
    : res.department?.label || "No department (legacy run)";
  const facts = [deptFact, stage, p.hq].filter(Boolean);
  const longSummary = String(res.summary || "").length > 180;

  return (
    <div>
      <div className="profile-head">
        <div className="ph-row">
          <div className="ph-logo" aria-hidden="true">{(res.company || "?").slice(0, 1).toUpperCase()}</div>
          <div className="ph-main">
            <div className="ph-titleline">
              <h1 className="ph-title">{res.company}</h1>
              {/* No pillar until routing has run. An empty pill would read as a verdict of
                  nothing rather than as a verdict not yet reached. */}
              {rt.pillar && <span className={`pill ${rt.pillar === "Defer" ? "pill-warn" : rt.pillar === "Pass" ? "pill-neutral" : "pill-ok"}`}>{rt.pillar}</span>}
              {(rt.secondary || []).map((s) => <span key={s} className={`pill ghost ${s}`}>+{s}</span>)}
              {/* Only the competing case earns a place in the headline: a startup that does what a
                  Siemens product already does is a different conversation entirely. */}
              {rt.portfolio_stance?.competes && <span className="pill sfs" title={rt.portfolio_stance.note}>Competes</span>}
              {pending("score") && <span className="muted ph-pending" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" /> assessing…</span>}
            </div>
            <p className="ph-facts">
              {facts.map((f, i) => <span key={i}>{f}</span>)}
              {age && <span className={ageDays > 7 ? "ph-stale" : ""} title={res.run_created_at}>{res.cached ? "Cached · " : ""}Evaluated {age}</span>}
            </p>
            {res.summary && (!compactHead || showContext) && (
              <p className={`ph-desc${showContext ? " open" : ""}`}>{res.summary}</p>
            )}
            <div className="ph-badges">
              {(longSummary || compactHead) && res.summary && (
                <button type="button" className="link-btn ph-more" aria-expanded={showContext}
                  onClick={() => setShowContext((v) => !v)}>{showContext ? "Less" : compactHead ? "Show summary" : "More"}</button>
              )}
              {/* A run assembled from the web rather than a curated record is a caveat on every
                  figure below it. */}
              {res.source === "tracxn" && <span className="badge">Tracxn</span>}
              {res.source === "web" && <span className="badge">Web-sourced · verify figures</span>}
              {rt.sfs_relevant && <span className="badge">SFS relevant</span>}
            </div>
          </div>
          <div className="ph-actions">
            <IxButton variant="secondary" icon={iconRefresh} onClick={refreshData} disabled={refreshing}
              title="Re-run the full pipeline with fresh data (the old run is kept for history)">{refreshing ? "Refreshing…" : "Refresh data"}</IxButton>
            <IxButton variant={watching ? "primary" : "secondary"} icon={watching ? iconStarFilled : iconStar}
              onClick={() => toggleWatch(res.company)}>{watching ? "Watching" : "Watch"}</IxButton>
            <IxButton variant="subtle-primary" icon={iconArrowLeft} onClick={() => nav("/explore")}>Companies</IxButton>
          </div>
        </div>
      </div>
      <DegradedNotice degraded={res.degraded} />

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
            : <ScoringTab res={res} runId={runId} onRefresh={refreshData} onAssessment={(a) => setRes((old) => !old || (old.run_id && old.run_id !== runId) ? old : ({...old,
                ...(a.routing?.status === "assessed" ? {routing:a.routing} : {}),
                ...(a.score?.status === "assessed" ? {score:a.score} : {}),
                ...(a.department_fit?.status === "assessed" ? {department_assessments:{...old.department_assessments,[a.department_fit.department.id]:a.department_fit}} : {}),
              }))} />)
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
