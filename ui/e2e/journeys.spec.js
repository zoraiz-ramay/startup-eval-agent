import {
  expect, RUN_FIXTURE, RUNS_FIXTURE, stabilise, stubAdminOverview, stubChallenges, stubEvaluation,
  stubIdentity, stubRoutableRun, stubRuns, stubStatus, test,
} from "./fixtures.js";

/**
 * The user journeys from contract/feature-inventory.md. Each test names its contract ID so a
 * failure says which behaviour broke, not just which selector moved.
 */

test.describe("shell", () => {
  test("SHELL-01: icon rail exposes the primary destinations", async ({ page }) => {
    await page.goto("/");
    // At the 'sm' breakpoint (mobile), IxApplicationHeader collapses ix-menu's content behind
    // its own auto-generated "Expand" toggle (real iX responsive behaviour, see AUTH-02) — open
    // it if the nav doesn't show up on its own within a beat, so this check holds at every
    // viewport width. isVisible() is a one-shot, non-polling check, so it can't be used to
    // decide whether to click — it can catch the toggle mid-hydration and skip the click.
    const nav = page.getByRole("navigation", { name: /primary/i });
    try {
      await expect(nav).toBeVisible({ timeout: 3000 });
    } catch {
      await page.getByRole("button", { name: "Expand" }).click();
    }
    await expect(nav).toBeVisible();
    // Not scoped through the nav locator: IxMenu projects its IxMenuItem children into a
    // shadow-internal menubar via a default <slot>, and Playwright's chained getByRole() does not
    // flatten across that slot boundary (the same testability limit as PROF-04's tablist scoping
    // — not a real containment gap, since these names are unique page-wide).
    // exact: true — "Views" as a substring regex also matches the secondary "Saved views"
    // menuitem, a genuine ambiguity once IxMenuCategory's own items share the flattened
    // menubar accessibility tree with the primary rail's.
    //
    // Every routed item now carries an href (App.jsx's Rail), so the underlying tag is a real
    // <a>, restoring middle-click/ctrl-click/"copy link address"/crawlability. That does NOT
    // surface as role="link", though: ix-menu-item's getEffectiveRole() deliberately forces
    // role="menuitem" for anything hosted inside a menu context, href or not — the WAI-ARIA
    // menubar pattern keeps items as menuitems for a screen reader regardless of the backing
    // element (verified against the compiled source and empirically: an item with href="/"
    // resolves to <a role="menuitem" href="/">, and getByRole("link", ...) finds nothing). So
    // the role assertion stays "menuitem" — asserting "link" here would be asserting something
    // that is false, not restoring a lost check — and the real, restored semantics are verified
    // at the DOM level instead, via the href attribute Playwright's role query can't see.
    for (const label of ["Home", "Explore", "Views", "Tracking", "Settings"]) {
      await expect(page.getByRole("menuitem", { name: label, exact: true })).toBeVisible();
    }
    const routedHrefs = { Home: "/", Explore: "/explore", Views: "/saved", Tracking: "/alerts", Settings: "/settings" };
    for (const [label, href] of Object.entries(routedHrefs)) {
      await expect(page.locator(`ix-menu-item:has-text("${label}") a`).first()).toHaveAttribute("href", href);
    }
    // Ask AI toggles the assistant dock rather than navigating anywhere, so it stays a <button>
    // with no href — there is nothing for it to link to.
    await expect(page.getByRole("menuitem", { name: /ask ai/i })).toBeVisible();
    await expect(page.locator('ix-menu-item:has-text("Ask AI") a')).toHaveCount(0);
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
  test("PROF-04: the section rail reaches every part of the run on one page", async ({ page }) => {
    await stubEvaluation(page);
    await page.goto("/startup/1");

    // The tab bar is gone — the report is one scrolling page. What this row protects is
    // unchanged: every part of a run is reachable, and getting to one does not cost you the
    // others. The evidence table is the furthest thing down the page, so it is the test case.
    const rail = page.getByRole("navigation", { name: /profile sections/i });
    await expect(rail).toBeVisible();
    await rail.getByRole("button", { name: "Evidence" }).click();
    await expect(page.locator("#sub-facts")).toBeInViewport();
    // Still the same run, and the header never went anywhere.
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

  test("PROF-14: a what-if weighting moves only the what-if figure, never the stored score", async ({ page }) => {
    await stubEvaluation(page);
    await page.goto("/startup/1");
    // No tab to open: the scoring panel is already on the page, further down it.
    await page.getByRole("button", { name: /what-if weights/i }).click();

    // The profile header's score — the canonical one, rendered straight from the stored run.
    const headline = page.locator(".ph-meta span", { hasText: /^Score / }).first();
    const storedBefore = await headline.textContent();
    const whatIf = page.getByRole("status");
    const before = await whatIf.textContent();

    await page.getByLabel(/^siemens fit$/i).fill("60");
    await expect(whatIf).not.toHaveText(before);
    // Deliberately asserts change and non-change, never equality between the two numbers:
    // RUN_FIXTURE's recorded final_score does not match what its own dimensions imply.
    await expect(headline).toHaveText(storedBefore);

    // The whole point is that this never becomes the shared answer — it survives a reload as a
    // local preference while the stored score is re-fetched from the API unchanged.
    await page.reload();
    await expect(page.locator(".ph-meta span", { hasText: /^Score / }).first()).toHaveText(storedBefore);
  });

  test("PROF-15: a weighting can demote the pillar without touching the stored one", async ({ page }) => {
    await stubRoutableRun(page);
    await page.goto("/startup/2");
    // No tab to open: the scoring panel is already on the page, further down it.
    await page.getByRole("button", { name: /what-if weights/i }).click();

    // MIG-01 moved the header pillar off a `.pill`-classed span onto `IxPill` — the label is
    // still slotted (light DOM) content, so a plain locator + toHaveText still works.
    // MIG-18 moved the pillar pill off `.ph-title` (retired along with the old logo-chip header
    // block) onto IxContentHeader's `header` slot, `.ph-header-slot` (Profile.jsx).
    const headerPill = page.locator(".ph-header-slot ix-pill").first();
    await expect(page.getByText(/still/i).first()).toBeVisible();

    // One edit. Ecosystem to 52% of the weighting drops Collaborate's card 67.3 -> 46.4, under
    // its own 55 gate, so only the ungated Empower survives. The control is a share slider now,
    // so the value is the share directly rather than a raw point count normalised afterwards —
    // 52% is the same weighting the old "ecosystem = 100 points" produced (100/192).
    await page.getByLabel(/^ecosystem$/i).fill("52");

    await expect(page.getByText(/not the evaluation result/i).first()).toBeVisible();
    await expect(page.getByText(/46\.4/).first()).toBeVisible();
    await expect(page.getByText(/needs ≥ 55/).first()).toBeVisible();

    // The decision itself is untouched — that is the whole contract of a what-if.
    await expect(headerPill).toHaveText("Collaborate");
    await page.reload();
    await expect(page.locator(".ph-header-slot ix-pill").first()).toHaveText("Collaborate");
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
    // /api/my/searches, not /api/runs: Explore's data source moved when lists became
    // per-reviewer, so a 500 on /api/runs left the page loading happily and this asserted
    // nothing. The endpoint here has to be the one the page under test actually calls.
    await page.route("**/api/my/searches",
      (route) => route.fulfill({ status: 500, json: { detail: "boom" } }));
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
    await page.route("**/api/my/searches", (route) => route.fulfill({ json: runs }));
    await page.goto("/explore");
    // MIG-01 moved Explore's pillar chip off `.pill.Pass` onto `IxPill`; the coloured surface
    // is its shadow-DOM `.container` div, not the host, so locate the host by its slotted text
    // and pierce the shadow root for the painted element.
    await expect(page.locator("ix-pill", { hasText: "Pass" }).first()).toBeVisible();

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
      // browser itself does, since getComputedStyle never pre-blends alpha for you. Crosses the
      // shadow boundary via getRootNode().host, since IxPill's colour lives on a shadow-DOM node.
      function effectiveBg(el) {
        const layers = [];
        for (let node = el; node; ) {
          const c = parseColor(getComputedStyle(node).backgroundColor);
          if (c.a > 0) layers.push(c);
          node = node.parentElement || node.getRootNode().host || null;
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
        const host = [...document.querySelectorAll("ix-pill")].find((n) => n.textContent.trim() === pillar);
        if (!host || !host.shadowRoot) continue;
        const container = host.shadowRoot.querySelector(".container");
        if (!container) continue;
        const bg = effectiveBg(container);
        const textColor = parseColor(getComputedStyle(container).color);
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
 * Visual regression — the enforceable form of "the shell layout is preserved".
 * Baselines are human-owned; agents must not regenerate them.
 */
test.describe("layout", () => {
  test("X-05/X-06: app shell holds its shape", async ({ page }, testInfo) => {
    await stubIdentity(page);
    await stubRuns(page);
    await page.goto("/explore");
    await stabilise(page);
    await expect(page).toHaveScreenshot(`explore-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: profile layout holds its shape", async ({ page }, testInfo) => {
    await stubIdentity(page);
    await stubEvaluation(page);
    await page.goto("/startup/1");
    await stabilise(page);
    await expect(page.getByRole("tablist")).toBeVisible();
    await expect(page).toHaveScreenshot(`profile-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: no horizontal body scroll at any width", async ({ page }) => {
    await stubRuns(page);
    await stubChallenges(page);
    // Two distinct failure modes, and the old assertion caught only the first:
    //   (a) the document itself scrolls sideways — documentElement grows past the viewport;
    //   (b) content is wider than the viewport but an overflow:hidden ancestor (ix-content)
    //       clips it. The document never grows, so (a) stays false while real content is cut
    //       off the right edge and unreachable — which is exactly what Home's panels did at
    //       390px. Checking only (a), and only on /explore, is why that shipped green.
    // (b) is asserted on the main content region's own scrollWidth rather than by scanning for
    // wide descendants: Explore's data grid is *legitimately* wider than the viewport and scrolls
    // inside its own overflow:auto container (the intended "scroll inside its own container"
    // behaviour), so a descendant scan would false-positive on it. A scrollable child does not
    // inflate its parent's scrollWidth, so main.content.scrollWidth grows only when non-scrollable
    // content (a panel, a card list) overflows the region — the actual defect.
    for (const route of ["/", "/explore"]) {
      await page.goto(route);
      await stabilise(page);
      const report = await page.evaluate(() => {
        const de = document.documentElement;
        const region = document.querySelector("main.content");
        return {
          docOverflow: de.scrollWidth > de.clientWidth + 1,
          regionOverflow: region ? region.scrollWidth > region.clientWidth + 1 : false,
        };
      });
      expect(report.docOverflow, `${route}: the page scrolls horizontally — wide content must scroll inside its own container, not the document`).toBe(false);
      expect(report.regionOverflow, `${route}: content is wider than the viewport and clipped by an overflow:hidden ancestor — it must fit or scroll inside its own container`).toBe(false);
    }
  });

  test("X-05: the Scoring & Fit section holds its shape", async ({ page }, testInfo) => {
    await stubIdentity(page);
    await stubEvaluation(page);
    await page.goto("/startup/1");
    await stabilise(page);
    await page.getByRole("navigation", { name: /profile sections/i })
      .getByRole("button", { name: "Scoring & Fit" }).click();
    await expect(page.locator("#sub-score")).toBeInViewport();
    await expect(page).toHaveScreenshot(`scoring-fit-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: the Evidence section holds its shape", async ({ page }, testInfo) => {
    await stubIdentity(page);
    await stubEvaluation(page);
    await page.goto("/startup/1");
    await stabilise(page);
    await page.getByRole("navigation", { name: /profile sections/i })
      .getByRole("button", { name: "Evidence" }).click();
    await expect(page.locator("#sub-facts")).toBeInViewport();
    await expect(page).toHaveScreenshot(`evidence-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: Home layout holds its shape", async ({ page }, testInfo) => {
    await stubIdentity(page);
    await stubRuns(page);
    await stubChallenges(page);
    // Tracked companies is watchlist ∩ loaded runs — names must match RUNS_FIXTURE exactly.
    // Seeded via addInitScript so it's present before Home's usePersistent initializer reads it.
    await page.addInitScript(() => {
      localStorage.setItem("se.watchlist.v2", JSON.stringify(["Phena", "Meili Robots", "Hypertrain"]));
    });
    // Overrides the shared empty stub from fixtures.js (registered earlier, so this later
    // registration wins) for this spec only — other specs still see an empty saved-views list.
    await page.route("**/api/my/views", (route) =>
      route.fulfill({
        json: {
          views: [
            { name: "Connect shortlist", columns: ["final_score", "siemens_fit", "hq", "stage"], filters: {} },
            { name: "High fit, funded", columns: ["final_score", "funding", "founded_year"], filters: {} },
            { name: "Evidence review queue", columns: ["evidence", "trend", "pillar"], filters: {} },
          ],
        },
      }),
    );
    await page.goto("/");
    await stabilise(page);
    await expect(page).toHaveScreenshot(`home-${testInfo.project.name}.png`, { fullPage: false });
  });

  // Settings and Admin are desktop-only baselines — both are narrow-panel or admin-gated
  // back-office surfaces with no responsive risk beyond what Explore/Profile/Evidence already
  // exercise at all four widths (see contract/ui-backlog.md MIG-21).
  test("X-05: Settings layout holds its shape (desktop only)", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Settings is a narrow single-column panel — desktop baseline only.");
    await stubIdentity(page);
    await stubStatus(page);
    await page.goto("/settings");
    await stabilise(page);
    await expect(page).toHaveScreenshot(`settings-${testInfo.project.name}.png`, { fullPage: false });
  });

  test("X-05: Admin layout holds its shape (desktop only)", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Admin is an internal, admin-gated back-office view — desktop baseline only.");
    await stubIdentity(page, { admin: true });
    await stubAdminOverview(page);
    await page.goto("/admin");
    await stabilise(page);
    await expect(page.getByRole("heading", { name: "Admin", exact: true })).toBeVisible();
    await expect(page).toHaveScreenshot(`admin-${testInfo.project.name}.png`, { fullPage: false });
  });
});
