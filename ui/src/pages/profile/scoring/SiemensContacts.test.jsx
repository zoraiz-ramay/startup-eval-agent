import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/**
 * "Relevant Siemens Contact" under Empower → Tool fit. What a reviewer relies on: the department is
 * shown as the catalogue gives it, a contact is a name · department · email they can act on, the
 * ranking is labelled an inference, and a missing directory key reads "not configured" — never an
 * empty list that would look like nobody works on the tool.
 */
vi.mock("../../../api.js", () => ({ api: { runLookup: vi.fn() } }));

import { api } from "../../../api.js";
import SiemensContacts from "./SiemensContacts.jsx";

describe("SiemensContacts", () => {
  it("lists each tool's contacts under its department, with the inference note", async () => {
    api.runLookup.mockResolvedValueOnce({ status: "ok", note: "Ranked by the app … not tool ownership.", tools: [
      { tool: "Teamcenter", department: "DI SW PLM", department_query: "DI SW PLM", translated: false, note: "",
        contacts: [{ name: "Ada Lovelace", department: "DI SW PLM PD", email: "ada@siemens.test" },
          { name: "Grace Hopper", department: null, email: null }] },
      { tool: "NX", department: "Digital Industries Software", department_query: "DI SW", translated: true,
        note: "Nobody is listed under DI SW.", contacts: [] }] });
    render(<SiemensContacts runId={7} />);
    expect(await screen.findByRole("heading", { name: "Relevant Siemens Contact" })).toBeInTheDocument();
    expect(api.runLookup).toHaveBeenCalledWith(7, "contacts", false);
    expect(screen.getByText(/not tool ownership/)).toBeInTheDocument();
    const ada = screen.getByText("Ada Lovelace").closest("li");
    expect(within(ada).getByRole("link", { name: "ada@siemens.test" })).toHaveAttribute("href", "mailto:ada@siemens.test");
    expect(screen.getByText("Grace Hopper").closest("li")).toHaveTextContent("Department not available");
    expect(screen.getByText("Digital Industries Software")).toBeInTheDocument();      // as supplied
    expect(screen.getByText(/Searched as DI SW/)).toBeInTheDocument();
    expect(screen.getByText("Nobody is listed under DI SW.")).toBeInTheDocument();
  });

  it("says the directory is not configured rather than showing an empty list", async () => {
    api.runLookup.mockResolvedValueOnce({ status: "not_configured", tools: [],
      note: "The Siemens Directory is not configured (SIEMENS_DIRECTORY_API_KEY)." });
    render(<SiemensContacts runId={8} />);
    expect(await screen.findByText(/not configured/)).toBeInTheDocument();
    expect(screen.queryByText("No contact to show.")).toBeNull();
  });
});
