import { render, screen, within, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * "How this startup works" is a short story in plain words — the problem, what they offer, how
 * it works, who buys it, how it makes money — each sentence cited (checked on the server), with
 * no labels on the cards and one numbered sources line underneath.
 */
vi.mock("../../api.js", () => ({ api: { runBusinessFlow: vi.fn() } }));

import { api } from "../../api.js";
import BusinessFlow from "./BusinessFlow.jsx";
import OverviewTab from "./OverviewTab.jsx";

const src = (id, source, quote, url = "") => ({ id, source, quote, url });
const FLOW = { version: "business-flow-v1", status: "ok", message: "", steps: [
  { id: "problem", label: "The problem", text: "Mixed plastic waste cannot be recycled today.", sources: [src("E1", "summary", "unrecyclable plastic waste")] },
  { id: "offer", label: "What they offer", text: "A technology that turns plastic waste into chemicals.", sources: [src("E1", "summary", "chemical recycling")] },
  { id: "customers", label: "Who buys it", text: "Chemical producers.", sources: [src("E11", "profile.Reference customers", "Chemical producers"),
    src("E68", "deep_profile.customer_segment", "chemical producers", "https://seg.test")] },
] };

beforeEach(() => vi.clearAllMocks());

describe("BusinessFlow", () => {
  it("tells the business as plain steps, with the sources as numbered footnotes rather than labels", async () => {
    api.runBusinessFlow.mockResolvedValue(FLOW);
    render(<BusinessFlow res={{ run_id: 601, company: "Radical Dot" }} />);
    const story = await screen.findByRole("list", { name: "How this startup works, step by step" });
    const cards = within(story).getAllByRole("listitem");
    expect(cards.map((c) => c.querySelector(".biz-card-label").textContent)).toEqual(["The problem", "What they offer", "Who buys it"]);
    expect(cards[0]).toHaveTextContent("Mixed plastic waste cannot be recycled today.");
    expect(cards[0]).not.toHaveTextContent("Research summary");                 // no labels on the cards
    expect(cards[0]).toHaveAttribute("title", "unrecyclable plastic waste");    // the sentence it came from, on hover
    // One source, one number, however many cards cite it.
    expect(within(cards[1]).getByRole("link", { name: "Source 1" })).toHaveAttribute("href", "#biz-src-1");
    expect(within(cards[2]).getAllByRole("link").map((a) => a.textContent)).toEqual(["2", "3"]);
    const sources = document.querySelector(".biz-sources");
    expect(sources).toHaveTextContent("Research summary");
    expect(within(sources).getByRole("link", { name: /seg\.test/ })).toHaveAttribute("href", "https://seg.test");
    expect(api.runBusinessFlow).toHaveBeenCalledWith(601);
  });

  it("says when the research does not describe enough, instead of drawing a thin story", async () => {
    api.runBusinessFlow.mockResolvedValue({ status: "insufficient", steps: [], message: "The research does not describe enough of how this business works." });
    render(<BusinessFlow res={{ run_id: 602 }} />);
    expect(await screen.findByText("The research does not describe enough of how this business works.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /step by step/ })).toBeNull();
  });

  it("waits for a saved run, and shows an error instead of an empty section", async () => {
    const { unmount } = render(<BusinessFlow res={{ streaming: true }} />);
    expect(screen.getByText("Available once the evaluation has finished.")).toBeInTheDocument();
    expect(api.runBusinessFlow).not.toHaveBeenCalled();
    unmount();
    api.runBusinessFlow.mockRejectedValue(new Error("Could not write the flow"));
    render(<BusinessFlow res={{ run_id: 603 }} />);
    expect(await screen.findByText("Could not write the flow")).toBeInTheDocument();
  });
});

describe("Revenue tile", () => {
  const tile = (division) => {
    render(<OverviewTab res={{ company: "X", score: {}, traction: { divisions: division ? [division] : [] } }} />);
    return screen.getByText("Revenue").closest(".metric");
  };

  it("shows a sourced figure with its link", () => {
    const t = tile({ id: "revenue", status: "evidenced", value_eur: 1200000, basis: "arr", source_url: "https://arr.test" });
    expect(t).toHaveTextContent("€1.2M");
    expect(t).toHaveTextContent("ARR");
    expect(within(t).getByRole("link", { name: /source/ })).toHaveAttribute("href", "https://arr.test");
  });

  it("says pre-revenue only when a source says so", () => {
    expect(tile({ id: "revenue", status: "zero_evidenced", source_url: "https://pre.test" })).toHaveTextContent("Pre-revenue");
  });

  it("is a dash with no sourced revenue", async () => {
    const t = tile({ id: "revenue", status: "unknown", source_url: "" });
    expect(within(t).getByText("—")).toBeInTheDocument();
    expect(within(t).queryByRole("link")).toBeNull();
    await waitFor(() => expect(api.runBusinessFlow).not.toHaveBeenCalled());   // no run id, no request
  });
});
