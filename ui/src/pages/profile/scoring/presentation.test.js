import { describe, expect, it } from "vitest";
import { catalogGroups, contributions, dedupeEvidence, evidenceLabel, opportunity, pillarRows, signals } from "./presentation.js";

/* The adapter reads the engine's decisions; these pin that it never makes one. */
const p = (total, band, third, extra = {}) => ({ status: "assessed", total, band,
  criteria: [{ id: "tool_fit", score: 3, catalog: [] }, { id: "benefit_fit", score: 3, catalog: [] },
    { id: extra.third || "actionability", score: third, catalog: [] }], ...extra });
const run = (pillars, pick = "Empower", extra = {}) => ({ department: { id: "di" },
  routing: { version: "pillar-route-v1", pillar: pick }, assessment: { pillars, ...extra } });

describe("pillarRows", () => {
  it("normalises x/9 to 0–100 and keeps a fixed order", () => {
    const rows = pillarRows(run({ Empower: p(9, "strong", 3), Connect: p(7, "strong", 2, { third: "ecosystem_value" }), Collaborate: p(0, "no_match", 0) }));
    expect(rows.map((r) => [r.name, r.value])).toEqual([["Empower", 100], ["Connect", 78], ["Collaborate", 0]]);
  });

  it("labels only the backend-selected pillar Recommended, even on a tie", () => {
    const rows = pillarRows(run({ Empower: p(9, "strong", 3), Connect: p(9, "strong", 3, { third: "ecosystem_value" }) }, "Connect"));
    expect(rows.find((r) => r.name === "Connect").role).toBe("Recommended");
    expect(rows.find((r) => r.name === "Empower").role).toBe("Alternative");
  });

  it("says Collaborate is not recommended when every department scored 0/9", () => {
    const res = { ...run({ Empower: p(5, "review", 2), Collaborate: p(0, "no_match", 0) }, "Defer"),
      departments: { recommended: null, basis: "no_collaborate_match" } };
    expect(pillarRows(res).find((r) => r.name === "Collaborate").role).toBe("Not recommended · 0/9 for every department");
  });

  it("never offers a seller the startup duplicates as an ecosystem audience", () => {
    const pillar = { criteria: [{ id: "ecosystem_gap", basis: "derived", catalog: [{ id: "seller:rival", name: "Rival" }] },
      { id: "ecosystem_value", catalog: [{ id: "seller:oem", name: "OEM" }] }] };
    expect(catalogGroups(pillar).sellers.map((s) => s.name)).toEqual(["OEM"]);
  });

  it("keeps the backend band: a high total with low actionability is Review and flagged", () => {
    const [empower] = pillarRows(run({ Empower: p(7, "review", 1) }, "Defer"));
    expect(empower).toMatchObject({ value: 78, role: "Review", lowActionability: true });
  });

  it("separates a scored zero, a not-assessed pillar, a pending one and a legacy run", () => {
    const rows = pillarRows(run({ Empower: p(0, "no_match", 0), Connect: { status: "unassessed", message: "no catalog" } }, "Defer"));
    expect(rows[0]).toMatchObject({ state: "assessed", value: 0, role: "No match" });
    expect(rows[1]).toMatchObject({ state: "unassessed", value: null, role: "Not assessed", message: "no catalog" });
    expect(rows[2]).toMatchObject({ state: "unassessed", value: null });
    expect(pillarRows({ streaming: true })[0].state).toBe("pending");
    expect(pillarRows({ company: "Old" })[0].state).toBe("legacy");
  });

  it("marks a provisional no-match as against current needs", () => {
    const rows = pillarRows(run({ Collaborate: p(0, "no_match", 0, { provisional: true }) }));
    expect(rows[2].role).toBe("No match to current needs");
  });
});

describe("contributions", () => {
  const res = { department: { id: "di" }, assessment: { weights: { traction: 0.3, siemens_fit: 0.35, team_ecosystem: 0.2, market: 0.15 },
    components: { traction: 65.7, siemens_fit: 100, team_ecosystem: 75, market: null }, total: null } };

  it("puts every component on the points scale with its maximum", () => {
    const c = contributions(res);
    expect(c.rows.map((r) => [r.key, r.earned, r.max])).toEqual([["traction", 19.7, 30], ["siemens_fit", 35, 35],
      ["team_ecosystem", 15, 20], ["market", null, 15]]);
  });

  it("keeps the total pending and names what is missing, never summing the rest", () => {
    expect(contributions(res)).toMatchObject({ total: null, status: "pending", missing: ["Market"] });
  });

  it("treats a scored zero as zero, not missing", () => {
    const c = contributions({ ...res, assessment: { ...res.assessment, components: { traction: 0, siemens_fit: 0, team_ecosystem: 0, market: 0 }, total: 0 } });
    expect(c.rows.every((r) => r.earned === 0)).toBe(true);
    expect(c.status).toBe("complete");
  });
});

describe("catalog and evidence", () => {
  it("merges catalog entries cited by several criteria and groups them by kind", () => {
    const pillar = { criteria: [{ catalog: [{ id: "industry:chemicals", name: "Chemicals" }, { id: "seller:acme", name: "Acme" }] },
      { catalog: [{ id: "industry:chemicals", name: "Chemicals" }, { id: "topic:quality", name: "Quality" }] }] };
    const g = catalogGroups(pillar);
    expect(g.all.map((e) => e.id)).toEqual(["industry:chemicals", "seller:acme", "topic:quality"]);
    expect(g.industries).toHaveLength(1);
    expect(g.sellers.map((s) => s.name)).toEqual(["Acme"]);
  });

  it.each([
    [{ source: "deep_profile.founders[0].name", url: "https://www.crunchbase.com/p" }, "Founder background · crunchbase.com"],
    [{ source: "facts[3].value", url: "" }, "Web research"],
    [{ source: "search:Connect", url: "https://acme.example/about" }, "Targeted web search · acme.example"],
    [{ source: "something.unknown" }, "Research record"],
  ])("labels %o for people", (e, label) => expect(evidenceLabel(e)).toBe(label));

  it("shows identical evidence once and keeps every reference", () => {
    const list = dedupeEvidence([{ source: "summary", quote: "Q", url: "u" }, { source: "facts[1].value", quote: "Q", url: "u" }]);
    expect(list).toHaveLength(1);
    expect(list[0].refs).toEqual(["summary", "facts[1].value"]);
  });
});

describe("opportunity", () => {
  it("never draws a link the assessment did not support", () => {
    const res = run({ Collaborate: p(0, "no_match", 0, { needs: ["automation"], statement: "" }) });
    const o = opportunity(res, "Collaborate");
    expect(o.gap).toBe(true);
    expect(o.nodes[1].items).toEqual([{ text: "automation", tag: "Department need" }]);
    expect(o.nodes[2].statement).toBe("");
    expect(o.nodes[2].empty).toBe("No specific department use case identified");
  });

  it("lists every stated need a no-match was assessed against, and suggests another department", () => {
    const collab = p(1, "no_match", 0, { needs: ["Process Automation", "Data Cleansing"], statement: "" });
    collab.criteria[1].catalog = [{ id: "need:si-01-1", name: "Process Automation", description: "Automating repetitive tasks." }];
    const res = { ...run({ Collaborate: collab }), department: { id: "si", label: "Smart Infrastructure", demo: false } };
    const o = opportunity(res, "Collaborate");
    expect(o.nodes[1].items.map((i) => [i.text, i.detail || ""])).toEqual([
      ["Process Automation", "Automating repetitive tasks."], ["Data Cleansing", ""]]);
    expect(o.nextStep).toBe("None of Smart Infrastructure's stated needs is addressed; consider assessing it for another department.");
  });

  it("puts the needs closest to the startup first when nothing was matched, and says so", () => {
    const collab = p(0, "no_match", 0, { needs: ["Asset Tracking", "Defect Detection", "Cybersecurity"], statement: "",
      closest_needs: ["Defect Detection", "Not this department's"] });
    const o = opportunity(run({ Collaborate: collab }), "Collaborate");
    expect(o.nodes[1].items.map((i) => [i.text, i.tag])).toEqual([
      ["Defect Detection", "Closest to the startup"], ["Asset Tracking", "Department need"], ["Cybersecurity", "Department need"]]);
  });

  it("gives Connect's third step the audience with its role and the case for connecting", () => {
    const connect = p(8, "strong", 2, { third: "ecosystem_value", statement: "s",
      case: { verdict: "makes_sense", title: "Connecting makes sense", summary: "x", points: [] } });
    connect.criteria[2].audience = [{ id: "seller:oem", name: "OEM", role: "integrate", reason: "Wires it into lines.", url: "https://oem.test" }];
    const node = opportunity(run({ Connect: connect }, "Connect"), "Connect").nodes[2];
    expect(node.case.verdict).toBe("makes_sense");
    expect(node.items).toEqual([{ text: "OEM", tag: "Would integrate it", detail: "Wires it into lines.", url: "https://oem.test" }]);
  });

  it("tags each startup term with its kind and the sentence it was grounded in", () => {
    const res = run({ Empower: p(9, "strong", 3, { statement: "" }) });
    res.assessment.pillars.Empower.criteria[0].evidence = [{ id: "E4", quote: "Scaling Oxolysis to 10 kt.", url: "https://x.test" }];
    res.assessment.concepts = { needs_gaps: [{ term: "scale-up", citations: ["E4"] }], use_cases: [{ term: "acetic acid", citations: ["E9"] }] };
    const o = opportunity(res, "Empower");
    expect(o.nodes[0].items).toEqual([
      { text: "scale-up", tag: "Need", quote: "Scaling Oxolysis to 10 kt.", url: "https://x.test" },
      { text: "acetic acid", tag: "Use case", quote: "", url: "" }]);   // an unresolved citation shows no quote
    expect(o.nodes.every((n) => n.hint)).toBe(true);
  });

  it("shows low actionability as a next step that needs definition", () => {
    const s = signals(p(7, "review", 1), "Empower");
    expect(s[2]).toMatchObject({ weak: true, text: "Next step needs definition" });
  });
});

import { divisionDisplay, formatMoney, scoringNotices } from "./presentation.js";

describe("display formatting", () => {
  it.each([[2831100, "€2.8M"], [23116800000, "€23.1B"], [450000, "€450k"], [120e6, "€120M"], [950, "€950"], [null, "—"]])(
    "formats %s as %s", (v, text) => expect(formatMoney(v)).toBe(text));

  it("says what a traction division holds in words", () => {
    expect(divisionDisplay({ id: "funding", status: "evidenced", value: "2831100", value_eur: 2831100 })).toBe("€2.8M raised");
    expect(divisionDisplay({ id: "employees", status: "evidenced", value: "8" })).toBe("8 people");
    expect(divisionDisplay({ id: "employees", status: "evidenced", value: "11-50" })).toBe("11+ people");
    expect(divisionDisplay({ id: "customers", status: "evidenced", value: "3 named customer(s)",
      items: [{ counted: true, size: "large_enterprise" }, { counted: true, size: "sme" }, { counted: false }] })).toBe("1 big-name + 1 SME");
    expect(divisionDisplay({ id: "revenue", status: "zero_evidenced" })).toBe("Sourced as pre-revenue");
    expect(divisionDisplay({ id: "revenue", status: "unknown" })).toBe("No evidence");
  });
});

describe("scoringNotices", () => {
  it("raises nothing for a complete, configured run", () => {
    expect(scoringNotices({ department: { id: "di", demo: false }, assessment: { total: 80, siemens_fit: { partial: false } } })).toEqual([]);
  });

  it("does not call a streaming run's total pending before it could exist", () => {
    expect(scoringNotices({ streaming: true, department: { id: "di" }, assessment: { total: null } })).toEqual([]);
  });
});
