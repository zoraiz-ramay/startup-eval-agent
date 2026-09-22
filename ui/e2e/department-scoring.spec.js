import { test, expect } from "@playwright/test";
import { RUN_FIXTURE } from "./fixtures.js";

const departments = [
  {id:"di",label:"Digital Industries",interests:["automation", "manufacturing"],demo:true},
  {id:"si",label:"Smart Industries",interests:["energy", "buildings"],demo:true},
  {id:"mobility",label:"Siemens Mobility",interests:["rail", "fleet"],demo:true},
];
const dimensions = Object.fromEntries(["traction","siemens_fit","product","market","founder","ecosystem"].map((k)=>[k,67]));
const score = {version:"llm-judgment-v1",status:"assessed",dimensions,final_score:62,
  judgments:Object.fromEntries(Object.keys(dimensions).map((k)=>[k,{rationale:`Judgment for ${k}: promising pilots, limited independent evidence.`,evidence:[]}])),
  overall:{rationale:"Promising industrial startup; validate the pilot outcomes."}};

test("department needs drive fit while partnership routes stay under development", async ({page}, testInfo) => {
  const requested=[];
  let views=[]; let failSave=true;
  let run={...RUN_FIXTURE,run_id:12};
  await page.route("**/api/**", async (route) => {
    const path=new URL(route.request().url()).pathname; let body={};
    if(path==="/api/auth/me") body={authenticated:true,user:{oid:"department-test",name:"Reviewer"}};
    else if(path==="/api/departments") body={departments};
    else if(path.includes("/assessment/")) {
      const department=departments.find((d)=>path.endsWith(d.id)); requested.push(department.id);
      body={score,department_fit:{status:"assessed",department,score:department.id === "di" ? 78 : 38,summary:`Opportunity in ${department.interests[0]}; customer outcomes need validation.`,criteria:[
        {id:"strategic",label:"Relevant Siemens use case",rationale:`Potential ${department.interests[0]} use case.`,evidence:[]},
        {id:"complement",label:"Relevant Siemens portfolio",rationale:"The identified portfolio matches need business-owner validation.",evidence:[]},
        {id:"impact",label:"Demonstrated customer value",rationale:"No measured customer outcome is evidenced.",evidence:[]},
      ]}};
      run={...run,score,department_assessments:{...run.department_assessments,[department.id]:body.department_fit}};
    } else if(path.endsWith("/decision")) {
      run={...run,routing:{version:"llm-decision-v2",status:"assessed",pillar:"Pass",confidence:0.72,reasons:["The evidenced offering does not address the identified Siemens needs."],next_steps:["Close the review without pursuing a pilot.","Reconsider if a relevant industrial use case is evidenced."],evidence:[]}}; body={routing:run.routing};
    } else if(path.startsWith("/api/runs/")) body=run;
    else if(path==="/api/my/searches") body={runs:[{id:12,company:run.company,final_score:run.score.final_score,siemens_fit:run.score.dimensions?.siemens_fit,department_assessments:run.department_assessments,summary:run.summary}]};
    else if(path==="/api/my/views") {
      if(route.request().method()==="POST") {
        if(failSave) {failSave=false; return route.fulfill({status:503,json:{detail:"Please retry saving."}});}
        body=route.request().postDataJSON(); views=[body];
      } else body={views};
    }
    await route.fulfill({json:body});
  });
  await page.goto("/startup/12?tab=Scoring+%26+Fit");
  await expect(page.getByRole("button",{name:"Assess department fit"})).toBeVisible();
  expect(requested).toEqual([]);
  await page.getByRole("button",{name:"Generate recommendation"}).click();
  await expect(page.getByRole("heading",{name:"How to proceed"})).toBeVisible();
  await expect(page.locator("#scoring-decision .pill")).toHaveText("Pass");
  await expect(page.getByText("Close the review without pursuing a pilot.")).toBeVisible();
  await page.getByRole("button",{name:"Assess department fit"}).click();
  await expect(page.getByRole("heading",{name:"Why this startup fits Digital Industries"})).toBeVisible();
  await expect(page.getByText("Potential automation use case.")).toBeVisible();
  await page.locator("ix-select").click();
  await page.getByRole("option",{name:"Siemens Mobility",exact:true}).click();
  expect(requested).toEqual(["di"]);
  await page.getByRole("button",{name:"Assess department fit"}).click();
  await expect(page.getByRole("heading",{name:"Why this startup fits Siemens Mobility"})).toBeVisible();
  await expect(page.getByText("Potential rail use case.")).toBeVisible();
  expect(requested).toContain("mobility");
  await page.locator("#scoring-department").screenshot({path:testInfo.outputPath("department-fit.png")});
  for(const label of ["Empower","Connect","Collaborate"]) {
    await page.getByRole("tab",{name:label,exact:true}).click();
    await expect(page.locator(`#pillar-panel-${label}`)).toBeVisible();
    await expect(page.locator(`#pillar-panel-${label}`)).toHaveText("Under development");
  }
  for(const removed of ["Readiness to deliver","Integration feasibility","Challenge-library match","Flags & gaps","Override routing"]) {
    await expect(page.getByText(removed,{exact:true})).toHaveCount(0);
  }
  await expect(page.getByText("These are the same Overall score and Siemens fit values shown in Database. Department fit is saved separately for each team.")).toBeVisible();
  await expect(page.getByRole("heading",{name:"Siemens portfolio fit"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Siemens Financial Services"})).toBeVisible();
  await page.goto("/explore?department=mobility");
  const row=page.getByRole("row").filter({hasText:run.company}).last();
  await expect(row).toContainText("62");
  await expect(row).toContainText("67");
  await expect(row.getByRole("link",{name:"38",exact:true})).toBeVisible();
  for (const label of ["DI", "SI", "SMO"]) await expect(page.getByRole("columnheader", {name:label, exact:true})).toBeVisible();
  await expect(row.getByRole("link",{name:"78",exact:true})).toBeVisible();
  await page.getByRole("button", {name:/customise columns/i}).click();
  await page.getByLabel("Save these columns and filters").fill("Department comparison");
  await page.getByRole("button", {name:"Save view",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("Please retry saving.");
  await expect(page.getByLabel("Save these columns and filters")).toHaveValue("Department comparison");
  await page.getByRole("button", {name:"Save view",exact:true}).click();
  await expect(page.getByText("View: Department comparison",{exact:false})).toBeVisible();
  await page.reload();
  await expect(page.getByText("View: Department comparison",{exact:false})).toBeVisible();
  expect(views[0].columns).toEqual(expect.arrayContaining(["di_fit","si_fit","smo_fit"]));
  await page.goto("/startup/12?tab=Scoring+%26+Fit&department=di");
  await expect(page.getByRole("heading",{name:"Why this startup fits Digital Industries"})).toBeVisible();
  expect(requested).toEqual(["di","mobility"]);
  await expect(page.getByRole("menuitem",{name:"Department interests",exact:true,includeHidden:true})).toHaveCount(0);
  await expect(page.getByRole("menuitem",{name:"Database",exact:true,includeHidden:true})).toHaveCount(1);
});
