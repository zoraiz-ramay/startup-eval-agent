import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { findShadowRole, getAllShadowRole, getShadowRole } from "./test/shadow.js";

vi.mock("./api.js", () => ({
  api: {
    me: vi.fn(),
    tracxnStatus: vi.fn(async () => ({connected: false})),
    search: vi.fn(async () => ({ results: [] })),
    myRuns: vi.fn(async () => ({ runs: [] })),
    views: vi.fn(async () => ({ views: [] })),
    challenges: vi.fn(async () => ({ challenges: [] })),
    logout: vi.fn(async () => ({ ok: true })),
    departments: vi.fn(async () => ({ departments: [] })),
  },
  setUnauthorizedHandler: vi.fn(),
  ApiError: class extends Error {},
}));

import { api } from "./api.js";
import App from "./App.jsx";

const renderApp = () => render(<MemoryRouter><App /></MemoryRouter>);

describe("authentication gate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the sign-in screen when nobody is signed in", async () => {
    api.me.mockResolvedValue({ authenticated: false, mode: "entra" });
    renderApp();
    // IxButton (button.js) has `encapsulation: "shadow"` — MIG-28 moved SignIn's button onto
    // it, so its real <button> needs the same shadow-piercing query as the rail below.
    expect(await findShadowRole(document.body, "button", { name: /sign in with siemens/i })).toBeInTheDocument();
  });

  it("never calls the API for data while signed out", async () => {
    // The shell's command bar searches as soon as it mounts, so a gate placed inside the
    // shell instead of above it would fire a guaranteed-401 request on first paint. This
    // asserts the gate is in the right place, which no rendering assertion would catch.
    api.me.mockResolvedValue({ authenticated: false, mode: "entra" });
    renderApp();
    await findShadowRole(document.body, "button", { name: /sign in with siemens/i });
    expect(api.search).not.toHaveBeenCalled();
    expect(api.myRuns).not.toHaveBeenCalled();
  });

  it("renders the app shell once signed in", async () => {
    api.me.mockResolvedValue({
      authenticated: true, mode: "entra",
      user: { name: "Ada Lovelace", email: "ada@siemens.com", initials: "AL", oid: "9f" },
    });
    renderApp();
    // MIG-08: the rail is now an IxMenu, whose landmark <nav aria-label> lives inside its
    // shadow root (encapsulation: "shadow" in the compiled source) — not the light DOM
    // Testing Library's plain `screen` queries can see, hence the shadow-piercing helper.
    expect(await findShadowRole(document.body, "navigation", { name: /primary/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sign in with siemens/i })).not.toBeInTheDocument();
  });

  it("warns unmissably when the sign-in is stubbed", async () => {
    api.me.mockResolvedValue({
      authenticated: true, mode: "stub",
      user: { name: "E2E Reviewer", email: "e2e@siemens.com", initials: "ER", oid: "1" },
    });
    renderApp();
    expect(await screen.findByText(/authentication is stubbed/i)).toBeInTheDocument();
  });
});

/**
 * The assistant dock opens itself, and the rail is the only way back.
 *
 * The width condition is not cosmetic. Below 1180px `.content.with-dock` stops reserving
 * room for the panel (styles.css), so an auto-opened dock would sit on top of the page
 * instead of beside it — which on a phone means covering nearly all of it.
 */
const signedIn = () => api.me.mockResolvedValue({
  authenticated: true, mode: "entra",
  user: { name: "Ada Lovelace", email: "ada@siemens.com", initials: "AL", oid: "9f" },
});

const widthIs = (wide) => {
  globalThis.matchMedia = (query) => ({
    matches: wide, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  });
};

describe("assistant dock", () => {
  beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });

  it("starts collapsed when the reviewer has not chosen otherwise", async () => {
    widthIs(true);
    signedIn();
    renderApp();
    await findShadowRole(document.body, "navigation", { name: /primary/i });
    expect(screen.queryByRole("complementary", { name: /ai assistant/i })).not.toBeInTheDocument();
  });

  it("reopens on a wide screen when the reviewer left it open", async () => {
    localStorage.setItem("se.dockOpen.v1", "open");
    widthIs(true);
    signedIn();
    renderApp();
    expect(await screen.findByRole("complementary", { name: /ai assistant/i })).toBeInTheDocument();
  });

  it("stays closed on a narrow screen, where it would cover the page", async () => {
    localStorage.setItem("se.dockOpen.v1", "open");
    widthIs(false);
    signedIn();
    renderApp();
    await findShadowRole(document.body, "navigation", { name: /primary/i });
    expect(screen.queryByRole("complementary", { name: /ai assistant/i })).not.toBeInTheDocument();
  });

  it("no longer duplicates the control in the command bar", async () => {
    widthIs(true);
    signedIn();
    renderApp();
    await findShadowRole(document.body, "navigation", { name: /primary/i });
    // Exactly one control for the assistant, and it is the rail's. MIG-08: the rail is now an
    // IxMenu, whose items render with role="menuitem" (verified against the compiled source —
    // ix-menu-item sets an internal "menuitem" role whenever it is a direct child of ix-menu),
    // not "button" as the old hand-rolled <button class="rail-item"> did. That role-bearing
    // markup lives in ix-menu-item's shadow root, hence the shadow-piercing helper.
    const controls = getAllShadowRole(document.body, "menuitem", { name: /ask ai|ai assistant/i });
    expect(controls).toHaveLength(1);
    expect(controls[0]).toHaveAccessibleName(/ask ai/i);
  });

  it("can be reopened from the rail after it is closed", async () => {
    localStorage.setItem("se.dockOpen.v1", "open");
    widthIs(true);
    signedIn();
    renderApp();
    const toggle = await findShadowRole(document.body, "menuitem", { name: /ask ai/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    // MIG-11: the close control is now IxPane's own title-bar button (ariaLabelCollapseCloseButton
    // ="Close assistant"), not a hand-rolled one — it lives inside ix-pane's shadow root (and, one
    // level deeper, ix-icon-button's), so it needs the same shadow-piercing helper as the rail.
    await userEvent.click(getShadowRole(document.body, "button", { name: /close assistant/i }));
    expect(screen.queryByRole("complementary", { name: /ai assistant/i })).not.toBeInTheDocument();

    await userEvent.click(toggle);
    expect(screen.getByRole("complementary", { name: /ai assistant/i })).toBeInTheDocument();
  });
});
