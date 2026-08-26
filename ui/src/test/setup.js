import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);
afterEach(() => { globalThis.__observers = []; });

// Nothing in a component test may reach the network. A test that silently falls back to a real
// fetch passes for the wrong reason locally and fails in CI, so the default is a hard error and
// each test opts in by stubbing the specific call it needs.
globalThis.fetch = vi.fn(() => {
  throw new Error(
    "Unstubbed fetch in a component test — stub the api module or vi.mocked(fetch) explicitly.",
  );
});

// jsdom implements neither, and both are used by the layout code under test.
globalThis.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
});
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
// jsdom has no IntersectionObserver either. This records the instances so a test can drive the
// callback directly — the scroll-spy's decision is made from element rects inside that callback,
// which is exactly the part worth asserting.
globalThis.__observers = [];
globalThis.IntersectionObserver ??= class {
  constructor(cb, options) {
    this.cb = cb;
    this.options = options;
    this.elements = [];
    this.disconnected = false;
    globalThis.__observers.push(this);
  }
  observe(el) { this.elements.push(el); }
  unobserve(el) { this.elements = this.elements.filter((e) => e !== el); }
  disconnect() { this.disconnected = true; }
  // Test helper: pretend something crossed the band.
  trigger() { this.cb([], this); }
};
