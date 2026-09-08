import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ProblemSolver from "./ProblemSolver.jsx";
import { ResearchProvider } from "../research.jsx";
import { api } from "../api.js";
import { findShadowRole } from "../test/shadow.js";
vi.mock("../api.js", () => ({ api: { tracxnStatus: vi.fn(), tracxnConnect: vi.fn(), tracxnDisconnect: vi.fn(), startJobs: vi.fn(), job: vi.fn() } }));
const mount = () => render(<MemoryRouter><ResearchProvider userId="test"><ProblemSolver /></ResearchProvider></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); api.tracxnStatus.mockResolvedValue({connected: false}); });
function complete(result) {
  api.startJobs.mockImplementation(async (body) => ({jobs: [{id: "job1", kind: "solve", query: body.problem, status: "complete", result}]}));
}
describe("problem-led scouting", () => {
  it("lets the user edit an example before starting a background search", async () => {
    complete({problem: "inspection", candidates: [], sources: [], method: "llm"});
    const {container} = mount();
    await userEvent.click(await findShadowRole(container, "button", {name: "Reduce downtime"}));
    expect(api.startJobs).not.toHaveBeenCalled();
    const input = await findShadowRole(container, "textbox", {name: "Describe your problem"});
    await waitFor(() => expect(input.value).toMatch(/legacy PLC/));
    await userEvent.click(await findShadowRole(container, "button", {name: "Find solutions"}));
    expect(await screen.findByText("No strong matches yet")).toBeInTheDocument();
    expect(api.startJobs).toHaveBeenCalledOnce();
  });
  it("shows provider, rationale, and evaluation link", async () => {
    complete({problem:"inspection", candidates:[{name:"Alpha",source:"tracxn",relevance:80,description:"Visual inspection",rationale:"Detects surface defects."}], sources:[{provider:"tracxn",status:"used"}]});
    const {container} = mount();
    await userEvent.type(await findShadowRole(container,"textbox",{name:"Describe your problem"}),"inspection");
    await userEvent.click(await findShadowRole(container,"button",{name:"Find solutions"}));
    expect(await screen.findByText("Detects surface defects.")).toBeInTheDocument();
    expect(screen.getByText("Tracxn: Used")).toBeInTheDocument();
    expect(screen.getByRole("link",{name:/evaluate solution/i})).toHaveAttribute("href","/startup/new?name=Alpha");
  });
  it("keeps the brief after a queue error", async () => {
    api.startJobs.mockRejectedValue(new Error("Queue is full"));
    const {container} = mount();
    const input = await findShadowRole(container,"textbox",{name:"Describe your problem"});
    await userEvent.type(input,"inspection");
    await userEvent.click(await findShadowRole(container,"button",{name:"Find solutions"}));
    await screen.findByText(/Queue is full/);
    expect(input.value).toBe("inspection");
  });
});
