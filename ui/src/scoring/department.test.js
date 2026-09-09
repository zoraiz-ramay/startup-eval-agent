import { expect, it } from "vitest";
import { departmentScore } from "./department.js";
it("uses the selected department's stored score and rejects outdated interests", () => {
  const di={id:"di",label:"Digital Industries",interests:["automation"]};
  const si={id:"si",label:"Smart Industries",interests:["energy"]};
  const run={department_assessments:{di:{status:"assessed",department:di,score:78},si:{status:"assessed",department:si,score:32}}};
  expect(departmentScore(run,di)).toBe(78);
  expect(departmentScore(run,si)).toBe(32);
  expect(departmentScore(run,{...di,interests:["robotics"]})).toBeNull();
  expect(departmentScore({},di)).toBeNull();
});
