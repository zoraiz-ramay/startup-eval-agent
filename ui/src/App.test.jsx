import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("./api.js", () => ({
  api: {
    me: vi.fn(),
    search: vi.fn(async () => ({ results: [] })),
    myRuns: vi.fn(async () => ({ runs: [] })),
    views: vi.fn(async () => ({ views: [] })),
    challenges: vi.fn(async () => ({ challenges: [] })),
    logout: vi.fn(async () => ({ ok: true })),
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
    expect(await screen.findByRole("button", { name: /sign in with siemens/i })).toBeInTheDocument();
  });

  it("never calls the API for data while signed out", async () => {
    // The shell's command bar searches as soon as it mounts, so a gate placed inside the
    // shell instead of above it would fire a guaranteed-401 request on first paint. This
    // asserts the gate is in the right place, which no rendering assertion would catch.
    api.me.mockResolvedValue({ authenticated: false, mode: "entra" });
    renderApp();
    await screen.findByRole("button", { name: /sign in with siemens/i });
    expect(api.search).not.toHaveBeenCalled();
    expect(api.myRuns).not.toHaveBeenCalled();
  });

  it("renders the app shell once signed in", async () => {
    api.me.mockResolvedValue({
      authenticated: true, mode: "entra",
      user: { name: "Ada Lovelace", email: "ada@siemens.com", initials: "AL", oid: "9f" },
    });
    renderApp();
    await waitFor(() => expect(screen.getByRole("navigation", { name: /primary/i })).toBeInTheDocument());
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
  beforeEach(() => vi.clearAllMocks());

  it("is open on first paint on a wide screen", async () => {
    widthIs(true);
    signedIn();
    renderApp();
    expect(await screen.findByRole("complementary", { name: /ai assistant/i })).toBeInTheDocument();
  });

  it("stays closed on a narrow screen, where it would cover the page", async () => {
    widthIs(false);
    signedIn();
    renderApp();
    await screen.findByRole("navigation", { name: /primary/i });
    expect(screen.queryByRole("complementary", { name: /ai assistant/i })).not.toBeInTheDocument();
  });

  it("no longer duplicates the control in the command bar", async () => {
    widthIs(true);
    signedIn();
    renderApp();
    await screen.findByRole("navigation", { name: /primary/i });
    // Exactly one control for the assistant, and it is the rail's.
    const controls = screen.getAllByRole("button", { name: /ask ai|ai assistant/i });
    expect(controls).toHaveLength(1);
    expect(controls[0]).toHaveAccessibleName(/ask ai/i);
  });

  it("can be reopened from the rail after it is closed", async () => {
    widthIs(true);
    signedIn();
    renderApp();
    const toggle = await screen.findByRole("button", { name: /ask ai/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(screen.getByRole("button", { name: /close assistant/i }));
    expect(screen.queryByRole("complementary", { name: /ai assistant/i })).not.toBeInTheDocument();

    await userEvent.click(toggle);
    expect(screen.getByRole("complementary", { name: /ai assistant/i })).toBeInTheDocument();
  });
});
