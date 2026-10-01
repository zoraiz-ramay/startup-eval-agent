import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TractionPanel from "./TractionPanel.jsx";

/**
 * The traction rubric's panel. What these pin is the distinction the rubric exists to keep: a
 * division nobody found evidence for is EXCLUDED from the total, and must never render as "0 / 30",
 * which would read as a finding that the company has no revenue. A sourced pre-revenue statement
 * is the opposite case — a real zero that stays in the total and keeps its link.
 */
const division = (over) => ({
  id: "funding", label: "Funding", max: 30, status: "unknown", points: null, value: "", band: "",
  source_url: "", origin: "", basis: "", conflict: false, currency_assumed: false, stale: false,
  rationale: "", candidates: [], ...over,
});

const TRACTION = {
  version: "traction-rubric-v2", status: "scored", score_0_100: 72.2, earned: 32.5,
  available_max: 45, total_max: 100, confidence: 0.45, divisions_known: 3, fx_as_of: "2026-09-01",
  divisions: [
    division({ status: "evidenced", points: 25, value: "€2.8M", band: "≥ €2M", origin: "GlassDollar",
      currency_assumed: true, rationale: "€2.8M → ≥ €2M: 25 of 30." }),
    division({ id: "customers", label: "Customers", rationale: "No named customer." }),
    division({ id: "revenue", label: "Revenue", status: "zero_evidenced", points: 0,
      value: "we are pre-revenue", band: "Pre-revenue", source_url: "https://example.com/about" }),
    division({ id: "employees", label: "Employees", max: 10, status: "evidenced", points: 6,
      value: "8", band: "7 – 10" }),
  ],
};

const row = (name) => screen.getByRole("rowheader", { name }).closest("tr");

describe("TractionPanel", () => {
  it("shows an unevidenced division as excluded, never as zero points", () => {
    render(<TractionPanel res={{ traction: TRACTION }} detailed />);
    const customers = within(row("Customers"));
    expect(customers.getByText("Not found")).toBeInTheDocument();
    expect(customers.getByText("excluded from total")).toBeInTheDocument();
    expect(customers.queryByText(/^0$/)).toBeNull();
  });

  it("keeps an evidenced zero in the table with its source", () => {
    render(<TractionPanel res={{ traction: TRACTION }} detailed />);
    const revenue = within(row("Revenue"));
    expect(revenue.getByText("Pre-revenue")).toBeInTheDocument();
    expect(revenue.getByRole("link", { name: "source" })).toHaveAttribute("href", "https://example.com/about");
    expect(row("Revenue").textContent).toMatch(/0\s*\/ 30/);
  });

  it("reports the normalised score with the points it covers and its confidence", () => {
    render(<TractionPanel res={{ traction: TRACTION }} detailed />);
    expect(screen.getByRole("img", { name: "Traction 72 of 100" })).toBeInTheDocument();
    expect(screen.getByText(/32\.5 of 45 available points/)).toBeInTheDocument();
    expect(screen.getByText("45%")).toBeInTheDocument();
    expect(screen.getByText("of the 100 points had evidence")).toBeInTheDocument();
  });

  it("flags a currency that was assumed rather than stated", () => {
    render(<TractionPanel res={{ traction: TRACTION }} detailed />);
    expect(within(row("Funding")).getByText("currency assumed €")).toBeInTheDocument();
  });

  it("says there is no score, not a score of zero, when nothing was evidenced", () => {
    const empty = { ...TRACTION, status: "no_evidence", score_0_100: null, earned: 0, available_max: 0,
      confidence: 0, divisions: TRACTION.divisions.map((d) => division({ id: d.id, label: d.label, max: d.max })) };
    render(<TractionPanel res={{ traction: empty }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/no score — not a score of zero/);
    expect(document.querySelector(".ring-gauge .ring-value").textContent).toBe("—");
  });

  it("says it is still computing while a run streams, and that it was never computed on an old run", () => {
    const { unmount } = render(<TractionPanel res={{ streaming: true }} />);
    expect(screen.getByText("Computing traction…")).toBeInTheDocument();
    unmount();
    render(<TractionPanel res={{}} />);
    expect(screen.getByRole("status")).toHaveTextContent(/not computed for this run/);
  });

  it("draws each division against its maximum in the summary view, and an unevidenced one as excluded", () => {
    render(<TractionPanel res={{ traction: TRACTION }} />);
    expect(screen.queryByRole("table")).toBeNull();                    // the table is the detailed view
    expect(screen.getByRole("img", { name: "Funding: 25 of 30 points" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Customers: no evidence, excluded from the total" })).toBeInTheDocument();
    expect(screen.getByText("No evidence · excluded")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Revenue: 0 of 30 points" })).toBeInTheDocument();   // a real zero is a bar
  });

  it("opens one division at a time from its bar, against the rubric ladder, and closes on a second press", () => {
    const ladders = {
      funding: [{ group: "By amount raised", label: "Raised ≥ €2M", points: 25, match: "≥ €2M" },
        { group: "By amount raised", label: "Raised €1.5M – 2M", points: 15, match: "€1.5M – 2M" }],
      customers: [{ group: "Named SME customers", label: "3+ SME customers", points: 15, kind: "sme", min: 3 },
        { group: "Named SME customers", label: "2+ SME customers", points: 7, kind: "sme", min: 2 }],
    };
    render(<TractionPanel res={{ traction: TRACTION, traction_ladders: ladders }} />);
    const funding = screen.getByRole("button", { name: /^Funding: 25 of 30 points/ });
    fireEvent.click(funding);
    expect(funding).toHaveAttribute("aria-expanded", "true");
    const region = screen.getByRole("region", { name: "Traction: Funding" });
    expect(within(region).getByText("€2.8M → ≥ €2M: 25 of 30.")).toBeInTheDocument();
    const marked = region.querySelectorAll('[aria-current="true"]');
    expect(marked).toHaveLength(1);
    expect(marked[0]).toHaveTextContent("Raised ≥ €2M");
    expect(within(region).getByText("currency assumed €")).toBeInTheDocument();
    fireEvent.click(funding);
    expect(screen.queryByRole("region", { name: /Traction:/ })).toBeNull();
  });

  it("marks no rung for a division with no evidence and says it was left out", () => {
    render(<TractionPanel res={{ traction: TRACTION, traction_ladders: { customers: [
      { group: "Named SME customers", label: "3+ SME customers", points: 15, kind: "sme", min: 3 }] } }} />);
    fireEvent.click(screen.getByRole("button", { name: "Customers: no evidence, excluded from the total" }));
    const region = screen.getByRole("region", { name: "Traction: Customers" });
    expect(region.querySelectorAll('[aria-current="true"]')).toHaveLength(0);
    expect(within(region).getByText(/left out of the total — not scored zero/)).toBeInTheDocument();
  });

  it("refuses to render a breakdown shape it does not know", () => {
    render(<TractionPanel res={{ traction: { version: "traction-rubric-v0" } }} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/version this page cannot read/);
  });
});
