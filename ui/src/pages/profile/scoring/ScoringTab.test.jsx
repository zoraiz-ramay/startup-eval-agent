import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

/* The page shell: the Summary / Detailed toggle (remembered per browser), the iX notices that
   carry the qualifiers a reader must not miss, and the Actions menu. */
vi.mock("../../../api.js", () => ({
  api: { runDepartments: vi.fn(async () => ({ departments: [] })), assessDepartment: vi.fn(), decideRun: vi.fn() },
}));

import ScoringTab, { VIEW_KEY } from "./ScoringTab.jsx";

const crit = (ids) => ids.map(([id, label, score]) => ({ id, label, score, anchor: `${label} anchor`, rationale: "r",
  evidence: [], catalog: [] }));
const RUN = {
  company: "Acme", department: { id: "di", label: "Digital Industries", interests: ["automation"], demo: true },
  routing: { version: "pillar-route-v1", status: "assessed", pillar: "Empower", reasons: ["Empower is strong."],
    next_steps: ["Book a call."], evidence: [] },
  assessment: {
    pillars: {
      Empower: { status: "assessed", total: 8, band: "strong", statement: "Tool could help the startup by X.", next_step: "Book a call.",
        criteria: crit([["tool_fit", "Tool fit", 3], ["benefit_fit", "Benefit fit", 3], ["actionability", "Actionability", 2]]), notes: [] },
      Connect: { status: "unassessed", message: "Workbook missing" },
    },
    siemens_fit: { score: 89, winner: "Empower", raw: 8, partial: true, status: "assessed" },
    weights: { traction: 0.3, siemens_fit: 0.35, team_ecosystem: 0.2, market: 0.15 },
    components: { traction: 50, siemens_fit: 89, team_ecosystem: null, market: 60 }, total: null,
  },
};
const renderTab = (props = {}) => render(<MemoryRouter><ScoringTab res={RUN} runId={1} {...props} /></MemoryRouter>);
const toggle = (name) => [...document.querySelectorAll("ix-toggle-button")].find((b) => b.textContent === name);

beforeEach(() => localStorage.clear());

describe("ScoringTab", () => {
  it("opens in the summary view and keeps the reasoning out of it", () => {
    renderTab();
    expect(toggle("Summary").pressed).toBe(true);
    expect(screen.queryByText("Scoring method")).toBeNull();
    expect(screen.queryByText("Route reasoning (audit)")).toBeNull();
  });

  it("switches to the detailed view and remembers it", async () => {
    renderTab();
    fireEvent.click(toggle("Detailed"));
    expect(await screen.findByText("Route reasoning (audit)")).toBeInTheDocument();
    expect(localStorage.getItem(VIEW_KEY)).toBe("detailed");
    expect(toggle("Detailed").pressed).toBe(true);
    expect(toggle("Summary").pressed).toBe(false);
  });

  it("starts in the view the reviewer last chose", () => {
    localStorage.setItem(VIEW_KEY, "detailed");
    renderTab();
    expect(screen.getByText("Scoring method")).toBeInTheDocument();
  });

  it("raises provisional needs, a partial Siemens Fit and a pending total as notices", () => {
    renderTab();
    const notices = [...document.querySelectorAll("ix-message-bar")];
    expect(notices.map((n) => n.textContent)).toEqual([
      expect.stringMatching(/^Collaborate is provisional\. It is scored against example Digital Industries needs/),
      expect.stringMatching(/^Siemens Fit is partial\. Connect and Collaborate could not be assessed/),
      expect.stringMatching(/^Total pending\. Team & Ecosystem not scored yet/),
    ]);
    expect(notices.map((n) => n.type)).toEqual(["warning", "info", "info"]);
  });

  it("offers re-evaluation, a copy link and the evidence in the Actions menu", async () => {
    const onRefresh = vi.fn();
    renderTab({ onRefresh });
    await waitFor(() => expect(document.querySelector("ix-dropdown-button")).not.toBeNull());
    const items = [...document.querySelectorAll("ix-dropdown-button ix-dropdown-item")];
    expect(items.map((i) => i.label)).toEqual(["Re-evaluate with fresh data", "Copy link to this view", "Open evidence"]);
    fireEvent.click(items[0]);
    expect(onRefresh).toHaveBeenCalled();
  });
});
