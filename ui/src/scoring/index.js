import CONSTANTS from "./engine-constants.json";

/**
 * Re-scores a stored run under a different weighting, in the browser only.
 *
 * This replicates `core/score.py:121-129`. That duplication is deliberate but load-bearing: the
 * what-if is per-user browser state, so the server cannot compute it without being told the
 * weights, and doing so per row is a round trip we do not want. The duplication is pinned from
 * both sides — `tests/test_whatif_weight_parity.py` compares these constants to `core.config` by
 * value and re-derives the formula's shape from live engine output, and `scoring.test.js` checks
 * this code reproduces real stored runs. If you change `core/score.py`'s scoring arithmetic, those
 * tests are what will tell you this file needs the same change.
 *
 * Nothing here writes anywhere. The engine's score remains the only stored, shared, exportable one.
 */

// The single dimension registry for the UI. Profile's labels and Radar's axis order both read it,
// so they cannot disagree about which dimensions exist or what order they appear in.
export const DIMENSIONS = Object.keys(CONSTANTS.weights);

export const DIMENSION_LABELS = {
  traction: "Traction", siemens_fit: "Siemens Fit", product: "Product",
  market: "Market", founder: "Founder", ecosystem: "Ecosystem",
};

// Expressed as points out of 100 rather than the engine's 0-1 fractions: this is what the editor
// puts in its inputs, and at defaults the number a user sees is also the effective percentage.
// Rounded because the scaling is not exact in binary — 0.28 * 100 is 28.000000000000004, which a
// number input renders as "28.00" and makes the default state look like something already edited.
export const DEFAULT_WEIGHTS = Object.freeze(
  Object.fromEntries(DIMENSIONS.map((k) => [k, Math.round(CONSTANTS.weights[k] * 10000) / 100])),
);

const THIN_PROFILE_CAP = CONSTANTS.thin_profile_cap;
const COMPLETENESS_DENOM = CONSTANTS.completeness_denominator;

/**
 * localStorage is user-writable, so anything read from it is untrusted input. A NaN reaching the
 * screen would print a number the engine never produced, which is the one thing this product must
 * not do — so an unusable stored value becomes `null` (meaning "no override") rather than a
 * partially-repaired object.
 */
export function sanitiseWeights(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const out = {};
  for (const k of DIMENSIONS) {
    const v = raw[k];
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0) return null;
    out[k] = v;
  }
  return out;
}

/**
 * Scales any six non-negative numbers to sum to 1.
 *
 * Normalising is not only ergonomic. The engine's own arithmetic assumes the weights sum to 1: it
 * guarantees `raw <= 100`, which in turn keeps `final < THIN_PROFILE_CAP` whenever completeness is
 * below 0.5, so the cap never binds in practice. Weights summing to 2 would double `raw`, start
 * tripping a cap that never fires in production, and read as an engine bug rather than a
 * consequence of the entered numbers.
 */
export function normaliseWeights(weights) {
  const w = sanitiseWeights(weights);
  if (!w) return { weights: null, sum: 0, ok: false };
  const sum = DIMENSIONS.reduce((s, k) => s + w[k], 0);
  if (!(sum > 0)) return { weights: null, sum: 0, ok: false };
  return {
    weights: Object.fromEntries(DIMENSIONS.map((k) => [k, w[k] / sum])),
    sum,
    ok: true,
  };
}

export function isDefaultWeights(weights) {
  const w = sanitiseWeights(weights);
  if (!w) return true;
  const a = normaliseWeights(w).weights, b = normaliseWeights(DEFAULT_WEIGHTS).weights;
  return DIMENSIONS.every((k) => Math.abs(a[k] - b[k]) < 1e-9);
}

/**
 * `data_completeness` is always k/8, but the engine rounds it to 2dp on the way out
 * (`core/score.py:151`), and it rounds `data_confidence` separately. Recomputing from the rounded
 * confidence is visibly wrong: across the nine real runs in golden-runs.json it misses seven of
 * them (39.7 where the engine said 40.0). Snapping back to the 1/8 grid recovers the exact value,
 * because the 2dp error (<=0.005) is far smaller than the 0.125 grid spacing.
 */
function snapCompleteness(c) {
  return Math.round(c * COMPLETENESS_DENOM) / COMPLETENESS_DENOM;
}

/**
 * Returns null rather than a partial result when the run predates the current dimension set or
 * carries no dimensions at all. Python would raise KeyError here, so every complete run has all
 * six; the callers use null to show "unavailable for this run" instead of rendering NaN.
 */
/**
 * Each dimension's share of the score under a weighting, on the same 0-100 scale as the dimensions
 * themselves so the radar can draw both.
 *
 * The `* DIMENSIONS.length` factor is what makes contribution comparable to evidence: under an even
 * weighting every w[k] is 1/n, so values[k] === dimensions[k] and the two polygons coincide. Under
 * the engine's own weights they do NOT coincide — the engine leans on traction and fit by design —
 * which is informative but has to be captioned, or it reads as "the what-if already changed
 * something".
 *
 * mean(values) === rawScore, which is the property that makes this a decomposition of the score
 * rather than a decorative second series.
 */
export function contributionProfile(dimensions, weights) {
  const { weights: w, ok } = normaliseWeights(weights);
  if (!ok || !dimensions) return null;
  if (DIMENSIONS.some((k) => typeof dimensions[k] !== "number" || !Number.isFinite(dimensions[k]))) {
    return null;
  }
  const values = {};
  const overflow = [];
  for (const k of DIMENSIONS) {
    const v = dimensions[k] * w[k] * DIMENSIONS.length;
    values[k] = v;
    // Reported rather than silently clipped: a dimension drawn at the ring edge is a different
    // statement from one that reaches it exactly, and the caller has to be able to say which.
    if (v > 100) overflow.push(k);
  }
  const mean = DIMENSIONS.reduce((s, k) => s + values[k], 0) / DIMENSIONS.length;
  return { values, overflow, mean };
}

export function reweight(score, weights) {
  if (!score || typeof score !== "object") return null;
  const dims = score.dimensions;
  if (!dims || DIMENSIONS.some((k) => typeof dims[k] !== "number" || !Number.isFinite(dims[k]))) {
    return null;
  }
  const { weights: w, ok } = normaliseWeights(weights);
  if (!ok) return null;

  const rawScore = DIMENSIONS.reduce((s, k) => s + dims[k] * w[k], 0);
  const completeness = snapCompleteness(Number(score.data_completeness) || 0);
  const dataConfidence = 0.5 + 0.5 * completeness;
  let finalScore = rawScore * dataConfidence;
  if (completeness < 0.5) finalScore = Math.min(finalScore, THIN_PROFILE_CAP);

  return { rawScore, finalScore, dataConfidence, completeness };
}
