import { expect, stabilise, stubEvaluation, stubRuns, test } from "./fixtures.js";

/**
 * The user journeys from contract/feature-inventory.md. Each test names its contract ID so a
 * failure says which behaviour broke, not just which selector moved.
 */

test.describe("shell", () => {
  test("SHELL-01: icon rail exposes the primary destinations", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: /primary/i });
    // The visible labels are the product's wording, not the route names: /saved is "Views" and
    // /alerts is "Tracking". Asserting the route names instead would pass only by accident.
    for (const label of ["Home", "Explore", "Views", "Tracking", "Ask AI", "Settings"]) {
      await expect(nav.getByRole("link", { name: new RegExp(label, "i") })).toBeVisible();
    }
  });

  test("SHELL-02/04: Ctrl+K focuses the command bar and Enter opens a profile", async ({ page }) => {
    await stubEvaluation(page);
    await page.goto("/");

    const search = page.getByPlaceholder(/search a startup/i);
    // Wait for the command bar to exist before sending the shortcut. Its listener is attached in
    // an effect, and a keypress fired before that is simply lost — no assertion timeout can
    // recover it, which is what made this flaky.
    await expect(search).toBeVisible();

    // press() on body rather than page.keyboard: a bare click lands on whatever sits at the
    // centre of the viewport, which differs per breakpoint and navigated away on the narrow ones.
    await page.locator("body").press("Control+k");
    await expect(search).toBeFocused();

    await search.fill("Phena");
    await search.press("Enter");

    // Assert the destination, not the transient URL: the app navigates to /startup/new?name=…,
    // evaluates, then replaces the URL with the saved run id. Matching the intermediate step is a
    // race that only passes when the machine is slow.
    await expect(page).toHaveURL(/\/startup\//);
    await expect(page.getByText(/Phena/i).first()).toBeVisible();
  });
});

test.describe("explore", () => {
  test("EXP-02/08: column drawer opens and closes on Escape", async ({ page }) => {
    await page.goto("/explore");
    const drawer = page.getByRole("complementary", { name: /customise columns/i });
    await expect(drawer).toBeHidden();

    await page.getByRole("button", { name: /customise columns/i }).click();
    await expect(drawer).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
  });

  test("EXP-09: table state lives in the URL and survives a reload", async ({ page }) => {
    await page.goto("/explore?density=comfortable");
    await page.reload();
    await expect(page).toHaveURL(/density=comfortable/);
  });
});

test.describe("profile", () => {
  test("PROF-04: tabs switch without losing the run", async ({ page }) => {
    await stubEvaluation(page);
    await page.goto("/startup/1");

    const tablist = page.getByRole("tablist");
    await expect(tablist).toBeVisible();
    await tablist.getByRole("tab", { name: /evidence/i }).click();
    await expect(tablist.getByRole("tab", { name: /evidence/i })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText(/Phena/i).first()).toBeVisible();
  });

  test("PROF-02/X-01: a web-sourced value links to its real source", async ({ page }) => {
    await stubEvaluation(page);
    await page.goto("/startup/1");
    const badge = page.getByRole("link", { name: /^web$/i }).first();
    await expect(badge).toHaveAttribute("href", "https://www.cbinsights.com/company/phena");
  });

  test("PROF-05: a company-claimed membership is labelled as such", async ({ page }) => {
    await stubEvaluation(page);
    await page.goto("/startup/1");
    // NVIDIA Inception is self_asserted in the fixture; presenting it as verified would
    // overstate the evidence, which is the one thing this product must not do.
    await expect(page.getByText(/NVIDIA Inception/i).first()).toBeVisible();
    await expect(page.getByText(/claimed/i).first()).toBeVisible();
  });
});

test.describe("error states", () => {
  test("X-03: an API failure is announced, not silently blank", async ({ page }) => {
    await page.route("**/api/runs", (route) => route.fulfill({ status: 500, json: { detail: "boom" } }));
    await page.goto("/explore");
    await expect(page.getByRole("alert")).toBeVisible();
  });
});

/**
 * Visual regression — the enforceable form of "the Tracxn layout is preserved".
 * Baselines are human-owned; agents must not regenerate them.
 */
test.describe("layout", () => {
  test("X-05/X-06: Tracxn shell holds its shape", async ({ page }, testInfo) => {
    await stubRuns(page);
    await page.goto("/explore");
    await stabilise(page);
    await expect(page).toHaveScreenshot(`explore-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: profile layout holds its shape", async ({ page }, testInfo) => {
    await stubEvaluation(page);
    await page.goto("/startup/1");
    await stabilise(page);
    await expect(page.getByRole("tablist")).toBeVisible();
    await expect(page).toHaveScreenshot(`profile-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: no horizontal body scroll at any width", async ({ page }) => {
    await stubRuns(page);
    await page.goto("/explore");
    await stabilise(page);
    const overflows = await page.evaluate(() =>
      document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflows, "body scrolls horizontally — wide content must scroll inside its own container")
      .toBe(false);
  });
});
