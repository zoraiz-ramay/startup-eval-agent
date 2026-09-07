import { expect } from "@playwright/test";
import { test, stubRuns } from "./fixtures.js";

/**
 * The sign-in guard, end to end.
 *
 * Deliberately no screenshots: visual baselines are human-owned, and these assertions are
 * about behaviour rather than layout.
 */

test.describe("authentication", () => {
  test("AUTH-01: a signed-out visitor gets the sign-in screen, not the app", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/explore");

    await expect(page.getByRole("button", { name: /sign in with siemens/i })).toBeVisible();
    // The shell must not render at all — not merely be empty. Anything else means the
    // command bar mounted and started issuing requests it cannot be authorised for.
    await expect(page.getByRole("navigation", { name: /primary/i })).toHaveCount(0);
  });

  test("AUTH-02: a session that ends mid-session swaps the screen without navigating away", async ({ page }) => {
    await stubRuns(page);
    await page.goto("/explore");
    // At the 'sm' breakpoint (mobile), IxApplicationHeader collapses ix-menu's content behind
    // its own auto-generated "Expand" toggle — real, working iX responsive behaviour (see
    // docs/ix/guidance.md), not a regression. Confirmed by clicking it: the nav goes from
    // hidden to visible. Open it here so this precondition holds at every viewport width.
    // isVisible() is a one-shot, non-polling check, so it can't decide whether to click — it
    // can catch the toggle mid-hydration and skip the click; wait for the nav first instead.
    const nav = page.getByRole("navigation", { name: /primary/i });
    try {
      await expect(nav).toBeVisible({ timeout: 3000 });
    } catch {
      await page.getByRole("button", { name: "Expand" }).click();
    }
    await expect(nav).toBeVisible();

    await page.route("**/api/my/searches", (route) =>
      route.fulfill({ status: 401, json: { detail: "Not signed in.", code: "unauthenticated" } }));
    await page.reload();

    await expect(page.getByRole("button", { name: /sign in with siemens/i })).toBeVisible();
    // Staying on /explore is the point: a hard redirect to the login endpoint would throw
    // away whatever the reviewer had open, including a four-minute evaluation in flight.
    expect(new URL(page.url()).pathname).toBe("/explore");
  });

  test("AUTH-03: signing out ends access until you sign in again", async ({ page }) => {
    await page.goto("/settings");
    await page.getByRole("button", { name: /sign out/i }).click();

    await expect(page.getByRole("button", { name: /sign in with siemens/i })).toBeVisible();

    await page.goto("/explore");
    await expect(page.getByRole("button", { name: /sign in with siemens/i })).toBeVisible();
  });
});
