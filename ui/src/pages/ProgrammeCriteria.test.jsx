import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProvider } from "../state.jsx";

/**
 * The Siemens programme criteria checklist and the SFS panel on the Scoring & Fit tab.
 *
 * These assert the distinction the criteria layer exists to make. A pillar that is BLOCKED and a
 * pillar that is merely UNPROVEN used to render identically — as the pillar not appearing — and a
 * reviewer could not tell "this is the wrong programme for them" from "we have not shown it yet",
 * which are opposite conclusions. Likewise the SFS chip was a bare boolean that was true for every
 * company ever evaluated; it now has to name a line, and has to be able to say it never looked.
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
      { id: "not_a_substitute", label: "Complements rather than replaces Siemens software",
        status: "unmet", note: "The closest portfolio match is classified a substitute.",
        evidence_url: "" },
      { id: "cloud_or_edge", label: "Cloud and/or edge, delivered as a service",
        status: "unknown", note: "Deployment model not evidenced.", evidence_url: "" },
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
  it("distinguishes a blocked pillar from an unproven one", async () => {
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [], pillar_assessments: ASSESSMENTS } };
    await renderScoringTab();

    const panel = (await screen.findByRole("heading", { name: /Siemens programme criteria/i }))
      .closest(".panel");
    expect(within(panel).getByText("blocked")).toBeInTheDocument();
    expect(within(panel).getByText("unproven")).toBeInTheDocument();
    expect(within(panel).getByText("eligible")).toBeInTheDocument();
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

  it("shows nothing for a run evaluated before the criteria existed", async () => {
    RUN = { ...BASE, routing: { pillar: "Empower", secondary: [] } };
    await renderScoringTab();
    await screen.findByRole("heading", { name: /Routing rationale/i });
    expect(screen.queryByRole("heading", { name: /Siemens programme criteria/i })).toBeNull();
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
      .closest(".panel");
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
      .closest(".panel");
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
    await screen.findByRole("heading", { name: /Siemens programme criteria/i });
    expect(screen.queryByText(/scorecard gate is what it has not cleared/i)).toBeNull();
  });
});
