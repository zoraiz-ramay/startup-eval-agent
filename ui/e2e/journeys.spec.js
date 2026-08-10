import { expect, RUN_FIXTURE, RUNS_FIXTURE, stabilise, stubEvaluation, stubRuns, test } from "./fixtures.js";

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
    // Accessible name is field-specific (UI-01) so a screen reader can tell which figure this
    // badge backs; the visible text stays the literal word "web".
    const badge = page.getByRole("link", { name: /^web — founded year source$/i });
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

  test("PROF-12: headcount trend shows its one-line empty state by default (X-03)", async ({ page }) => {
    // RUN_FIXTURE's employees_over_time is [] — the common case, since the engine never returns
    // a single-point series. The Overview tab is the default tab, so this must be visible on
    // first paint without switching tabs.
    await stubEvaluation(page);
    await page.goto("/startup/1");
    await expect(page.getByText(/no cited headcount history/i)).toBeVisible();
  });

  test("PROF-12: a cited headcount series renders sourced, dated points (X-01)", async ({ page }) => {
    await page.route("**/api/evaluate", (route) =>
      route.fulfill({ json: { ...RUN_FIXTURE, cached: false, run_id: 1 } }));
    await page.route("**/api/runs/1", (route) =>
      route.fulfill({
        json: {
          ...RUN_FIXTURE,
          deep_profile: {
            ...RUN_FIXTURE.deep_profile,
            employees_over_time: [
              { year: 2022, count: 3, source_url: "https://crunchbase.example/acme" },
              { year: 2024, count: 60, source_url: "https://linkedin.example/acme" },
            ],
          },
        },
      }));
    await page.route("**/api/runs/*/audit", (route) => route.fulfill({ json: { overrides: [] } }));
    await page.goto("/startup/1");

    await expect(page.getByText(/3.*60/)).toBeVisible();
    const link = page.getByRole("link", { name: /source \(2022\)/i });
    await expect(link).toHaveAttribute("href", "https://crunchbase.example/acme");
  });
});

test.describe("error states", () => {
  test("X-03: an API failure is announced, not silently blank", async ({ page }) => {
    await page.route("**/api/runs", (route) => route.fulfill({ status: 500, json: { detail: "boom" } }));
    await page.goto("/explore");
    await expect(page.getByRole("alert")).toBeVisible();
  });
});

test.describe("accessibility", () => {
  test("X-06: pillar pill labels hold AA contrast (4.5:1) against their own backgrounds", async ({ page }) => {
    // A fourth row carrying "Pass" — RUNS_FIXTURE (shared with the visual baselines) only has
    // the other three pillars, and adding one there would perturb screenshots this test has no
    // business touching.
    const runs = {
      runs: [...RUNS_FIXTURE.runs, { ...RUNS_FIXTURE.runs[0], id: 4, company: "Fourth Pillar Co", pillar: "Pass" }],
    };
    await page.route("**/api/runs", (route) => route.fulfill({ json: runs }));
    await page.goto("/explore");
    await expect(page.locator(".pill.Pass").first()).toBeVisible();

    // Reads the values the browser actually painted — not the source tokens — so the assertion
    // survives a theme swap and can't be satisfied by a literal sitting unused in a comment.
    const ratios = await page.evaluate(() => {
      function parseColor(str) {
        const m = str.match(/rgba?\(([^)]+)\)/);
        const parts = m[1].split(",").map((s) => parseFloat(s.trim()));
        return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
      }
      // Composite the ancestor chain's backgrounds (outermost first) over white, then the
      // element's own (possibly translucent) text colour over that — the same compositing the
      // browser itself does, since getComputedStyle never pre-blends alpha for you.
      function effectiveBg(el) {
        const layers = [];
        for (let node = el; node; node = node.parentElement) {
          const c = parseColor(getComputedStyle(node).backgroundColor);
          if (c.a > 0) layers.push(c);
        }
        layers.reverse();
        return layers.reduce(
          (bg, c) => ({
            r: c.a * c.r + (1 - c.a) * bg.r,
            g: c.a * c.g + (1 - c.a) * bg.g,
            b: c.a * c.b + (1 - c.a) * bg.b,
          }),
          { r: 255, g: 255, b: 255 },
        );
      }
      function lin(c) { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }
      function relLum(c) { return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b); }
      function contrastRatio(a, b) {
        const [hi, lo] = [relLum(a), relLum(b)].sort((x, y) => y - x);
        return (hi + 0.05) / (lo + 0.05);
      }

      const out = {};
      for (const pillar of ["Connect", "Collaborate", "Empower", "Pass"]) {
        const el = document.querySelector(`.pill.${pillar}`);
        if (!el) continue;
        const bg = effectiveBg(el);
        const textColor = parseColor(getComputedStyle(el).color);
        const text = {
          r: textColor.a * textColor.r + (1 - textColor.a) * bg.r,
          g: textColor.a * textColor.g + (1 - textColor.a) * bg.g,
          b: textColor.a * textColor.b + (1 - textColor.a) * bg.b,
        };
        out[pillar] = contrastRatio(text, bg);
      }
      return out;
    });

    for (const [pillar, ratio] of Object.entries(ratios)) {
      expect(ratio, `${pillar} pill: ${ratio.toFixed(2)}:1, needs >= 4.5:1 for 11px bold text (AA)`).toBeGreaterThanOrEqual(4.5);
    }
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
