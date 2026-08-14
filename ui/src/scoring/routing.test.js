import { describe, expect, it } from "vitest";
import GOLDEN_FILE from "./golden-runs.json";
import { DEFAULT_WEIGHTS, DIMENSIONS } from "./index.js";
import {
  ROUTES, breakevenWeight, routeWeightsFor, scorecardsFor, weightsWithShare, whatIfRouting,
} from "./routing.js";

const GOLDEN = GOLDEN_FILE.runs;

// The engine computed its scorecards from unrounded dimensions, but stores those dimensions at 1dp,
// so recomputing from the fixture propagates up to 0.05; the stored card is itself 1dp for another
// 0.05. 0.1 is exactly reachable (run 1's Connect card is 38.45625 → 38.5 against a stored 38.4),
// hence the epsilon: 0.1 has no exact binary representation and the bound is inclusive.
const TOLERANCE = 0.1 + 1e-9;

/**
 * The JS half of the routing pin. tests/test_whatif_route_parity.py holds the other half — it
 * drives the real core/route.py to each threshold boundary, so a moved literal fails there.
 */

// Seeded, so a property failure is reproducible. Math.random would report a bug nobody can rerun.
function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function randomWeights(rand) {
  return Object.fromEntries(DIMENSIONS.map((k) => [k, rand() * 100]));
}

describe("identity at the engine's own weights", () => {
  it("reproduces the route scorecards the engine actually stored, for every real run", () => {
    // The most valuable test here: it means the delta blend degenerates to the engine's own
    // ROUTE_WEIGHTS at defaults, so any drift in the blend shows up against real recorded output.
    expect(GOLDEN.length).toBeGreaterThan(0);
    for (const run of GOLDEN) {
      const got = scorecardsFor(run, DEFAULT_WEIGHTS);
      expect(got, `run ${run.run_id}`).not.toBeNull();
      for (const route of ROUTES) {
        expect(
          Math.abs(got[route] - run.route_scorecards[route]),
          `run ${run.run_id} (${run.company}) ${route}: got ${got[route]}, engine stored ${run.route_scorecards[route]}`,
        ).toBeLessThanOrEqual(TOLERANCE);
      }
    }
  });

  it("reproduces the pillar and secondary the engine recorded", () => {
    for (const run of GOLDEN) {
      const got = whatIfRouting(run, { aligned: run.fit_aligned }, DEFAULT_WEIGHTS);
      expect(got.pillar, `run ${run.run_id} (${run.company})`).toBe(run.pillar);
      expect(got.secondary, `run ${run.run_id}`).toEqual(run.secondary);
    }
  });
});

describe("what a weighting can and cannot change", () => {
  it("never turns an aligned run into a Pass, however extreme the weighting", () => {
    // Empower has no score gate, so once alignment passes the eligible list can never empty.
    // This is why the panel must not promise "could become Pass".
    const rand = lcg(20260811);
    const aligned = GOLDEN.filter((r) => r.fit_aligned && r.dimensions.siemens_fit >= 50);
    expect(aligned.length).toBeGreaterThan(0);
    for (const run of aligned) {
      for (let i = 0; i < 200; i++) {
        expect(whatIfRouting(run, { aligned: true }, randomWeights(rand)).pillar).not.toBe("Pass");
      }
    }
  });

  it("never rescues a run that fails the alignment gate", () => {
    const rand = lcg(7);
    const barred = GOLDEN.filter((r) => !r.fit_aligned || r.dimensions.siemens_fit < 50);
    expect(barred.length).toBeGreaterThan(0);
    for (const run of barred) {
      for (let i = 0; i < 200; i++) {
        const got = whatIfRouting(run, { aligned: run.fit_aligned }, randomWeights(rand));
        expect(got.pillar).toBe("Pass");
        expect(got.invariant).toBe("alignment");
      }
    }
  });

  it("leaves a traction-barred run on Empower alone, and says so provably", () => {
    // Both gated routes have a traction clause no weighting touches, so the outcome is fixed.
    const run = GOLDEN.find((r) => r.fit_aligned && r.dimensions.siemens_fit >= 50
      && r.dimensions.traction < 35);
    expect(run, "expected an aligned run with traction below the Collaborate gate").toBeTruthy();
    const rand = lcg(99);
    for (let i = 0; i < 200; i++) {
      const got = whatIfRouting(run, { aligned: true }, randomWeights(rand));
      expect(got.pillar).toBe("Empower");
      expect(got.secondary).toEqual([]);
      expect(got.invariant).toBe("traction");
    }
  });
});

describe("the delta blend", () => {
  it("returns the engine's own profile untouched at default weights", () => {
    for (const route of ROUTES) {
      const w = routeWeightsFor(route, DEFAULT_WEIGHTS);
      const sum = DIMENSIONS.reduce((s, k) => s + w[k], 0);
      expect(sum).toBeCloseTo(1, 10);
    }
  });

  it("keeps weights non-negative and summing to one however extreme the input", () => {
    const rand = lcg(4242);
    for (let i = 0; i < 200; i++) {
      const weights = randomWeights(rand);
      for (const route of ROUTES) {
        const w = routeWeightsFor(route, weights);
        expect(DIMENSIONS.every((k) => w[k] >= 0)).toBe(true);
        expect(DIMENSIONS.reduce((s, k) => s + w[k], 0)).toBeCloseTo(1, 10);
      }
    }
  });

  it("never collapses the three routes onto one number", () => {
    // A convex average would; the clip-at-zero in the delta blend is what preserves the distinction
    // between what Connect needs and what Empower needs.
    const rand = lcg(31337);
    for (const run of GOLDEN) {
      for (let i = 0; i < 50; i++) {
        const cards = scorecardsFor(run, randomWeights(rand));
        expect(new Set(ROUTES.map((r) => cards[r])).size).toBeGreaterThan(1);
      }
    }
  });
});

describe("untrusted input", () => {
  it("returns null rather than a routing decision built on nonsense", () => {
    const run = GOLDEN[0];
    expect(whatIfRouting(run, { aligned: true }, { ...DEFAULT_WEIGHTS, product: NaN })).toBeNull();
    expect(whatIfRouting(run, { aligned: true }, null)).toBeNull();
    expect(whatIfRouting({ dimensions: {} }, { aligned: true }, DEFAULT_WEIGHTS)).toBeNull();
    expect(scorecardsFor(run, Object.fromEntries(DIMENSIONS.map((k) => [k, 0])))).toBeNull();
  });
});

describe("breakeven sensitivity", () => {
  const fitOf = (run) => ({ aligned: run.fit_aligned });

  it("agrees with whatIfRouting everywhere inside the band it reports", () => {
    // The property that makes the number trustworthy: if the panel says "eligible between 31%
    // and 58%", re-scoring at any weight in that range must actually produce that route.
    for (const run of GOLDEN) {
      for (const route of ROUTES) {
        const bw = breakevenWeight(run, fitOf(run), "traction", route);
        expect(bw, `run ${run.run_id} ${route}`).not.toBeNull();
        if (!bw.reachable) continue;
        for (const share of [bw.band.from, (bw.band.from + bw.band.to) / 2, bw.band.to]) {
          const probed = whatIfRouting(run, fitOf(run), weightsWithShare(DEFAULT_WEIGHTS, "traction", share));
          expect(
            probed.gates[route].eligible,
            `run ${run.run_id} ${route} at traction=${share}`,
          ).toBe(true);
        }
      }
    }
  });

  it("says a route is unreachable rather than inventing a weight for it", () => {
    // Every golden run is alignment-blocked or traction-blocked for at least one route, and the
    // honest answer there is "no weighting does this" — the panel must never print a breakeven
    // the reviewer could chase and never reach.
    const unreachable = [];
    for (const run of GOLDEN) {
      for (const route of ROUTES) {
        const bw = breakevenWeight(run, fitOf(run), "traction", route);
        if (!bw.reachable) {
          unreachable.push([run.run_id, route]);
          expect(bw.band).toBeNull();
        }
      }
    }
    expect(unreachable.length).toBeGreaterThan(0);
  });

  it("reports delta 0 when the route is already eligible at the reviewer's weighting", () => {
    for (const run of GOLDEN) {
      const at = whatIfRouting(run, fitOf(run), DEFAULT_WEIGHTS);
      for (const route of at.eligible) {
        const bw = breakevenWeight(run, fitOf(run), "traction", route);
        expect(bw.currentlyEligible, `run ${run.run_id} ${route}`).toBe(true);
        expect(bw.delta, `run ${run.run_id} ${route}`).toBe(0);
      }
    }
  });

  it("short-circuits an alignment-blocked run without claiming a band", () => {
    const blocked = { ...GOLDEN[0], dimensions: { ...GOLDEN[0].dimensions, siemens_fit: 10 } };
    const bw = breakevenWeight(blocked, { aligned: false }, "traction", "Connect");
    expect(bw.invariant).toBe("alignment");
    expect(bw.reachable).toBe(false);
    expect(bw.band).toBeNull();
  });

  it("refuses unknown dimensions, unknown routes and unusable weights", () => {
    const run = GOLDEN[0];
    expect(breakevenWeight(run, fitOf(run), "vibes", "Connect")).toBeNull();
    expect(breakevenWeight(run, fitOf(run), "traction", "Pass")).toBeNull();
    expect(breakevenWeight(run, fitOf(run), "traction", "Connect", null)).toBeNull();
  });
});
