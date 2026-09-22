import { test, expect, stubEvaluation } from "./fixtures.js";

test("profile navigation follows scrolling in both directions", async ({page}) => {
  await stubEvaluation(page);
  await page.goto("/startup/1");
  await expect(page.getByRole("link",{name:"Key metrics",exact:true})).toHaveAttribute("aria-current","location");
  // Give the compact fixture the height of a fully researched profile, so every heading can
  // reach the reading line even on the largest viewport.
  await page.locator(".profile-section").evaluateAll(nodes=>nodes.forEach(el=>el.style.minHeight="650px"));
  // Scroll content without clicking a navigation item or pinning its state.
  for (const [id,label] of [["profile-team-ecosystem","Team & ecosystem"],["profile-executive-summary","Executive summary"],["profile-key-metrics","Key metrics"]]) {
    await page.locator(`#${id}`).evaluate(el=>el.scrollIntoView({block:"start",behavior:"instant"}));
    await expect(page.getByRole("link",{name:label,exact:true})).toHaveAttribute("aria-current","location");
    await expect(page.locator('.section-rail a[aria-current="location"]')).toHaveCount(1);
  }
});
