import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import SignIn from "./SignIn.jsx";

/**
 * Sign-in failures under Conditional Access are the one place this app talks to someone
 * who cannot get in and cannot see any other screen. Each case has to name the actual next
 * action, so these assert on the actionable noun rather than on the copy as a whole.
 */
const setQuery = (search) => {
  window.history.replaceState({}, "", `/signin${search}`);
};

describe("SignIn", () => {
  beforeEach(() => setQuery(""));
  afterEach(() => setQuery(""));

  it("offers sign-in with no error by default", () => {
    render(<SignIn />);
    expect(screen.getByRole("button", { name: /sign in with siemens/i })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("tells a non-compliant device where to go", () => {
    setQuery("?e=device_not_compliant");
    render(<SignIn />);
    expect(screen.getByRole("alert")).toHaveTextContent(/company portal/i);
  });

  it("names both device and network for a Conditional Access block", () => {
    // Entra returns the same code whether the device or the location failed, so the copy
    // cannot claim one without misdirecting half the people who see it.
    setQuery("?e=access_blocked");
    render(<SignIn />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/VPN/i);
    expect(alert).toHaveTextContent(/device/i);
  });

  it("tells an unassigned user to request access", () => {
    setQuery("?e=not_assigned");
    render(<SignIn />);
    expect(screen.getByRole("alert")).toHaveTextContent(/request access/i);
  });

  it("owns a misconfiguration instead of blaming the user", () => {
    setQuery("?e=config_error");
    render(<SignIn />);
    expect(screen.getByRole("alert")).toHaveTextContent(/not something you can fix/i);
  });

  it("falls back to a generic message for an unrecognised code", () => {
    setQuery("?e=something_microsoft_added_last_week");
    render(<SignIn />);
    expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i);
  });

  it("shows the correlation ID for IT, stripped of anything injectable", () => {
    setQuery("?e=unknown&cid=abc-123<script>");
    render(<SignIn />);
    expect(screen.getByText("abc-123script")).toBeInTheDocument();
  });

  it("sends the current location through so sign-in returns you where you were", async () => {
    window.history.replaceState({}, "", "/explore?q=siemens");
    render(<SignIn />);
    // jsdom refuses real navigation; capture the assignment instead.
    const assigned = [];
    delete window.location;
    window.location = { pathname: "/explore", search: "?q=siemens",
      set href(v) { assigned.push(v); } };
    await userEvent.click(screen.getByRole("button", { name: /sign in with siemens/i }));
    expect(assigned[0]).toBe(`/api/auth/login?next=${encodeURIComponent("/explore?q=siemens")}`);
  });
});
