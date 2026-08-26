import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";

/**
 * PROF-01 / PROF-04 — profile header and navigation.
 *
 * The pipeline ribbon and the tab bar are gone; the section rail is the page's whole navigation.
 * jsdom does not do layout, so "is it actually stuck to the top" is a visual-regression concern
 * (contract row X-06) rather than something this layer can honestly assert. What it CAN verify is
 * that navigation exists as a landmark, that switching a group switches what is rendered, and
 * that the two removed pieces of chrome are really gone rather than merely hidden.
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

// The what-if weighting persists to localStorage, so without this one test's weighting leaks into
// the next and the failures point at the wrong place.
beforeEach(() => localStorage.clear());

describe("Profile", () => {
  it("navigates from the rail, with exactly one group open", async () => {
    await renderProfile();
    const rail = await screen.findByRole("navigation", { name: "Profile navigation" });
    const expanded = within(rail).getAllByRole("button")
      .filter((b) => b.getAttribute("aria-expanded") === "true");
    expect(expanded).toHaveLength(1);
    expect(expanded[0]).toHaveAccessibleName("Profile");
  });

  it("no longer stacks a pipeline ribbon and a tab bar above the content", async () => {
    // The ribbon rendered all seven steps as done on every finished run, so it reported nothing a
    // reader could act on while costing sticky height on every profile. Two navigation systems for
    // one page was the other half of the problem.
    const { container } = await renderProfile();
    await screen.findByRole("navigation", { name: "Profile navigation" });
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(container.querySelector(".ribbon")).toBeNull();
  });

  it("gives the open group's content a region a reader can jump to", async () => {
    await renderProfile();
    expect(await screen.findByRole("region", { name: "Profile" })).toBeInTheDocument();
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

/**
 * PROF-14 — the browser-local what-if weighting.
 *
 * The risk this feature carries is that a re-weighted number gets mistaken for the evaluation
 * result, so the assertions below are as much about what does NOT change (the stored score, on
 * every other surface) as about what does.
 */
const SCORED_RUN = {
  ...RUN,
  score: {
    ...RUN.score,
    final_score: 40.0,
    raw_score: 64.0,
    data_completeness: 0.25,
    data_confidence: 0.62,
    dimensions: { traction: 60, siemens_fit: 70, product: 80, market: 50, founder: 55, ecosystem: 65 },
  },
};

const railLoaded = () => screen.findByRole("navigation", { name: "Profile navigation" });

async function openScoringTab() {
  fireEvent.click(await screen.findByRole("button", { name: /^scoring & fit$/i }));
}

async function openWhatIf() {
  await openScoringTab();
  const toggle = await screen.findByRole("button", { name: /what-if weights/i });
  fireEvent.click(toggle);
  return toggle;
}

describe("what-if weights (PROF-14)", () => {
  it("stays collapsed until asked for, leaving the stored score alone", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(SCORED_RUN);
    await renderProfile();
    await openScoringTab();

    const toggle = await screen.findByRole("button", { name: /what-if weights/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("re-weighting changes the what-if figure but never the stored score", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(SCORED_RUN);
    await renderProfile();
    await openWhatIf();

    const storedRow = () => screen.getByText(/engine score \(stored\)/i).closest(".spec");
    const before = (await screen.findByRole("status")).textContent;
    const storedBefore = within(storedRow()).getByText("40");

    fireEvent.change(screen.getByLabelText(/^siemens fit$/i), { target: { value: "60" } });

    const after = (await screen.findByRole("status")).textContent;
    expect(after).not.toEqual(before);
    // The engine's score is unmoved, and it sits inside this panel beside the what-if — so no
    // screenshot crop can capture the what-if without also capturing what it is being compared to.
    expect(within(storedRow()).getByText("40")).toBe(storedBefore);
    expect(screen.getByText(/not the evaluation result/i)).toBeInTheDocument();
  });

  it("resets back to the engine's weighting in one action", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(SCORED_RUN);
    await renderProfile();
    await openWhatIf();

    const original = (await screen.findByRole("status")).textContent;
    fireEvent.change(screen.getByLabelText(/^product$/i), { target: { value: "70" } });
    expect((await screen.findByRole("status")).textContent).not.toEqual(original);

    fireEvent.click(screen.getByRole("button", { name: /reset to engine weights/i }));
    expect((await screen.findByRole("status")).textContent).toEqual(original);
    expect(localStorage.getItem("se.whatIfWeights.v1")).toBe("null");
  });

  it("says so plainly when a run has no dimensions to re-weight", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(RUN);   // dimensions: {}
    await renderProfile();
    await openWhatIf();

    expect(await screen.findByText(/no recorded dimension scores/i)).toBeInTheDocument();
    // The point of the empty state: no number at all, rather than NaN.
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

/**
 * PROF-15 — the what-if routing derivation.
 *
 * The failure mode this guards is a reviewer reading a what-if pillar as the evaluation's verdict.
 * A wrong score is bad; a wrong pillar drives a wrong partnership call. So these assert the engine's
 * pillar stays put and stays visible as much as they assert the what-if is derived correctly.
 */
const ALIGNED_RUN = {
  ...SCORED_RUN,
  fit: { aligned: true, matches: [] },
  routing: { pillar: "Empower", secondary: [] },
  score: { ...SCORED_RUN.score, route_scorecards: { Connect: 60, Collaborate: 58, Empower: 62 } },
};

describe("what-if routing (PROF-15)", () => {
  it("explains every gate, including the ones that pass", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    await renderProfile();
    await openWhatIf();

    // Scoped to the what-if panel. The per-pillar sections now report the ENGINE's own gates in
    // the same vocabulary, so an unscoped query matches both and would pass while the what-if
    // rendered nothing at all.
    const panel = (await screen.findByText(/what-if routing/i)).closest(".panel");
    // All four rows, always — a reviewer looking at a blocked pillar needs the whole reason,
    // and an empty state would be the least useful thing to show them.
    expect(within(panel).getByText(/portfolio alignment/i)).toBeInTheDocument();
    for (const route of ["Connect", "Collaborate", "Empower"]) {
      expect(within(panel).getAllByText(route).length).toBeGreaterThan(0);
    }
    // Empower's row states the absence of a gate rather than inventing a threshold for symmetry.
    expect(within(panel).getByText(/no score gate/i)).toBeInTheDocument();
  });

  it("marks the clauses no weighting can move, so a blocked pillar is not read as 'nearly there'", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    await renderProfile();
    await openWhatIf();
    expect(screen.getAllByText(/not affected by your weighting/i).length).toBeGreaterThan(0);
  });

  it("says a verdict cannot change when that is provable, rather than merely that it did not", async () => {
    // RUN's fit has no `aligned`, so the alignment gate fails — and it reads the raw dimension,
    // which no weighting touches. "Cannot" is the honest word here.
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce({ ...SCORED_RUN, fit: { matches: [] } });
    await renderProfile();
    await openWhatIf();
    expect(await screen.findByText(/cannot change this/i)).toBeInTheDocument();
  });

  it("leaves the header pillar untouched while the what-if is on screen", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    const { container } = await renderProfile();
    await openWhatIf();
    fireEvent.change(screen.getByLabelText(/^ecosystem$/i), { target: { value: "100" } });

    // The canonical pillar lives in the profile header and must be unmoved by anything here.
    const headerPill = container.querySelector(".ph-title .pill, .ph-head .pill") ||
      container.querySelector(".pill");
    expect(headerPill.textContent).toBe("Empower");
  });

  it("keeps exactly one live region on the tab", async () => {
    // Two polite regions announce in unpredictable order, and every existing assertion selects
    // this one unqualified.
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    await renderProfile();
    await openWhatIf();
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });
});

/**
 * The overview metric row answers "what is this company", so it carries funding and location.
 * Completeness and the trend verdict are not lost — the first is inside the score derivation
 * further down the tab, the second is the Market tab's headline.
 */
const RUN_WITH_FACTS = {
  ...RUN,
  profile: { ...RUN.profile, hq: "Istanbul, Turkey", funding: "EUR 2.4M seed" },
};

describe("Profile — headline facts", () => {
  const metric = (label) =>
    screen.getByText(label, { selector: ".metric .k" }).closest(".metric");

  async function renderWithFacts() {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(RUN_WITH_FACTS);
    await renderProfile();
    await railLoaded();
  }

  it("shows funding and location as metric tiles", async () => {
    await renderWithFacts();
    expect(metric("Funding")).toHaveTextContent("EUR 2.4M seed");
    expect(metric("Location")).toHaveTextContent("Istanbul, Turkey");
  });

  it("no longer spends a tile on completeness or the trend label", async () => {
    await renderWithFacts();
    expect(screen.queryByText("Completeness", { selector: ".metric .k" })).not.toBeInTheDocument();
    expect(screen.queryByText("Market signal", { selector: ".metric .k" })).not.toBeInTheDocument();
  });

  it("keeps the header line to the score, not the company facts", async () => {
    await renderWithFacts();
    const meta = document.querySelector(".ph-meta");
    expect(meta).toHaveTextContent(/Score/);
    expect(meta).not.toHaveTextContent("Istanbul");
    expect(meta).not.toHaveTextContent("2.4M");
  });

  it("shows an em dash rather than an empty tile when a fact is missing", async () => {
    await renderProfile();          // base RUN has no hq and blank funding
    await railLoaded();
    expect(metric("Funding")).toHaveTextContent("—");
    expect(metric("Location")).toHaveTextContent("—");
  });
});

/**
 * An empty headcount series has three causes and they are not interchangeable: one is about
 * the company, one about the evidence, one about our own run. Reporting all three as "no cited
 * headcount history" told reviewers a company had been checked when it had not.
 */
describe("Profile — headcount trend empty states", () => {
  const withStatus = async (status) => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce({
      ...RUN,
      deep_profile: { ...RUN.deep_profile, employees_over_time: [],
                      employees_history_status: status },
    });
    await renderProfile();
    await railLoaded();
  };

  it("says a young company is too new rather than unsourced", async () => {
    await withStatus("too_young");
    expect(screen.getByText(/too new for a headcount trend/i)).toBeInTheDocument();
  });

  it("distinguishes a failed run from an absence of evidence", async () => {
    await withStatus("unavailable");
    expect(screen.getByText(/could not be retrieved on this run/i)).toBeInTheDocument();
    expect(screen.queryByText(/fewer than two independently sourced/i)).not.toBeInTheDocument();
  });

  it("still reports genuine absence as absence", async () => {
    await withStatus("not_found");
    expect(screen.getByText(/fewer than two independently sourced/i)).toBeInTheDocument();
  });

  it("falls back to the absence wording for a run stored before the status existed", async () => {
    await withStatus(undefined);
    expect(screen.getByText(/fewer than two independently sourced/i)).toBeInTheDocument();
  });
});
