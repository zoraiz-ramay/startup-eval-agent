import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
// @siemens/ix-react's barrel registers ~100 custom elements as a side effect of import (MIG-01
// needs one of them, IxPill). Paying that cost here, once, in setup — rather than letting whichever
// test first imports a component that uses it eat several seconds against its own timeout.
import "@siemens/ix-react";

afterEach(cleanup);

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
// jsdom doesn't implement it either, and IxTabs calls it on the newly-active tab item
// (tabs.js's setTabActive) every time the active tab changes.
Element.prototype.scrollIntoView ??= () => {};

// jsdom's ElementInternals stub (used by attachInternals()) implements the ARIA reflection
// properties but not the form-association half of the spec -- setFormValue is simply absent. Every
// form-associated iX control (ix-slider among them) calls it on every input event, so leaving it
// missing throws on the very first interaction rather than on anything this suite is testing for.
if (typeof ElementInternals !== "undefined") {
  ElementInternals.prototype.setFormValue ??= () => {};
}
