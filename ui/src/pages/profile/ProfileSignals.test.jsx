import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Reference customers show only accounts the research ties to the startup — never the
 * application form's free text split on commas — and Recent signals show dated, sourced momentum
 * in four categories, each saying which way it points in words as well as colour.
 */
vi.mock("../../api.js", () => ({ api: { runLookup: vi.fn() } }));

import { api } from "../../api.js";
import ReferenceCustomers from "./ReferenceCustomers.jsx";
import MarketSignals from "./MarketSignals.jsx";

beforeEach(() => vi.clearAllMocks());

describe("ReferenceCustomers", () => {
  it("shows the customers the rubric counted, with their sources, and never the form's free text", () => {
    const res = { company: "Radical Dot",
      profile: { customers: "Industries addressed:\nChemical producers\nFor scale-up" },
      deep_profile: { reference_customers: [], customer_segment: "chemical producers", customer_segment_source: "https://seg.test" },
      traction: { divisions: [{ id: "customers", items: [
        { name: "Covestro", counted: true, size: "large_enterprise", source_url: "https://cov.test/case" },
        { name: "Acme Capital", counted: false, reason: "listed as an investor" }] }] } };
    render(<ReferenceCustomers res={res} />);
    const list = screen.getByRole("list", { name: "Named customers" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(list).toHaveTextContent("Covestro");
    expect(list).toHaveTextContent("Big-name customer");
    expect(within(list).getByRole("link", { name: "cov.test" })).toHaveAttribute("href", "https://cov.test/case");
    expect(screen.queryByText(/Acme Capital|For scale-up|Industries addressed/)).toBeNull();
    expect(screen.getByText(/chemical producers/)).toBeInTheDocument();
  });

  it("says no named customer was found rather than filling the space", () => {
    render(<ReferenceCustomers res={{ company: "X", profile: { customers: "In parallel, For scale-up" }, deep_profile: {} }} />);
    expect(screen.getByText("No named customer was found in the research.")).toBeInTheDocument();
  });
});

describe("MarketSignals", () => {
  const signal = (category, direction, what, extra = {}) => ({ category, direction, what, date: "March 2026", who: "",
    figure: "", sources: [{ title: "tech.eu", url: "https://tech.eu/a" }], ...extra });

  it("groups dated, sourced signals into the four categories, with a direction in words and a tally", async () => {
    api.runLookup.mockResolvedValue({ provider: "web", note: "", sources: [], market: "AI sales assistants for field teams", signals: [
      signal("funding", "up", "raised €2.8 million", { who: "Bliro", figure: "€2.8 million", relevance: "core" }),
      signal("competition", "down", "Plastic Energy entered administration", { relevance: "core" }),
      signal("policy", "new", "the EU AI Act entered into force", { date: "August 2024", relevance: "adjacent" })] });
    render(<MarketSignals res={{ run_id: 701, trend: { niche: "AI sales assistants" } }} />);
    const funding = (await screen.findByRole("heading", { name: "VC funding & investor momentum" })).closest("section");
    expect(within(funding).getByText("Bliro")).toBeInTheDocument();
    expect(within(funding).getByLabelText("Growth")).toBeInTheDocument();
    expect(within(funding).getByText("1 growth")).toBeInTheDocument();
    expect(within(funding).getByRole("link", { name: "tech.eu" })).toBeInTheDocument();
    const competition = screen.getByRole("heading", { name: "Competitive momentum" }).closest("section");
    expect(within(competition).getByLabelText("Decline")).toBeInTheDocument();
    const adoption = screen.getByRole("heading", { name: "Corporate & strategic adoption" }).closest("section");
    // A quiet domain says so, rather than being padded out.
    expect(within(adoption).getByText("Nothing specific to this market in the last 24 months.")).toBeInTheDocument();
    expect(screen.getByText("AI sales assistants for field teams")).toBeInTheDocument();       // how the market was understood
    const policy = screen.getByRole("heading", { name: "Government & regulatory momentum" }).closest("section");
    expect(within(policy).getByText("Adjacent")).toBeInTheDocument();
    expect(within(funding).queryByText("Adjacent")).toBeNull();
    expect(api.runLookup).toHaveBeenCalledWith(701, "signals", false);
  });

  it("waits for a saved run before looking anything up", () => {
    render(<MarketSignals res={{ streaming: true }} />);
    expect(api.runLookup).not.toHaveBeenCalled();
  });
});
