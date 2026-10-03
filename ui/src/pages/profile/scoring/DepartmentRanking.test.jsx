import React, { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import DepartmentRanking, { viewAs } from "./DepartmentRanking.jsx";

const entry = (id, label, collab, total) => ({
  department: { id, label },
  assessment: { total, pillars: { Collaborate: collab == null
    ? { status: "unassessed" } : { status: "assessed", total: collab, band: collab >= 7 ? "strong" : "review" } } },
  routing: { pillar: collab >= 7 ? "Collaborate" : "Empower" },
  score: { final_score: total },
});

const RUN = {
  company: "Acme", department: { id: "mobility", label: "Siemens Mobility" },
  assessment: { total: 81 }, score: { final_score: 81 },
  departments: { scope: "all", recommended: "mobility", basis: "collaborate", ranked: [
    entry("mobility", "Siemens Mobility", 8, 81), entry("di", "Digital Industries", 5, 74),
    entry("si", "Smart Infrastructure", null, 70)] },
};

function Harness({ run }) {
  const [dept, setDept] = useState(null);
  const shown = viewAs(run, dept);
  return <><DepartmentRanking res={run} selected={dept} onSelect={setDept} /><output>{shown.score.final_score}</output></>;
}

describe("DepartmentRanking", () => {
  it("leads with the department whose needs the startup answers best, then the rest in order", () => {
    render(<Harness run={RUN} />);
    expect(screen.getByText(/Best fit for Collaborate:/)).toHaveTextContent("Siemens Mobility");
    const items = within(screen.getByRole("list", { name: /best Collaborate fit first/ })).getAllByRole("button");
    expect(items.map((b) => b.textContent)).toEqual([
      "Siemens MobilityRecommendedCollaborate 8/9 · strong match · total 81",
      "Digital IndustriesCollaborate 5/9 · worth a review · total 74",
      "Smart InfrastructureCollaborate not assessed · total 70"]);
    expect(items[0]).toHaveAttribute("aria-pressed", "true");
  });

  it("shows another department's assessment when it is chosen", () => {
    render(<Harness run={RUN} />);
    expect(document.querySelector("output")).toHaveTextContent("81");
    fireEvent.click(screen.getByRole("button", { name: /Digital Industries/ }));
    expect(document.querySelector("output")).toHaveTextContent("74");
    expect(screen.getByRole("button", { name: /Digital Industries/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("recommends nothing when no department's needs could be assessed", () => {
    render(<Harness run={{ ...RUN, departments: { ...RUN.departments, recommended: null } }} />);
    expect(screen.getByText(/none is recommended/)).toBeInTheDocument();
    expect(screen.queryByText("Recommended")).toBeNull();
  });

  it("leaves a one-department run exactly as it was", () => {
    const legacy = { company: "Acme", department: { id: "di" }, score: { final_score: 60 } };
    expect(viewAs(legacy, "si")).toBe(legacy);
  });
});
