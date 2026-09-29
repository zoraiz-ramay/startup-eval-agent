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
    departments: vi.fn(async () => ({departments:[{id:"di",label:"Digital Industries",interests:["automation"],demo:true}]})),
    assessRun: vi.fn(async () => ({score:{status:"unavailable"},department_fit:{status:"unavailable",message:"Assessment unavailable"}})),
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

describe("partnership placeholders", () => {
  it("keeps the three partnership panels empty while under development", async () => {
    RUN = {...BASE, routing:{pillar:"Empower", secondary:[], pillar_assessments:ASSESSMENTS}};
    await renderScoringTab();
    await screen.findByRole("region", {name:"Scoring & Fit"});
    for (const pillar of ["Empower", "Connect", "Collaborate"]) {
      expect(within(pillarSection(pillar)).getByText("Under development")).toBeInTheDocument();
      expect(pillarSection(pillar).querySelector(".crit")).toBeNull();
    }
    expect(screen.queryByText("Challenge-library match")).toBeNull();
    expect(screen.queryByText("Flags & gaps")).toBeNull();
    expect(screen.queryByText("Override routing")).toBeNull();
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
