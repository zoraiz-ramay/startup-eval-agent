import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";

/**
 * A search starts from a name alone. Every evaluation is assessed for all departments and the
 * profile recommends the best one for Collaborate, so there is no department to choose first —
 * choosing one asked the reviewer to guess what the evaluation exists to find out.
 */
vi.mock("../api.js", () => ({
  api: {
    departments: vi.fn(async () => ({ departments: [] })),
    startJobs: vi.fn(async (body) => ({ jobs: body.names.map((n, i) => ({ id: `job-${i}`, kind: "evaluate", query: n, status: "queued" })) })),
    job: vi.fn(async () => null),
    tracxnStatus: vi.fn(async () => ({ connected: false })),
  },
  setUnauthorizedHandler: vi.fn(),
}));

import { api } from "../api.js";
import SearchHome from "./SearchHome.jsx";

const renderHome = () => render(<MemoryRouter><AppProvider><SearchHome /></AppProvider></MemoryRouter>);

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); vi.clearAllMocks(); });

describe("search needs no department", () => {
  it("starts from a typed name, with no department step and no department in the request", async () => {
    renderHome();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByText(/Assess for department/i)).toBeNull();
    fireEvent.change(screen.getByLabelText("Search a startup"), { target: { value: "Acme" } });
    fireEvent.keyDown(screen.getByLabelText("Search a startup"), { key: "Enter" });
    await waitFor(() => expect(api.startJobs).toHaveBeenCalledTimes(1));
    expect(api.startJobs.mock.calls[0][0]).toEqual(expect.objectContaining({ kind: "evaluate", names: ["Acme"] }));
    expect(api.startJobs.mock.calls[0][0]).not.toHaveProperty("department_id");
  });

  it("starts a batch as one evaluation per startup", async () => {
    renderHome();
    // The "Mass search" option lives in the search field's iX dropdown menu; find it by label.
    fireEvent.click([...document.querySelectorAll("ix-dropdown-item")]
      .find((i) => String(i.label || "").startsWith("Mass search")));
    const input = await screen.findByLabelText("Startup names or websites");
    fireEvent.change(input, { target: { value: "Acme, Beta" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(api.startJobs).toHaveBeenCalledTimes(1));
    expect(api.startJobs.mock.calls[0][0]).toMatchObject({ kind: "evaluate", names: ["Acme", "Beta"] });
    expect(await screen.findAllByText(/Startup evaluation · queued/)).toHaveLength(2);
  });
});

describe("Assess button", () => {
  it("appears once a name is typed and starts the evaluation", async () => {
    renderHome();
    expect(screen.queryByRole("button", { name: "Assess" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Search a startup"), { target: { value: "Radical Dot" } });
    fireEvent.click(screen.getByRole("button", { name: "Assess" }));
    await waitFor(() => expect(api.startJobs).toHaveBeenCalledTimes(1));
    expect(api.startJobs.mock.calls[0][0]).toMatchObject({ kind: "evaluate", names: ["Radical Dot"] });
  });
});
