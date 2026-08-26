import { useCallback, useEffect, useRef, useState } from "react";

/* Which section the reader is currently in.
 *
 * Knows nothing about companies, scores or evidence — it takes element ids and returns the one
 * that owns the reading position. That is the whole contract.
 *
 * WHY AN ACTIVATION BAND AND NOT "MOST VISIBLE"
 * The Overview's panels differ in height by an order of magnitude: Reference customers can be two
 * chips, Team & ecosystem can be a screenful. "Whichever section is 50% visible" therefore tracks
 * panel size rather than reading position, and a short panel can never win against a tall
 * neighbour. Instead a horizontal band sits just below the sticky tab bar, and the section that
 * owns that band is current — which is where a reader's eye actually is.
 *
 * The band is expressed as a rootMargin that crops the viewport to a strip starting just below
 * the sticky chrome — see `activationBand` for why its height is measured against the space
 * that chrome leaves rather than against the viewport.
 */

// The band's height, as a fraction of the space left BELOW the sticky chrome — not of the whole
// viewport. That distinction is load-bearing here: this profile's sticky header measures ~408px,
// so a band expressed as "the top 30% of the viewport" is entirely above the readable area on a
// laptop, the observer's root rect comes out with negative height, and it then never fires at all.
const BAND_DEPTH_RATIO = 0.4;
const MIN_BAND_PX = 80;
// However tall the chrome gets, detection must not be pushed off the bottom of the screen.
const MAX_CHROME_RATIO = 0.6;
// A clicked anchor lands its section at `scroll-margin-top`, which is deliberately a few pixels
// BELOW the band's line so the heading is not flush against the sticky header. Without a matching
// tolerance here, a section can never satisfy "has crossed the line" at the moment it is scrolled
// to, and clicking "Headcount trend" would land there and immediately mark the section above it.
// Keep in step with `.profile-section { scroll-margin-top }` in styles.css.
export const CROSS_TOLERANCE_PX = 16;

/** The activation band in viewport coordinates, given the sticky chrome above the content. */
export function activationBand(topOffset, viewportHeight) {
  const top = Math.min(topOffset, viewportHeight * MAX_CHROME_RATIO);
  const height = Math.max(MIN_BAND_PX, (viewportHeight - top) * BAND_DEPTH_RATIO);
  return { top, bottom: Math.max(0, viewportHeight - top - height) };
}

// A click scrolls smoothly through every intervening section, and the observer would faithfully
// light each one up on the way past. Suppressing it briefly makes a click land on the section the
// reader asked for instead of flickering through its neighbours. Cleared early once the target
// arrives, so this is a ceiling and not a fixed delay.
const CLICK_SETTLE_MS = 700;

/**
 * @param {string[]} ids       section element ids, in document order
 * @param {number}   topOffset px of sticky chrome above the content (band's top edge)
 */
export default function useScrollSpy(ids, topOffset) {
  const [activeId, setActiveId] = useState("");
  const [presentIds, setPresentIds] = useState([]);
  // Set by a rail click; while it holds, observer updates are ignored. A ref rather than state:
  // changing it must not re-render, and the observer callback needs to read it synchronously.
  const pinnedUntil = useRef(0);
  const pinnedId = useRef("");

  /* Reads the registered elements' rects and decides. Called only from observer callbacks, never
     from a scroll handler, so it runs a handful of times per scroll gesture rather than per frame.
     Reading rects here rather than trusting entry order is deliberate: IntersectionObserver
     batches entries and their order is not specified, so choosing "the first entry that
     intersects" produces different answers for the same scroll position. */
  const resolve = useCallback(() => {
    if (Date.now() < pinnedUntil.current) {
      // The target has arrived — release early rather than sitting out the full window.
      const el = pinnedId.current && document.getElementById(pinnedId.current);
      // Released once the target has essentially arrived. The window is generous because the
      // anchor lands the section at its scroll-margin — a little below the band line — and smooth
      // scrolling settles with a pixel or two of overshoot.
      const line = activationBand(topOffset, window.innerHeight).top;
      if (!el || Math.abs(el.getBoundingClientRect().top - line) > CROSS_TOLERANCE_PX + 8) return;
      pinnedUntil.current = 0;
    }

    const line = activationBand(topOffset, window.innerHeight).top;
    const rows = ids
      .map((id) => ({ id, el: document.getElementById(id) }))
      .filter((r) => r.el)
      .map((r) => ({ id: r.id, top: r.el.getBoundingClientRect().top }));
    if (!rows.length) return;

    // At the bottom of the document the last section may sit permanently below the band — a short
    // "Recent signals" under a tall page can never reach it. The reader is plainly at the end, so
    // the end is what is current.
    const doc = document.documentElement;
    if (window.innerHeight + window.scrollY >= doc.scrollHeight - 2) {
      setActiveId(rows[rows.length - 1].id);
      return;
    }

    // The last section to have crossed the line owns it. This is the same rule scrolling in both
    // directions, which is what stops the indicator jumping back and forth on a slow scroll, and
    // it handles a section taller than the band (its top is above the line, nothing else has
    // crossed yet) without a special case.
    const crossed = rows.filter((r) => r.top <= line + CROSS_TOLERANCE_PX);
    setActiveId(crossed.length ? crossed[crossed.length - 1].id : rows[0].id);
  }, [ids, topOffset]);

  /* Which sections are actually on the page. Deliberately separate from the observer below:
     knowing a section exists needs no IntersectionObserver, so the rail still renders — as plain
     working anchors, minus the active tracking — where the API is missing. Folding the two
     together made the whole table of contents vanish in that case. */
  useEffect(() => {
    const found = ids.filter((id) => document.getElementById(id));
    setPresentIds((prev) =>
      (prev.length === found.length && prev.every((id, i) => id === found[i]) ? prev : found));
  });

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return undefined;
    const elements = ids.map((id) => document.getElementById(id)).filter(Boolean);
    if (!elements.length) {
      setActiveId("");
      return undefined;
    }

    // One observer for every section, not one each: the callback recomputes from rects anyway, so
    // per-element observers would multiply callbacks without adding information.
    let observer;
    const connect = () => {
      observer?.disconnect();
      const band = activationBand(topOffset, window.innerHeight);
      observer = new IntersectionObserver(resolve, {
        rootMargin: `-${Math.round(band.top)}px 0px -${Math.round(band.bottom)}px 0px`,
        threshold: [0, 1],
      });
      elements.forEach((el) => observer.observe(el));
      resolve();
    };

    connect();          // also settles the initial position, before any scrolling has happened
    // A resize moves the band itself, so the observer is rebuilt rather than merely re-run.
    window.addEventListener("resize", connect, { passive: true });
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", connect);
    };
  }, [ids, topOffset, resolve]);

  /* Called by the rail on click. The browser still does the scrolling — this only stops the
     observer contradicting the reader mid-flight. */
  const pin = useCallback((id) => {
    pinnedId.current = id;
    pinnedUntil.current = Date.now() + CLICK_SETTLE_MS;
    setActiveId(id);
  }, []);

  return { activeId, presentIds, pin };
}
