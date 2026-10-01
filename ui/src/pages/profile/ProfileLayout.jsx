import React, { useEffect, useMemo, useRef } from "react";
import ProfileSectionNav from "../../components/ProfileSectionNav.jsx";
import useScrollSpy, { scrollContainer } from "./useScrollSpy.js";
import useStickyOffset from "./useStickyOffset.js";
import { PROFILE_VIEWS, viewById } from "./sections.js";

/* The profile's chrome below the header: the navigation rail and the region it drives.
 *
 * The rail used to belong to the Overview and navigate only that one tab, with a pipeline ribbon
 * and a tab bar stacked above it. It is now the page's whole navigation, which is why it lives
 * here rather than inside any one view — every view is just a list of sections rendered into the
 * region beside it.
 *
 * One measurement feeds three things that must not disagree: the rail's sticky top and the
 * sections' scroll-margin (through the `--profile-sticky-h` custom property useStickyOffset
 * publishes) and the scroll-spy's activation band (through the value it returns).
 */
export default function ProfileLayout({ view, onSelectView, children }) {
  const current = viewById(view);
  const ids = useMemo(() => current.sections.map((s) => s.id), [current]);
  const stickyOffset = useStickyOffset();
  const { activeId, presentIds, pin } = useScrollSpy(ids, stickyOffset);

  // Only the sections actually rendered, so the rail never offers an anchor that goes nowhere:
  // Recent signals exists only when the run found signals, Competitors only when the market wave
  // named any.
  const railSections = useMemo(
    () => current.sections.filter((s) => presentIds.includes(s.id)),
    [current, presentIds],
  );

  /* Switching view returns to the top. Without it a reader who is deep inside a long Evidence
     table and selects Market & Risk lands past the end of a much shorter view, on blank page.
     Skipped on first render so a permalink carrying a #section still opens where it points. */
  const mounted = useRef(false);
  useEffect(() => {
    // Guarded because scrolling is a convenience, not a correctness requirement: jsdom defines
    // window.scrollTo and then throws "Not implemented" from it, and a host that refuses to
    // scroll must not take the rest of this effect — and the view switch — down with it.
    if (mounted.current) {
      try {
        const root = scrollContainer(document.querySelector(".profile-body-main"));
        (root || window).scrollTo({ top: 0, behavior: "auto" });
      } catch { /* host does not support programmatic scrolling */ }
    }
    mounted.current = true;
  }, [current.id]);

  return (
    <div className="profile-body">
      <ProfileSectionNav views={PROFILE_VIEWS} activeView={current.id} onSelectView={onSelectView}
                         sections={railSections} activeId={activeId} onNavigate={pin} />
      {/* Named region rather than a bare div: the rail is a landmark, and the thing it controls
          has to be reachable as one too, or a screen-reader user can jump to the navigation and
          then has nowhere to jump to. */}
      {/* An in-page link to one of this view's sections (the Total score legend's, say) gets
          the rail's behaviour: the browser scrolls, and the scroll-spy is pinned to the target
          so a section that cannot reach the top — Market, near the end — is still the one marked. */}
      <div className="profile-body-main" role="region" aria-label={current.label}
        onClickCapture={(e) => {
          const id = e.target.closest?.('a[href^="#"]')?.getAttribute("href")?.slice(1);
          if (id && ids.includes(id)) pin(id);
        }}>
        {children}
      </div>
    </div>
  );
}
