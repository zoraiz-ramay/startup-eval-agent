import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { ScoreBar, Radar, Spec, ExtLink } from "../components/widgets.jsx";

const STEPS = ["Input", "Enrich", "Verify", "Structure", "Score", "Review", "Route"];
const TABS = ["Overview", "Scoring & Fit", "Market & Risk", "Evidence", "Ask"];
const DIM_META = {
  traction: "Traction (28%)", siemens_fit: "Siemens Fit (27%)", product: "Product (15%)",
  market: "Market (12%)", founder: "Founder (10%)", ecosystem: "Ecosystem (8%)",
};

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

/* ---------------- tab bodies ---------------- */
/* A value the DB did not have, filled in from web research. Marked so it is never mistaken
   for application data — the source link is the evidence for it. */
function WebSourced({ src }) {
  if (!src) return null;
  const title = src.url ? `Web-sourced: ${src.url}` : "Web-sourced (no direct link captured)";
  return src.url
    ? <a className="chip" href={src.url} target="_blank" rel="noreferrer" title={title}>web</a>
    : <span className="chip" title={title}>web</span>;
}

function OverviewTab({ res }) {
  const p = res.profile || {}, sc = res.score || {}, dp = res.deep_profile || {};
  const trend = res.trend || {};
  const psrc = res.profile_sources || {};
  const founders = (dp.founders || []).filter((f) => f?.name);
  const advisors = (dp.advisors || []).filter((a) => a?.name);
  const programs = (dp.programs || []).filter((x) => x?.name);
  const customers = dp.reference_customers?.length ? dp.reference_customers
    : String(p.customers || p["Reference customers"] || "").split(/[,;|\n]+/).map((s) => s.trim()).filter(Boolean);
  return (
    <div>
      <div className="metric-row">
        <div className="metric"><div className="k">Fit Score</div><div className="v">{Number(sc.final_score || 0).toFixed(0)}</div></div>
        <div className="metric"><div className="k">Employees</div><div className="v">{dp.employees || p.employees_count || p.employee_band || "—"}</div></div>
        <div className="metric"><div className="k">Founded</div>
          <div className="v">{p.founded_year || "—"} <WebSourced src={psrc.founded_year} /></div></div>
        <div className="metric"><div className="k">Completeness</div><div className="v">{Math.round((sc.data_completeness || 0) * 100)}%</div></div>
        <div className="metric"><div className="k">Verified customers</div><div className="v">{sc.verified_customers ?? "—"}</div></div>
        <div className="metric"><div className="k">Market signal</div><div className="v" style={{ fontSize: 13 }}>{trend.label || "—"}</div></div>
      </div>
      <div className="grid2">
        <div className="panel">
          <h3>Executive summary</h3>
          <p style={{ marginTop: 0 }}>{res.summary || <span className="muted">No summary.</span>}</p>
          <Spec k="Headquarters">{p.hq}</Spec>
          <Spec k="Stage">{p["Development stage of your solution"]}</Spec>
          <Spec k="Business model">{p["Business model"]}</Spec>
          <Spec k="Funding">{p.funding}{p.funding && <> <WebSourced src={psrc.funding} /></>}</Spec>
          <Spec k="Website"><ExtLink href={p.website} /></Spec>
          <Spec k="LinkedIn"><ExtLink href={p.linkedin_url} /></Spec>
          {dp.parent_group && <Spec k="Part of group">{dp.parent_group}</Spec>}
        </div>
        <div>
          <div className="panel">
            <h3>Team &amp; ecosystem</h3>
            {founders.length === 0 && advisors.length === 0 && programs.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>No researched team data.</p>
            )}
            {founders.map((f, i) => (
              <Spec key={i} k="Founder">
                {f.name} — {f.role || "founder"}
                {f.background && <span className="muted"> · {f.background}</span>}{" "}
                {f.linkedin && <ExtLink href={f.linkedin}>LinkedIn</ExtLink>}
              </Spec>
            ))}
            {advisors.map((a, i) => (
              <Spec key={i} k="Advisor">{a.name} — {a.role || "advisor"}{a.affiliation ? `, ${a.affiliation}` : ""}</Spec>
            ))}
            {programs.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {programs.map((x, i) => {
                  // A membership found only on the company's own site is a claim, not a
                  // verified fact — several such programs publish no searchable member
                  // directory, so it is shown but explicitly marked as uncorroborated.
                  const claimed = String(x.confidence || "").toLowerCase() === "self_asserted";
                  return (
                    <span key={i} className="chip"
                          title={claimed
                            ? `${x.type} — company-claimed, not independently corroborated`
                            : `${x.type} — independently corroborated`}>
                      {x.name}{claimed && <span className="muted"> · claimed</span>}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
          <div className="panel">
            <h3>Reference customers</h3>
            {customers.length
              ? customers.map((c, i) => <span key={i} className="chip">{c}</span>)
              : <p className="muted" style={{ margin: 0 }}>
                  {dp.customer_segment ? "None named on record." : "None on record."}
                </p>}
            {dp.customer_segment && (
              <p className="muted" style={{ margin: "8px 0 0" }}>
                Customer profile: {dp.customer_segment}
              </p>
            )}
          </div>
        </div>
      </div>
      {(trend.signals || []).length > 0 && (
        <div className="panel">
          <h3>Recent signals</h3>
          {trend.signals.map((s, i) => <div key={i} className="reason">{s}</div>)}
        </div>
      )}
    </div>
  );
}

function OverridePanel({ runId, currentPillar }) {
  const [audit, setAudit] = useState([]);
  const [open, setOpen] = useState(false);
  const [pillar, setPillar] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (runId) api.audit(runId).then((d) => setAudit(d.overrides || [])).catch(() => {});
  }, [runId]);

  const submit = async () => {
    if (!pillar || reason.trim().length < 5 || busy) return;
    setBusy(true); setError("");
    try {
      const rec = await api.override(runId, pillar, reason.trim(), note.trim());
      setAudit((a) => [...a, rec]);
      setOpen(false); setPillar(""); setReason(""); setNote("");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  if (!runId) return null;
  return (
    <div className="panel">
      <h3>Reviewer decision</h3>
      {audit.length === 0 && !open && (
        <p className="muted" style={{ margin: "0 0 8px" }}>
          Automated recommendation stands — no reviewer override recorded.
        </p>
      )}
      {audit.map((o, i) => (
        <div key={i} className="risk" style={{ borderLeftColor: "var(--accent)", background: "var(--accent-soft)" }}>
          <strong>{o.prev_pillar} → {o.new_pillar}</strong>
          {o.reviewer && <span className="badge">{o.reviewer}</span>}
          <span className="badge">{String(o.created_at).slice(0, 10)}</span>
          <div style={{ fontSize: 12.5 }}>{o.reason}</div>
          {o.evidence_note && <div className="muted" style={{ fontSize: 12 }}>Evidence: {o.evidence_note}</div>}
        </div>
      ))}
      {!open ? (
        <button className="tool-btn" onClick={() => setOpen(true)}>Override routing…</button>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 460 }}>
          <select className="input" value={pillar} onChange={(e) => setPillar(e.target.value)}
            aria-label="New route">
            <option value="">New route…</option>
            {["Connect", "Collaborate", "Empower", "Pass"].filter((p) => p !== currentPillar)
              .map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <input className="input" placeholder="Reason (required)" value={reason}
            onChange={(e) => setReason(e.target.value)} />
          <input className="input" placeholder="Supporting evidence (optional)" value={note}
            onChange={(e) => setNote(e.target.value)} />
          {error && <div className="error-box">{error}</div>}
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn" disabled={busy || !pillar || reason.trim().length < 5}
              onClick={submit}>{busy ? "Saving…" : "Record override"}</button>
            <button className="btn secondary" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

function ScoringTab({ res, runId }) {
  const sc = res.score || {}, fit = res.fit || {}, rt = res.routing || {};
  const dims = sc.dimensions || {};
  return (
    <div className="grid2">
      <div>
        <div className="panel">
          <h3>Score breakdown</h3>
          {Object.entries(DIM_META).map(([k, label]) =>
            k in dims ? <ScoreBar key={k} label={label} value={dims[k]} /> : null)}
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
            Raw {sc.raw_score} × data confidence {sc.data_confidence} (completeness{" "}
            {Math.round((sc.data_completeness || 0) * 100)}%) = <strong>{Number(sc.final_score || 0).toFixed(0)}</strong>.
            Effective traction {sc.effective_traction} (verified {sc.verified_customers} /
            unverified {sc.unverified_customers}).
          </p>
        </div>
        <div className="panel">
          <h3>Routing rationale</h3>
          <p style={{ margin: "0 0 6px" }}>
            <span className={`pill ${rt.pillar}`}>{rt.pillar}</span>{" "}
            {(rt.secondary || []).map((s) => <span key={s} className={`pill ghost ${s}`}>+{s}</span>)}{" "}
            {rt.sfs_relevant && <span className="pill sfs" title={rt.sfs_rationale}>SFS financing</span>}
            <span className="badge">confidence {Math.round((rt.confidence || 0) * 100)}%</span>
          </p>
          {(rt.reasons || []).map((r, i) => <div key={i} className="reason">{r}</div>)}
          {(rt.risks || []).map((r, i) => <div key={i} className="risk">{r}</div>)}
          {(rt.route_recommendations || []).length > 0 && (
            <>
              <h3 style={{ marginTop: 12 }}>Route scorecards</h3>
              {rt.route_recommendations.map((r) => (
                <div key={r.route} className="spec">
                  <div className="k"><span className={`pill ${r.route}`}>{r.route}</span></div>
                  <div className="v">
                    <span className="num">{r.score}</span>
                    <div className="muted" style={{ fontSize: 12.5 }}>{r.recommendation}</div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
        {((sc.red_flags || []).length > 0 || (sc.missing_evidence || []).length > 0) && (
          <div className="panel">
            <h3>Red flags &amp; gaps</h3>
            {(sc.red_flags || []).map((f, i) => (
              <div key={i} className="risk" style={{ borderLeftColor: "var(--danger)", background: "var(--danger-soft)" }}>{f}</div>
            ))}
            {(sc.missing_evidence || []).length > 0 && (
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
                Missing evidence (unknown, not negative): {sc.missing_evidence.join(", ")}
              </p>
            )}
          </div>
        )}
        <OverridePanel runId={runId} currentPillar={rt.pillar} />
      </div>
      <div>
        <div className="panel" style={{ display: "flex", justifyContent: "center" }}>
          <Radar dimensions={dims} />
        </div>
        <div className="panel">
          <h3>Siemens portfolio fit</h3>
          {fit.aligned && (fit.matches || []).length ? fit.matches.map((m, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              <strong>{m.tool}</strong>
              <span className="badge">{m.division}</span>
              {m.relation && <span className="badge">{m.relation}</span>}
              <ScoreBar label="match confidence" value={m.confidence} />
              <p className="muted" style={{ margin: "3px 0 0", fontSize: 12.5 }}>{m.rationale}</p>
            </div>
          )) : <p className="muted">No tool met the fit threshold.</p>}
          {fit.challenge_match?.library_size > 0 && (
            <div className="info-box">
              Challenge-library match <strong>{fit.challenge_match.score}</strong>
              {fit.challenge_match.best_problem && <> — closest problem: “{fit.challenge_match.best_problem}”</>}
            </div>
          )}
          <p className="muted" style={{ fontSize: 11.5, marginBottom: 0 }}>method: {fit.method || "—"}</p>
        </div>
      </div>
    </div>
  );
}

function MarketTab({ res }) {
  const t = res.trend || {}, rt = res.routing || {};
  if (!t.label || t.method === "disabled") {
    return <div className="empty"><div className="big">◔</div><h4>No market analysis</h4>
      <p>Trend analysis was disabled or returned nothing for this run.</p></div>;
  }
  return (
    <div className="grid2">
      <div className="panel">
        <h3>Market trend</h3>
        <div className="metric-row">
          <div className="metric"><div className="k">Verdict</div><div className="v" style={{ fontSize: 14 }}>{t.label}</div></div>
          <div className="metric"><div className="k">Momentum</div><div className="v">{t.momentum ?? "—"}</div></div>
        </div>
        {t.niche && <Spec k="Niche">{t.niche}</Spec>}
        <p style={{ marginBottom: 0 }}>{t.summary}</p>
      </div>
      <div>
        <div className="panel">
          <h3>Signals</h3>
          {(t.signals || []).length
            ? t.signals.map((s, i) => <div key={i} className="reason">{s}</div>)
            : <p className="muted" style={{ margin: 0 }}>No discrete signals extracted.</p>}
          {(rt.risks || []).length > 0 && <h3 style={{ marginTop: 12 }}>Risks</h3>}
          {(rt.risks || []).map((r, i) => <div key={i} className="risk">{r}</div>)}
        </div>
        {(t.evidence || []).length > 0 && (
          <div className="panel">
            <h3>Market evidence</h3>
            {t.evidence.slice(0, 6).map((e, i) => (
              <div key={i} className="list-row" style={{ fontSize: 12.5 }}>
                <div className="list-main">
                  <ExtLink href={e.url || e.href}>{e.title || e.url || e.href}</ExtLink>
                  <div className="muted">{(e.snippet || e.body || "").slice(0, 140)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceTab({ res }) {
  const [filter, setFilter] = useState("");
  const facts = (res.facts || []).filter((f) =>
    !filter || `${f.key} ${f.value} ${f.method}`.toLowerCase().includes(filter.toLowerCase()));
  const dot = (v) => (
    <span className="status-dot" style={{ background: v ? "var(--success)" : "var(--border-2)" }} />
  );
  return (
    <div className="panel" style={{ padding: 0 }}>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)" }}>
        <input className="input" style={{ maxWidth: 280 }} placeholder="Filter evidence…"
          value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter evidence" />
        <span className="muted" style={{ marginLeft: 10, fontSize: 12 }}>{facts.length} facts</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="dtable dense">
          <thead>
            <tr><th>Status</th><th>Claim</th><th>Value</th><th>Method</th><th>Source</th></tr>
          </thead>
          <tbody>
            {facts.slice(0, 120).map((f, i) => (
              <tr key={i} style={{ cursor: "default" }}>
                <td>{dot(f.verified === true || f.verified === "True")}
                  {f.verified === true || f.verified === "True" ? "verified" : "unverified"}</td>
                <td>{f.key}</td>
                <td style={{ whiteSpace: "normal", maxWidth: 380, overflowWrap: "anywhere" }}>{f.value}</td>
                <td className="muted">{f.method}</td>
                <td>{/^https?:\/\//.test(f.source_url || "")
                  ? <ExtLink href={f.source_url}>link</ExtLink>
                  : <span className="muted">{f.source_url || "—"}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AskTab({ res, runId }) {
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const suggestions = [
    "Summarise why this startup matches the brief",
    "What are the top risks?",
    "Compare this startup with similar companies",
    "What evidence is weakest?",
  ];
  const send = async (text) => {
    const question = (text || q).trim();
    if (!question || busy) return;
    setQ(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: question }]);
    try {
      const r = await api.ask(question, runId);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, source: r.source, evidence: r.evidence }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: `Request failed: ${e.message}`, source: "error" }]);
    } finally { setBusy(false); }
  };
  return (
    <div className="panel">
      <h3>Ask about {res.company}</h3>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
        The assistant drafts from AI knowledge, verifies against a targeted web search, and cites sources.
      </p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        {suggestions.map((s) => (
          <button key={s} className="chip action" onClick={() => send(s)}>{s}</button>
        ))}
      </div>
      {msgs.map((m, i) => (
        <div key={i} className={`dock-msg ${m.role}`} style={{ maxWidth: 760 }}>
          {m.role === "assistant" && m.source && <div className="src">{m.source}</div>}
          {m.text}
          {m.evidence?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {m.evidence.slice(0, 5).map((e, j) => (
                <div key={j} style={{ fontSize: 11 }}>
                  <a href={e.url} target="_blank" rel="noopener noreferrer">[{j + 1}] {e.title || e.url}</a>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {busy && <p className="muted"><span className="spinner" /> Drafting, searching, refining…</p>}
      <div style={{ display: "flex", gap: 6, maxWidth: 760 }}>
        <input className="input" placeholder={`Ask about ${res.company}…`} value={q}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
        <button className="btn ai" disabled={busy || !q.trim()} onClick={() => send()}>Ask</button>
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
  const tab = params.get("tab") || "Overview";
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
            </h1>
            <p className="ph-desc">{res.summary}</p>
            <div className="ph-meta">
              {p.hq && <span>📍 {p.hq}</span>}
              {p.funding && <span>💰 {p.funding}</span>}
              <span>Score <strong>{Number(sc.final_score || 0).toFixed(0)}</strong></span>
              <span>Confidence {Math.round((rt.confidence || 0) * 100)}%</span>
              <span className="muted">{res.engine}</span>
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
        <div className="ribbon" aria-label="Pipeline status">
          {STEPS.map((s, i) => (
            <React.Fragment key={s}>
              <span className="step done">{s}</span>
              {i < STEPS.length - 1 && <span className="sep">›</span>}
            </React.Fragment>
          ))}
          {res.source === "web" && <span className="badge">web-sourced — verify figures</span>}
        </div>
        <div className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t} role="tab" aria-selected={tab === t}
              className={"tab" + (tab === t ? " active" : "")}
              onClick={() => setParams({ tab: t }, { replace: true })}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === "Overview" && <OverviewTab res={res} />}
      {tab === "Scoring & Fit" && <ScoringTab res={res} runId={runId} />}
      {tab === "Market & Risk" && <MarketTab res={res} />}
      {tab === "Evidence" && <EvidenceTab res={res} />}
      {tab === "Ask" && <AskTab res={res} runId={runId} />}
    </div>
  );
}
