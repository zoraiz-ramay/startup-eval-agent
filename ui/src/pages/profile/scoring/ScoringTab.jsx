import React from "react";
import { useSearchParams } from "react-router-dom";
import FitRubric from "./FitRubric.jsx";
import { ScoreBar } from "../../../components/widgets.jsx";
import Section from "../Section.jsx";
import { engineGate } from "../../../scoring/routing.js";
import BreakdownPanel from "./BreakdownPanel.jsx";
import PillarSection from "./PillarSection.jsx";
import EmpowerPanel from "./EmpowerPanel.jsx";
import CollaboratePanel from "./CollaboratePanel.jsx";
import SfsPanel from "./SfsPanel.jsx";
import OverridePanel from "./OverridePanel.jsx";

/* Scoring & Fit, as one column of addressable sections.
 *
 * It was a two-column `grid2`, which the rail cannot navigate: a table of contents needs a reading
 * ORDER, and side-by-side panels share a scroll position, so there is no single current section to
 * mark. The reorganisation is not only mechanical though — the three pillars are what a reviewer
 * is actually deciding between, and they now each get a section of their own instead of being
 * split across a "Route scorecards" list and a separate criteria checklist.
 */
const PILLARS = ["Empower", "Collaborate", "Connect"];
const PILLAR_SECTION = {
  Connect: "scoring-connect",
  Collaborate: "scoring-collaborate",
  Empower: "scoring-empower",
};

export default function ScoringTab({ res, runId }) {
  const [params, setParams] = useSearchParams();
  const activePillar = PILLARS.includes(params.get("pillar")) ? params.get("pillar") : "Empower";
  const setActivePillar = (p) => setParams((old) => { const next = new URLSearchParams(old); next.set("pillar", p); return next; }, { replace: true });
  const sc = res.score || {}, fit = res.fit || {}, rt = res.routing || {};
  const assessments = rt.pillar_assessments || {};
  const recommendations = rt.route_recommendations || [];
  const hasFlags = (sc.red_flags || []).length > 0 || (sc.missing_evidence || []).length > 0;

  return (
    <>
      <Section id="scoring-decision">
        <h3>Decision</h3>
        <p style={{ margin: "0 0 6px" }}>
          <span className={`pill ${rt.pillar}`}>{rt.pillar}</span>{" "}
          {(rt.secondary || []).map((s) => <span key={s} className={`pill ghost ${s}`}>+{s}</span>)}{" "}
          {rt.sfs_relevant && (
            <span className="pill sfs" title={rt.sfs_rationale}>
              SFS{rt.sfs_line ? ` · ${rt.sfs_line}` : " financing"}
            </span>
          )}
          <span className="badge">confidence {Math.round((rt.confidence || 0) * 100)}%</span>
          {rt.pillar_status && rt.pillar_status !== "eligible" && rt.pillar !== "Pass" && (
            <span className={`verdict ${rt.pillar_status}`}>{rt.pillar_status}</span>
          )}
        </p>
        {(rt.reasons || []).map((r, i) => <div key={i} className="reason">{r}</div>)}
        {(rt.risks || []).map((r, i) => <div key={i} className="risk">{r}</div>)}
      </Section>

      <FitRubric rubric={fit.rubric} />
      <BreakdownPanel score={sc} fit={fit} routing={rt} />

      {/* One section per pillar, each carrying BOTH gates. `engineGate` reads the thresholds the
          engine applied off this stored run, so a pillar that was rejected can finally explain
          itself — the engine's own `route_recommendations` only ever contains routes that already
          qualified. */}
      <Section id="scoring-routes">
      <div className="pillar-tabs" role="tablist" aria-label="Partnership routes">
        {PILLARS.map((p, i) => <button key={p} type="button" role="tab" id={`pillar-tab-${p}`}
          aria-selected={activePillar === p} aria-controls={`pillar-panel-${p}`} tabIndex={activePillar === p ? 0 : -1}
          onClick={() => setActivePillar(p)} onKeyDown={(e) => {
            const next = e.key === "ArrowRight" ? (i + 1) % 3 : e.key === "ArrowLeft" ? (i + 2) % 3 : e.key === "Home" ? 0 : e.key === "End" ? 2 : null;
            if (next !== null) { e.preventDefault(); setActivePillar(PILLARS[next]); document.getElementById(`pillar-tab-${PILLARS[next]}`)?.focus(); }
          }}>{p}<span className="badge">{sc.route_scorecards?.[p] ?? "—"}</span></button>)}
      </div>
      {PILLARS.map((p) => <div key={p} role="tabpanel" id={`pillar-panel-${p}`} aria-labelledby={`pillar-tab-${p}`} hidden={activePillar !== p}>

        <div className="panel">
          <PillarSection
            pillar={p}
            assessment={assessments[p]}
            gate={engineGate(p, sc, fit)}
            recommendation={recommendations.find((r) => r.route === p)}
            routed={recommendations.some((r) => r.route === p)}
          >
            {p === "Empower" && <EmpowerPanel empower={rt.empower} tool={fit.matches?.[0]?.tool} />}
            {p === "Collaborate" && (
              <CollaboratePanel departments={rt.departments} detail={assessments.Collaborate?.detail} />
            )}
          </PillarSection>
        </div>
      </div>)}
      </Section>

      <Section id="scoring-portfolio">
        <h3>Siemens portfolio fit</h3>
        {rt.portfolio_stance?.label && (
          <p style={{ margin: "0 0 8px" }}>
            <span className={`verdict ${rt.portfolio_stance.competes ? "blocked" : "eligible"}`}>
              {rt.portfolio_stance.label}
            </span>{" "}
            <span className="muted" style={{ fontSize: 12.5 }}>{rt.portfolio_stance.note}</span>
          </p>
        )}
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
      </Section>

      <Section id="scoring-sfs"><SfsPanel rt={rt} /></Section>

      {hasFlags && (
        <Section id="scoring-flags">
          <h3>Flags &amp; gaps</h3>
          {(sc.red_flags || []).map((f, i) => (
            <div key={i} className="risk"
                 style={{ borderLeftColor: "var(--danger)", background: "var(--danger-soft)" }}>{f}</div>
          ))}
          {(sc.missing_evidence || []).length > 0 && (
            <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
              Missing evidence (unknown, not negative): {sc.missing_evidence.join(", ")}
            </p>
          )}
        </Section>
      )}

      {runId > 0 && (
        <Section id="scoring-review"><OverridePanel runId={runId} currentPillar={rt.pillar} /></Section>
      )}
    </>
  );
}
