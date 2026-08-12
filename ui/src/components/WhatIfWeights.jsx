import React, { useMemo } from "react";
import { DEFAULT_WEIGHTS, DIMENSIONS, DIMENSION_LABELS, reweight } from "../scoring/index.js";
import { ROUTES, breakevenWeight, whatIfRouting } from "../scoring/routing.js";
import WeightSliders, { useWeighting } from "./WeightSliders.jsx";

const pp = (x) => `${Math.round(x * 100)}%`;

/**
 * Lets a reviewer ask "what would this score be if my department weighted the dimensions
 * differently" without touching the evaluation.
 *
 * The whole design problem here is that a re-weighted number looks exactly like a real score. The
 * engine's score is the one that is stored, exported, shown everywhere else and shared between
 * reviewers; this one exists in a single browser. So the stored score is repeated inside this
 * panel next to the what-if — any crop that captures one captures the other — the what-if never
 * borrows the canonical score's typography, and it carries a literal disclaimer. Collapsed by
 * default so it costs nothing to reviewers who never open it.
 */
export default function WhatIfWeights({ score, fit, routing, open, setOpen }) {
  const { active, ok, modified, reset } = useWeighting();

  const atDefault = reweight(score, DEFAULT_WEIGHTS);
  const whatIf = reweight(score, active);
  const stored = typeof score?.final_score === "number" ? score.final_score : null;

  // A run whose stored score disagrees with what today's weights produce was scored under a
  // different engine. Saying so is more useful than a delta the reviewer cannot interpret.
  const stale = atDefault && stored !== null && Math.abs(atDefault.finalScore - stored) > 0.1;

  const wRouting = whatIfRouting(score, fit, active);
  const baseRouting = whatIfRouting(score, fit, DEFAULT_WEIGHTS);
  const enginePillar = routing?.pillar || "";
  // The stored pillar can differ from what today's engine derives — after a human override, or on a
  // run whose fit data predates the current shape. Comparing the what-if against the stored pillar
  // would then attribute someone else's change to the reviewer's weighting.
  const baselineDiffers = Boolean(baseRouting && enginePillar && baseRouting.pillar !== enginePillar);
  const baseline = baseRouting ? baseRouting.pillar : enginePillar;
  const pillarChanged = Boolean(wRouting && wRouting.pillar !== baseline);

  /* For each route the run does not currently qualify for, the smallest single weight change
   * that would get there. "Short by 6.2 points" is not a decision — it does not say whether
   * the gap is one this reviewer's own priorities could close. Memoised because finding it
   * sweeps six dimensions across the full weight range. */
  const paths = useMemo(() => {
    if (!score || !wRouting) return {};
    const out = {};
    for (const route of ROUTES) {
      if (wRouting.gates[route]?.eligible) continue;
      let best = null;
      for (const d of DIMENSIONS) {
        const bw = breakevenWeight(score, fit, d, route, active);
        if (!bw || !bw.reachable || bw.delta === 0) continue;
        if (!best || Math.abs(bw.delta) < Math.abs(best.delta)) best = bw;
      }
      out[route] = best;                      // null = no single dimension gets there alone
    }
    return out;
  }, [score, fit, active, wRouting]);

  return (
    <div className="panel">
      <button
        type="button"
        className="tool-btn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        style={{ width: "100%", textAlign: "left" }}
      >
        {open ? "▾" : "▸"} What-if weights (local only){modified && " · modified"}
      </button>

      {open && (
        <div style={{ marginTop: 10 }}>
          <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>
            Re-weights the six dimensions in your browser only. The score above is unchanged — it is
            what the database stores and what every other screen, export and reviewer sees.
          </p>

          {!whatIf ? (
            <p className="muted" style={{ margin: 0 }}>
              What-if is unavailable for this run — it has no recorded dimension scores.
            </p>
          ) : (
            <>
              <WeightSliders idPrefix="whatif" />

              <p className="muted" style={{ fontSize: 11.5, margin: "6px 0 10px" }}>
                {ok
                  ? "Moving one dimension rebalances the other five, so these are the shares the score actually uses."
                  : "Set at least one weight above zero."}
              </p>

              <div className="spec" style={{ alignItems: "center" }}>
                <div className="k">Engine score (stored)</div>
                <div className="v">{stored ?? "—"}</div>
              </div>
              <div className="spec" style={{ alignItems: "center" }}>
                <div className="k">What-if</div>
                <div className="v">
                  {/* One live region for score and pillar together: they are one thought, and two
                      simultaneous polite regions announce in unpredictable order. */}
                  <span
                    role="status"
                    aria-live="polite"
                    aria-label={`What-if score ${whatIf.finalScore.toFixed(1)}.` +
                      (wRouting ? ` What-if routing ${wRouting.pillar}. Evaluation routing ${baseline}.` : "")}
                  >
                    <strong>{whatIf.finalScore.toFixed(1)}</strong>
                  </span>
                  {atDefault && (
                    <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                      {(whatIf.finalScore - atDefault.finalScore >= 0 ? "+" : "") +
                        (whatIf.finalScore - atDefault.finalScore).toFixed(1)} vs engine
                    </span>
                  )}
                  <span className="badge" style={{ marginLeft: 8 }}>not the evaluation result</span>
                </div>
              </div>

              {stale && (
                <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
                  This run&apos;s stored score predates the current weighting, so the comparison is
                  against a re-scored baseline rather than the number above.
                </p>
              )}

              {wRouting && (
                <div style={{ marginTop: 14 }}>
                  <h3 style={{ marginBottom: 6 }}>What-if routing</h3>

                  <p style={{ margin: "0 0 8px" }}>
                    {wRouting.invariant ? (
                      <>
                        <span className={`pill ${baseline}`}>{baseline}</span>{" "}
                        <span className="muted">— your weighting cannot change this.</span>
                      </>
                    ) : pillarChanged ? (
                      <>
                        <span className={`pill ${baseline}`}>{baseline}</span>{" "}
                        <span className="muted">→</span>{" "}
                        <span className={`pill ${wRouting.pillar} ghost`}>{wRouting.pillar}</span>{" "}
                        <span className="badge">not the evaluation result</span>
                      </>
                    ) : (
                      <>
                        <span className="muted">Still </span>
                        <span className={`pill ${baseline}`}>{baseline}</span>{" "}
                        <span className="muted">under your weighting.</span>
                      </>
                    )}
                  </p>

                  {baselineDiffers && (
                    <p className="muted" style={{ fontSize: 11.5, margin: "0 0 8px" }}>
                      This run is stored as {enginePillar}, but today&apos;s engine derives{" "}
                      {baseline} from its own numbers — so the comparison above is against the
                      re-derived baseline, not the stored pillar.
                    </p>
                  )}

                  {/* Every gate, every time — including the ones that pass. A reviewer looking at a
                      Pass wants the whole reason, and an empty state would hide it. */}
                  <div className="spec" style={{ alignItems: "baseline" }}>
                    <div className="k">Portfolio alignment</div>
                    <div className="v" style={{ fontSize: 12.5 }}>
                      Siemens fit {wRouting.alignment.siemensFit} —{" "}
                      {wRouting.alignment.passes
                        ? `meets ≥ ${wRouting.alignment.threshold}`
                        : `needs ≥ ${wRouting.alignment.threshold} (short by ${wRouting.alignment.shortfall})`}
                      {wRouting.alignment.aligned ? "" : ", and no portfolio match was found"}.{" "}
                      <span className="muted">
                        Not affected by your weighting
                        {wRouting.alignment.passes ? "." : " — it blocks every pillar."}
                      </span>
                    </div>
                  </div>

                  {ROUTES.map((route) => (
                    <div key={route} className="spec" style={{ alignItems: "baseline" }}>
                      <div className="k">{route}</div>
                      <div className="v" style={{ fontSize: 12.5 }}>
                        {wRouting.gates[route].clauses.length === 0 ? (
                          <span className="muted">
                            No score gate — qualifies whenever the alignment gate passes.
                          </span>
                        ) : wRouting.gates[route].clauses.map((c, i) => (
                          <span key={c.kind}>
                            {i > 0 && <span className="muted"> · </span>}
                            {c.kind === "route_score" ? "route score" : "traction"} {c.value}
                            {c.kind === "route_score" && modified && c.engineValue !== null
                              && ` (engine ${c.engineValue})`}
                            {" — "}
                            {c.passes ? `meets ≥ ${c.threshold}` : `needs ≥ ${c.threshold} (short by ${c.shortfall})`}
                            {!c.weightSensitive && (
                              <span className="muted"> (not affected by your weighting)</span>
                            )}
                          </span>
                        ))}
                        {/* The shortfall says how far off the route is; this says whether the
                            reviewer's own weighting can close it, which is the actual question. */}
                        {route in paths && (
                          <div className="muted" style={{ marginTop: 2 }}>
                            {wRouting.invariant ? (
                              "No weighting reaches this."
                            ) : paths[route] ? (
                              <>
                                Reachable: move{" "}
                                <strong>{DIMENSION_LABELS[paths[route].dimension]}</strong>{" "}
                                from {pp(paths[route].current)} to{" "}
                                <strong>
                                  {pp(paths[route].delta > 0
                                    ? paths[route].band.from
                                    : paths[route].band.to)}
                                </strong>{" "}
                                ({paths[route].delta > 0 ? "+" : "−"}
                                {Math.abs(Math.round(paths[route].delta * 100))}pp)
                                {paths[route].band.to < 0.999
                                  && ` — holds to ${pp(paths[route].band.to)}`}.
                              </>
                            ) : (
                              "No single dimension's weight reaches this on its own."
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <button
                type="button"
                className="btn secondary"
                style={{ marginTop: 10 }}
                disabled={!modified}
                onClick={reset}
              >
                Reset to engine weights
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
