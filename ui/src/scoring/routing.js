import CONSTANTS from "./route-constants.json";
import { DEFAULT_WEIGHTS, DIMENSIONS, normaliseWeights, reweight } from "./index.js";

/**
 * Derives what the routing decision WOULD be under a reviewer's own weighting.
 *
 * Separate from index.js on purpose: that module mirrors core/score.py and is pinned by value,
 * this one mirrors core/route.py whose thresholds are bare inline literals and can only be pinned
 * behaviourally (tests/test_whatif_route_parity.py drives the real route() to each boundary). Two
 * modules means a failing test names the engine file that actually moved.
 *
 * Two things route() returns are deliberately NOT reproduced here:
 *   - `confidence`, which would mean mirroring four more unnamed literals to surface a second-order
 *     artefact of whether the pillar is Pass. Not worth the drift surface.
 *   - `reasons` / `risks`, which are model prose when a key is configured (core/route.py:71-80).
 *     Nothing client-side can regenerate them, so the panel shows the gate arithmetic instead —
 *     which is the more useful answer anyway, because it says what would have to change.
 */

export const ROUTES = CONSTANTS.pillars.filter((p) => p !== "Pass");
const GATES = CONSTANTS.gates;
const FIT_ALIGN_THRESHOLD = CONSTANTS.fit_align_threshold;

// Full strength: the reviewer's deviation is applied to each route profile as typed. Exposed as a
// name rather than a UI control because scaling it reaches no state the six inputs cannot already
// reach — P + a(Wu - Wd) is the full-strength blend of some other weighting the reviewer could
// type — and a hidden multiplier would stop the panel being reproducible from the weights on screen.
export const ROUTE_DELTA_STRENGTH = 1;

/**
 * A route's weights, shifted by how far the reviewer's weighting departs from the engine's.
 *
 * Not a convex average with the reviewer's weights: that is a no-op on every run in the corpus
 * (the best reachable Collaborate card stays below its own gate at any mix), and at full strength
 * it collapses all three routes onto one number, destroying the distinction between what Connect
 * needs and what Empower needs. The delta keeps each route's own shape and moves it, so
 * `routeWeightsFor(r, DEFAULT_WEIGHTS)` returns the engine's own profile exactly — which is what
 * lets the golden runs pin this module.
 */
export function routeWeightsFor(route, weights) {
  const base = CONSTANTS.route_weights[route];
  if (!base) return null;
  const user = normaliseWeights(weights);
  const dflt = normaliseWeights(DEFAULT_WEIGHTS);
  if (!user.ok || !dflt.ok) return null;

  // Clipping at zero is what stops a large deviation driving a weight negative — and it is also
  // why full strength does not collapse the routes together.
  const shifted = {};
  let sum = 0;
  for (const k of DIMENSIONS) {
    const v = Math.max(0, base[k] + ROUTE_DELTA_STRENGTH * (user.weights[k] - dflt.weights[k]));
    shifted[k] = v;
    sum += v;
  }
  if (!(sum > 0)) return null;
  // Renormalising is load-bearing, not tidiness: the gates are absolute numbers, so weights summing
  // to 1.07 would inflate every card and let a startup clear Connect's 70 on arithmetic alone.
  return Object.fromEntries(DIMENSIONS.map((k) => [k, shifted[k] / sum]));
}

export function scorecardsFor(score, weights) {
  const base = reweight(score, weights);
  if (!base) return null;
  const dims = score.dimensions;
  const out = {};
  for (const route of ROUTES) {
    const w = routeWeightsFor(route, weights);
    if (!w) return null;
    // dataConfidence comes from reweight's snapped completeness, never score.data_confidence: the
    // stored value is rounded to 2dp and reproduces 38.1 where the engine recorded 38.4, which
    // would break the identity property this module is pinned on.
    out[route] = Math.round(
      DIMENSIONS.reduce((s, k) => s + dims[k] * w[k], 0) * base.dataConfidence * 10,
    ) / 10;
  }
  return out;
}

function clause(kind, value, threshold, engineValue, weightSensitive) {
  return {
    kind,
    value,
    engineValue,
    threshold,
    passes: value >= threshold,
    shortfall: value >= threshold ? 0 : Math.round((threshold - value) * 10) / 10,
    weightSensitive,
  };
}

/**
 * Replicates core/route.py:21-35 over recomputed scorecards.
 *
 * Note what this means for the headline question "could this become a Pass?": it cannot. Empower is
 * appended with no score gate and no traction gate, so once the alignment gate passes the eligible
 * list is never empty; and the alignment gate reads fit.aligned and the RAW siemens_fit dimension,
 * neither of which any weighting touches. Pass is a fixed point in both directions, and the
 * `invariant` field below is how the UI says so honestly.
 */
export function whatIfRouting(score, fit, weights) {
  const scorecards = scorecardsFor(score, weights);
  if (!scorecards) return null;
  const engineScorecards = scorecardsFor(score, DEFAULT_WEIGHTS);
  const dims = score.dimensions;
  const traction = dims.traction;
  const siemensFit = dims.siemens_fit;
  const aligned = Boolean((fit || {}).aligned);

  const alignmentPasses = aligned && siemensFit >= FIT_ALIGN_THRESHOLD;
  const alignment = {
    passes: alignmentPasses,
    aligned,
    siemensFit,
    threshold: FIT_ALIGN_THRESHOLD,
    shortfall: siemensFit >= FIT_ALIGN_THRESHOLD ? 0
      : Math.round((FIT_ALIGN_THRESHOLD - siemensFit) * 10) / 10,
    weightSensitive: false,
  };

  const gates = {};
  const eligible = [];
  for (const route of ROUTES) {
    const gate = GATES[route] || {};
    const clauses = [];
    if (typeof gate.route_score === "number") {
      clauses.push(clause("route_score", scorecards[route], gate.route_score,
        engineScorecards ? engineScorecards[route] : null, true));
    }
    if (typeof gate.traction === "number") {
      clauses.push(clause("traction", traction, gate.traction, traction, false));
    }
    const ok = alignmentPasses && clauses.every((c) => c.passes);
    gates[route] = { eligible: ok, clauses };
    if (ok) eligible.push(route);
  }

  eligible.sort((a, b) => scorecards[b] - scorecards[a]);
  const pillar = eligible.length ? eligible[0] : "Pass";

  // Only two classes are provable, and the UI must not overclaim. Anything else gets `null`, which
  // the panel renders as "does not change" rather than "cannot change".
  let invariant = null;
  if (!alignmentPasses) {
    invariant = "alignment";
  } else if (ROUTES.every((r) => {
    const t = (GATES[r] || {}).traction;
    return typeof t !== "number" || traction < t;
  })) {
    // Every gated route is barred by a traction clause no weighting can move, so only the
    // ungated route survives whatever the reviewer types.
    invariant = "traction";
  }

  return {
    pillar,
    secondary: eligible.slice(1),
    eligible,
    scorecards,
    engineScorecards,
    alignment,
    gates,
    invariant,
  };
}

/* ---------------------------------------------------------------- breakeven sensitivity */

// 0.5pp steps. Fine enough to report a breakeven to the nearest percentage point, and cheap:
// each probe is six multiplications per route, so a full sweep is a few thousand flops.
const SWEEP_STEP = 0.005;

/**
 * The reviewer's weighting with one dimension pinned to `share`, the other five keeping their
 * relative proportions inside the remaining 1 - share.
 */
export function weightsWithShare(weights, dimension, share) {
  const { weights: w, ok } = normaliseWeights(weights);
  if (!ok) return null;
  const restSum = DIMENSIONS.reduce((s, k) => (k === dimension ? s : s + w[k]), 0);
  const out = {};
  for (const k of DIMENSIONS) {
    if (k === dimension) out[k] = share;
    // All the weight was on this dimension already, so there are no proportions to preserve:
    // spread what is left evenly rather than dividing by zero.
    else out[k] = restSum > 0 ? (w[k] / restSum) * (1 - share) : (1 - share) / (DIMENSIONS.length - 1);
  }
  return out;
}

/**
 * How much a single dimension's weight would have to move for a route to become eligible.
 *
 * "Connect is 6.2 points short" is not a decision — it does not say whether that gap is one
 * the reviewer's own priorities could close. This answers that directly: the band of weights
 * for `dimension` over which `route` is eligible, with the other five held in proportion.
 *
 * Swept rather than bisected. Bisection assumes eligibility is monotone in the weight, and it
 * is not guaranteed to be: routeWeightsFor clips each shifted weight at zero, so the route's
 * own profile changes shape as the deviation grows. A sweep finds the real band, including
 * the case where raising a weight past some point loses the route again.
 *
 * Returns null only when the run cannot be re-scored at all. `reachable: false` means no
 * weight for THIS dimension reaches the route with the other five held in proportion — it is
 * not a claim about every possible weighting, and the panel must not phrase it as one. The
 * only genuinely universal answers are `invariant`, which whatIfRouting proves.
 */
export function breakevenWeight(score, fit, dimension, route, weights = DEFAULT_WEIGHTS) {
  if (!DIMENSIONS.includes(dimension) || !ROUTES.includes(route)) return null;
  const { weights: w, ok } = normaliseWeights(weights);
  if (!ok) return null;
  const at = whatIfRouting(score, fit, weights);
  if (!at) return null;

  const current = w[dimension];
  const base = {
    dimension,
    route,
    current,
    currentlyEligible: Boolean(at.gates[route]?.eligible),
    // The alignment gate reads fit.aligned and the RAW siemens_fit dimension, neither of which
    // any weighting touches, so no sweep can move it. Say that instead of sweeping 201 probes
    // to report "no".
    invariant: at.invariant,
  };
  if (at.invariant === "alignment") {
    return { ...base, band: null, reachable: false };
  }

  const passing = [];
  for (let i = 0; i * SWEEP_STEP <= 1 + 1e-9; i += 1) {
    const share = Math.min(1, i * SWEEP_STEP);
    const probe = weightsWithShare(w, dimension, share);
    const r = probe && whatIfRouting(score, fit, probe);
    passing.push(Boolean(r?.gates[route]?.eligible));
  }
  if (!passing.some(Boolean)) return { ...base, band: null, reachable: false };

  // The contiguous run that contains the current weight, or failing that the nearest one —
  // the reviewer is asking "how far do I have to move from here", so a band on the far side
  // of a gap is the wrong answer even though it also passes.
  const runs = [];
  for (let i = 0; i < passing.length; i += 1) {
    if (!passing[i]) continue;
    const start = i;
    while (i + 1 < passing.length && passing[i + 1]) i += 1;
    runs.push([start * SWEEP_STEP, Math.min(1, i * SWEEP_STEP)]);
  }
  const chosen = runs.find(([a, b]) => current >= a - 1e-9 && current <= b + 1e-9)
    || runs.reduce((best, r) => {
      const d = current < r[0] ? r[0] - current : current - r[1];
      const bd = current < best[0] ? best[0] - current : current - best[1];
      return d < bd ? r : best;
    });

  return {
    ...base,
    reachable: true,
    band: { from: chosen[0], to: chosen[1] },
    // What the reviewer actually has to do: the signed move to the nearest edge of the band,
    // or 0 when they are already inside it.
    delta: current < chosen[0] ? chosen[0] - current
      : current > chosen[1] ? chosen[1] - current : 0,
  };
}
