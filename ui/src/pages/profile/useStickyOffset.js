import { useEffect, useState } from "react";

/* How much sticky chrome sits above the readable content, in pixels.
 *
 * This cannot be a constant. `.profile-head` is itself `position: sticky` and contains the company
 * title, its description, the meta row, optional tags, the action buttons, the pipeline ribbon and
 * the tab strip — so its height depends on the company being viewed and on the viewport width. A
 * hard-coded offset would put the heading under the header for exactly the companies with the
 * longest summaries.
 *
 * The measurement is published as a CSS custom property as well as returned, because three things
 * need the same number and they must not drift: the rail's `top` and the sections'
 * `scroll-margin-top` (CSS), and the scroll-spy's activation band (JS).
 */
const CSS_VAR = "--profile-sticky-h";
const FALLBACK = 200;

export default function useStickyOffset(selector = ".profile-head") {
  const [offset, setOffset] = useState(FALLBACK);

  useEffect(() => {
    const el = document.querySelector(selector);
    if (!el) return undefined;

    const measure = () => {
      // The header's own bottom edge in viewport coordinates while it is pinned is exactly where
      // content becomes readable, and it already includes the fixed top bar above it.
      const pinned = ["sticky", "fixed"].includes(getComputedStyle(el).position);
      const height = pinned ? Math.round(el.getBoundingClientRect().height + (parseFloat(getComputedStyle(el).top) || 0)) : 0;
      setOffset((prev) => (Math.abs(prev - height) > 1 ? height : prev));
      document.documentElement.style.setProperty(CSS_VAR, `${height}px`);
    };

    measure();
    // ResizeObserver rather than a resize listener: the header also changes height when the
    // summary wraps differently or the tag row appears, neither of which is a window resize.
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [selector]);

  return offset;
}
