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
  // Fails fast and legibly when the API is not running.
  page: async ({ page, baseURL }, use) => {
    const health = await page.request.get("http://localhost:8000/health").catch(() => null);
    if (!health || !health.ok()) {
      throw new Error(
        "Backend not reachable on :8000 — start it with:\n" +
        "  py -3 -m uvicorn api.main:app --port 8000",
      );
    }
    await use(page);
  },
});

/**
 * Fixed rows for the Explore table.
 *
 * Visual baselines must render identical pixels every run. Left unstubbed, /api/runs returns
 * whatever is in runs.db — which grows and re-scores every time anyone evaluates a company — so
 * the snapshot drifted and the mobile baseline failed on consecutive runs. A baseline that
 * flickers teaches people to ignore the diff, which defeats the point of having one.
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
  await page.route("**/api/runs", (route) => route.fulfill({ json: RUNS_FIXTURE }));
}

/** Stub the slow, non-deterministic endpoints so a journey is about the UI, not the network. */
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
    `,
  });
  await page.evaluate(() => document.fonts?.ready);
}

export { expect };
