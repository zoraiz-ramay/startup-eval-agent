import React from "react";
import { useApp } from "../state.jsx";
import {
  DEFAULT_WEIGHTS, DIMENSIONS, DIMENSION_LABELS, isDefaultWeights, normaliseWeights, reweight,
} from "../scoring/index.js";
import { ROUTES, whatIfRouting } from "../scoring/routing.js";

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
  const { whatIfWeights, setWhatIfWeights } = useApp();

  const modified = !isDefaultWeights(whatIfWeights);
  const active = whatIfWeights || DEFAULT_WEIGHTS;
  const { sum, ok } = normaliseWeights(active);

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

  const setDim = (k, raw) => {
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) return;
    setWhatIfWeights({ ...active, [k]: n });
  };

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
              <div className="grid2" style={{ gap: 4 }}>
                {DIMENSIONS.map((k) => (
                  <div key={k} className="spec" style={{ alignItems: "center" }}>
                    <div className="k">
                      <label htmlFor={`whatif-${k}`}>{DIMENSION_LABELS[k]}</label>
                    </div>
                    <div className="v">
                      <input
                        id={`whatif-${k}`}
                        className="input"
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        value={active[k]}
                        onChange={(e) => setDim(k, e.target.value)}
                        style={{ width: 70 }}
                      />
                      <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                        {ok ? `→ ${Math.round((active[k] / sum) * 100)}%` : "—"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <p className="muted" style={{ fontSize: 11.5, margin: "6px 0 10px" }}>
                {ok
                  ? `Sum ${Math.round(sum)} — normalised to 100 before scoring.`
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
                onClick={() => setWhatIfWeights(null)}
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
