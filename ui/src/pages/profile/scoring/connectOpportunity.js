/**
 * Connect's three-node opportunity map. Connect is Siemens partnering with the startup itself, as
 * a solution provider in Xcelerator — never introducing it to Xcelerator sellers — so every
 * version reads as the case for that partnership.
 *
 * Rubric v5 leads its third step with the sellers that already sell the same kind of solution
 * (five named, the rest counted), because how many there are is what the score rests on. Runs
 * stored under v3 also scored an "ecosystem audience" of sellers who would use or resell the
 * startup; stored runs are never rewritten, so that audience is still shown, but as one line with
 * a pointer to re-evaluate — its per-seller reasons ran to a paragraph each and answered a
 * question Connect no longer asks.
 */

const TITLE = "Why Siemens could partner with it";
const OLD_RUBRIC = "Scored under an earlier Connect rubric · re-evaluate to score it as a direct Siemens partnership";
const AUDIENCE_POINT = "Who in the ecosystem would benefit";
const NO_AUDIENCE_POINT = "No Xcelerator seller was found who would use";
const OLD_TITLES = { makes_sense: "Partnering makes sense", worth_exploring: "Worth exploring, with open questions",
  not_yet: "Partnering does not make sense on current evidence" };

function names(list, limit = 5) {
  const shown = list.slice(0, limit).join(", ");
  return list.length > limit ? `${shown} + ${list.length - limit} more` : shown;
}

/* A stored v3 case, restated as a Siemens partnership: the audience point shrinks to its names,
   the "nobody would resell it" point goes (it is not a reason against partnering), and the
   summary says the score predates the current rubric. */
function historicCase(c, audience) {
  if (!c) return null;
  const points = c.points
    .filter((pt) => !pt.text.startsWith(NO_AUDIENCE_POINT))
    .map((pt) => (pt.text.startsWith(AUDIENCE_POINT)
      ? { tone: "plus", text: `Named as an ecosystem audience, which the current rubric no longer counts: ${names(audience)}.`, sources: [] }
      : pt));
  return { ...c, title: OLD_TITLES[c.verdict] || c.title, points,
    summary: "This score also counted Xcelerator sellers who would use or resell the startup. Siemens partners with the startup directly, so re-evaluate for the current score." };
}

export function connectOpportunity(p, { startup, industries, sellers, linked, entry }) {
  const value = (p.criteria || []).find((c) => c.id === "ecosystem_value" || c.id === "market_signals");
  const nodes = [
    { label: "Startup offering", items: startup, empty: "No startup offering was cited.",
      hint: "What the startup sells or builds, from its cited research." },
    { label: "Xcelerator industry & topic", items: industries.map(entry), empty: "No Xcelerator industry or topic was matched.",
      hint: "Where that offering sits in the Siemens Xcelerator catalog: the industries it serves and the topics it covers." }];
  const market = (value?.evidence || []).filter((e) => String(e.source || "").startsWith("market:"))
    .map((e) => ({ text: e.quote, tag: "Market signal", url: e.url || "" }));
  const sim = p.similar;
  if (sim || value?.path === "partnership") {
    const similar = sim ? [...sim.shown.map((s) => ({ text: s.name, tag: "Already sells this", url: s.url || "" })),
      ...(sim.more ? [{ text: `+ ${sim.more}${sim.at_least ? " or more" : ""} more similar sellers in Xcelerator`, tag: "" }] : [])] : [];
    const items = similar.concat(market);
    return { title: TITLE, note: "Direct partnership · the ecosystem is checked for providers already selling this",
      connector: "potential partnership", linked,
      nodes: [...nodes,
        // All of it shown: five named sellers, "+ N more" and at most three market signals.
        { label: "Partnership case", items, max: items.length, statement: linked ? p.statement : "", case: p.case || null,
          empty: "No similar seller and no good market signal.",
          hint: "Whether partnering makes sense: the providers that already sell this, the market signals, and the case built from them." }],
      nextStep: p.next_step, gap: !linked };
  }
  const audience = (value?.audience || []).map((a) => a.name);
  const fallback = audience.length ? [] : sellers.map(entry);            // rubric v1 cited sellers directly
  const items = [...(audience.length ? [{ text: `Ecosystem audience: ${names(audience)}`, tag: "Earlier rubric" }] : []),
    ...fallback, ...market];
  return { title: TITLE, note: OLD_RUBRIC, connector: "potential partnership", linked,
    nodes: [...nodes,
      { label: "Partnership case", items, max: items.length || undefined, statement: linked ? p.statement : "",
        case: historicCase(p.case, audience), empty: "No supported partnership case identified.",
        hint: "Whether partnering made sense under the rubric this run was scored with." }],
    nextStep: p.next_step, gap: !linked };
}
