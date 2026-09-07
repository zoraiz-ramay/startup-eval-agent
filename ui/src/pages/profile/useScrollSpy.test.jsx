import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import useScrollSpy, { activationBand } from "./useScrollSpy.js";

/**
 * The scroll-spy's decision rule.
 *
 * jsdom does no layout, so every rect is zero — which would make these tests assert nothing. Each
 * section's `getBoundingClientRect` is therefore stubbed to a scripted position, and the observer
 * callback is fired by hand. That is the honest boundary: what is under test is the RULE for
 * choosing a section from a set of positions, not the browser's intersection maths.
 *
 * The rule is "the last section whose top has crossed the activation line". It is worth pinning
 * because the obvious alternatives are all subtly wrong here: "first intersecting entry" depends
 * on IntersectionObserver's unspecified entry order, and "most visible" tracks panel height
 * rather than reading position, so a two-chip Reference customers can never win against a
 * screenful of Team & ecosystem.
 */
const IDS = ["a", "b", "c"];
const OFFSET = 100;

function mount(tops, { scrollY = 0, innerHeight = 800, scrollHeight = 3000 } = {}) {
  document.body.innerHTML = IDS.map((id) => `<div id="${id}"></div>`).join("");
  IDS.forEach((id, i) => {
    document.getElementById(id).getBoundingClientRect = () => ({ top: tops[i], height: 400 });
  });
  window.scrollY = scrollY;
  window.innerHeight = innerHeight;
  Object.defineProperty(document.documentElement, "scrollHeight",
    { value: scrollHeight, configurable: true });

  const seen = {};
  function Probe() {
    Object.assign(seen, useScrollSpy(IDS, OFFSET));
    return null;
  }
  const utils = render(<Probe />);
  return { seen, ...utils };
}

const fire = () => act(() => { globalThis.__observers.forEach((o) => o.trigger()); });

afterEach(() => { document.body.innerHTML = ""; });

describe("useScrollSpy", () => {
  it("starts on the first section before any scrolling", () => {
    const { seen } = mount([120, 520, 920]);
    expect(seen.activeId).toBe("a");
  });

  it("advances as each section crosses the line", () => {
    const { seen } = mount([-300, 40, 600]);   // b has crossed, c has not
    fire();
    expect(seen.activeId).toBe("b");
  });

  it("comes back to the previous section when scrolling up", () => {
    const { seen, rerender } = mount([-300, 40, 600]);
    fire();
    expect(seen.activeId).toBe("b");

    // Same rule in reverse — nothing about the decision depends on scroll direction, which is
    // what stops the marker sticking or jumping on a slow upward scroll.
    IDS.forEach((id, i) => {
      document.getElementById(id).getBoundingClientRect = () => ({ top: [120, 520, 920][i], height: 400 });
    });
    fire();
    expect(seen.activeId).toBe("a");
  });

  it("keeps a section taller than the viewport active while it is being read", () => {
    // b's top is far above the line and c has not reached it: nothing intersects the band, and a
    // naive "first intersecting entry" rule would leave the marker stranded on a.
    const { seen } = mount([-2000, -900, 700]);
    fire();
    expect(seen.activeId).toBe("b");
  });

  it("activates a short final section once the reader is at the bottom", () => {
    // c never reaches the line — the page ends first. The reader is plainly at the end.
    const { seen } = mount([-2400, -1600, 600], { scrollY: 2200, innerHeight: 800, scrollHeight: 3000 });
    fire();
    expect(seen.activeId).toBe("c");
  });

  it("reports which sections are actually on the page", () => {
    const { seen } = mount([120, 520, 920]);
    expect(seen.presentIds).toEqual(["a", "b", "c"]);
  });

  it("survives sections that were never rendered", () => {
    document.body.innerHTML = '<div id="a"></div>';
    document.getElementById("a").getBoundingClientRect = () => ({ top: 120, height: 100 });
    const seen = {};
    function Probe() { Object.assign(seen, useScrollSpy(IDS, OFFSET)); return null; }
    expect(() => render(<Probe />)).not.toThrow();
    expect(seen.presentIds).toEqual(["a"]);
  });

  it("disconnects its observer on unmount", () => {
    const { unmount } = mount([120, 520, 920]);
    const observer = globalThis.__observers.at(-1);
    expect(observer.disconnected).toBe(false);
    unmount();
    expect(observer.disconnected).toBe(true);
  });

  it("uses one observer for all the sections, not one each", () => {
    mount([120, 520, 920]);
    expect(globalThis.__observers).toHaveLength(1);
    expect(globalThis.__observers[0].elements).toHaveLength(3);
  });

  it("crops the viewport to a band below the sticky chrome", () => {
    mount([120, 520, 920], { innerHeight: 800 });
    // Band = 40% of what is left below the chrome: top 100, height 280, so 420 is cropped off
    // the bottom. Expressed in pixels rather than a percentage of the viewport — see
    // activationBand for the header that made a percentage produce a negative root.
    expect(globalThis.__observers[0].options.rootMargin).toBe("-100px 0px -420px 0px");
  });

  it("keeps a usable band even under a header taller than the viewport allows", () => {
    // The real profile header measures ~408px. A band of "the top 30% of the viewport" would sit
    // entirely above the readable area, give the observer a negative root rect, and stop it
    // firing at all — the section marker would then simply never move.
    const { top, bottom } = activationBand(408, 720);
    expect(top).toBeLessThanOrEqual(720 * 0.6);
    expect(720 - top - bottom).toBeGreaterThanOrEqual(80);
  });

  it("holds the clicked section while the smooth scroll runs past its neighbours", () => {
    const { seen } = mount([-300, 40, 600]);
    fire();
    expect(seen.activeId).toBe("b");

    act(() => seen.pin("c"));
    expect(seen.activeId).toBe("c");
    // The observer keeps firing during the scroll; without the pin it would repaint every
    // section on the way down and the click would look like it went to the wrong place.
    fire();
    expect(seen.activeId).toBe("c");
  });

  it("releases the pin once the target has arrived", () => {
    const { seen } = mount([-300, 40, 600]);
    act(() => seen.pin("c"));

    // c has landed where a clicked anchor puts it: at scroll-margin-top, a few pixels below the
    // line. The observer is back in charge and must agree that c is current — this is the exact
    // case where a zero-tolerance "has crossed the line" test marks the section ABOVE the one
    // the reader just clicked.
    document.getElementById("c").getBoundingClientRect = () => ({ top: OFFSET + 8, height: 400 });
    fire();
    expect(seen.activeId).toBe("c");

    // Scrolled back up and away from c: the observer moves on, so the pin really was released.
    document.getElementById("c").getBoundingClientRect = () => ({ top: 600, height: 400 });
    fire();
    expect(seen.activeId).toBe("b");
  });

  it("does not blow up where IntersectionObserver is missing", () => {
    const original = globalThis.IntersectionObserver;
    // eslint-disable-next-line no-global-assign
    globalThis.IntersectionObserver = undefined;
    try {
      const { seen } = mount([120, 520, 920]);
      // The rail still renders as working anchors; only the active tracking is absent.
      expect(seen.presentIds).toEqual(["a", "b", "c"]);
    } finally {
      globalThis.IntersectionObserver = original;
    }
  });
});
