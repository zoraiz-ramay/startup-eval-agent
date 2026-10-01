import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/** The admin's list of catalog tools a web search could not find, and its empty state. */
vi.mock("../api.js", () => ({ api: { adminToolChecks: vi.fn() } }));

import { api } from "../api.js";
import UnverifiedTools from "./UnverifiedTools.jsx";

describe("UnverifiedTools", () => {
  it("lists each catalog tool the search could not find, with what it found and how often it came up", async () => {
    api.adminToolChecks.mockResolvedValue({ tools: [{ tool_id: "tool:ghost", name: "Ghost Suite", category: "Simulation",
      division: "DI", status: "not_found", note: "No Siemens product by this name; likely Simcenter.", times_recommended: 3,
      checked_at: "2026-10-01T10:00:00+00:00" }] });
    render(<UnverifiedTools />);
    const table = await screen.findByRole("table", { name: "Unverified Siemens tools" });
    const row = within(table).getByText("Ghost Suite").closest("tr");
    expect(row).toHaveTextContent("likely Simcenter");
    expect(row).toHaveTextContent("3×");
    expect(api.adminToolChecks).toHaveBeenCalledWith("not_found");
  });

  it("says when every recommended tool was found", async () => {
    api.adminToolChecks.mockResolvedValue({ tools: [] });
    render(<UnverifiedTools />);
    expect(await screen.findByText("Every recommended tool checked so far was found.")).toBeInTheDocument();
  });
});
