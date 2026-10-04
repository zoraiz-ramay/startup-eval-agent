import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { RecommendedTools } from "./OpportunityDetail.jsx";

const TOOLS = [
  { id: "tool:process-simulate", name: "Process Simulate", division: "DI SW", relation: "complement", rank: 1,
    reason: "Simulates and virtually commissions the robot cells NOVA programs.", check: "verified",
    url: "https://www.siemens.com/process-simulate" },
  { id: "tool:tecnomatix", name: "Tecnomatix", division: "DI SW", relation: "integration", rank: 2,
    reason: "Plant-level simulation the robot programs plug into.", check: "unchecked", url: "" },
];

describe("RecommendedTools", () => {
  it("lists the ranked tools strongest first, with relation, reason and how existence was checked", () => {
    render(<RecommendedTools pillar={{ recommended_tools: TOOLS, retrieval: { method: "hybrid" } }} />);
    const items = within(screen.getByRole("list", { name: /strongest first/ })).getAllByRole("listitem");
    expect(items.map((li) => li.querySelector("strong").textContent)).toEqual(["Process Simulate", "Tecnomatix"]);
    expect(items[0]).toHaveTextContent("complement");
    expect(items[0]).toHaveTextContent("virtually commissions");
    expect(items[0]).toHaveTextContent("Confirmed as a Siemens offering");
    expect(within(items[0]).getByRole("link", { name: "siemens.com" })).toHaveAttribute("href", "https://www.siemens.com/process-simulate");
    expect(items[1]).toHaveTextContent("Existence not checked");
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("says when the shortlist came from word matching only", () => {
    render(<RecommendedTools pillar={{ recommended_tools: TOOLS, retrieval: { method: "words", reason: "this provider has no embedding model" } }} />);
    expect(screen.getByRole("note")).toHaveTextContent(/word matching only \(this provider has no embedding model\)/);
  });

  it("renders nothing for a run with no ranked tools and semantic search", () => {
    const { container } = render(<RecommendedTools pillar={{ recommended_tools: [], retrieval: { method: "hybrid" } }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
