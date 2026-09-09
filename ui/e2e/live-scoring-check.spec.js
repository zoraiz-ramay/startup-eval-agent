import { test, expect } from "@playwright/test";

test("live API saves views and persists a cited decision", async ({page}) => {
  test.skip(process.env.LIVE_SCORING_CHECK !== "1", "Opt-in: uses the configured model and an existing run.");
  const runId=Number(process.env.LIVE_SCORING_RUN_ID || 10);
  await page.goto("/api/auth/login?next=/explore");
  await page.goto("/explore");
  const name=`View check ${Date.now()}`;
  await page.getByRole("button", {name:/customise columns/i}).click();
  await page.getByLabel("Save these columns and filters").fill(name);
  const saved=page.waitForResponse(r=>r.url().endsWith("/api/my/views") && r.request().method()==="POST");
  await page.getByRole("button", {name:"Save view",exact:true}).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByText(`View: ${name}`,{exact:false})).toBeVisible();
  await page.reload();
  await expect(page.getByText(`View: ${name}`,{exact:false})).toBeVisible();
  await page.evaluate(async name => {
    const csrf=document.cookie.split("; ").find(c=>c.startsWith("sea_csrf="))?.split("=")[1];
    await fetch(`/api/my/views/${encodeURIComponent(name)}`, {method:"DELETE",headers:{"X-CSRF-Token":decodeURIComponent(csrf||"")}});
  },name);
  await page.goto(`/startup/${runId}?tab=Scoring+%26+Fit`);
  const button=page.getByRole("button",{name:"Generate recommendation"});
  await expect(button.or(page.getByRole("heading",{name:"How to proceed"}))).toBeVisible();
  if(await button.count()) await button.click();
  await expect(page.getByRole("heading",{name:"How to proceed"})).toBeVisible({timeout:180000});
  await page.reload();
  await expect(page.getByRole("heading",{name:"How to proceed"})).toBeVisible();
  const run=await page.evaluate(id=>fetch(`/api/runs/${id}`).then(r=>r.json()),runId);
  expect(run.routing.status).toBe("assessed");
  expect(run.routing.evidence.length).toBeGreaterThan(0);
  console.log(JSON.stringify({pillar:run.routing.pillar, steps:run.routing.next_steps.length, citations:run.routing.evidence.length}));
});
