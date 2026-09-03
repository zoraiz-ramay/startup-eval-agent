import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
// @siemens/ix-react's barrel registers ~100 custom elements as a side effect of import (MIG-01
// needs one of them, IxPill). Paying that cost here, once, in setup — rather than letting whichever
// test first imports a component that uses it eat several seconds against its own timeout.
import "@siemens/ix-react";
import { addIcons } from "@siemens/ix-icons";
import { iconLock, iconStar, iconBookmark, iconTrashcan, iconScale, iconTableRows } from "@siemens/ix-icons/icons";

afterEach(cleanup);

// Every `icon="…"` prop on an iX component (IxEmptyState, IxIconButton, …) resolves to a real
// network fetch of an SVG asset (resolveIcon.js) unless the name is pre-registered — and this
// project's global fetch stub above hard-throws on anything unstubbed, so the first render of an
// unregistered icon becomes an unhandled rejection that fails the whole run despite every
// assertion passing. Registering the handful the pages under test actually use (lock: Admin's
// forbidden state, star: Alerts' empty state, bookmark: Saved's empty state, trashcan: Saved's
// delete action, table-rows/scale: Explore's density/weighting toggles, MIG-16) resolves them
// from an in-memory cache instead of a fetch.
addIcons({ iconLock, iconStar, iconBookmark, iconTrashcan, iconScale, iconTableRows });

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

// jsdom implements neither this one — needed once IxInput (MIG-24's query composer) mounts in a
// test, since ix-input's field-wrapper uses it internally.
globalThis.IntersectionObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// jsdom's ElementInternals stub (used by attachInternals()) implements the ARIA reflection
// properties but not the form-association half of the spec — setFormValue/setValidity are simply
// absent. Every form-associated iX control (ix-slider, ix-input) calls these on every input event,
// so leaving them missing throws on the very first interaction rather than on anything this suite
// is testing for. No-ops are enough: nothing under test relies on native <form> submission
// semantics, only on the change events these components dispatch themselves.
if (typeof ElementInternals !== "undefined") {
  ElementInternals.prototype.setFormValue ??= function () {};
  ElementInternals.prototype.setValidity ??= function () {};
}
