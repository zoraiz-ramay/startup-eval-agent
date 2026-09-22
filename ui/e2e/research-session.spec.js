import { test, expect } from "@playwright/test";
import { RUN_FIXTURE } from "./fixtures.js";

test("a batch continues across pages and restores after reload", async ({ page }, testInfo) => {
  const jobs = new Map(); let complete = false; let submissions = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname; let body = {};
    if (path === "/api/auth/me") body = {authenticated:true,mode:"entra",user:{oid:"batch-user",name:"Reviewer",initials:"R",email:"r@example.com"}};
    else if (path === "/api/integrations/tracxn") body={connected:true,configured:true};
    else if (path === "/api/my/searches") body={runs:[]};
    else if (path === "/api/my/views") body={views:[]};
    else if (path === "/api/departments") body={departments:[{id:"di",label:"Digital Industries",interests:["automation"]}]};
    else if (path.includes("/assessment/")) body={score:{status:"unavailable"},department_fit:{status:"unavailable",message:"Unavailable"}};
    else if (path === "/api/jobs") {
      const request=route.request().postDataJSON(); submissions++;
      expect(request.names).toHaveLength(10);
      body={jobs:request.names.map((query,i)=>{const j={id:`batch-${i}`,query,kind:"evaluate",status:"queued"};jobs.set(j.id,j);return j;})};
    } else if (path.startsWith("/api/jobs/")) {
      const j=jobs.get(path.split("/").pop());
      body=complete ? {...j,status:"complete",result:{...RUN_FIXTURE,company:j.query,run_id:12}} : j;
    } else if (path.startsWith("/api/runs/")) body={...RUN_FIXTURE,company:"Startup 1",run_id:12};
    await route.fulfill({json:body});
  });
  await page.goto("/");
  await expect(page.getByText("Tracxn connected",{exact:true})).toBeVisible();
  await page.screenshot({path:testInfo.outputPath("startup-home.png"),fullPage:true});
  await page.getByRole("button",{name:"Search options"}).click();
  await page.getByText("Mass search · up to 10 startups", {exact:true}).click();
  await page.getByRole("textbox",{name:"Startup names or websites"}).fill(Array.from({length:11},(_,i)=>`Startup ${i+1}`).join(", "));
  await expect(page.getByRole("button",{name:"Evaluate 11 startups"})).toBeDisabled();
  await page.getByRole("textbox",{name:"Startup names or websites"}).fill(Array.from({length:10},(_,i)=>`Startup ${i+1}`).join(", "));
  await page.screenshot({path:testInfo.outputPath("mass-search.png"),fullPage:true});
  await page.getByRole("button",{name:"Evaluate 10 startups"}).click();
  await expect(page.getByRole("link",{name:"Open research"})).toHaveCount(10);
  await page.goto("/workspace"); complete=true; await page.goto("/");
  await page.getByText("Your research session (10)",{exact:true}).click();
  await expect(page.getByText("Startup evaluation · complete")).toHaveCount(10);
  expect(submissions).toBe(1);
  await page.getByRole("link",{name:"Open research"}).first().click();
  await expect(page.getByRole("heading",{name:/Startup 1/})).toBeVisible();
  await page.getByRole("button",{name:"Scoring & Fit",exact:true}).click();
  await expect(page.getByRole("tab",{name:/Empower/})).toBeVisible();
  await page.getByRole("tab",{name:/Collaborate/}).click();
  await expect(page.getByRole("tabpanel",{name:/Collaborate/})).toBeVisible();
  await expect(page.getByText(/What-if weights/)).toHaveCount(0);
  await page.getByRole("tabpanel",{name:/Collaborate/}).screenshot({path:testInfo.outputPath("collaborate-tab.png")});
});
