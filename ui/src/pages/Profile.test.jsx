import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";
import { findShadowRole } from "../test/shadow.js";

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

// The what-if weighting persists to localStorage, so without this one test's weighting leaks into
// the next and the failures point at the wrong place.
beforeEach(() => localStorage.clear());

describe("Profile", () => {
  it("offers every section of the report from one navigation landmark", async () => {
    // The tab bar is gone: the report is one scrolling page and the rail is a map of it. What
    // the old tablist assertion protected — that there is a single, marked, complete way to
    // reach each part of a run — is what this asserts of its replacement, so a rail that
    // silently loses a destination still fails here.
    const { container } = await renderProfile();
    const rail = await screen.findByRole("navigation", { name: /profile sections/i });
    for (const label of ["Profile", "Scoring & Fit", "Market & Risk", "Evidence"]) {
      expect(within(rail).getByRole("button", { name: label })).toBeTruthy();
    }
    // Every group heading is a real button, so the rail is operable by keyboard and not a set of
    // styled divs — the failure mode the hand-rolled tab bar had before it became IxTabs.
    expect(container.querySelector(".sec-nav")).toBeTruthy();
  });

  it("anchors every rail destination to something actually on the page", async () => {
    // A rail entry that scrolls nowhere is worse than no entry, and `present` (Profile.jsx) is
    // what is supposed to prevent one. RUN has no trend and no red flags, so those anchors must
    // be absent from BOTH the rail and the document — not listed and dead.
    const { container } = await renderProfile();
    const rail = await screen.findByRole("navigation", { name: /profile sections/i });
    expect(within(rail).queryByRole("button", { name: "Recent signals" })).toBeNull();
    expect(container.querySelector("#sub-signals")).toBeNull();
    // …while the ones it does list resolve to a real anchor element.
    fireEvent.click(within(rail).getByRole("button", { name: "Key metrics" }));
    expect(container.querySelector("#sub-metrics")).toBeTruthy();
  });

  it("renders the header's pillar as an IxPill carrying its own colour, not a bare class name (MIG-01)", async () => {
    // RUN's routing.pillar is "Connect". Before MIG-01 this was a `<span class="pill Connect">`
    // whose colour came only from a stylesheet rule keyed on that class; the delivery mechanism
    // itself is the thing under test, so this must fail if the pillar reverts to a plain span.
    const { container } = await renderProfile();
    // Scoped to the header: the routing rationale renders the same pillar further down the page
    // now that everything is on one screen, so an unscoped text query matches twice.
    await screen.findAllByText("Connect");
    const pill = within(container.querySelector(".ph-header-slot")).getByText("Connect");
    expect(pill.closest(".ph-header-slot")).toBeTruthy();
    expect(pill.tagName.toLowerCase()).toBe("ix-pill");
    // variant="custom" is what makes background/pillColor apply at all (components.md) — without
    // it the props are silently ignored and the pill renders iX's default primary colour instead
    // of the pillar ramp. Its reflected attribute lags the slotted text by a render tick (Stencil's
    // own update cycle), so this waits rather than reading it the instant the text resolves.
    await vi.waitFor(() => expect(pill).toHaveAttribute("variant", "custom"));
    // `background`/`pillColor` don't reflect to attributes (components.md), so read them as the
    // element properties the custom element actually consumes.
    expect(pill.background).toBe("var(--pillar-connect-bg)");
    expect(pill.pillColor).toBe("var(--pillar-connect)");
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

// Scoring & Fit used to be behind a tab click. The report is one scrolling page now, so the
// panel is already mounted and there is nothing to open — kept as a named no-op so each test
// below still reads as "get to the scoring panel, then assert", and so the wait for the run to
// have loaded stays where it was.
async function openScoringTab() {
  await screen.findAllByText(/score breakdown/i);
}

// IxBlind's header <button> (aria-expanded, aria-labelledby the shadow title node) renders inside
// its own shadow root (blind.js: encapsulation "shadow"), so opening/reading it needs the
// shadow-piercing helper rather than a plain screen query.
async function openWhatIf(container) {
  await openScoringTab();
  const toggle = await findShadowRole(container, "button", { name: /what-if weights/i });
  fireEvent.click(toggle);
  return toggle;
}

// Likewise IxSlider's native `<input type="range" role="slider">` lives inside its shadow root
// (slider.js), with its accessible name set directly on that element by ix-field-wrapper from the
// `label` prop -- so it's findable by name once shadow-pierced, same as the button above.
function getWeightSlider(container, name) {
  return findShadowRole(container, "slider", { name });
}

describe("what-if weights (PROF-14)", () => {
  it("stays collapsed until asked for, leaving the stored score alone", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(SCORED_RUN);
    const { container } = await renderProfile();
    await openScoringTab();

    const toggle = await findShadowRole(container, "button", { name: /what-if weights/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("re-weighting changes the what-if figure but never the stored score", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(SCORED_RUN);
    const { container } = await renderProfile();
    await openWhatIf(container);

    const storedRow = () => screen.getByText(/engine score \(stored\)/i).closest(".spec");
    const before = (await screen.findByRole("status")).textContent;
    const storedBefore = within(storedRow()).getByText("40");

    fireEvent.input(await getWeightSlider(container, /^siemens fit$/i), { target: { value: "60" } });

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
    const { container } = await renderProfile();
    await openWhatIf(container);

    const original = (await screen.findByRole("status")).textContent;
    fireEvent.input(await getWeightSlider(container, /^product$/i), { target: { value: "70" } });
    expect((await screen.findByRole("status")).textContent).not.toEqual(original);

    fireEvent.click(screen.getByRole("button", { name: /reset to engine weights/i }));
    expect((await screen.findByRole("status")).textContent).toEqual(original);
    expect(localStorage.getItem("se.whatIfWeights.v1")).toBe("null");
  });

  it("says so plainly when a run has no dimensions to re-weight", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(RUN);   // dimensions: {}
    const { container } = await renderProfile();
    await openWhatIf(container);

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
    const { container } = await renderProfile();
    await openWhatIf(container);

    expect(await screen.findByText(/what-if routing/i)).toBeInTheDocument();
    // All four rows, always — a reviewer looking at a blocked pillar needs the whole reason,
    // and an empty state would be the least useful thing to show them.
    expect(screen.getByText(/portfolio alignment/i)).toBeInTheDocument();
    for (const route of ["Connect", "Collaborate", "Empower"]) {
      expect(screen.getAllByText(route).length).toBeGreaterThan(0);
    }
    // Empower's row states the absence of a gate rather than inventing a threshold for symmetry.
    expect(screen.getByText(/no score gate/i)).toBeInTheDocument();
  });

  it("marks the clauses no weighting can move, so a blocked pillar is not read as 'nearly there'", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    const { container } = await renderProfile();
    await openWhatIf(container);
    expect(screen.getAllByText(/not affected by your weighting/i).length).toBeGreaterThan(0);
  });

  it("says a verdict cannot change when that is provable, rather than merely that it did not", async () => {
    // RUN's fit has no `aligned`, so the alignment gate fails — and it reads the raw dimension,
    // which no weighting touches. "Cannot" is the honest word here.
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce({ ...SCORED_RUN, fit: { matches: [] } });
    const { container } = await renderProfile();
    await openWhatIf(container);
    expect(await screen.findByText(/cannot change this/i)).toBeInTheDocument();
  });

  it("leaves the header pillar untouched while the what-if is on screen", async () => {
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    const { container } = await renderProfile();
    await openWhatIf(container);
    fireEvent.input(await getWeightSlider(container, /^ecosystem$/i), { target: { value: "100" } });

    // The canonical pillar lives in the profile header and must be unmoved by anything here.
    const header = container.querySelector(".ph-header-slot");
    expect(within(header).getByText("Empower")).toBeInTheDocument();
  });

  it("keeps exactly one live region on the tab", async () => {
    // Two polite regions announce in unpredictable order, and every existing assertion selects
    // this one unqualified.
    const { api } = await import("../api.js");
    api.run.mockResolvedValueOnce(ALIGNED_RUN);
    const { container } = await renderProfile();
    await openWhatIf(container);
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });
});
