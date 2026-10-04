import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useParams, useSearchParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Scoring & Fit after the redesign (output/ui-review/scoring-fit-ui-plan.md). What is pinned:
 * one recommendation instead of repeated criterion scores, pillar bars on one scale that never
 * override the backend band, a gap drawn as a gap, a pending total that never shows a partial
 * sum, and one keyboard-reachable detail interaction.
 */
vi.mock("../../../api.js", () => ({
  api: { runDepartments: vi.fn(), assessDepartment: vi.fn(), decideRun: vi.fn() },
}));

import { api } from "../../../api.js";
import FitSummary from "./FitSummary.jsx";
import FitComparison from "./FitComparison.jsx";
import TotalContribution from "./TotalContribution.jsx";
import TeamPanel from "./TeamPanel.jsx";
import MarketScorePanel from "./MarketScorePanel.jsx";
import DepartmentPanel from "./DepartmentPanel.jsx";

const crit = (rows) => rows.map(([id, label, score, anchor]) => ({ id, label, score, anchor, rationale: `${label} because`,
  evidence: [{ id: "E1", source: "deep_profile.founders[0].name", quote: "Oxolysis scale-up", url: "https://crunchbase.com/x" },
    { id: "E1", source: "summary", quote: "Oxolysis scale-up", url: "https://crunchbase.com/x" }],
  catalog: [{ id: "tool:gproms", name: "gPROMS", url: "https://siemens.test/gproms" }] }));
const EMPOWER = { status: "assessed", total: 9, band: "strong",
  criteria: crit([["tool_fit", "Tool fit", 3, "Tool directly supports a core startup activity"],
    ["benefit_fit", "Benefit fit", 3, "Material benefit"], ["actionability", "Actionability", 3, "Clear tool + next step"]]),
  statement: "gPROMS could help the startup scale Oxolysis by simulating the process.", next_step: "Book a gPROMS session.",
  notes: [], catalog: { name: "siemens_tools", checksum: "abcdef0123456789" } };
const CONNECT = { ...EMPOWER, criteria: crit([["industry_fit", "Industry fit", 3, "Directly targets"],
  ["topic_fit", "Topic fit", 3, "Core match"], ["ecosystem_value", "Ecosystem value", 3, "Clear target"]]),
  statement: "The startup could be relevant to the Xcelerator ecosystem because Oxolysis addresses circularity for chemicals." };
const COLLAB = { status: "assessed", total: 0, band: "no_match", provisional: true, needs: ["automation", "inspection"],
  criteria: crit([["capability_fit", "Capability fit", 0, "Does not provide"], ["need_fit", "Need fit", 0, "Does not address"],
    ["actionability", "Actionability", 0, "No plausible collaboration"]]).map((c) => ({ ...c, catalog: [] })),
  statement: "", next_step: "", notes: [] };
const RUN = {
  company: "Radical Dot", department: { id: "di", label: "Digital Industries", interests: ["automation"], demo: true },
  routing: { version: "pillar-route-v1", status: "assessed", pillar: "Empower",
    reasons: ["Empower is a strong match (9/9).", "Tool fit 3/3: because"], next_steps: ["Book a gPROMS session."], evidence: [] },
  assessment: {
    concepts: { needs_gaps: [{ term: "process scale-up" }], capabilities: [{ term: "chemical recycling" }], use_cases: [{ term: "circular chemicals" }] },
    siemens_fit: { score: 100, winner: "Empower", raw: 9, partial: false, status: "assessed" },
    scales: { pillars: { Empower: { tool_fit: ["No relevant capability", "Broad/indirect relevance", "Clearly relevant",
      "Tool directly supports a core startup activity"] } },
    team_ecosystem: { founder_experience: ["None", "First-time", "Some", "Relevant", "Significant leadership experience", "Serial"] } },
    pillars: { Empower: EMPOWER, Connect: CONNECT, Collaborate: COLLAB },
    weights: { traction: 0.3, siemens_fit: 0.35, team_ecosystem: 0.2, market: 0.15 },
    components: { traction: 65.7, siemens_fit: 100, team_ecosystem: 75, market: null }, total: null,
    team_ecosystem: { status: "assessed", points: 15, score_0_100: 75, band: "Strong",
      criteria: crit([["founder_experience", "Founder experience", 4, "Significant leadership experience"],
        ["domain_expertise", "Domain expertise", 4, "Strong domain expertise"],
        ["external_validation", "External validation", 4, "Well-known accelerator"], ["strategic_network", "Strategic network", 3, "Several partnerships"]]) },
  },
};

function Pillar() { return <p data-testid="pillar">{useSearchParams()[0].get("pillar") || "none"}</p>; }
function Opened() { return <p>opened run {useParams().id}</p>; }
const withRouter = (ui, entry = "/startup/1") => render(<MemoryRouter initialEntries={[entry]}><Routes>
  <Route path="/startup/1" element={<>{ui}<Pillar /></>} /><Route path="/startup/:id" element={<Opened />} /></Routes></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); api.runDepartments.mockResolvedValue({ departments: [] }); });

describe("FitSummary", () => {
  it("leads with one recommendation, one opportunity and one next step — no criterion scores", () => {
    withRouter(<FitSummary res={RUN} runId={1} detailed />);
    expect(screen.getByText("Recommended · Empower")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: EMPOWER.statement })).toBeInTheDocument();
    expect(screen.getByText("Book a gPROMS session.")).toBeInTheDocument();
    expect(screen.getByText("Connect is an equally strong alternative in this assessment.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Siemens Fit 100 out of 100" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Total score pending" })).toBeInTheDocument();
    // The four components as tiles; an unscored one says so rather than showing 0.
    const tiles = within(screen.getByRole("list", { name: "Score components" })).getAllByRole("listitem");
    expect(tiles.map((t) => t.textContent)).toEqual([
      "Traction6619.7 of 30 points", "Siemens Fit10035 of 35 points",
      "Team & Ecosystem7515 of 20 points", "Marketnot scoredup to 15 points"]);
    // The route's own reason strings, with their 3/3s, stay only in the audit disclosure.
    const audit = screen.getByText("Route reasoning (audit)").closest("details");
    expect(within(audit).getByText("Tool fit 3/3: because")).toBeInTheDocument();
    expect(screen.getAllByText(/3\/3/).every((el) => audit.contains(el))).toBe(true);
  });
});

describe("FitComparison", () => {
  it("shows all three routes on one scale, the tie honestly, and only the backend pick as Recommended", () => {
    withRouter(<FitComparison res={RUN} />);
    const empower = screen.getByRole("button", { name: /^Empower: 100 out of 100, Recommended/ });
    expect(screen.getByRole("button", { name: /^Connect: 100 out of 100, Alternative/ })).toBeInTheDocument();
    const collab = screen.getByRole("button", { name: /^Collaborate: 0 out of 100, No match to current needs, provisional/ });
    expect(empower).toHaveAttribute("aria-pressed", "true");
    expect(collab.querySelector(".ring-value").textContent).toBe("0");   // a scored zero reads 0, not a blank
  });

  it("moves between routes with the arrow keys and records the choice in ?pillar=", () => {
    withRouter(<FitComparison res={RUN} />);
    const empower = screen.getByRole("button", { name: /^Empower/ });
    empower.focus();
    fireEvent.keyDown(empower, { key: "ArrowRight" });
    expect(screen.getByTestId("pillar")).toHaveTextContent("Connect");
    expect(screen.getByRole("button", { name: /^Connect/ })).toHaveFocus();
    expect(screen.getByRole("heading", { name: "Where the offering could connect" })).toBeInTheDocument();
  });

  it("draws a no-match as a labelled gap, not a fabricated connection", () => {
    withRouter(<FitComparison res={RUN} detailed />, "/startup/1?pillar=Collaborate");
    expect(screen.getByRole("heading", { name: "No supported link to the current needs" })).toBeInTheDocument();
    expect(screen.getByText("No specific department use case identified")).toBeInTheDocument();
    expect(screen.getByText("inspection")).toBeInTheDocument();
    // Cited needs with no supported link are what it was assessed against, never "matched".
    expect(screen.getByText(/^The needs it was assessed against/)).toBeInTheDocument();
    expect(screen.getByText(/next step needs definition/)).toBeInTheDocument();
  });

  it("keeps exact scores in a row per criterion in Scoring method, with the band the engine chose", () => {
    withRouter(<FitComparison res={RUN} detailed />);
    const method = screen.getByRole("heading", { name: "Scoring method" }).closest("section");
    expect(within(method).getByRole("row", { name: /Tool fit 3\/3 Tool directly supports a core startup activity/ })).toBeInTheDocument();
    expect(within(method).getByRole("img", { name: "Empower total 9 of 9, band Strong" })).toBeInTheDocument();
    expect(screen.getAllByText(/\d\/3/).every((el) => method.contains(el))).toBe(true);
  });

  it("opens one criterion at a time from its cell, against its whole scale, and closes on a second press", async () => {
    const user = userEvent.setup();
    withRouter(<FitComparison res={RUN} />);
    const tool = screen.getByRole("button", { name: /^Tool fit: 3 of 3/ });
    await user.click(tool);
    expect(tool).toHaveAttribute("aria-expanded", "true");
    const region = screen.getByRole("region", { name: "Empower · criterion 1 of 3: Tool fit" });
    expect(within(region).getByText("Does a Siemens tool support something the startup actually does?")).toBeInTheDocument();
    // Every level of the rubric, with the one reached marked; the others are context, not claims.
    const levels = within(region).getAllByRole("listitem").filter((li) => li.closest(".crit-scale"));
    expect(levels.map((li) => li.querySelector(".crit-level").textContent)).toEqual(["3", "2", "1", "0"]);
    expect(levels[0]).toHaveAttribute("aria-current", "true");
    // Two records with the same quote and link are one entry, under a human label.
    expect(within(region).getAllByText("Oxolysis scale-up")).toHaveLength(1);
    expect(within(region).getByText("Founder background · crunchbase.com")).toBeInTheDocument();
    expect(within(region).queryByText("Record path")).toBeNull();     // the audit trail lives under Evidence
    expect(within(region).getByText("Matched Siemens tools")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Benefit fit: 3 of 3/ }));
    expect(screen.getByRole("region", { name: "Empower · criterion 2 of 3: Benefit fit" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Benefit fit: 3 of 3/ }));
    expect(screen.queryByRole("region", { name: /criterion/ })).toBeNull();
  });

  it("opening another route's criterion explores that route; Escape closes and keeps focus on the cell", async () => {
    const user = userEvent.setup();
    // A zero that still names the need it was held against.
    const collab = { ...COLLAB, criteria: COLLAB.criteria.map((c) => (c.id === "need_fit" ? { ...c, catalog: [{ id: "need:automation", name: "automation" }] } : c)) };
    withRouter(<FitComparison res={{ ...RUN, assessment: { ...RUN.assessment, pillars: { ...RUN.assessment.pillars, Collaborate: collab } } }} />);
    const need = screen.getByRole("button", { name: /^Need fit: 0 of 3/ });
    await user.click(need);
    expect(screen.getByTestId("pillar")).toHaveTextContent("Collaborate");
    expect(within(screen.getByRole("region", { name: /Need fit/ })).getByText("Compared against department needs")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("region", { name: /Need fit/ })).toBeNull();
    expect(need).toHaveFocus();
  });

  it("shows Connect's ecosystem gap as the nearest sellers, not as matches, and keeps them out of the audience", async () => {
    const user = userEvent.setup();
    const seller = (id, name, overlap, differentiator = "") => ({ id: `seller:${id}`, name, url: `https://${id}.test`, overlap, differentiator, evidence: [] });
    const gap = { id: "ecosystem_gap", label: "Ecosystem gap", score: 1, basis: "derived", anchor: "Partially represented",
      rationale: "1 seller(s) already offer this", evidence: [], catalog: [{ id: "seller:plas", name: "PlasCo" }],
      neighbours: [seller("dist", "Elsewhere", "distinct"), seller("plas", "PlasCo", "equivalent"),
        seller("chem", "ChemLoop", "equivalent", "Runs at ambient pressure")] };
    const connect = { ...CONNECT, criteria: [gap, ...CONNECT.criteria.slice(1)] };
    withRouter(<FitComparison res={{ ...RUN, assessment: { ...RUN.assessment, pillars: { ...RUN.assessment.pillars, Connect: connect } } }} />);
    await user.click(screen.getByRole("button", { name: /^Ecosystem gap: 1 of 3/ }));
    const region = screen.getByRole("region", { name: /Ecosystem gap/ });
    expect(within(region).getByText("Nearest Xcelerator sellers")).toBeInTheDocument();
    const names = within(region).getAllByRole("link").map((a) => a.textContent);
    expect(names.slice(0, 3)).toEqual(["PlasCo", "ChemLoop", "Elsewhere"]);          // same offering first
    expect(within(region).getByText("Differs: Runs at ambient pressure")).toBeInTheDocument();
    expect(within(region).getByText("Nothing evidenced sets the startup apart.")).toBeInTheDocument();
    expect(within(region).queryByText(/^Matched/)).toBeNull();
  });

  it("says in Connect's third step whether connecting makes sense, point by point, with sources", async () => {
    const user = userEvent.setup();
    const value = { id: "ecosystem_value", label: "Ecosystem value", score: 2, basis: "derived", path: "open_space",
      anchor: "An audience with a clear fit or a good market, or open space with both", rationale: "Open space.",
      signals: { audience: false, industry_topic: true, market: true }, audience: [], evidence: [], catalog: [] };
    const connect = { ...CONNECT, criteria: [...CONNECT.criteria.slice(0, 2), value],
      case: { verdict: "worth_exploring", title: "Worth exploring, with open questions", summary: "Nobody in the ecosystem uses it yet.",
        points: [{ tone: "plus", text: "Good market signals: growth 12% CAGR.", sources: ["https://m.test/report"] },
          { tone: "minus", text: "No Xcelerator seller was found who would use, integrate or resell it.", sources: [] }] } };
    withRouter(<FitComparison res={{ ...RUN, assessment: { ...RUN.assessment, pillars: { ...RUN.assessment.pillars, Connect: connect } } }} />, "/startup/1?pillar=Connect");
    const map = screen.getByRole("group", { name: "Connect opportunity map" });
    expect(within(map).getByText("Worth exploring, with open questions")).toBeInTheDocument();
    const points = within(map).getByRole("list", { name: "Why" });
    expect(within(points).getByText(/Good market signals/).closest("li")).toHaveTextContent("In favour:");
    expect(within(points).getByRole("link", { name: "m.test" })).toHaveAttribute("href", "https://m.test/report");
    expect(within(points).getByText(/No Xcelerator seller/).closest("li")).toHaveTextContent("Against:");
    await user.click(screen.getByRole("button", { name: /^Ecosystem value: 2 of 3/ }));
    const region = screen.getByRole("region", { name: /Ecosystem value/ });
    expect(within(region).getByText("Open space: no ecosystem audience")).toBeInTheDocument();
    const signals = within(region).getAllByRole("listitem").filter((li) => li.closest(".value-signals")).map((li) => li.textContent);
    expect(signals).toEqual(["No An ecosystem audience", "Yes A clear industry & topic fit", "Yes A good market signal"]);
  });

  it("opens a criterion from Scoring method too", async () => {
    const user = userEvent.setup();
    withRouter(<FitComparison res={RUN} detailed />);
    await user.click(screen.getByRole("button", { name: "How Actionability was scored" }));
    expect(screen.getByRole("region", { name: "Empower · criterion 3 of 3: Actionability" })).toBeInTheDocument();
  });

  it("stops following the window once a criterion is closed", async () => {
    const off = vi.spyOn(window, "removeEventListener");
    const user = userEvent.setup();
    withRouter(<FitComparison res={RUN} />);
    await user.click(screen.getByRole("button", { name: /^Tool fit: 3 of 3/ }));
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(off).toHaveBeenCalledWith("resize", expect.any(Function));
    off.mockRestore();
  });

  it("says a pillar was not assessed and how to retry, which is not a no-match", () => {
    const res = { ...RUN, assessment: { ...RUN.assessment, pillars: { ...RUN.assessment.pillars,
      Empower: { status: "unassessed", message: "The assessment model is not configured." } } } };
    withRouter(<FitComparison res={res} />);
    expect(screen.getByText("Not assessed", { selector: ".verdict" })).toBeInTheDocument();
    expect(screen.getByText(/Refresh the evaluation/)).toBeInTheDocument();
  });

  it("shows a skeleton while a pillar is still being assessed", () => {
    withRouter(<FitComparison res={{ streaming: true, department: RUN.department }} />);
    expect(screen.getByRole("status", { name: "Empower is being assessed" })).toBeInTheDocument();
  });
});

describe("TotalContribution", () => {
  it("draws earned points against each component's maximum and never shows a partial sum", () => {
    render(<TotalContribution res={RUN} />);
    expect(screen.getByRole("img", { name: "Traction: 19.7 of 30 points (score 66/100)" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Siemens Fit: 35 of 35 points (score 100/100)" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Team & Ecosystem: 15 of 20 points (score 75/100)" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Market: not scored, up to 15 points" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Total pending · Market not scored yet");
    expect(screen.queryByText("69.7")).toBeNull();                      // 19.7 + 35 + 15 is never shown
  });

  it("links each component to the section that scores it", () => {
    render(<TotalContribution res={RUN} />);
    const hrefs = ["Traction", "Siemens Fit", "Team & Ecosystem", "Market"].map((name) =>
      screen.getByRole("link", { name: new RegExp(`^${name}: .*Go to ${name}$`) }).getAttribute("href"));
    expect(hrefs).toEqual(["#scoring-traction", "#scoring-routes", "#scoring-team", "#scoring-market"]);
  });

  it("shows the total when all four are scored", () => {
    const res = { ...RUN, assessment: { ...RUN.assessment, components: { ...RUN.assessment.components, market: 73.3 }, total: 80.7 } };
    render(<TotalContribution res={res} />);
    expect(screen.getByText("80.7")).toBeInTheDocument();
  });

  it("labels a legacy run instead of inventing a total", () => {
    render(<TotalContribution res={{ company: "Old" }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/Legacy run/);
  });
});

describe("Team & Ecosystem", () => {
  it("draws the radar with names only and puts each criterion in a box that opens its reasoning", async () => {
    const user = userEvent.setup();
    render(<TeamPanel res={RUN} />);
    const radar = screen.getByRole("img", { name: /^Team and ecosystem: Founder experience 4 of 5, Domain expertise 4 of 5/ });
    expect([...radar.querySelectorAll("text")].map((t) => t.textContent)).toEqual(["Founder", "Domain", "Validation", "Network"]);
    const boxes = within(screen.getByRole("group", { name: "Team and ecosystem criteria" })).getAllByRole("button");
    expect(boxes).toHaveLength(4);
    const founder = screen.getByRole("button", { name: "Founder experience: 4 of 5, Significant leadership experience" });
    await user.click(founder);
    const region = screen.getByRole("region", { name: "Team & Ecosystem: Founder experience" });
    expect(within(region).getByText("Founder experience because")).toBeInTheDocument();
    expect(within(region).getAllByRole("listitem").filter((li) => li.closest(".crit-scale"))).toHaveLength(6);
    expect(radar.querySelector("text.on")).toHaveTextContent("Founder");
    await user.click(founder);
    expect(screen.queryByRole("region", { name: /Founder experience/ })).toBeNull();
  });

  it("says where each market score came from", () => {
    const market = { status: "assessed", points: 11, score_0_100: 73.3, band: "Attractive Market", notes: [],
      criteria: [{ id: "market_size", label: "Market size", score: 4, anchor: "Very large market", basis: "cited_figure",
        value: "USD 26.88 billion", source_url: "https://reports.test/m", evidence: [], areas: [] },
      { id: "market_growth", label: "Market growth", score: 2, anchor: "Low growth", basis: "model_judgment", evidence: [], areas: [] },
      { id: "strategic_relevance", label: "Strategic relevance", score: 5, anchor: "Core strategic area", basis: "model_judgment",
        evidence: [], areas: ["Plastics"] }] };
    render(<MarketScorePanel res={{ market }} detailed />);
    expect(screen.getByRole("link", { name: "source" })).toHaveAttribute("href", "https://reports.test/m");
    expect(screen.getByText(/no figure cited \(max 2\)/)).toBeInTheDocument();
    expect(screen.getByText("Plastics")).toBeInTheDocument();
  });

  it("says why market was not assessed instead of showing a score", () => {
    render(<MarketScorePanel res={{ market: { status: "unassessed", message: "The assessment model is not configured." } }} />);
    expect(screen.getByText("Not assessed")).toBeInTheDocument();
  });
});

const pick = async (id) => {
  await waitFor(() => expect(document.querySelector("ix-select")).not.toBeNull());
  fireEvent(document.querySelector("ix-select"), new CustomEvent("valueChange", { detail: id }));
};

describe("DepartmentPanel", () => {
  it("opens the other department's saved current run", async () => {
    api.runDepartments.mockResolvedValue({ departments: [
      { id: "di", label: "Digital Industries", demo: true, run_id: 1, current: true },
      { id: "si", label: "Smart Infrastructure", demo: false, run_id: 42, current: true }] });
    withRouter(<DepartmentPanel res={RUN} runId={1} />);
    await pick("si");
    expect(await screen.findByText("opened run 42")).toBeInTheDocument();
  });

  it("offers an explicit assessment when that department has no run", async () => {
    api.runDepartments.mockResolvedValue({ departments: [
      { id: "di", label: "Digital Industries", demo: true, run_id: 1, current: true },
      { id: "si", label: "Smart Infrastructure", demo: false, run_id: null, current: false }] });
    api.assessDepartment.mockResolvedValue({ run_id: 77 });
    withRouter(<DepartmentPanel res={RUN} runId={1} />);
    await pick("si");
    fireEvent.click(await screen.findByText("Assess for Smart Infrastructure"));
    expect(await screen.findByText("opened run 77")).toBeInTheDocument();
  });

  it("labels a legacy run", async () => {
    withRouter(<DepartmentPanel res={{ company: "Old" }} runId={5} />);
    expect(await screen.findByText(/Legacy run: assessed before departments existed/)).toBeInTheDocument();
  });
});
