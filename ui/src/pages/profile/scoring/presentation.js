/* The presentation adapter for Scoring & Fit.
 *
 * Pure functions from a stored run to what the page shows: normalised pillar bars, weighted
 * contributions, opportunity maps, qualitative signals and human evidence labels. It reads the
 * engine's decisions and never makes one — no route is recomputed here and no link between a
 * startup concept and a catalog entry is drawn unless the saved assessment cited it.
 */

export const PILLAR_ORDER = ["Empower", "Connect", "Collaborate"];
export const COMPONENTS = [
  ["traction", "Traction"], ["siemens_fit", "Siemens Fit"],
  ["team_ecosystem", "Team & Ecosystem"], ["market", "Market"],
];
const DEFAULT_WEIGHTS = { traction: 0.3, siemens_fit: 0.35, team_ecosystem: 0.2, market: 0.15 };
const BAND_LABEL = { strong: "Strong", review: "Review", no_match: "No match" };
const THIRD = { Empower: "actionability", Collaborate: "actionability", Connect: "ecosystem_value" };

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** One comparison row per pillar, in a fixed order that never moves as results arrive. */
export function pillarRows(res) {
  const pillars = res?.assessment?.pillars || {};
  const recommended = res?.routing?.version === "pillar-route-v1" ? res.routing.pillar : null;
  return PILLAR_ORDER.map((name) => {
    const p = pillars[name];
    if (!p) {
      const state = res?.streaming ? "pending" : res?.department ? "unassessed" : "legacy";
      return { name, state, value: null, band: null, role: state === "pending" ? "Assessing…" : "Not assessed",
        provisional: false, lowActionability: false, message: "" };
    }
    if (p.status !== "assessed") {
      return { name, state: "unassessed", value: null, band: null, role: "Not assessed",
        provisional: Boolean(p.provisional), lowActionability: false, message: p.message || "" };
    }
    const third = (p.criteria || []).find((c) => c.id === THIRD[name]);
    const noDepartment = name === "Collaborate" && res?.departments?.basis === "no_collaborate_match";
    const role = name === recommended ? "Recommended"
      : noDepartment ? "Not recommended · 0/9 for every department"
      : p.band === "strong" ? "Alternative"
      : p.band === "review" ? "Review"
      : p.provisional ? "No match to current needs" : "No match";
    return {
      name, state: "assessed", value: Math.round((100 * p.total) / 9), band: p.band,
      bandLabel: BAND_LABEL[p.band], role, provisional: Boolean(p.provisional),
      // A long bar must not hide that the route still has no concrete next step.
      lowActionability: Boolean(third && third.score < 2 && p.total >= 4),
      message: "",
    };
  });
}

/** Weighted contributions: every row on the same points scale, capacity = weight × 100. */
export function contributions(res) {
  const a = res?.assessment || {};
  const weights = a.weights || DEFAULT_WEIGHTS;
  const parts = a.components || {
    traction: res?.traction?.status === "scored" ? res.traction.score_0_100 : null,
    siemens_fit: null,
    team_ecosystem: res?.team_ecosystem?.status === "assessed" ? res.team_ecosystem.score_0_100 : null,
    market: res?.market?.status === "assessed" ? res.market.score_0_100 : null,
  };
  const rows = COMPONENTS.map(([key, label]) => {
    const value = num(parts[key]);
    const max = Math.round(weights[key] * 100);
    return { key, label, max, value, earned: value == null ? null : Math.round(weights[key] * value * 10) / 10 };
  });
  const total = num(a.total);
  const missing = rows.filter((r) => r.value == null).map((r) => r.label);
  return { rows, total, missing, status: total != null ? "complete" : "pending" };
}

/** Catalog entries a pillar's criteria cited, merged by id, grouped for display. Connect's
    Ecosystem gap is left out: its entries are sellers that already offer the same thing, which
    are competitors to the startup, not an audience it could reach. */
export function catalogGroups(pillar) {
  const seen = new Map();
  for (const c of pillar?.criteria || []) {
    if (c.basis === "derived") continue;
    for (const e of c.catalog || []) if (e?.id && !seen.has(e.id)) seen.set(e.id, e);
  }
  const all = [...seen.values()];
  const kind = (e) => e.id.split(":")[0];
  return {
    all,
    tools: all.filter((e) => kind(e) === "tool"),
    needs: all.filter((e) => kind(e) === "need"),
    industries: all.filter((e) => kind(e) === "industry"),
    topics: all.filter((e) => kind(e) === "topic"),
    sellers: all.filter((e) => kind(e) === "seller"),
  };
}

const CONCEPT_GROUPS = { Empower: ["needs_gaps", "use_cases", "technologies"],
  Collaborate: ["capabilities", "technologies", "use_cases"], Connect: ["use_cases", "technologies", "industries"] };
const CONCEPT_KIND = { needs_gaps: "Need", use_cases: "Use case", technologies: "Technology",
  capabilities: "Capability", industries: "Industry", topics: "Topic" };
const CATALOG_KIND = { tool: "Siemens tool", need: "Department need", industry: "Industry", topic: "Topic", seller: "Partner" };

/* Every record the pillar criteria cited, by id. Concepts cite the same evidence ids, so a term
   can show the sentence it was grounded in without the page holding any evidence of its own. */
export function evidenceIndex(res) {
  const out = new Map();
  for (const p of Object.values(res?.assessment?.pillars || {})) {
    for (const c of p?.criteria || []) for (const e of c.evidence || []) if (e?.id && !out.has(e.id)) out.set(e.id, e);
  }
  return out;
}

function concepts(res, name, limit = 8) {
  const c = res?.assessment?.concepts || {};
  const index = evidenceIndex(res);
  const seen = new Set();
  const out = [];
  for (const g of CONCEPT_GROUPS[name]) for (const item of c[g] || []) {
    if (!item?.term || seen.has(item.term)) continue;
    seen.add(item.term);
    const e = (item.citations || []).map((id) => index.get(id)).find(Boolean);
    out.push({ text: item.term, tag: CONCEPT_KIND[g], quote: e?.quote || "", url: e?.url || "" });
  }
  return out.slice(0, limit);
}

const ROLE = { use: "Would use it", integrate: "Would integrate it", resell: "Would resell it", partner: "Would partner on it" };
const entry = (e) => ({ text: e.name, tag: e.division || CATALOG_KIND[e.id?.split(":")[0]] || "", detail: e.description || "", url: e.url || "" });

/** What each criterion asks, in a sentence, so a score can be read without knowing the rubric. */
export const CRITERION_QUESTIONS = {
  Empower: {
    tool_fit: "Does a Siemens tool support something the startup actually does?",
    benefit_fit: "How much would that tool help the startup — in development, operations or scaling?",
    actionability: "Is there a concrete tool, a startup application and a next step?" },
  Collaborate: {
    capability_fit: "Does the startup provide a capability the department is looking for?",
    need_fit: "Does it address one of the department's stated needs?",
    actionability: "Can a concrete pilot with the department be described, with a next step?" },
  Connect: {
    ecosystem_gap: "Do Xcelerator sellers already offer the same thing, with nothing evidenced to set the startup apart?",
    industry_topic_fit: "Does it target an Xcelerator industry, with a core offering that matches an Xcelerator topic?",
    // Rubric v1, for stored runs.
    industry_fit: "Does the startup target an industry in the Siemens Xcelerator catalog?",
    topic_fit: "Does its core offering match an Xcelerator topic?",
    ecosystem_value: "Would connecting it be worth something: an ecosystem audience for it, or, without one, a clear industry and topic fit and a good market?" },
  team_ecosystem: {
    founder_experience: "What leadership, startup or senior experience do the founders bring?",
    domain_expertise: "How deep is the team's expertise in the field it works in?",
    external_validation: "Have programmes, accelerators or investors backed the team?",
    strategic_network: "What partnerships and ecosystem relationships can the team draw on?" },
};

/** The notes the engine attached to one criterion (a cap, a zeroed score), matched by its label. */
export function criterionNotes(pillar, criterion) {
  return (pillar?.notes || []).filter((n) => n.startsWith(`${criterion.label}:`) || n.startsWith(`${criterion.label} capped`));
}

/* The three-node opportunity map. Nodes hold only what the saved assessment contains: grounded
   startup concepts (tagged with the kind of concept and the sentence they came from), catalog
   entries the criteria cited, and the validated statement. Each node says in `hint` what it is,
   because "Startup activity" beside "Siemens tool" does not explain itself. When the assessment
   found no supported link, the last node says so rather than drawing one. */
export function opportunity(res, name) {
  const p = res?.assessment?.pillars?.[name];
  if (!p || p.status !== "assessed") return null;
  const g = catalogGroups(p);
  const startup = concepts(res, name);
  const linked = Boolean(p.statement) && p.total >= 4;
  const dept = res?.department?.label || "the department";
  if (name === "Empower") {
    // A tool a web search found as a Siemens offering says so (core/tool_check.py).
    const checks = Object.fromEntries((p.tool_checks || []).map((c) => [c.id, c]));
    const tools = g.tools.map((t) => ({ ...entry(t), verified: checks[t.id]?.status === "verified",
      url: entry(t).url || (checks[t.id]?.status === "verified" ? checks[t.id].url : "") }));
    return { title: "How Siemens could help", note: "Proposed application · no existing integration is implied",
      connector: "could support", linked,
      nodes: [
        { label: "Startup activity", items: startup, empty: "No startup activity was cited.",
          hint: "What the startup does or needs, from its cited research — the part a Siemens tool would support." },
        { label: "Siemens tool", items: tools, empty: "No Siemens tool was matched.",
          hint: linked ? "Tools from the Siemens portfolio the assessment matched to that activity."
            : "Tools from the Siemens portfolio it was compared with — no supported benefit was found." },
        { label: "Potential benefit", statement: linked ? p.statement : "", empty: "No supported benefit identified.",
          hint: "The validated sentence: which tool, what it would improve, and how it would be applied." }],
      nextStep: p.next_step, gap: !linked };
  }
  if (name === "Connect") {
    // Rubric v3 runs carry the audience the value was derived from, and the case for connecting.
    const value = (p.criteria || []).find((c) => c.id === "ecosystem_value");
    const audience = value?.audience ? value.audience.map((a) => ({ text: a.name, tag: ROLE[a.role] || a.role, detail: a.reason, url: a.url || "" }))
      : g.sellers.map(entry);
    return { title: "Where the offering could connect", note: "Potential relevance · catalog presence is not a partnership",
      connector: "potential relevance", linked,
      nodes: [
        { label: "Startup offering", items: startup, empty: "No startup offering was cited.",
          hint: "What the startup sells or builds, from its cited research." },
        { label: "Xcelerator industry & topic", items: [...g.industries, ...g.topics].map(entry), empty: "No Xcelerator industry or topic was matched.",
          hint: "Where that offering sits in the Siemens Xcelerator catalog: the industries it serves and the topics it covers." },
        { label: "Ecosystem audience", items: audience, statement: linked ? p.statement : "", case: p.case || null,
          empty: "No supported ecosystem link identified.",
          hint: p.case ? "Who in the ecosystem would use, integrate or resell it, and whether connecting makes sense on the evidence this run holds."
            : "Xcelerator partners the startup could reach, and why the connection would matter to them." }],
      nextStep: p.next_step, gap: !linked };
  }
  // With a link, the needs it was matched to. Without one, every need it was assessed against —
  // listing only the ones the model happened to cite would read as if those were all there are.
  const cited = new Map(g.needs.map((n) => [n.name, n]));
  // Without a link, the needs closest to the startup come first and say so (ranked by meaning and
  // words, core/pillar_match.py) — the pointer a reviewer needs when the match found nothing.
  const closest = p.closest_needs || [];
  const unlinked = [...closest.filter((n) => (p.needs || []).includes(n)), ...(p.needs || []).filter((n) => !closest.includes(n))];
  const needs = linked && g.needs.length ? g.needs.map(entry)
    : unlinked.map((n) => (cited.has(n) ? entry(cited.get(n))
      : { text: n, tag: closest.includes(n) ? "Closest to the startup" : p.provisional ? "Example need" : "Department need" }));
  return { title: linked ? "How the department could pilot it" : "No supported link to the current needs",
    note: `${res?.department?.label || "Department"} · ${p.provisional ? "example needs · provisional" : "configured needs"}`,
    connector: linked ? "could address" : "no supported link", linked,
    nodes: [
      { label: "Startup capability", items: startup, empty: "No startup capability was cited.",
        hint: `What the startup can deliver that ${dept} could pilot.` },
      // A cited need is not a matched one: a criterion can name the need it was held against and
      // still score 0, so "matched" is said only when the assessment found a supported link.
      { label: "Department needs", items: needs, empty: "No department needs are configured.",
        hint: `${linked ? "The needs it was matched to" : "The needs it was assessed against"}${p.provisional ? " — example needs until the department's real ones are configured" : ""}.` },
      { label: "Proposed pilot", statement: linked ? p.statement : "", empty: "No specific department use case identified",
        hint: "The validated use case: which capability, for which need, piloted how." }],
    nextStep: linked ? p.next_step
      : p.provisional ? "Review against the department's actual requirements once they are configured."
      : `None of ${dept}'s stated needs is addressed; consider assessing it for another department.`,
    gap: !linked };
}

/** Qualitative strip: each criterion's anchor, in words. Exact numbers live in Scoring method. */
export function signals(pillar, name) {
  if (!pillar || pillar.status !== "assessed") return [];
  return (pillar.criteria || []).map((c) => ({
    id: c.id, label: c.label, anchor: c.anchor,
    weak: c.id === THIRD[name] && c.score < 2,
    text: c.id === THIRD[name] && c.score < 2 ? "Next step needs definition" : c.anchor,
  }));
}

const SOURCE_LABELS = [
  [/^search:/, "Targeted web search"],
  [/^deep_profile\.founders/, "Founder background"],
  [/^deep_profile\.(key_team|advisors)/, "Team background"],
  [/^deep_profile\.programs/, "Programme membership"],
  [/^deep_profile\.reference_customers|customer_segment/, "Customers"],
  [/^deep_profile\.commercial\.investors/, "Investors"],
  [/^deep_profile\.commercial/, "Commercial profile"],
  [/^deep_profile\.(funding|employees|hq|founded)/, "Company facts"],
  [/^deep_profile/, "Company research"],
  [/^profile/, "Company profile"],
  [/^summary/, "Research summary"],
  [/^company/, "Company"],
  [/^facts/, "Web research"],
  [/^verification/, "Claim verification"],
  [/^trend/, "Market research"],
  [/^application/, "Application form"],
  [/^portfolio_analysis|^fit/, "Portfolio analysis"],
  [/^traction\./, "Traction rubric"],
];

/** A human label for an evidence record instead of an internal field path. */
export function evidenceLabel(e) {
  const source = String(e?.source || "");
  const base = (SOURCE_LABELS.find(([re]) => re.test(source)) || [null, "Research record"])[1];
  let host = "";
  try { host = e?.url ? new URL(e.url).hostname.replace(/^www\./, "") : ""; } catch { host = ""; }
  return host ? `${base} · ${host}` : base;
}

/** Identical evidence (same quote and link) shown once, keeping every reference to it. */
export function dedupeEvidence(list) {
  const out = new Map();
  for (const e of list || []) {
    if (!e) continue;
    const key = `${e.quote || e.text || ""}|${e.url || ""}`;
    const prior = out.get(key);
    if (prior) prior.refs.push(e.source);
    else out.set(key, { ...e, label: evidenceLabel(e), refs: [e.source] });
  }
  return [...out.values()];
}

/* ------------------------------------------------------------------ display formatting */

/** "€2.8M", "€23.1B", "€450k" — a figure the way a reviewer reads it, not "2831100". */
export function formatMoney(eur) {
  const v = num(eur);
  if (v == null) return "—";
  const short = (x, unit) => `€${x >= 100 ? Math.round(x) : String(Math.round(x * 10) / 10)}${unit}`;
  if (v >= 1e9) return short(v / 1e9, "B");
  if (v >= 1e6) return short(v / 1e6, "M");
  if (v >= 1e3) return `€${Math.round(v / 1e3)}k`;
  return `€${Math.round(v)}`;
}

/** A traction division's value in words. The raw stored value stays in the detail table. */
export function divisionDisplay(d) {
  if (!d || d.status === "unknown") return "No evidence";
  if (d.id === "funding") return d.value_eur != null ? `${formatMoney(d.value_eur)} raised` : String(d.value || "");
  if (d.id === "revenue") {
    if (d.status === "zero_evidenced") return "Sourced as pre-revenue";
    return d.value_eur != null ? `${formatMoney(d.value_eur)} revenue` : String(d.value || "");
  }
  if (d.id === "customers") {
    const counted = (d.items || []).filter((i) => i.counted);
    if (!counted.length) return String(d.value || "");
    const big = counted.filter((i) => i.size === "large_enterprise").length;
    const sme = counted.length - big;
    return [big && `${big} big-name`, sme && `${sme} SME${sme > 1 ? "s" : ""}`].filter(Boolean).join(" + ");
  }
  if (d.id === "employees") {
    const n = String(d.value || "").match(/\d[\d,]*/);
    return n ? `${n[0]}${/-/.test(String(d.value)) ? "+" : ""} people` : String(d.value || "");
  }
  return String(d.value || "");
}

/* The market rubric's bands, as the engine defines them (core/market.py): the band index equals
   the criterion's score, so the highlighted band and the stated score always agree. */
export const MARKET_SCALES = {
  market_size: { edges: [1e8, 1e9, 5e9, 2e10, 1e11], min: 1e7, max: 1e12, log: true, format: formatMoney },
  market_growth: { edges: [0, 2, 5, 10, 25], min: -5, max: 40, log: false, format: (v) => `${v}%` },
};

/** The qualifiers a reader must not miss, as notices above the page rather than small badges:
    provisional needs, partial Siemens Fit, a pending total. Legacy runs say so in the toolbar. */
export function scoringNotices(res) {
  const out = [];
  const a = res?.assessment;
  if (res?.department?.demo) {
    out.push({ id: "provisional", type: "warning", title: "Collaborate is provisional.",
      text: `It is scored against example ${res.department.label} needs until the department's real requirements are configured.` });
  }
  if (a?.siemens_fit?.partial) {
    const missing = PILLAR_ORDER.filter((p) => a.pillars?.[p]?.status !== "assessed");
    out.push({ id: "partial", type: "info", title: "Siemens Fit is partial.",
      text: `${missing.join(" and ")} could not be assessed, so the score is the best of the others and Pass is not possible.` });
  }
  if (res?.department && !res?.streaming && a && a.total == null) {
    const c = contributions(res);
    out.push({ id: "pending", type: "info", title: "Total pending.",
      text: `${c.missing.join(", ") || "A component"} not scored yet — the total is only calculated when all four are.` });
  }
  return out;
}
