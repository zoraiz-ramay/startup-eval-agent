import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";

/**
 * PROF-01 / PROF-04 — profile header and tab bar.
 *
 * Replaces tests/test_sticky_profile_tab_bar.py, which asserted the literal string
 * "sticky-header" appeared somewhere in Profile.jsx. That is satisfied by writing the word in a
 * comment, and said nothing about whether the tabs were usable.
 *
 * jsdom does not do layout, so "is it actually stuck to the top" is a visual-regression concern
 * (contract row X-06) rather than something this layer can honestly assert. What it CAN verify is
 * that the tab bar is a real tablist, correctly marked, and carries the sticky affordance.
 */
const RUN = {
  found: true,
  company: "Phena",
  source: "web",
  summary: "Industrial computer vision for manufacturing quality control.",
  profile: { company_name: "Phena", founded_year: "2026", employees_count: "2-10", funding: "" },
  profile_sources: { founded_year: { origin: "web", url: "https://www.cbinsights.com/company/phena" } },
  score: { final_score: 37.5, dimensions: {}, route_scorecards: {}, missing_evidence: [], red_flags: [] },
  routing: { pillar: "Connect", secondary: [] },
  fit: { matches: [] },
  facts: [],
  verification: { claims: [], red_flags: [] },
  trend: {},
  deep_profile: { founders: [], advisors: [], programs: [], employees: "2-10", reference_customers: [] },
};

vi.mock("../api.js", () => ({
  api: {
    run: vi.fn(async () => RUN),
    evaluate: vi.fn(async () => RUN),
    audit: vi.fn(async () => ({ overrides: [] })),
    ask: vi.fn(async () => ({ answer: "", evidence: [] })),
  },
}));

async function renderProfile() {
  const { default: Profile } = await import("./Profile.jsx");
  return render(
    <MemoryRouter initialEntries={["/startup/1"]}>
      <AppProvider>
        <Routes>
          <Route path="/startup/:id" element={<Profile />} />
        </Routes>
      </AppProvider>
    </MemoryRouter>,
  );
}

describe("Profile", () => {
  it("renders the tab bar as a tablist with a selected tab", async () => {
    await renderProfile();
    const tablist = await screen.findByRole("tablist");
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs.length).toBeGreaterThan(1);
    expect(tabs.filter((t) => t.getAttribute("aria-selected") === "true")).toHaveLength(1);
  });

  it("keeps the tab bar reachable while scrolling a long report", async () => {
    await renderProfile();
    // The affordance, not the computed position — see the note above.
    expect(await screen.findByRole("tablist")).toHaveClass("sticky-header");
  });

  it("shows a web-sourced field with its provenance link (PROF-02, X-01)", async () => {
    await renderProfile();
    // The badge's visible text is "web", but its accessible name is field-specific — see UI-01 —
    // so query by that name, exactly what a screen reader exposes.
    const link = await screen.findByRole("link", { name: /^web — founded year source$/i });
    expect(link).toHaveAttribute("href", "https://www.cbinsights.com/company/phena");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
    // WCAG 2.5.3 Label in Name: the visible label ("web") must still be a prefix of the name.
    expect(link).toHaveTextContent("web");
  });

  it("shows a provenance badge on the Employees metric when profile_sources.employees_count is populated (UI-06, PROF-02, X-01)", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce({
      ...RUN,
      profile_sources: {
        ...RUN.profile_sources,
        employees_count: { origin: "web", url: "https://www.linkedin.com/company/phena/people" },
      },
    });
    await renderProfile();
    const metric = (await screen.findByText("Employees")).closest(".metric");
    const link = within(metric).getByRole("link", { name: /^web — employees source$/i });
    expect(link).toHaveAttribute("href", "https://www.linkedin.com/company/phena/people");
  });

  it("gives the Employees and Founded provenance badges distinguishable accessible names (UI-01, X-01, X-04)", async () => {
    // Regression for UI-01: before the fix both badges' accessible name was the literal string
    // "web", so a screen-reader user tabbing the metric row heard "web", "web" with no way to
    // tell which figure each one backs. Both sources populated in one render is the point —
    // a test that only checked one badge would still pass with both named "web".
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce({
      ...RUN,
      profile_sources: {
        founded_year: { origin: "web", url: "https://www.cbinsights.com/company/phena" },
        employees_count: { origin: "web", url: "https://www.linkedin.com/company/phena/people" },
      },
    });
    await renderProfile();
    const employeesLink = await screen.findByRole("link", { name: /^web — employees source$/i });
    const foundedLink = screen.getByRole("link", { name: /^web — founded year source$/i });
    expect(employeesLink).not.toBe(foundedLink);
    expect(employeesLink).toHaveAttribute("href", "https://www.linkedin.com/company/phena/people");
    expect(foundedLink).toHaveAttribute("href", "https://www.cbinsights.com/company/phena");
    // Visible text is identical on purpose — only the accessible name disambiguates them.
    expect(employeesLink).toHaveTextContent("web");
    expect(foundedLink).toHaveTextContent("web");
  });

  it("shows no provenance badge on the Employees metric when no source was recorded (UI-06)", async () => {
    // RUN.profile_sources only carries founded_year — employees_count came straight from the DB
    // (or wasn't backfilled), so asserting a web source there would claim evidence that isn't there.
    await renderProfile();
    const metric = (await screen.findByText("Employees")).closest(".metric");
    expect(within(metric).queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders an unevidenced field as an em dash rather than a guess (X-02)", async () => {
    await renderProfile();
    // RUN has funding: "" — the UI must show absence, never substitute a plausible number.
    const funding = (await screen.findAllByText(/^—$/)).length;
    expect(funding).toBeGreaterThan(0);
  });

  it("shows the headcount trend panel's one-line empty state when no series was cited (PROF-12, X-03)", async () => {
    // RUN.deep_profile carries no employees_over_time key at all — the common case, since the
    // engine returns [] (never a single-point series) whenever it can't corroborate a number.
    // A section's empty state is a sentence, not "—" (that idiom is reserved for single fields).
    await renderProfile();
    expect(await screen.findByText(/no cited headcount history/i)).toBeInTheDocument();
  });

  it("renders each cited headcount point with its own source link, never batching provenance away (PROF-12, X-01)", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce({
      ...RUN,
      deep_profile: {
        ...RUN.deep_profile,
        employees_over_time: [
          { year: 2022, count: 3, source_url: "https://crunchbase.example/acme" },
          { year: 2024, count: 60, source_url: "https://linkedin.example/acme" },
        ],
      },
    });
    await renderProfile();
    // The growth headline splits "3" and "60" across separate <strong> nodes for emphasis, so
    // the default single-node text matcher can't see the combined string — match on the
    // paragraph's full textContent instead.
    expect(await screen.findByText(
      (_, node) => node?.tagName === "P" && /3\s*→\s*60\s*employees/.test(node.textContent || ""),
    )).toBeInTheDocument();
    const link2022 = await screen.findByRole("link", { name: /source \(2022\)/i });
    expect(link2022).toHaveAttribute("href", "https://crunchbase.example/acme");
    const link2024 = await screen.findByRole("link", { name: /source \(2024\)/i });
    expect(link2024).toHaveAttribute("href", "https://linkedin.example/acme");
  });
});
