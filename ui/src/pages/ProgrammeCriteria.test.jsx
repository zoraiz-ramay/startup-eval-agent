import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";

/**
 * The Siemens programme criteria and the SFS panel on the Scoring & Fit view.
 *
 * These assert the distinction the criteria layer exists to make. A pillar that is BLOCKED and a
 * pillar that is merely UNPROVEN used to render identically — as the pillar not appearing — and a
 * reviewer could not tell "this is the wrong programme for them" from "we have not shown it yet",
 * which are opposite conclusions. Likewise the SFS chip was a bare boolean that was true for every
 * company ever evaluated; it now has to name a line, and has to be able to say it never looked.
 *
 * The criteria used to live in one shared "Siemens programme criteria" panel. Each pillar now owns
 * a section carrying BOTH of its gates, so these queries scope to the pillar's own section — which
 * is also the property worth pinning: a reviewer reading about Connect must not be shown
 * Collaborate's verdict a few lines below it with nothing separating them.
 */
const BASE = {
  found: true,
  company: "Phena",
  summary: "Industrial computer vision for manufacturing quality control.",
  profile: { company_name: "Phena" },
  profile_sources: {},
  score: { final_score: 52, dimensions: {}, route_scorecards: {}, missing_evidence: [], red_flags: [] },
  fit: { matches: [] },
  facts: [],
  verification: { claims: [], red_flags: [] },
  trend: {},
  deep_profile: { founders: [], advisors: [], programs: [], reference_customers: [] },
};

const ASSESSMENTS = {
  Connect: {
    pillar: "Connect", status: "blocked",
    criteria: [
      // `blocking` mirrors what core/programs.py::_c actually serialises, and the distinction it
      // carries is the point: being a substitute is what the company IS, so no further evidence
      // changes it; an unevidenced deployment model is something it could go and publish.
      { id: "not_a_substitute", label: "Complements rather than replaces Siemens software",
        status: "unmet", note: "The closest portfolio match is classified a substitute.",
        evidence_url: "", required: true, blocking: true },
      { id: "cloud_or_edge", label: "Cloud and/or edge, delivered as a service",
        status: "unknown", note: "Deployment model not evidenced.", evidence_url: "",
        required: true, blocking: false },
    ],
    blockers: ["The closest portfolio match is classified a substitute."],
    next_steps: [], detail: {},
  },
  Collaborate: {
    pillar: "Collaborate", status: "unproven",
    criteria: [
      { id: "innovation_domain", label: "Falls in a named Collaborate domain", status: "met",
        note: "AI and data analytics (digital twins, pattern recognition)",
        evidence_url: "https://www.siemens.com/en-us/company/innovation/startups/collaborate/" },
      { id: "pilot_ready", label: "Technology mature enough to pilot", status: "unmet",
        note: "product 40 — below a working prototype in a real environment.", evidence_url: "" },
    ],
    blockers: [],
    next_steps: ["Technology mature enough to pilot: product 40 — below a working prototype."],
    detail: {},
  },
  Empower: {
    pillar: "Empower", status: "eligible",
    criteria: [
      { id: "bundle_match", label: "A Siemens Xcelerator bundle fits the build", status: "met",
        note: "Simcenter 3D — discounted simulation", evidence_url: "" },
    ],
    blockers: [], next_steps: [], detail: {},
  },
};

let RUN = BASE;

vi.mock("../api.js", () => ({
  api: {
    run: vi.fn(async () => RUN),
    evaluate: vi.fn(async () => RUN),
    audit: vi.fn(async () => ({ overrides: [] })),
    ask: vi.fn(async () => ({ answer: "", evidence: [] })),
  },
}));

/** One pillar's section, by the id the rail links to. */
function pillarSection(pillar) {
  return document.getElementById(`pillar-panel-${pillar}`);
}

async function renderScoringTab() {
  const { default: Profile } = await import("./Profile.jsx");
  return render(
    <MemoryRouter initialEntries={["/startup/1?tab=Scoring+%26+Fit"]}>
      <AppProvider>
        <Routes>
          <Route path="/startup/:id" element={<Profile />} />
        </Routes>
      </AppProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  RUN = BASE;
});

describe("programme criteria checklist", () => {
  it("distinguishes a blocked pillar from an unproven one, in each pillar's own section", async () => {
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS } };
    await renderScoringTab();
    await screen.findByRole("region", { name: "Scoring & Fit" });

    expect(within(pillarSection("Connect")).getByText("blocked")).toBeInTheDocument();
    expect(within(pillarSection("Collaborate")).getByText("unproven")).toBeInTheDocument();
    expect(within(pillarSection("Empower")).getByText("eligible")).toBeInTheDocument();
  });

  it("gives every pillar a section, including the ones that were not recommended", async () => {
    // The engine only emits a route_recommendation for a route that already qualified, so a
    // rejected pillar used to be simply absent — the reviewer was told nothing about the pillar
    // they were most likely asking about.
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS,
                                route_recommendations: [] } };
    await renderScoringTab();
    await screen.findByRole("region", { name: "Scoring & Fit" });
    for (const pillar of ["Connect", "Collaborate", "Empower"]) {
      expect(pillarSection(pillar)).toBeInTheDocument();
    }
  });

  it("marks which unmet criterion is the one that ends the conversation", async () => {
    /* Some unmet criteria are things a startup can go and acquire — a certification, API docs —
       and some are what the company IS. Both rendered as an identical red cross, so the checklist
       could not say which one is fatal. Connect's substitute criterion blocks; its unevidenced
       deployment does not. */
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS } };
    await renderScoringTab();
    await screen.findByRole("region", { name: "Scoring & Fit" });

    const blocking = within(pillarSection("Connect")).getByText(/blocks this route/i);
    expect(blocking.closest(".crit"))
      .toHaveTextContent("Complements rather than replaces Siemens software");
    // Connect's other failing criterion is merely unevidenced, so it must NOT carry the badge.
    expect(within(pillarSection("Connect")).getAllByText(/blocks this route/i)).toHaveLength(1);
  });

  it("states a blocker once, not twice", async () => {
    /* `assess_pillar` builds every blocker out of the note of the criterion that blocked. While
       the checklist and the blocker list lived in separate panels that repetition was invisible;
       in one section per pillar it printed the same sentence twice, a few lines apart. */
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS } };
    await renderScoringTab();
    await screen.findByRole("region", { name: "Scoring & Fit" });
    expect(within(pillarSection("Connect"))
      .getAllByText(/The closest portfolio match is classified a substitute/)).toHaveLength(1);
  });

  it("says what would have to be proven, not just that it was not", async () => {
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS } };
    await renderScoringTab();
    expect(await screen.findByText(/Nothing disqualifies it/i)).toBeInTheDocument();
    expect(screen.getByText(/below a working prototype in a real environment/i)).toBeInTheDocument();
  });

  it("carries each criterion's state as text, not only as colour", async () => {
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS } };
    await renderScoringTab();
    const criterion = (await screen.findByText("Falls in a named Collaborate domain"))
      .closest(".crit");
    // WCAG 1.4.1: the glyph is aria-hidden, so the word has to be in the accessible name.
    expect(criterion.textContent).toMatch(/met/);
  });

  it("says a run predates the criteria rather than rendering an empty checklist", async () => {
    // BASE has no dimensions either, so neither gate can be shown. "Nothing met" and "not assessed"
    // are opposite readings and an empty checklist is the wrong one.
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [] } };
    await renderScoringTab();
    await screen.findByRole("region", { name: "Scoring & Fit" });
    expect(within(pillarSection("Connect")).getByText(/predates the programme criteria/i))
      .toBeInTheDocument();
    expect(within(pillarSection("Connect")).queryByText(/^eligible$|^unproven$|^blocked$/))
      .toBeNull();
  });
});

describe("SFS panel", () => {
  it("names the financing line rather than saying only 'SFS'", async () => {
    RUN = {
      ...BASE,
      routing: {
        pillar: "Empower", secondary: [], sfs_relevant: true,
        sfs_line: "Vendor / sales finance",
        sfs_lines: [{ line: "Vendor / sales finance", fit: "strong",
                      rationale: "Sells physical equipment, so its own buyers are the counterparty.",
                      evidence_url: "https://phena.tech/products", missing: [] }],
        sfs_blockers: [],
      },
    };
    await renderScoringTab();
    const panel = (await screen.findByRole("heading", { name: /Siemens Financial Services/i }))
      .closest(".profile-section");
    expect(within(panel).getAllByText(/Vendor \/ sales finance/).length).toBeGreaterThan(0);
    expect(within(panel).getByText(/Sells physical equipment/)).toBeInTheDocument();
  });

  it("states what is still missing on a conditional line", async () => {
    RUN = {
      ...BASE,
      routing: {
        pillar: "Empower", secondary: [], sfs_relevant: false, sfs_line: "Vendor / sales finance",
        sfs_lines: [{ line: "Vendor / sales finance", fit: "conditional", rationale: "Sells equipment.",
                      evidence_url: "", missing: ["named B2B customers to extend financing to"] }],
        sfs_blockers: [],
      },
    };
    await renderScoringTab();
    expect(await screen.findByText(/named B2B customers to extend financing to/)).toBeInTheDocument();
  });

  it("gives the reason when no line applies", async () => {
    RUN = {
      ...BASE,
      routing: {
        pillar: "Empower", secondary: [], sfs_relevant: false, sfs_line: "", sfs_lines: [],
        sfs_blockers: ["No asset, project or equipment is evidenced — that the startup's customers "
                       + "are capital-intensive is a fact about them, not about this company."],
      },
    };
    await renderScoringTab();
    expect(await screen.findByText(/a fact about them, not about this company/)).toBeInTheDocument();
  });

  it("says it never looked, rather than saying no", async () => {
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], sfs_relevant: false } };
    await renderScoringTab();
    const panel = (await screen.findByRole("heading", { name: /Siemens Financial Services/i }))
      .closest(".profile-section");
    expect(within(panel).getByText("not assessed")).toBeInTheDocument();
    expect(within(panel).getByText(/Re-evaluate to assess it/i)).toBeInTheDocument();
  });
});

describe("criteria vs. scorecard", () => {
  it("explains a pillar that meets every criterion but is not a recommended route", async () => {
    /* Two gates answer different questions. Phena's live run met every published Collaborate
       criterion while its traction of 11.2 kept it off the Collaborate scorecard — and the panel
       showing "Collaborate: eligible" next to a scorecard list without Collaborate reads as the
       page contradicting itself unless it says which gate is the one it missed. */
    RUN = {
      ...BASE,
      routing: {
        pillar: "Empower", secondary: [],
        pillar_assessments: {
          // Collaborate's published criteria are all met; only the scorecard keeps it out.
          Collaborate: { ...ASSESSMENTS.Collaborate, status: "eligible", next_steps: [] },
          Empower: ASSESSMENTS.Empower,
        },
        route_recommendations: [{ route: "Empower", score: 62.6, status: "eligible",
                                  recommendation: "Offer Siemens tools/credits." }],
      },
    };
    await renderScoringTab();
    expect(await screen.findByText(/the Collaborate scorecard gate is what it has not cleared/i))
      .toBeInTheDocument();
  });

  it("says nothing extra when the pillar is both eligible and routed", async () => {
    RUN = {
      ...BASE,
      routing: {
        pillar: "Empower", secondary: [],
        pillar_assessments: { Empower: ASSESSMENTS.Empower },
        route_recommendations: [{ route: "Empower", score: 62.6, status: "eligible",
                                  recommendation: "Offer Siemens tools/credits." }],
      },
    };
    await renderScoringTab();
    await screen.findByRole("region", { name: "Scoring & Fit" });
    expect(screen.queryByText(/scorecard gate is what it has not cleared/i)).toBeNull();
  });
});
