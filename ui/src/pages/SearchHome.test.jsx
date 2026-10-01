import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";

/**
 * A search cannot start without a department, and a batch applies its one department to every
 * startup in it. Both are what make a saved run mean "this startup, for this department".
 */
vi.mock("../api.js", () => ({
  api: {
    departments: vi.fn(async () => ({ departments: [
      { id: "di", label: "Digital Industries", interests: ["automation"], demo: true },
      { id: "si", label: "Smart Infrastructure", interests: ["grid"], demo: false }] })),
    startJobs: vi.fn(async (body) => ({ jobs: body.names.map((n, i) => ({ id: `job-${i}`, kind: "evaluate", query: n, status: "queued", department_id: body.department_id })) })),
    job: vi.fn(async () => null),
    tracxnStatus: vi.fn(async () => ({ connected: false })),
  },
  setUnauthorizedHandler: vi.fn(),
}));

import { api } from "../api.js";
import SearchHome from "./SearchHome.jsx";

const renderHome = () => render(<MemoryRouter><AppProvider><SearchHome /></AppProvider></MemoryRouter>);
// Up to five departments are radio cards; pick one by its visible name.
const choose = async (label) => fireEvent.click(await screen.findByRole("radio", { name: new RegExp(label) }));

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); vi.clearAllMocks(); });

describe("search requires a department", () => {
  it("refuses to start without one and says why", async () => {
    renderHome();
    fireEvent.change(screen.getByLabelText("Search a startup"), { target: { value: "Acme" } });
    fireEvent.keyDown(screen.getByLabelText("Search a startup"), { key: "Enter" });
    expect(await screen.findByText("Choose a department before starting an evaluation.")).toBeInTheDocument();
    expect(api.startJobs).not.toHaveBeenCalled();
  });

  it("applies the chosen department to every startup in a batch", async () => {
    renderHome();
    await choose("Smart Infrastructure");
    // The "Mass search" option lives in the search field's iX dropdown menu; find it by label.
    fireEvent.click([...document.querySelectorAll("ix-dropdown-item")]
      .find((i) => String(i.label || "").startsWith("Mass search")));
    const input = await screen.findByLabelText("Startup names or websites");
    fireEvent.change(input, { target: { value: "Acme, Beta" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(api.startJobs).toHaveBeenCalledTimes(1));
    const body = api.startJobs.mock.calls[0][0];
    expect(body).toMatchObject({ kind: "evaluate", names: ["Acme", "Beta"], department_id: "si" });
    expect(await screen.findAllByText(/Startup evaluation · Smart Infrastructure/)).toHaveLength(2);
  });
});

describe("department segmented control", () => {
  it("is one radio group that moves with the arrow keys", async () => {
    renderHome();
    const di = await screen.findByRole("radio", { name: "Digital Industries" });
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    fireEvent.click(di);
    expect(di).toHaveAttribute("aria-checked", "true");
    fireEvent.keyDown(di, { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "Smart Infrastructure" })).toHaveAttribute("aria-checked", "true");
    expect(JSON.parse(localStorage.getItem("se.department.v1"))).toBe("si");
  });
});

describe("Assess button", () => {
  it("appears once a name is typed and starts the evaluation", async () => {
    renderHome();
    await choose("Digital Industries");
    expect(screen.queryByRole("button", { name: "Assess" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Search a startup"), { target: { value: "Radical Dot" } });
    fireEvent.click(screen.getByRole("button", { name: "Assess" }));
    await waitFor(() => expect(api.startJobs).toHaveBeenCalledTimes(1));
    expect(api.startJobs.mock.calls[0][0]).toMatchObject({ kind: "evaluate", names: ["Radical Dot"], department_id: "di" });
  });
});
