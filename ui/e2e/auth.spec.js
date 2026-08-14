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
    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();

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
