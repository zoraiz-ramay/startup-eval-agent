import { expect, test as base } from "@playwright/test";

/**
 * Shared setup for the journey specs.
 *
 * Two decisions worth knowing about:
 *
 * 1. The backend is NOT started by Playwright. It holds real data and a real API key, and a suite
 *    that silently boots its own would be testing something other than the app you run. If it is
 *    not up, the run fails with an instruction rather than a confusing cascade of timeouts.
 *
 * 2. Evaluation is stubbed by default. A live /api/evaluate takes ~60s and its result changes with
 *    whatever DuckDuckGo returns that minute — neither acceptable in a gate that must be fast and
 *    deterministic. Specs that genuinely need the real pipeline opt in explicitly.
 */
export const RUN_FIXTURE = {
  found: true,
  company: "Phena",
  source: "web",
  engine: "test-fixture",
  summary: "Industrial computer vision for manufacturing quality control.",
  profile: {
    company_name: "Phena",
    website: "https://phena.tech",
    hq: "Istanbul, Turkey",
    founded_year: "2026",
    employees_count: "2-10",
    funding: "",
  },
  profile_sources: {
    founded_year: { origin: "web", url: "https://www.cbinsights.com/company/phena" },
  },
  score: {
    final_score: 37.5,
    data_completeness: 0.5,
    data_confidence: 0.75,
    verified_customers: 0,
    dimensions: { traction: 0, siemens_fit: 40, product: 65, market: 50, founder: 70, ecosystem: 100 },
    route_scorecards: { Connect: 35, Collaborate: 38, Empower: 40 },
    missing_evidence: ["funding"],
    red_flags: [],
  },
  routing: { pillar: "Connect", secondary: [], rationale: "Deployable computer vision." },
  fit: { matches: [], challenge_match: {} },
  facts: [
    { key: "site:/", value: "Phena — Our Supporters", source_url: "https://phena.tech",
      method: "site_fetch", confidence: 0.6, verified: true },
  ],
  verification: { claims: [], red_flags: [] },
  trend: { label: "Emerging", signals: [] },
  deep_profile: {
    method: "llm",
    founders: [{ name: "Kutadgu Gokalp Demirci", role: "Co-Founder", background: "", linkedin: "", source_url: "" }],
    advisors: [],
    key_team: [],
    employees: "2-10",
    employees_over_time: [],
    parent_group: "",
    founded_year: "2026",
    funding: "",
    programs: [
      { name: "NVIDIA Inception", type: "corporate_program", prestige: "tier1",
        confidence: "self_asserted", source_url: "https://phena.tech" },
    ],
    reference_customers: [],
    customer_segment: "",
    sfs: { relevant: true, rationale: "Hardware-adjacent." },
  },
};

export const test = base.extend({
  // Fails fast and legibly when the API is not running, then signs in.
  page: async ({ page, baseURL }, use) => {
    const health = await page.request.get("http://localhost:8000/health").catch(() => null);
    if (!health || !health.ok()) {
      throw new Error(
        "Backend not reachable on :8000 — start it with:\n" +
        "  AUTH_MODE=stub SESSION_BACKEND=memory py -3 -m uvicorn api.main:app --port 8000",
      );
    }

    // Every journey below starts from a bare page.goto() and would otherwise land on the
    // sign-in screen. Signing in here, once, is what keeps those journeys unchanged.
    //
    // Conditional Access at ACP 3 requires a compliant device on a trusted network, so no
    // CI runner can ever complete a real Entra sign-in. AUTH_MODE=stub replaces only the
    // round-trip to Entra: the cookies, the CSRF token, the session store and the guard
    // that reads them are all the production code paths, so these journeys still prove the
    // guard works rather than proving it was switched off.
    //
    // Relative URL on purpose — it goes through the vite proxy so the cookie is set on the
    // page's own origin. page.request.get() uses a separate context and the browser would
    // never see the cookie.
    // Saved views are server-side and per-reviewer now, and the stub principal is the SAME
    // person in every run — so a view someone created while poking at the dev backend would
    // appear in the sidenav and move every baseline. Pinned empty here; the specs that care
    // about views override it.
    await page.route("**/api/my/views", (route) => route.fulfill({ json: { views: [] } }));

    await page.goto("/api/auth/login?next=/");
    // Checked from inside the page for the same reason the login above is a page.goto:
    // page.request has its own cookie jar and would report "signed out" no matter what.
    const body = await page.evaluate(() =>
      fetch("/api/auth/me", { credentials: "same-origin" }).then((r) => r.json()).catch(() => ({})));
    if (!body.authenticated) {
      throw new Error(
        "Signed-in fixture failed. The backend must run in stub mode for e2e:\n" +
        "  AUTH_MODE=stub SESSION_BACKEND=memory py -3 -m uvicorn api.main:app --port 8000\n" +
        "(single process — the in-memory session store splits under gunicorn workers)",
      );
    }

    await use(page);
  },
});

/**
 * Fixed rows for the Explore table.
 *
 * Visual baselines must render identical pixels every run. Left unstubbed, /api/my/searches
 * returns whatever this reviewer has searched — which grows and re-scores every time anyone
 * evaluates a company — so the snapshot drifted and the mobile baseline failed on consecutive
 * runs. A baseline that flickers teaches people to ignore the diff, which defeats the point of
 * having one.
 */
export const RUNS_FIXTURE = {
  runs: [
    { id: 1, company: "Phena", final_score: 37.5, siemens_fit: 40, summary: "Industrial computer vision for quality control.",
      hq: "Istanbul, Turkey", stage: "Early market stage", funding: "", founded_year: "2026", founders: "",
      evidence_count: 12, verified_facts: 7, trend: "Emerging", pillar: "Connect", secondary: [],
      sfs_relevant: true, confidence: 0.75, created_at: "2026-08-01T09:00:00+00:00" },
    { id: 2, company: "Meili Robots", final_score: 52.0, siemens_fit: 61, summary: "Fleet management for autonomous mobile robots.",
      hq: "Odense, Denmark", stage: "Growth market stage", funding: "292621.0", founded_year: "2019", founders: "",
      evidence_count: 18, verified_facts: 12, trend: "Steady", pillar: "Collaborate", secondary: [],
      sfs_relevant: true, confidence: 0.82, created_at: "2026-08-02T09:00:00+00:00" },
    { id: 3, company: "Hypertrain", final_score: 44.0, siemens_fit: 48, summary: "AI training infrastructure for industrial models.",
      hq: "Tallinn, Estonia", stage: "Early market stage", funding: "", founded_year: "2024", founders: "",
      evidence_count: 9, verified_facts: 5, trend: "Emerging", pillar: "Empower", secondary: [],
      sfs_relevant: false, confidence: 0.68, created_at: "2026-08-03T09:00:00+00:00" },
  ],
};

/** Deterministic table data — required before any screenshot of a data view. */
export async function stubRuns(page) {
  // /api/my/searches, not /api/runs: lists became per-reviewer, and /api/runs is now the
  // admin-only whole-tenant view that no journey below reads.
  await page.route("**/api/my/searches", (route) => route.fulfill({ json: RUNS_FIXTURE }));
}

/** Stub the slow, non-deterministic endpoints so a journey is about the UI, not the network. */
/**
 * A run that actually routes, for exercising the what-if routing derivation (PROF-15).
 *
 * Separate from RUN_FIXTURE on purpose: that one backs the visual baselines, and it is also not
 * engine-consistent (its recorded final_score does not match what its own dimensions imply), so it
 * cannot support an assertion about derived routing.
 *
 * These numbers ARE engine-consistent — the scorecards are ROUTE_WEIGHTS x dimensions x data
 * confidence, and the pillar is what core/route.py's gates produce from them. Giving ecosystem a
 * 52% share drops the Collaborate card from 67.3 to 46.4, under its 55 gate, so the pillar
 * demotes to Empower. An 8.6-point margin, from a single slider.
 */
export const ROUTABLE_RUN_FIXTURE = {
  ...RUN_FIXTURE,
  company: "Routable Robotics",
  score: {
    ...RUN_FIXTURE.score,
    final_score: 62.5,
    raw_score: 66.7,
    data_completeness: 0.875,
    data_confidence: 0.94,
    dimensions: { traction: 55, siemens_fit: 78, product: 85, market: 70, founder: 75, ecosystem: 20 },
    route_scorecards: { Connect: 63.0, Collaborate: 67.3, Empower: 64.1 },
  },
  routing: { pillar: "Collaborate", secondary: ["Empower"], rationale: "Strong portfolio fit." },
  fit: { aligned: true, matches: [{ tool: "Simcenter", confidence: 80 }], challenge_match: {} },
};

export async function stubRoutableRun(page) {
  await page.route("**/api/runs/2", (route) => route.fulfill({ json: ROUTABLE_RUN_FIXTURE }));
  await page.route("**/api/runs/*/audit", (route) => route.fulfill({ json: { overrides: [] } }));
}

export async function stubEvaluation(page) {
  await page.route("**/api/evaluate", (route) =>
    route.fulfill({ json: { ...RUN_FIXTURE, cached: false, run_id: 1 } }));
  await page.route("**/api/runs/1", (route) => route.fulfill({ json: RUN_FIXTURE }));
  await page.route("**/api/runs/*/audit", (route) => route.fulfill({ json: { overrides: [] } }));
  await page.route("**/api/ask", (route) =>
    route.fulfill({ json: { answer: "Stubbed answer.", evidence: [], source: "AI" } }));
}

/**
 * Hide anything that legitimately changes between runs before a screenshot. Without this the
 * baselines fail on timestamps and score jitter, everyone starts ignoring the diff, and the gate
 * stops meaning anything.
 */
export async function stabilise(page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after { transition: none !important; animation: none !important; }
      .spinner { visibility: hidden !important; }
      /* The stubbed-auth banner exists only under AUTH_MODE=stub, which is to say only
         here — production can never render it (api/auth.py refuses to start). It is not
         part of the layout these baselines record, so it would be noise in the diff.
         That it appears at all is asserted in src/App.test.jsx instead. */
      .stub-banner { display: none !important; }
    `,
  });
  await page.evaluate(() => document.fonts?.ready);
}

export { expect };
