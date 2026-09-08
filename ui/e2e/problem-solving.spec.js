import { test, expect } from "@playwright/test";

// Self-contained: no company searches, credentials, or paid APIs are used.
test("turn a problem brief into sourced candidate cards", async ({ page }, testInfo) => {
  let latestJob;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/api/auth/me") body = { authenticated: true, mode: "entra", user: {
      oid: "scouting-browser-test", name: "Test Reviewer", initials: "TR", email: "test@example.com", roles: [],
    } };
    else if (path === "/api/integrations/tracxn") body = { connected: false, configured: true };
    else if (path === "/api/my/searches") body = { runs: [] };
    else if (path === "/api/my/views") body = { views: [] };
    else if (path === "/api/my/watchlist") body = { companies: [] };
    else if (path === "/api/jobs" || path.startsWith("/api/jobs/")) {
      if (route.request().method() === "GET") { await route.fulfill({json:latestJob}); return; }
      const result = { problem: JSON.parse(route.request().postData()).problem,
      candidates: [{ name: "Example Vision", source: "glassdollar", description: "Visual inspection for production lines.",
        rationale: "Detects surface defects during manufacturing.", relevance: 84, website: "https://example.com" }],
      sources: [{ provider: "tracxn", status: "not_connected" }, { provider: "glassdollar", status: "used" },
        { provider: "web", status: "skipped" }], method: "llm", elapsed_seconds: 1.2 };
      latestJob = {id:"problem-test", kind:"solve", query:result.problem, status:"complete", result};
      body = {jobs:[latestJob]};
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Solve a Problem", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("problem-brief.png"), fullPage: true });
  await page.getByRole("button", { name: "Improve quality", exact: true }).click();
  const brief = page.getByRole("textbox", { name: "Describe your problem" });
  await expect(brief).toHaveValue(/surface defects/);
  await page.getByRole("button", { name: "Find solutions", exact: true }).click();
  await expect(page.getByText("Detects surface defects during manufacturing.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Evaluate solution" })).toHaveAttribute("href", /startup\/new\?name=Example%20Vision/);
  await expect(page.getByText("GlassDollar: Used")).toBeVisible();
  await expect(page.getByRole("link", { name: "example.com" })).toHaveAttribute("href", "https://example.com");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.goto("/");
  await expect(page.getByRole("heading", {name:"Explore a startup"})).toBeVisible();
  await page.goto("/workspace");
  await expect(page.getByText("Detects surface defects during manufacturing.")).toBeVisible();
  await page.getByRole("heading", { name: "1 potential solution" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("problem-results.png"), fullPage: true });
});
