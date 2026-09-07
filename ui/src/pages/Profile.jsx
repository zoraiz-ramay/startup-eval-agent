import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { IxCard, IxCardContent, IxContentHeader, IxKeyValueList } from "@siemens/ix-react";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { ScoreBar, Radar, Spec, ExtLink, PillarPill } from "../components/widgets.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import WhatIfWeights from "../components/WhatIfWeights.jsx";
import { contributionProfile, DEFAULT_WEIGHTS, DIMENSIONS, DIMENSION_LABELS } from "../scoring/index.js";

/**
 * The profile is one continuously scrolling page with a section rail beside it, not a tab set.
 *
 * Tabs hid the shape of an evaluation: a reviewer comparing a score against the evidence behind it
 * had to leave the score to look, and could not tell from the Overview that a scoring risk had been raised at
 * all. Everything the run produced is now on one page in reading order — profile, then how it
 * scored, then market risk, then the raw facts — and the rail is a map of it that scroll-spies
 * rather than a set of doors.
 *
 * `subs` are anchor targets inside a group. Several are conditional on what the run found, so the
 * rail is filtered against a `present` set rather than listing anchors that scroll nowhere.
 */
const SECTIONS = [
  {
    id: "sec-profile", label: "Profile", subs: [
      { id: "sub-metrics", label: "Key metrics" },
      { id: "sub-summary", label: "Executive summary" },
      { id: "sub-team", label: "Team & ecosystem" },
      { id: "sub-customers", label: "Reference customers" },
      { id: "sub-headcount", label: "Headcount trend" },
      { id: "sub-signals", label: "Recent signals" },
    ],
  },
  {
    id: "sec-scoring", label: "Scoring & Fit", subs: [
      { id: "sub-score", label: "Score breakdown" },
      { id: "sub-routing", label: "Routing rationale" },
      { id: "sub-flags", label: "Risk flags & gaps" },
      { id: "sub-fit", label: "Siemens portfolio fit" },
      { id: "sub-decision", label: "Reviewer decision" },
    ],
  },
  {
    id: "sec-market", label: "Market & Risk", subs: [
      { id: "sub-trend", label: "Market trend" },
      { id: "sub-market-signals", label: "Signals" },
      { id: "sub-market-evidence", label: "Market evidence" },
    ],
  },
  {
    id: "sec-evidence", label: "Evidence", subs: [
      { id: "sub-facts", label: "Fact table" },
    ],
  },
];
// Derived, not written out: these percentages used to be literals, which quietly became a claim
// the code could contradict. They are the engine's weights and say so.
const DIM_META = Object.fromEntries(
  DIMENSIONS.map((k) => [k, `${DIMENSION_LABELS[k]} (${Math.round(DEFAULT_WEIGHTS[k])}%)`]),
);

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

/* ---------------- section rail ---------------- */
/** Anchor target. `data-sub` is what the scroll-spy observes; the id is what a jump scrolls to. */
function Sub({ id, children }) {
  return <div id={id} data-sub={id} className="sub">{children}</div>;
}

/**
 * Which anchor is being read, from an IntersectionObserver rather than a scroll handler.
 *
 * rootMargin's -45% bottom inset means a section counts as "current" once its top reaches the
 * upper half of the viewport — without it the last short section on the page can never win,
 * because a taller neighbour above it is always intersecting too.
 */
function useScrollSpy(deps) {
  const [active, setActive] = useState("");
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll("[data-sub]"));
    if (!nodes.length) return;
    const visible = new Map();
    const obs = new IntersectionObserver((entries) => {
      for (const e of entries) visible.set(e.target.id, e.isIntersecting ? e.boundingClientRect.top : null);
      const candidates = nodes.map((n) => n.id).filter((id) => visible.get(id) != null);
      if (candidates.length) setActive(candidates[0]);
    }, { rootMargin: "0px 0px -45% 0px", threshold: 0 });
    nodes.forEach((n) => obs.observe(n));
    return () => obs.disconnect();
  }, deps);                     // eslint-disable-line react-hooks/exhaustive-deps
  return active;
}

function SectionNav({ present, active }) {
  const activeSection = SECTIONS.find((s) => s.subs.some((x) => x.id === active)) || SECTIONS[0];
  const jump = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  return (
    <nav className="sec-nav" aria-label="Profile sections">
      {SECTIONS.map((s) => {
        const subs = s.subs.filter((x) => present.has(x.id));
        const open = s.id === activeSection.id;
        return (
          <div key={s.id} className={"sec-group" + (open ? " open" : "")}>
            {/* A section with no anchors still rendered — it shows its own empty state, e.g.
                "No market analysis" — so the group stays in the rail and jumps to the section
                itself. Dropping it would hide from the reader that the run covered that ground
                and found nothing, which is not the same as not having looked. */}
            <button className="sec-head" onClick={() => jump(subs[0]?.id || s.id)} aria-current={open ? "true" : undefined}>
              <span className="caret" aria-hidden="true">{open ? "▾" : "▸"}</span>{s.label}
            </button>
            {/* Only the group being read lists its anchors, as the reference layout did: all four
                expanded at once is a 15-item wall that stops being a map. */}
            {open && (
              <ul>
                {subs.map((x) => (
                  <li key={x.id}>
                    <button className={"sec-item" + (x.id === active ? " active" : "")}
                      onClick={() => jump(x.id)} aria-current={x.id === active ? "true" : undefined}>
                      {x.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );
}

/* ---------------- section bodies ---------------- */
/* A value the DB did not have, filled in from web research. Marked so it is never mistaken
   for application data — the source link is the evidence for it.
   `field` names which metric this badge sources (e.g. "employees"), so that when several of
   these sit in the same row a screen reader hears which figure each one backs, not just "web"
   repeated (UI-01). The visible text stays "web" — this is a dense data canvas and the label
   isn't meant to grow — but WCAG 2.5.3 requires the accessible name to still start with the
   visible word, so speech-input users saying "click web" keep matching. */
function WebSourced({ src, field }) {
  if (!src) return null;
  // origin "llm" means the engine had neither a database record nor a cited page and answered
  // from model knowledge (core/profile.py's _recall_hq_offline). Calling that "web" would claim
  // a source that does not exist, so it gets its own word.
  if (src.origin === "llm") {
    return (
      <span className="chip unverified"
        title={`Not evidenced — recalled by the model${field ? ` for ${field}` : ""}, no source found`}>
        unverified
      </span>
    );
  }
  const title = src.url ? `Web-sourced: ${src.url}` : "Web-sourced (no direct link captured)";
  const label = field ? `web — ${field} source` : "web";
  // The no-URL span is inert (no href to follow, nothing to activate), so it gets no role or
  // tabstop — giving it an aria-label would announce a "control" that does nothing. Its visible
  // "web" text plus the title tooltip is all the non-interactive case needs.
  return src.url
    ? <a className="chip" href={src.url} target="_blank" rel="noreferrer" title={title} aria-label={label}>web</a>
    : <span className="chip" title={title}>web</span>;
}

// PROF-12. `deep_profile.employees_over_time` is either [] or >=2 cited points, sorted
// ascending by year (core/profile.py's _clean_employee_series refuses a single-dot series, and
// every point is guaranteed an http(s) source_url). A length-1 array is a contract violation
// upstream, not something this component needs to guard against — but it still only renders the
// list when there's enough to call a trend, matching the engine's own bar.
function HeadcountTrend({ points }) {
  const pts = points || [];
  // MIG-20: only the container moves to IxCard — the list itself is plain data markup, not a
  // chart, so there is no iX primitive for it to become.
  return (
    <IxCard>
      <IxCardContent>
        <h3>Headcount trend</h3>
        {pts.length >= 2 ? (
          <>
            <p style={{ marginTop: 0 }}>
              <strong>{pts[0].count}</strong> → <strong>{pts[pts.length - 1].count}</strong> employees
              <span className="muted"> ({pts[0].year}–{pts[pts.length - 1].year})</span>
            </p>
            {pts.map((pt, i) => (
              <div key={i} className="list-row" style={{ padding: "5px 0", fontSize: 12.5 }}>
                <div className="list-main">{pt.year} · {pt.count} employees</div>
                <ExtLink href={pt.source_url}>{`source (${pt.year})`}</ExtLink>
              </div>
            ))}
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            No cited headcount history — fewer than two independently sourced data points.
          </p>
        )}
      </IxCardContent>
    </IxCard>
  );
}

function ProfileSection({ res }) {
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
      {/* Location and Funding replace Completeness and Market signal. Both of those were derived
          numbers about the *run* — how much of the record was filled in, and a one-word trend
          verdict — sitting where a reviewer looks for facts about the *company*. Completeness is
          still stated where it does work, in the score arithmetic under Score breakdown; the trend
          verdict is the Market & Risk section's own headline. */}
      <Sub id="sub-metrics">
        <div className="metric-row">
          <div className="metric"><div className="k">Fit Score</div><div className="v">{Number(sc.final_score || 0).toFixed(0)}</div></div>
          <div className="metric"><div className="k">Employees</div>
            <div className="v">{dp.employees || p.employees_count || p.employee_band || "—"} <WebSourced src={psrc.employees_count} field="employees" /></div></div>
          <div className="metric"><div className="k">Founded</div>
            <div className="v">{p.founded_year || "—"} <WebSourced src={psrc.founded_year} field="founded year" /></div></div>
          <div className="metric"><div className="k">Funding</div>
            <div className="v">{p.funding || "—"} <WebSourced src={psrc.funding} field="funding" /></div></div>
          <div className="metric"><div className="k">Verified customers</div><div className="v">{sc.verified_customers ?? "—"}</div></div>
          <div className="metric"><div className="k">Location</div>
            <div className="v loc">{p.hq || "—"} <WebSourced src={psrc.hq} field="location" /></div></div>
        </div>
      </Sub>
      <div>
        <div>
          <Sub id="sub-summary">
          <IxCard>
            <IxCardContent>
              <h3>Executive summary</h3>
              <p style={{ marginTop: 0 }}>{res.summary || <span className="muted">No summary.</span>}</p>
              <IxKeyValueList>
                <Spec k="Headquarters">{p.hq}</Spec>
                <Spec k="Stage">{p["Development stage of your solution"]}</Spec>
                <Spec k="Business model">{p["Business model"]}</Spec>
                <Spec k="Funding">{p.funding}{p.funding && <> <WebSourced src={psrc.funding} field="funding" /></>}</Spec>
                <Spec k="Website"><ExtLink href={p.website} /></Spec>
                <Spec k="LinkedIn"><ExtLink href={p.linkedin_url} /></Spec>
                {dp.parent_group && <Spec k="Part of group">{dp.parent_group}</Spec>}
              </IxKeyValueList>
            </IxCardContent>
          </IxCard>
          </Sub>
        </div>
        <div>
          <Sub id="sub-team">
          <IxCard>
            <IxCardContent>
              <h3>Team &amp; ecosystem</h3>
              {founders.length === 0 && advisors.length === 0 && programs.length === 0 && (
                <p className="muted" style={{ margin: 0 }}>No researched team data.</p>
              )}
              {(founders.length > 0 || advisors.length > 0) && (
                <IxKeyValueList>
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
                </IxKeyValueList>
              )}
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
            </IxCardContent>
          </IxCard>
          </Sub>
          <Sub id="sub-customers">
          <IxCard>
            <IxCardContent>
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
            </IxCardContent>
          </IxCard>
          </Sub>
        </div>
      </div>
      <Sub id="sub-headcount"><HeadcountTrend points={dp.employees_over_time} /></Sub>
      {(trend.signals || []).length > 0 && (
        <Sub id="sub-signals">
          <IxCard>
            <IxCardContent>
              <h3>Recent signals</h3>
              {trend.signals.map((s, i) => <div key={i} className="reason">{s}</div>)}
            </IxCardContent>
          </IxCard>
        </Sub>
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
          {error && <ErrorBox message={error} />}
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

function ScoringSection({ res, runId }) {
  const sc = res.score || {}, fit = res.fit || {}, rt = res.routing || {};
  const dims = sc.dimensions || {};
  const { whatIfWeights } = useApp();
  // Lifted out of the panel so the radar overlay appears only while the panel is open. A second
  // polygon beside a collapsed panel would be an unexplained line on the chart — exactly the
  // mistaking-a-what-if-for-the-evaluation risk this feature has to avoid.
  const [whatIfOpen, setWhatIfOpen] = useState(false);
  const contribution = whatIfOpen ? contributionProfile(dims, whatIfWeights || DEFAULT_WEIGHTS) : null;
  return (
    <div>
      {/* The radar stays beside the bars it plots — they are two readings of the same six
          dimensions, and separating them onto different scroll positions would make the chart
          an unlabelled shape. Everything after this is full width, in reading order. */}
      <Sub id="sub-score">
        <div className="grid2">
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
          <div className="panel" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <Radar dimensions={dims} overlay={contribution ? contribution.values : null} />
            {contribution && (
              <p className="muted" style={{ fontSize: 11.5, margin: "6px 0 0", textAlign: "center" }}>
                Solid = evidence scores · dashed = each dimension&apos;s share of the score under your
                weighting. They coincide only when all six are weighted equally; the engine&apos;s own
                weights lean on traction and Siemens fit.
              </p>
            )}
          </div>
        </div>
        <WhatIfWeights score={sc} fit={fit} routing={rt} open={whatIfOpen} setOpen={setWhatIfOpen} />
      </Sub>
      <Sub id="sub-routing">
        <div className="panel">
          <h3>Routing rationale</h3>
          <p style={{ margin: "0 0 6px" }}>
            <PillarPill pillar={rt.pillar} />{" "}
            {(rt.secondary || []).map((s) => <PillarPill key={s} pillar={s} ghost>+{s}</PillarPill>)}{" "}
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
                  <div className="k"><PillarPill pillar={r.route} /></div>
                  <div className="v">
                    <span className="num">{r.score}</span>
                    <div className="muted" style={{ fontSize: 12.5 }}>{r.recommendation}</div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </Sub>
      {((sc.red_flags || []).length > 0 || (sc.missing_evidence || []).length > 0) && (
        <Sub id="sub-flags">
          <div className="panel">
            <h3>Risk flags &amp; gaps</h3>
            {(sc.red_flags || []).map((f, i) => (
              <div key={i} className="risk" style={{ borderLeftColor: "var(--danger)", background: "var(--danger-soft)" }}>{f}</div>
            ))}
            {(sc.missing_evidence || []).length > 0 && (
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
                Missing evidence (unknown, not negative): {sc.missing_evidence.join(", ")}
              </p>
            )}
          </div>
        </Sub>
      )}
      <Sub id="sub-fit">
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
      </Sub>
      <Sub id="sub-decision"><OverridePanel runId={runId} currentPillar={rt.pillar} /></Sub>
    </div>
  );
}

function MarketSection({ res }) {
  const t = res.trend || {}, rt = res.routing || {};
  if (!t.label || t.method === "disabled") {
    return <div className="empty"><div className="big">◔</div><h4>No market analysis</h4>
      <p>Trend analysis was disabled or returned nothing for this run.</p></div>;
  }
  return (
    <div>
      <Sub id="sub-trend">
      <IxCard>
        <IxCardContent>
          <h3>Market trend</h3>
          <div className="metric-row">
            <div className="metric"><div className="k">Verdict</div><div className="v" style={{ fontSize: 14 }}>{t.label}</div></div>
            <div className="metric"><div className="k">Momentum</div><div className="v">{t.momentum ?? "—"}</div></div>
          </div>
          {t.niche && <Spec k="Niche">{t.niche}</Spec>}
          <p style={{ marginBottom: 0 }}>{t.summary}</p>
        </IxCardContent>
      </IxCard>
      </Sub>
      <div>
        <Sub id="sub-market-signals">
        <IxCard>
          <IxCardContent>
            <h3>Signals</h3>
            {(t.signals || []).length
              ? t.signals.map((s, i) => <div key={i} className="reason">{s}</div>)
              : <p className="muted" style={{ margin: 0 }}>No discrete signals extracted.</p>}
            {(rt.risks || []).length > 0 && <h3 style={{ marginTop: 12 }}>Risks</h3>}
            {(rt.risks || []).map((r, i) => <div key={i} className="risk">{r}</div>)}
          </IxCardContent>
        </IxCard>
        </Sub>
        {(t.evidence || []).length > 0 && (
          <Sub id="sub-market-evidence">
          <IxCard>
            <IxCardContent>
              <h3>Market evidence</h3>
              {t.evidence.slice(0, 6).map((e, i) => (
                <div key={i} className="list-row" style={{ fontSize: 12.5 }}>
                  <div className="list-main">
                    <ExtLink href={e.url || e.href}>{e.title || e.url || e.href}</ExtLink>
                    <div className="muted">{(e.snippet || e.body || "").slice(0, 140)}</div>
                  </div>
                </div>
              ))}
            </IxCardContent>
          </IxCard>
          </Sub>
        )}
      </div>
    </div>
  );
}

function EvidenceSection({ res }) {
  const [filter, setFilter] = useState("");
  const facts = (res.facts || []).filter((f) =>
    !filter || `${f.key} ${f.value} ${f.method}`.toLowerCase().includes(filter.toLowerCase()));
  const dot = (v) => (
    <span className="status-dot" style={{ background: v ? "var(--success)" : "var(--border-2)" }} />
  );
  // The fact table itself keeps its plain <table> markup and .dtable/.dense classes untouched --
  // that class is shared with Explore's grid (MIG-15's row, not yet done) and lives in the
  // repo-wide styles.css, outside this row's file scope (Profile.jsx and named helpers only). Its
  // colours already come from tokens (var(--border), var(--surface), var(--accent-soft)) bar two
  // hard-coded hover backgrounds that are MIG-15's re-skin to fix, not this one's, since fixing
  // them here would silently reskin Explore's table too.
  return (
    <Sub id="sub-facts">
    <IxCard>
      <IxCardContent style={{ padding: 0 }}>
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
      </IxCardContent>
    </IxCard>
    </Sub>
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
  if (!res) return <SkeletonProfile name={evalName || `run #${id}`} />;

  const rt = res.routing || {}, sc = res.score || {};
  const trend = res.trend || {};
  const hasMarket = Boolean(trend.label) && trend.method !== "disabled";
  // Which anchors actually rendered. The rail lists a destination only when there is something
  // there to scroll to — a "Recent signals" entry that jumps nowhere is worse than no entry.
  const present = new Set([
    "sub-metrics", "sub-summary", "sub-team", "sub-customers", "sub-headcount",
    "sub-score", "sub-routing", "sub-fit", "sub-facts",
    ...((trend.signals || []).length ? ["sub-signals"] : []),
    ...((sc.red_flags || []).length || (sc.missing_evidence || []).length ? ["sub-flags"] : []),
    ...(runId ? ["sub-decision"] : []),
    ...(hasMarket ? ["sub-trend", "sub-market-signals"] : []),
    ...(hasMarket && (trend.evidence || []).length ? ["sub-market-evidence"] : []),
  ]);

  return (
    <div>
      <div className="profile-head">
        {/* MIG-18: IxContentHeader replaces the old logo-chip/name/pillar/summary/meta/tags/
            action-row block. Its `header` slot carries the pillar pill + secondary pills + tags
            (content that belongs beside the title, not below it); its default slot carries the
            action row. hasBackButton subsumes the old "← Explore" button, so that one is dropped
            rather than kept alongside a second, redundant way back.

            headerSubtitle is deliberately NOT used for the description any more. iX renders the
            subtitle with its `titleOverflow` class, which truncates to a single line — so a real
            two-or-three sentence description arrived as a thin clipped strip. It is a paragraph
            below the header instead, where it wraps and can be read. */}
        <IxContentHeader
          hasBackButton
          onBackButtonClick={() => nav("/explore")}
          headerTitle={res.company}
        >
          <div slot="header" className="ph-header-slot">
            <PillarPill pillar={rt.pillar} />{" "}
            {(rt.secondary || []).map((s) => <PillarPill key={s} pillar={s} ghost>+{s}</PillarPill>)}
            {tags.map((t) => <span key={t} className="chip">{t}</span>)}
          </div>
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
        </IxContentHeader>
        {res.summary && <p className="ph-summary">{res.summary}</p>}
        {/* Location and funding have left this line: they are headline facts about the company and
            now sit in the metric tiles, where a reviewer can compare them across evaluations. What
            stays is metadata about the run itself, each figure labelled rather than run together.
            The "web-sourced — verify figures" banner is gone too: every field that came from the
            web already carries its own `web` chip linking to the page it came from, which says the
            same thing per-fact instead of casting doubt over the whole page. */}
        <div className="ph-meta">
          {/* The explicit spaces are load-bearing: without them the label and the figure are
              adjacent elements and the span's text reads "Score38". */}
          <span><span className="k">Score</span>{" "}<strong>{Number(sc.final_score || 0).toFixed(0)}</strong></span>
          <span><span className="k">Confidence</span>{" "}<strong>{Math.round((rt.confidence || 0) * 100)}%</strong></span>
          <span><span className="k">Engine</span>{" "}{res.engine}</span>
        </div>
      </div>

      <div className="profile-body">
        <SectionNav present={present} active={active} />
        <div className="profile-sections">
          <section id="sec-profile" aria-label="Profile">
            <ProfileSection res={res} />
          </section>
          <section id="sec-scoring" aria-label="Scoring &amp; Fit">
            <h2 className="sec-title">Scoring &amp; Fit</h2>
            <ScoringSection res={res} runId={runId} />
          </section>
          <section id="sec-market" aria-label="Market &amp; Risk">
            <h2 className="sec-title">Market &amp; Risk</h2>
            <MarketSection res={res} />
          </section>
          <section id="sec-evidence" aria-label="Evidence">
            <h2 className="sec-title">Evidence</h2>
            <EvidenceSection res={res} />
          </section>
        </div>
      </div>
    </div>
  );
}
