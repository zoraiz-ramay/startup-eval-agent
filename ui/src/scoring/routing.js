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
