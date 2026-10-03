import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The traction divisions' detail: funding rounds and investors and a sourced headcount, looked up
 * on request (Tracxn first, web search second), and the customers, revenue and employee facts the
 * run already holds — each with its source, or saying it has none.
 */
vi.mock("../../../api.js", () => ({ api: { runLookup: vi.fn() } }));

import { api } from "../../../api.js";
import { FundingLookup, HeadcountLookup } from "./TractionLookup.jsx";
import TractionDetail from "./TractionDetail.jsx";

const FUNDING = {
  provider: "web", note: "", sources: [], retrieved_at: "2026-09-30",
  rounds: [{ date: "February 2025", stage: "Seed Round", amount: "€2.8 million", lead_investors: ["LEA Partners"],
    investors: ["468 Capital"], sources: [{ title: "tech.eu", url: "https://r.test/1" }, { title: "tech.eu", url: "https://r.test/2" }] }],
  investors: [{ name: "LEA Partners", type: "Private equity", type_detail: "private equity and venture capital firm",
    hq: "Karlsruhe, Germany", focus: "B2B software", portfolio: ["sevDesk"], sources: [{ title: "pitchbook.com", url: "https://p.test" }] }],
};

beforeEach(() => vi.clearAllMocks());

describe("FundingLookup", () => {
  it("shows each round with its investors and sources, one link per site, and investor profiles", async () => {
    api.runLookup.mockResolvedValue(FUNDING);
    render(<FundingLookup runId={501} />);
    const round = (await screen.findByText("€2.8 million")).closest("li");
    expect(within(round).getByText("LEA Partners")).toBeInTheDocument();
    expect(within(round).getAllByRole("link", { name: "tech.eu" })).toHaveLength(1);
    expect(screen.getByText("From web search · verify figures")).toBeInTheDocument();
    const card = within(screen.getByRole("list", { name: "Investor profiles" })).getByText("LEA Partners").closest("li");
    expect(within(card).getByText("Private equity")).toHaveAttribute("title", "private equity and venture capital firm");
    expect(card).toHaveTextContent("Karlsruhe, Germany");
    expect(api.runLookup).toHaveBeenCalledWith(501, "funding", false);
  });

  it("says where the answer came from when Tracxn could not answer, and refreshes on request", async () => {
    api.runLookup.mockResolvedValue({ ...FUNDING, rounds: [], investors: [], note: "Tracxn had nothing on this, so it comes from web search." });
    render(<FundingLookup runId={502} known={[{ name: "Rockstart", source_url: "https://rock.test" }]} />);
    expect(await screen.findByText(/Tracxn had nothing on this/)).toBeInTheDocument();
    expect(screen.getByText("No funding round with a source was found.")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Investors on record" })).getByRole("link", { name: "rock.test" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(api.runLookup).toHaveBeenLastCalledWith(502, "funding", true));
  });

  it("marks an investor only an earlier evaluation found, and leaves re-confirmed ones plain", async () => {
    api.runLookup.mockResolvedValue({ ...FUNDING, rounds: [], investors: [] });
    render(<FundingLookup runId={506} known={[
      { name: "Rockstart", source_url: "https://rock.test" },
      { name: "UVC Partners", source_url: "https://uvc.test", last_confirmed_at: "2026-08-22T03:00:00+00:00" },
    ]} />);
    const list = await screen.findByRole("list", { name: "Investors on record" });
    expect(within(list).getByText("UVC Partners").closest("li")).toHaveTextContent("last confirmed 22 Aug 2026");
    expect(within(list).getByText("Rockstart").closest("li")).not.toHaveTextContent(/last confirmed/);
  });

  it("says when a result served from the database was fetched", async () => {
    api.runLookup.mockResolvedValue({ ...FUNDING, from_store: true, stored_at: "2026-09-30T12:00:00+00:00" });
    render(<FundingLookup runId={505} />);
    expect(await screen.findByText("Saved 2026-09-30")).toBeInTheDocument();
  });

  it("shows an error instead of an empty list when the lookup fails", async () => {
    api.runLookup.mockRejectedValue(new Error("Lookup failed"));
    render(<FundingLookup runId={503} />);
    expect(await screen.findByText("Lookup failed")).toBeInTheDocument();
  });
});

describe("HeadcountLookup", () => {
  it("lists each reported headcount with when, where and its source", async () => {
    api.runLookup.mockResolvedValue({ provider: "tracxn", note: "", sources: [], figures: [
      { count: "16", as_of: "2025", where: "GetLatka", sources: [{ title: "Tracxn", url: "" }] }] });
    render(<HeadcountLookup runId={504} />);
    const list = await screen.findByRole("list", { name: "Reported headcounts" });
    expect(list).toHaveTextContent("16");
    expect(list).toHaveTextContent("GetLatka");
    expect(within(list).getByText("Tracxn")).toBeInTheDocument();
    expect(screen.getByText("From Tracxn")).toBeInTheDocument();
    expect(api.runLookup).toHaveBeenCalledWith(504, "headcount", false);
  });
});

const division = (over) => ({ label: "X", max: 30, status: "evidenced", points: 10, value: "", band: "", source_url: "",
  origin: "", basis: "", candidates: [], items: [], rationale: "", ...over });

describe("TractionDetail", () => {
  it("names customers at both levels — named, and the customer base as described — and marks which scored", () => {
    const d = division({ id: "customers", label: "Customers", basis: "named", items: [
      { name: "BASF", size: "large_enterprise", counted: true, source_url: "https://basf.test" },
      { name: "Acme Capital", size: "sme", counted: false, reason: "listed as an investor" }] });
    const res = { deep_profile: { customer_segment: "chemical producers", customer_segment_source: "https://seg.test",
      customer_segment_grade: { level: 2 } } };
    render(<TractionDetail d={d} res={res} onClose={() => {}} />);
    const panel = screen.getByRole("region", { name: "Traction: Customers" });
    expect(within(panel).getByText("Named customers")).toHaveTextContent("scored");
    expect(within(panel).getByText("BASF").closest("li")).toHaveTextContent("Big name");
    expect(within(panel).getByText("Acme Capital").closest("li")).toHaveTextContent("not counted · listed as an investor");
    expect(panel).toHaveTextContent("“chemical producers” · level 2 of 3");
    expect(within(panel).getByRole("link", { name: "seg.test" })).toBeInTheDocument();
  });

  it("gives the revenue figure its source, year and wording, even when it did not score", () => {
    const d = division({ id: "revenue", label: "Revenue", status: "unknown", points: null, rationale: "Stated figure is not revenue (estimate)." });
    const res = { deep_profile: { commercial: { revenue: { quote: "Bliro generates an estimated $1.8M in annual revenue.",
      metric: "estimate", fiscal_year: "2025", source_url: "https://getlatka.test/b" }, revenue_signal: "recurring", revenue_source: "https://bliro.test" } } };
    render(<TractionDetail d={d} res={res} onClose={() => {}} />);
    const panel = screen.getByRole("region", { name: "Traction: Revenue" });
    expect(panel).toHaveTextContent("Revenue estimate · 2025");
    expect(within(panel).getByRole("link", { name: "getlatka.test" })).toBeInTheDocument();
    expect(panel).toHaveTextContent("Recurring revenue (subscriptions or contracts)");
  });

  it("names where each headcount came from, and says when no link was captured", () => {
    const d = division({ id: "employees", label: "Employees", max: 10, points: 8, value: "11-20", origin: "web",
      candidates: [{ value: "11-20", origin: "web", source_url: "", used: true }, { value: "8", origin: "glassdollar", source_url: "" }] });
    render(<TractionDetail d={d} res={{}} onClose={() => {}} />);
    const panel = screen.getByRole("region", { name: "Traction: Employees" });
    expect(within(panel).getAllByText("Web research · no link captured").length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("GlassDollar database").length).toBeGreaterThan(0);
  });
});
