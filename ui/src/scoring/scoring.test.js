import { describe, expect, it } from "vitest";
import GOLDEN_FILE from "./golden-runs.json";

const GOLDEN = GOLDEN_FILE.runs;
import {
  DEFAULT_WEIGHTS, DIMENSIONS, isDefaultWeights, normaliseWeights, reweight, sanitiseWeights,
} from "./index.js";

/**
 * The anti-drift half that lives in JS. tests/test_whatif_weight_parity.py holds the other half:
 * it pins engine-constants.json to core.config by value and re-derives the formula's shape from
 * live engine output. Together they mean a change to core/score.py's arithmetic cannot land
 * silently while this module keeps returning the old answer.
 */

// Stored dimensions carry 1dp, so the error propagated into raw is at most 0.05 * sum(w) = 0.05,
// and final_score is itself stored at 1dp for another 0.05. 0.1 is the tightest bound that is
// provably satisfiable; anything smaller is flaky by construction rather than more correct.
const TOLERANCE = 0.1;

describe("reweight at engine defaults", () => {
  it("reproduces the score the engine actually stored, for every real run", () => {
    expect(GOLDEN.length).toBeGreaterThan(0);
    for (const run of GOLDEN) {
      const got = reweight(run, DEFAULT_WEIGHTS);
      expect(got, `run ${run.run_id}`).not.toBeNull();
      expect(Math.abs(got.finalScore - run.final_score), `run ${run.run_id} (${run.company})`)
        .toBeLessThanOrEqual(TOLERANCE);
    }
  });

  it("also reproduces the engine's raw score, before data confidence is applied", () => {
    for (const run of GOLDEN) {
      const got = reweight(run, DEFAULT_WEIGHTS);
      expect(Math.abs(got.rawScore - run.raw_score), `run ${run.run_id}`)
        .toBeLessThanOrEqual(TOLERANCE);
    }
  });
});

describe("normalisation", () => {
  it("scores identically whether weights are given as points or fractions", () => {
    const run = GOLDEN[0];
    const asPoints = { ...DEFAULT_WEIGHTS, siemens_fit: 40 };
    const scaled = Object.fromEntries(DIMENSIONS.map((k) => [k, asPoints[k] / 1.15]));
    expect(reweight(run, asPoints).finalScore).toBeCloseTo(reweight(run, scaled).finalScore, 10);
  });

  it("keeps raw score within 0-100 so the thin-profile cap stays non-binding", () => {
    // The engine's invariant: with weights summing to 1 the cap can never fire, because raw <= 100
    // and data confidence <= 1. Documents why we normalise rather than accept the raw sum.
    const lopsided = { traction: 900, siemens_fit: 3, product: 0, market: 0, founder: 0, ecosystem: 0 };
    for (const run of GOLDEN) {
      expect(reweight(run, lopsided).rawScore).toBeLessThanOrEqual(100);
    }
  });

  it("refuses to score when every weight is zero rather than dividing by zero", () => {
    const zeros = Object.fromEntries(DIMENSIONS.map((k) => [k, 0]));
    expect(normaliseWeights(zeros).ok).toBe(false);
    expect(reweight(GOLDEN[0], zeros)).toBeNull();
  });
});

describe("weighting behaviour", () => {
  it("raising a dimension's weight raises the score when that dimension is above average", () => {
    // Behavioural rather than a pinned constant: find a run whose product beats its own
    // default-weighted mean, then confirm favouring product moves the score the right way.
    const run = GOLDEN.find((r) => r.dimensions.product > reweight(r, DEFAULT_WEIGHTS).rawScore);
    expect(run, "expected at least one run with product above its weighted mean").toBeTruthy();
    const before = reweight(run, DEFAULT_WEIGHTS).finalScore;
    const after = reweight(run, { ...DEFAULT_WEIGHTS, product: DEFAULT_WEIGHTS.product + 30 }).finalScore;
    expect(after).toBeGreaterThan(before);
  });
});

describe("untrusted input", () => {
  it.each([
    ["null", null],
    ["an array", [1, 2, 3]],
    ["a missing dimension", { traction: 10 }],
    ["a NaN", { ...DEFAULT_WEIGHTS, product: NaN }],
    ["a negative", { ...DEFAULT_WEIGHTS, product: -5 }],
    ["a string", { ...DEFAULT_WEIGHTS, product: "20" }],
  ])("rejects %s instead of producing a number the engine never made", (_label, bad) => {
    expect(sanitiseWeights(bad)).toBeNull();
    expect(reweight(GOLDEN[0], bad)).toBeNull();
  });

  it("reports a run with no dimensions as unscoreable rather than guessing", () => {
    expect(reweight({ dimensions: {}, data_completeness: 0.5 }, DEFAULT_WEIGHTS)).toBeNull();
    expect(reweight(null, DEFAULT_WEIGHTS)).toBeNull();
  });
});

describe("isDefaultWeights", () => {
  it("treats no override and the engine's own weights as the same state", () => {
    expect(isDefaultWeights(null)).toBe(true);
    expect(isDefaultWeights(DEFAULT_WEIGHTS)).toBe(true);
    // Scaling every weight equally is the same weighting, so it must not read as modified.
    expect(isDefaultWeights(Object.fromEntries(DIMENSIONS.map((k) => [k, DEFAULT_WEIGHTS[k] * 3])))).toBe(true);
    expect(isDefaultWeights({ ...DEFAULT_WEIGHTS, siemens_fit: 40 })).toBe(false);
  });
});
