import { defineConfig, devices } from "@playwright/test";

/**
 * E2E journeys + visual regression.
 *
 * The visual baselines are the enforceable form of "the Tracxn layout still works". Everything
 * else in the gate checks behaviour; this is the only layer that can tell you the icon rail moved,
 * the data canvas lost its density, or a panel now overflows at 390px. The previous agent system
 * had no equivalent, which is why its UI reviewer could only offer opinions about source code.
 *
 * Baselines live in ui/e2e/__screenshots__ and are treated as human-owned: agents must never run
 * --update-snapshots. See contract/feature-inventory.md.
 */
const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:5173";

export default defineConfig({
  testDir: "./e2e",
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFilePath}/{arg}{ext}",
  // Evaluations legitimately take a minute; a stingy timeout would make the suite flaky in a way
  // that trains people to rerun it rather than read it.
  timeout: 90_000,
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      // Font rasterisation differs slightly across machines. Too tight and the gate cries wolf;
      // too loose and a real layout shift slips through. This catches geometry, not sub-pixels.
      maxDiffPixelRatio: 0.02,
      animations: "disabled",
      caret: "hide",
    },
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  // The four widths the layout must hold at (contract X-05).
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1920, height: 1080 } } },
    { name: "laptop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 768 } } },
    { name: "mobile", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } } },
  ],

  // Reuse a dev server if one is already up, otherwise start one. The backend is NOT started
  // here: it owns real data and a real API key, so the suite refuses to run rather than
  // silently testing against a server it spun up blind (see e2e/fixtures.js).
  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
