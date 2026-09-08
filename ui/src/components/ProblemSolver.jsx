import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { IxButton, IxCard, IxCardContent, IxTextarea } from "@siemens/ix-react";
import { api } from "../api.js";
import { useResearch } from "../research.jsx";
import { useAuth } from "../state.jsx";
import { ScoreBar, Loading, ExtLink } from "./widgets.jsx";
import ErrorBox from "./ErrorBox.jsx";

const EXAMPLES = [
  ["Reduce downtime", "We need to predict failures in legacy PLC-controlled production lines without replacing existing equipment."],
  ["Improve quality", "We need to detect surface defects in electronics on a fast-moving production line using visual inspection."],
  ["Use energy better", "We need to optimise grid-scale battery performance and identify degradation early."],
  ["Protect operations", "We need to detect cyber threats in OT networks without disrupting industrial equipment."],
];
const PROVIDERS = { tracxn: "Tracxn", glassdollar: "GlassDollar", web: "Web", applications: "Applications" };
const STATUS = { used: "Used", empty: "No matches", unavailable: "Unavailable · fallback used",
  empty_or_unavailable: "No matches or unavailable", not_connected: "Not connected", skipped: "Not needed",
  not_configured: "Not configured", disabled: "Disabled" };

export default function ProblemSolver() {
  const [params, setParams] = useSearchParams();
  const research = useResearch();
  const activeJob = research?.jobs.find((j) => params.get("job") ? j.id === params.get("job") : j.kind === "solve");
  const { user } = useAuth();
  const draftKey = `scouting-problem:${user?.oid || "local"}`;
  const [problem, setProblem] = useState(() => sessionStorage.getItem(draftKey) || "");
  const [result, setResult] = useState(null);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const input = useRef(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const inFlight = useRef(false);
  const resultHeading = useRef(null);
  useEffect(() => {
    let active = true;
    api.tracxnStatus().then((d) => { if (active) setConnection(d); })
      .catch(() => { if (active) setConnectionError("Connection status unavailable. You can still find solutions."); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (params.get("compose")) input.current?.focusInput?.();
    if (params.get("tracxn") === "failed") setConnectionError("Tracxn sign-in was not completed. Try connecting again.");
  }, [params]);
  useEffect(() => {
    sessionStorage.setItem(draftKey, problem);
  }, [problem, draftKey]);
  useEffect(() => {
    if (result) {
      resultHeading.current?.focus({ preventScroll: true });
      resultHeading.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);
  useEffect(() => {
    if (!solving) return;
    const start = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [solving]);
  const connect = async () => {
    setConnecting(true); setConnectionError("");
    try {
      if (connection?.connected) setConnection(await api.tracxnDisconnect());
      else {
        const { url } = await api.tracxnConnect();
        window.location.assign(url);
      }
    } catch (e) { setConnectionError(e.message); }
    finally { setConnecting(false); }
  };
  useEffect(() => {
    if (!activeJob) return;
    setSolving(["queued", "running"].includes(activeJob.status));
    if (activeJob.result) { setResult(activeJob.result); setProblem(activeJob.query); }
    if (activeJob.error) setError(activeJob.error);
  }, [activeJob]);
  const solve = async () => {
    if (problem.trim().length < 3 || inFlight.current) return;
    inFlight.current = true;
    setSolving(true); setError(""); setResult(null); setElapsed(0);
    try { const [j] = await research.start({ problem: problem.trim() }); if (alive.current) setParams({ job: j.id }, { replace: true }); }
    catch (e) { setError(e.message); setSolving(false); }
    finally { inFlight.current = false; }
  };
  return (
    <section className="problem-solver" aria-label="Find solutions to your problem">
      <div className="problem-layout">
        <IxCard className="problem-brief">
          <IxCardContent>
            <span className="problem-eyebrow">YOUR CHALLENGE</span>
            <h2>What would you like to solve?</h2>
            <p className="muted">Describe what is getting in the way and the outcome you need. Find startups with capabilities that could help.</p>
            <IxTextarea ref={input} label="Describe your problem" value={problem} maxLength={2000}
              disabled={solving} textareaRows={5} textareaWidth="100%" resizeBehavior="vertical"
              placeholder="We need to reduce unplanned downtime on our production lines. The solution should work with legacy PLCs and detect failures before they happen…"
              helperText="Include your use case, constraints, and what success looks like."
              onValueChange={(e) => setProblem(e.detail ?? "")}
              onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); solve(); } }} />
            <div className="problem-submit">
              <span className="muted">Ctrl/⌘ Enter to search</span>
              <IxButton disabled={solving || problem.trim().length < 3} onClick={solve}>
                {solving ? "Finding solutions…" : "Find solutions"}
              </IxButton>
            </div>
            <div className="problem-examples" aria-label="Example problems">
              <span className="muted">Try a starting point</span>
              <div>{EXAMPLES.map(([title, text]) => (
                <IxButton key={title} variant="secondary" disabled={solving}
                  onClick={() => { setProblem(text); input.current?.focusInput?.(); }}>{title}</IxButton>
              ))}</div>
            </div>
          </IxCardContent>
        </IxCard>
        <aside className="problem-sources panel" aria-label="Research sources">
          <h3>Your research sources</h3>
          <ol>
            <li><strong>Internal applications</strong><span>Matching applicants are shown first, followed by Tracxn, GlassDollar, and web results.</span></li>
            <li><strong>Tracxn</strong><span>{connection?.connected ? "Connected to your account" : "Add your subscription for company intelligence"}</span>
              <IxButton variant="secondary" disabled={connecting || solving} onClick={connect}>
                {connecting ? "Connecting…" : connection?.connected ? "Disconnect Tracxn" : "Connect Tracxn"}
              </IxButton>
              <small className="muted">Optional. Searching works without Tracxn.</small>
            </li>
            <li><strong>GlassDollar</strong><span>Company search when Tracxn has no results or is unavailable.</span></li>
            <li><strong>Web research</strong><span>Find additional candidates and fill missing details with sourced evidence.</span></li>
          </ol>
          <p className="muted">Your internal applications are included when they match. AI ranks candidates against your problem.</p>
          {connectionError && <ErrorBox message={connectionError} />}
        </aside>
      </div>
      {error && <ErrorBox message={error} hint="Your problem is saved here. Try the search again." />}
      {solving && <div className="problem-progress" role="status" aria-live="polite">
        <Loading text="Matching capabilities and checking available sources…" />
        <span className="muted">{elapsed}s elapsed. Research may take a minute.</span>
      </div>}
      {result && <section className="problem-results" aria-label="Suggested solutions" aria-live="polite">
        <div className="problem-results-head"><h2 ref={resultHeading} tabIndex={-1}>{result.candidates.length ? `${result.candidates.length} potential solution${result.candidates.length === 1 ? "" : "s"}` : "No strong matches yet"}</h2>
          <span className="muted">{result.cached ? "Recent search · reused" : result.elapsed_seconds != null ? `${result.elapsed_seconds}s` : ""}</span>
        </div>
        <p className="muted">For: {result.problem}</p>
        <div className="problem-source-status">{(result.sources || []).map((s) => (
          <span className="badge" key={s.provider}>{PROVIDERS[s.provider] || s.provider}: {STATUS[s.status] || s.status}</span>
        ))}</div>
        {result.method === "offline_keyword" && <p className="muted">Keyword matching was used. Review the evidence to confirm relevance.</p>}
        {!result.candidates.length && <p>Add a specific use case or relax a constraint, then try again.</p>}
        <div className="solution-grid">{result.candidates.map((c, i) => (
          <IxCard key={`${c.source}-${c.name}`} className="solution-card"><IxCardContent>
            <div className="solution-heading"><span className="muted">{String(i + 1).padStart(2, "0")}</span><h3>{c.name}</h3>
              <span className="badge">{PROVIDERS[c.source] || c.source}</span></div>
            <p>{c.description || "Open the evaluation to research this company's capabilities."}</p>
            {c.field_sources?.description?.provider === "web" && <ExtLink href={c.field_sources.description.url}>Description source</ExtLink>}
            <div className="solution-reason"><strong>Why it could help</strong><p>{c.rationale}</p></div>
            <ScoreBar label="Problem relevance" value={c.relevance} />
            <div className="solution-actions"><Link to={`/startup/new?name=${encodeURIComponent(c.name)}`}>Evaluate solution →</Link>
              {c.website && <ExtLink href={c.website} />}</div>
          </IxCardContent></IxCard>
        ))}</div>
      </section>}
    </section>
  );
}
