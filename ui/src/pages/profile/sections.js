/* Every navigable place on the profile, in reading order — the single source of truth.
 *
 * The rail, the scroll-spy, the view switch and the tests all read this list. Nothing else may
 * hold a copy: an id repeated in a component and again in a test is how a table of contents
 * starts pointing at sections that no longer exist.
 *
 * A view's `id` is also its `?tab=` value. Those strings are deliberately the ones the old tab bar
 * used, so permalinks a reviewer has already shared still open the right place — the navigation
 * changed, the addresses did not.
 *
 * `label` matches each panel's own heading. A rail that renames the thing it links to makes the
 * reader do a translation on every glance.
 *
 * Declaring a section here does not make it appear: the rail lists only the sections actually on
 * the page (see useScrollSpy's `presentIds`), so a run with no market landscape simply has no
 * Competitors entry rather than an anchor pointing at nothing.
 */
export const PROFILE_VIEWS = [
  {
    id: "Overview",
    label: "Profile",
    sections: [
      { id: "profile-key-metrics", label: "Key metrics" },
      { id: "profile-executive-summary", label: "Executive summary" },
      { id: "profile-team-ecosystem", label: "Team & ecosystem" },
      { id: "profile-reference-customers", label: "Reference customers" },
      { id: "profile-headcount-trend", label: "Headcount trend" },
      { id: "profile-recent-signals", label: "Recent signals" },
    ],
  },
  {
    id: "Scoring & Fit",
    label: "Scoring & Fit",
    sections: [
      { id: "scoring-decision", label: "Decision" },
      { id: "scoring-department", label: "Department fit" },
      { id: "scoring-breakdown", label: "Score breakdown" },
      { id: "scoring-routes", label: "Partnership routes" },
      { id: "scoring-portfolio", label: "Portfolio fit" },
      { id: "scoring-sfs", label: "SFS financing" },
    ],
  },
  {
    id: "Market & Risk",
    label: "Market & Risk",
    sections: [
      { id: "market-trend", label: "Market trend" },
      { id: "market-competitors", label: "Competitors" },
      { id: "market-peers", label: "Funded peers" },
      { id: "market-size", label: "Market size" },
      { id: "market-signals", label: "Signals & risks" },
      { id: "market-evidence", label: "Market evidence" },
    ],
  },
  {
    id: "Evidence",
    label: "Evidence",
    sections: [{ id: "evidence-table", label: "All evidence" }],
  },
];

export const DEFAULT_VIEW = PROFILE_VIEWS[0].id;

// id -> label, for the sections themselves. A <section> is a landmark, and a landmark without a
// name is worse than no landmark: a screen-reader user jumping by region hears "region" six times
// in a row. Reading the name from this registry rather than passing it at every call site keeps
// the rail entry and the section it points at spelled identically by construction.
const LABELS = Object.fromEntries(
  PROFILE_VIEWS.flatMap((v) => v.sections.map((s) => [s.id, s.label])),
);

export function sectionLabel(id) {
  return LABELS[id] || "";
}

/** The view a `?tab=` value names, falling back to the first rather than rendering nothing. */
export function viewById(id) {
  return PROFILE_VIEWS.find((v) => v.id === id) || PROFILE_VIEWS[0];
}

// Kept for the Overview, which is the only view whose sections another module needs by name.
export const PROFILE_SECTIONS = PROFILE_VIEWS[0].sections;
export const PROFILE_SECTION_IDS = PROFILE_SECTIONS.map((s) => s.id);
