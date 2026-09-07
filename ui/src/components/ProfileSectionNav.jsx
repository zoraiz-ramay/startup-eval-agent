import React from "react";

/* The profile's navigation: collapsible groups of sections, with the current one marked.
 *
 * This replaced a pipeline ribbon and a tab bar stacked above the content. Two navigation systems
 * for one page is one too many, and the ribbon only ever rendered every step as done — it reported
 * nothing a reader could act on while costing ~70px of sticky chrome on every profile.
 *
 * Exactly one group is open, and the open group IS the rendered view. That identity is the design:
 * rail state and `?tab=` are the same fact, so there is no second source of truth to drift, and a
 * permalink still opens the place it names.
 *
 * Presentation only — it is handed views, the current view and the current section. Knowing
 * nothing about the company being profiled is what lets the rail and the scroll-spy be reasoned
 * about, and tested, one at a time.
 *
 * Two levels, two patterns, both standard: a group header is a disclosure button (`aria-expanded`
 * + `aria-controls`), and a section is a real anchor. Not a tablist — a tablist's children must be
 * tabs, and these own a list. Real anchors buy keyboard activation, focus order, middle-click,
 * "copy link address" and the browser's own scrolling for free; the sticky chrome is accounted for
 * by `scroll-margin-top` on the sections themselves rather than by JavaScript arithmetic that
 * would have to be kept in step with the CSS.
 */
const panelId = (viewId) => `rail-group-${String(viewId).replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;

export default function ProfileSectionNav({ views, activeView, onSelectView,
                                            sections, activeId, onNavigate }) {
  if (!views?.length) return null;
  return (
    <nav className="section-rail" aria-label="Profile navigation">
      <ul className="section-rail-groups">
        {views.map((view) => {
          const open = view.id === activeView;
          const items = open ? (sections || []) : [];
          return (
            <li key={view.id} className={"section-rail-group" + (open ? " open" : "")}>
              <button type="button" className="section-rail-group-head"
                      aria-expanded={open} aria-controls={panelId(view.id)}
                      onClick={() => onSelectView?.(view.id)}>
                {/* The caret is drawn by CSS and announces nothing: aria-expanded already says
                    open or closed, and a screen reader reading "triangle" first would be noise. */}
                <span className="section-rail-caret" aria-hidden="true" />
                <span className="section-rail-group-label">{view.label}</span>
              </button>
              {/* Always rendered so aria-controls resolves to a real element even while closed. */}
              <ol id={panelId(view.id)} className="section-rail-list" hidden={!open}>
                {items.map((s) => {
                  const active = s.id === activeId;
                  return (
                    <li key={s.id} className={"section-rail-item" + (active ? " active" : "")}>
                      <a href={`#${s.id}`}
                         /* aria-current="location" is the value ARIA defines for "the current
                            place in a set of locations", which is what a section of the page you
                            are reading is — "page" would claim this is the current page in a site
                            nav. Exactly one item carries it. */
                         aria-current={active ? "location" : undefined}
                         onClick={() => onNavigate?.(s.id)}>
                        <span className="section-rail-node" aria-hidden="true" />
                        <span className="section-rail-label">{s.label}</span>
                      </a>
                    </li>
                  );
                })}
              </ol>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
