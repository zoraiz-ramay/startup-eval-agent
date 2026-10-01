import { test, expect } from "@playwright/test";
import { RUN_FIXTURE } from "./fixtures.js";

/* Scoring & Fit per department, end to end in a browser: the legacy route for a run assessed
   before departments, the pillar-based page for a department run, switching to a department with
   no run yet (which creates one), and the Database's one-row-per-department grid. */
const departments = [
  { id: "di", label: "Digital Industries", interests: ["automation", "manufacturing"], demo: true },
  { id: "si", label: "Smart Industries", interests: ["energy", "buildings"], demo: true },
];
const crit = (rows) => rows.map(([id, label, score, anchor]) => ({ id, label, score, anchor, rationale: `${label}: reasoning.`,
  evidence: [{ id: "E1", source: "summary", quote: "Industrial vision for quality control.", url: "" }],
  catalog: score > 0 ? [{ id: "tool:simatic", name: "SIMATIC AI", url: "" }] : [] }));
const DEPT_RUN = {
  ...RUN_FIXTURE, run_id: 21,
  department: { id: "di", label: "Digital Industries", interests: ["automation", "manufacturing"], demo: true },
  routing: { version: "pillar-route-v1", status: "assessed", pillar: "Empower", reasons: ["Empower is a strong match (8/9)."],
    next_steps: ["Scope a SIMATIC AI trial."], evidence: [], portfolio_stance: null },
  traction: { version: "traction-rubric-v2", status: "scored", score_0_100: 60, earned: 42, available_max: 70, confidence: 0.7,
    divisions_known: 3, fx_as_of: "2026-09-01", divisions: [] },
  market: { version: "market-rubric-v1", status: "assessed", points: 9, score_0_100: 60, band: "Moderate Market", figures: {},
    criteria: [{ id: "market_size", label: "Market size", score: 3, anchor: "Large market", basis: "model_judgment", evidence: [], areas: [] }] },
  assessment: {
    concepts: { needs_gaps: [{ term: "defect detection" }], capabilities: [{ term: "visual inspection" }] },
    pillars: {
      Empower: { status: "assessed", total: 8, band: "strong", statement: "SIMATIC AI could help the startup deploy faster by running models on the line.",
        next_step: "Scope a SIMATIC AI trial.", notes: [],
        criteria: crit([["tool_fit", "Tool fit", 3, "Direct"], ["benefit_fit", "Benefit fit", 3, "Material"], ["actionability", "Actionability", 2, "Realistic"]]) },
      Connect: { status: "assessed", total: 5, band: "review", statement: "", next_step: "", notes: [],
        criteria: crit([["industry_fit", "Industry fit", 2, "Relevant"], ["topic_fit", "Topic fit", 2, "Clear"], ["ecosystem_value", "Ecosystem value", 1, "Generic"]]) },
      Collaborate: { status: "assessed", total: 0, band: "no_match", provisional: true, needs: ["automation", "manufacturing"], statement: "", next_step: "", notes: [],
        criteria: crit([["capability_fit", "Capability fit", 0, "None"], ["need_fit", "Need fit", 0, "None"], ["actionability", "Actionability", 0, "None"]]) },
    },
    siemens_fit: { score: 89, winner: "Empower", raw: 8, partial: false, status: "assessed" },
    weights: { traction: 0.3, siemens_fit: 0.35, team_ecosystem: 0.2, market: 0.15 },
    components: { traction: 60, siemens_fit: 89, team_ecosystem: 70, market: 60 }, total: 72.2,
    team_ecosystem: { status: "assessed", points: 14, score_0_100: 70, band: "Strong",
      criteria: crit([["founder_experience", "Founder experience", 4, "Leadership"], ["domain_expertise", "Domain expertise", 4, "Strong"],
        ["external_validation", "External validation", 3, "Recognised"], ["strategic_network", "Strategic network", 3, "Several"]]) },
  },
};

test("a department run reads as a recommendation, three routes and a total, and switches department", async ({ page }) => {
  const assessed = [];
  let legacy = { ...RUN_FIXTURE, run_id: 12 };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/api/auth/me") body = { authenticated: true, user: { oid: "department-test", name: "Reviewer" } };
    else if (path === "/api/departments") body = { departments };
    else if (path === "/api/runs/21/departments") body = { company: DEPT_RUN.company, department_id: "di", legacy: false,
      departments: [{ ...departments[0], run_id: 21, current: true }, { ...departments[1], run_id: null, current: false }] };
    else if (path === "/api/runs/21/departments/si" && route.request().method() === "POST") {
      assessed.push("si");
      body = { ...DEPT_RUN, run_id: 22, department: { ...DEPT_RUN.department, id: "si", label: "Smart Industries" } };
    } else if (path === "/api/runs/12/departments") body = { company: legacy.company, department_id: null, legacy: true, departments: departments.map((d) => ({ ...d, run_id: null, current: false })) };
    else if (path.endsWith("/decision")) {
      legacy = { ...legacy, routing: { version: "llm-decision-v2", status: "assessed", pillar: "Pass", confidence: 0.72,
        reasons: ["The evidenced offering does not address the identified Siemens needs."], next_steps: ["Close the review."], evidence: [] } };
      body = { routing: legacy.routing };
    } else if (path === "/api/runs/12") body = legacy;
    else if (path === "/api/runs/21") body = DEPT_RUN;
    else if (path === "/api/runs/22") body = { ...DEPT_RUN, run_id: 22, department: { ...DEPT_RUN.department, id: "si", label: "Smart Industries" } };
    else if (path === "/api/my/searches") body = { runs: [
      { id: 21, company: "Phena", department_id: "di", department_label: "Digital Industries", legacy: false, final_score: 72.2, total_status: "complete", pillar: "Empower", created_at: "2026-09-30" },
      { id: 22, company: "Phena", department_id: "si", department_label: "Smart Industries", legacy: false, final_score: null, total_status: "pending", pillar: "Defer", created_at: "2026-09-30" },
      { id: 12, company: "Phena", department_id: "", department_label: "", legacy: true, final_score: 37.5, total_status: "", pillar: "Pass", created_at: "2026-08-01" }] };
    else if (path === "/api/my/views") body = { views: [] };
    await route.fulfill({ json: body });
  });

  // A run from before departments keeps its model recommendation, generated on request.
  await page.goto("/startup/12?tab=Scoring+%26+Fit");
  await expect(page.getByText("Legacy run: assessed before departments existed.")).toBeVisible();
  await page.getByRole("button", { name: "Generate legacy recommendation" }).click();
  await expect(page.locator("#scoring-summary .pill").first()).toHaveText("Pass");

  // A department run: recommendation, rings, three route cards and the total.
  await page.goto("/startup/21?tab=Scoring+%26+Fit");
  await expect(page.getByText("Recommended · Empower")).toBeVisible();
  await expect(page.getByRole("img", { name: "Total score 72.2 out of 100" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Siemens Fit 89 out of 100" })).toBeVisible();
  await expect(page.locator("ix-message-bar")).toContainText("Collaborate is provisional.");
  await page.getByRole("button", { name: /^Collaborate: 0 out of 100/ }).click();
  await expect(page.getByRole("heading", { name: "No supported link to the current needs" })).toBeVisible();
  await expect(page).toHaveURL(/pillar=Collaborate/);

  // Detailed view adds the scoring method; summary keeps it out.
  await expect(page.getByText("Scoring method")).toHaveCount(0);
  await page.locator("ix-toggle-button", { hasText: "Detailed" }).click();
  await expect(page.getByText("Scoring method").first()).toBeVisible();

  // A department with no run is offered an assessment, which opens the new run.
  await page.locator("#scoring-department ix-select").click();
  await page.getByRole("option", { name: "Smart Industries (example needs)", exact: true }).click();
  await page.getByRole("button", { name: "Assess for Smart Industries" }).click();
  await expect(page).toHaveURL(/\/startup\/22/);
  expect(assessed).toEqual(["si"]);

  // The Database lists one row per company and department, labelled.
  await page.goto("/explore");
  await page.evaluate(() => localStorage.removeItem("se.department.v1"));
  await page.reload();
  for (const label of ["Digital Industries", "Smart Industries", "Legacy"]) {
    await expect(page.getByRole("row").filter({ hasText: label })).toHaveCount(1);
  }
  await expect(page.getByRole("row").filter({ hasText: "Smart Industries" })).toContainText("pending");
});

/* Visual record of the department-run page: hero rings, score tiles, route cards and the total
   chart. Desktop and laptop only — the scoring page is a desktop tool. */
test("X-05: Scoring & Fit charts hold their shape for a department run", async ({ page }, testInfo) => {
  test.skip(!["desktop", "laptop"].includes(testInfo.project.name), "Scoring & Fit is desktop-only.");
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/api/auth/me") body = { authenticated: true, user: { oid: "department-visual", name: "Reviewer" } };
    else if (path === "/api/departments") body = { departments };
    else if (path === "/api/runs/21/departments") body = { company: DEPT_RUN.company, department_id: "di", legacy: false,
      departments: [{ ...departments[0], run_id: 21, current: true }, { ...departments[1], run_id: null, current: false }] };
    else if (path === "/api/runs/21") body = DEPT_RUN;
    else if (path === "/api/my/searches") body = { runs: [] };
    else if (path === "/api/my/views") body = { views: [] };
    await route.fulfill({ json: body });
  });
  await page.goto("/startup/21?tab=Scoring+%26+Fit");
  await expect(page.getByRole("img", { name: "Total score 72.2 out of 100" })).toBeVisible();
  await page.addStyleTag({ content: "*, *::before, *::after { transition: none !important; animation: none !important; }" });
  await expect(page.locator("#scoring-summary")).toHaveScreenshot(`scoring-summary-dept-${testInfo.project.name}.png`);
  await expect(page.locator("#scoring-routes")).toHaveScreenshot(`scoring-routes-dept-${testInfo.project.name}.png`);
  await expect(page.locator("#scoring-total")).toHaveScreenshot(`scoring-total-dept-${testInfo.project.name}.png`);
  await expect(page.locator("#scoring-team")).toHaveScreenshot(`scoring-team-dept-${testInfo.project.name}.png`);
  // An opened criterion: the panel under the cards, pointing at the cell it belongs to.
  await page.getByRole("button", { name: /^Benefit fit: 3 of 3/ }).click();
  await expect(page.getByRole("region", { name: "Empower · criterion 2 of 3: Benefit fit" })).toBeVisible();
  await expect(page.locator("#scoring-routes")).toHaveScreenshot(`scoring-criterion-dept-${testInfo.project.name}.png`);
});

test("a criterion cell opens its detail, a second press closes it, and the total sits above Siemens Fit", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Scoring & Fit is desktop-only.");
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/api/auth/me") body = { authenticated: true, user: { oid: "department-cells", name: "Reviewer" } };
    else if (path === "/api/departments") body = { departments };
    else if (path === "/api/runs/21") body = DEPT_RUN;
    else if (path === "/api/my/searches") body = { runs: [] };
    else if (path === "/api/my/views") body = { views: [] };
    await route.fulfill({ json: body });
  });
  await page.goto("/startup/21?tab=Scoring+%26+Fit");
  await expect(page.locator("#scoring-routes .route-card").first()).toBeVisible();
  const order =await page.locator("section.profile-section").evaluateAll((els) => els.map((e) => e.id));
  expect(order.indexOf("scoring-total")).toBeLessThan(order.indexOf("scoring-routes"));
  const tool = page.getByRole("button", { name: /^Tool fit: 3 of 3/ });
  await tool.click();
  await expect(page.getByRole("region", { name: "Empower · criterion 1 of 3: Tool fit" })).toBeVisible();
  await page.getByRole("button", { name: /^Benefit fit: 3 of 3/ }).click();
  await expect(page.getByRole("region", { name: /Tool fit/ })).toHaveCount(0);
  await page.getByRole("button", { name: /^Benefit fit: 3 of 3/ }).click();
  await expect(page.getByRole("region", { name: /criterion/ })).toHaveCount(0);
  await page.getByRole("button", { name: /^External validation: 3 of 5/ }).click();
  await expect(page.getByRole("region", { name: "Team & Ecosystem: External validation" })).toBeVisible();
  // Traction follows Siemens Fit, and each part of the total leads to its own section — Market,
  // near the end of the page, included, which the page cannot scroll to the top.
  expect(order.indexOf("scoring-traction")).toBe(order.indexOf("scoring-routes") + 1);
  for (const [name, id] of [["Market", "scoring-market"], ["Traction", "scoring-traction"]]) {
    await page.locator("#scoring-total").scrollIntoViewIfNeeded();
    await page.getByRole("link", { name: new RegExp(`^${name}: .*Go to ${name}$`) }).click();
    await expect(page).toHaveURL(new RegExp(`#${id}$`));
    await expect(page.locator('[aria-current="location"]')).toHaveText(name);
  }
});
