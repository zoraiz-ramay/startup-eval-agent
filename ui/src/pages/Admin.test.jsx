import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import Admin from "./Admin.jsx";
import { api } from "../api.js";

/**
 * The admin page is now the place access is granted, so the behaviour that matters is who
 * can be removed and who cannot.
 *
 * ADMIN_UPNS-seeded admins exist so a deployment can never end up with nobody able to
 * administer it. The server refuses to revoke them; if the page offered the control anyway,
 * the only way to find that out would be to press it and read an error. So the assertion
 * here is about the control being *absent*, not disabled.
 */
const OVERVIEW = {
  window_days: 30,
  users: { total: 2, recent: 1, searched_recent: 1 }, sessions: { total: 5 }, searches: { total: 9 },
  companies: { searched: 3, evaluated: 3 }, cache_hit_rate: 0.5,
  per_user: [], top_companies: [],
};

const ADMINS = {
  you: "e2e.reviewer@siemens.com",
  admins: [
    { upn: "e2e.reviewer@siemens.com", source: "env", granted_by: "", granted_at: "", note: "" },
    { upn: "colleague@siemens.com", source: "db", granted_by: "e2e.reviewer@siemens.com",
      granted_at: "2026-08-12T09:00:00+00:00", note: "" },
  ],
};

const renderAdmin = () => render(<MemoryRouter><Admin /></MemoryRouter>);

// Matched on the first cell, scoped to the administrators table: the granting admin's own
// name also appears in the "granted by" column, so a bare getByText finds two elements.
const rowFor = (upn) => {
  const table = screen.getByRole("heading", { name: /^administrators/i })
    .closest(".panel").querySelector("table");
  const row = within(table).getAllByRole("row")
    .find((r) => r.querySelector("td")?.textContent.startsWith(upn));
  if (!row) throw new Error(`no administrators row for ${upn}`);
  return row;
};

beforeEach(() => {
  vi.spyOn(api, "adminOverview").mockResolvedValue(OVERVIEW);
  vi.spyOn(api, "adminSearches").mockResolvedValue({ searches: [] });
  vi.spyOn(api, "runs").mockResolvedValue({ runs: [] });
  vi.spyOn(api, "adminList").mockResolvedValue(ADMINS);
});

afterEach(() => vi.restoreAllMocks());

describe("Admin — administrators", () => {
  it("lists both sources and says which is which", async () => {
    renderAdmin();
    await screen.findByRole("heading", { name: /administrators/i });

    expect(within(rowFor("e2e.reviewer@siemens.com")).getByText(/server setting/i)).toBeInTheDocument();
    expect(within(rowFor("colleague@siemens.com")).getByText(/granted in app/i)).toBeInTheDocument();
  });

  it("offers no remove control for a server-setting admin", async () => {
    renderAdmin();
    await screen.findByRole("heading", { name: /administrators/i });

    // The server would refuse this, so the button must not exist at all.
    expect(
      within(rowFor("e2e.reviewer@siemens.com")).queryByRole("button", { name: /remove/i }),
    ).not.toBeInTheDocument();
    expect(
      within(rowFor("colleague@siemens.com")).getByRole("button", { name: /remove/i }),
    ).toBeInTheDocument();
  });

  it("grants access and re-reads the list rather than guessing the new state", async () => {
    const grant = vi.spyOn(api, "adminGrant").mockResolvedValue({ upn: "new@siemens.com" });
    renderAdmin();
    await screen.findByRole("heading", { name: /administrators/i });

    await userEvent.type(screen.getByLabelText(/sign-in name/i), "new@siemens.com");
    await userEvent.click(screen.getByRole("button", { name: /grant access/i }));

    expect(grant).toHaveBeenCalledWith("new@siemens.com");
    // Two calls: the initial load and the reload after the change.
    await waitFor(() => expect(api.adminList).toHaveBeenCalledTimes(2));
  });

  it("surfaces a refused grant instead of clearing the field", async () => {
    vi.spyOn(api, "adminGrant").mockRejectedValue(new Error("already an administrator"));
    renderAdmin();
    await screen.findByRole("heading", { name: /administrators/i });

    const field = screen.getByLabelText(/sign-in name/i);
    await userEvent.type(field, "colleague@siemens.com");
    await userEvent.click(screen.getByRole("button", { name: /grant access/i }));

    expect(await screen.findByText(/already an administrator/i)).toBeInTheDocument();
    expect(field).toHaveValue("colleague@siemens.com");
  });

  it("explains a 403 rather than showing an error box", async () => {
    const forbidden = Object.assign(new Error("Administrator access required."), { status: 403 });
    api.adminOverview.mockRejectedValue(forbidden);
    api.adminSearches.mockRejectedValue(forbidden);
    api.runs.mockRejectedValue(forbidden);
    api.adminList.mockRejectedValue(forbidden);

    renderAdmin();
    expect(await screen.findByText(/administrator access required/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^administrators/i })).not.toBeInTheDocument();
  });

  it("says so when the deployment has no administrators at all", async () => {
    api.adminList.mockResolvedValue({ you: "", admins: [] });
    renderAdmin();
    expect(await screen.findByText(/nobody is an administrator/i)).toBeInTheDocument();
  });
});

/**
 * Three sign-in numbers sit together on this page because each is misleading alone: five
 * sign-ins by one person and five by five people are the same total and different facts.
 */
describe("Admin — sign-in metrics", () => {
  // "Reviewers" is both a stat label and the heading of the table below it, so the lookup is
  // pinned to the label element rather than to the text.
  const tile = (label) => screen.getByText(label, { selector: ".stat .k" }).closest(".stat");

  it("separates how many people from how many sign-ins", async () => {
    renderAdmin();
    await screen.findByText("Reviewers", { selector: ".stat .k" });

    expect(within(tile("Reviewers")).getByText("2")).toBeInTheDocument();
    expect(within(tile("Sign-ins")).getByText("5")).toBeInTheDocument();
  });

  it("reports unique sign-ins for the window, labelled with its length", async () => {
    renderAdmin();
    await screen.findByText("Signed in (30d)", { selector: ".stat .k" });
    expect(within(tile("Signed in (30d)")).getByText("1")).toBeInTheDocument();
  });

  it("lists a reviewer who signed in but never searched", async () => {
    api.adminOverview.mockResolvedValue({
      ...OVERVIEW,
      per_user: [{ oid: "oid-lurker", upn: "lurker@siemens.com", sign_ins: 2, searches: 0,
                   companies: 0, last_seen: "", last_sign_in: "2026-08-14T09:00:00+00:00" }],
    });
    renderAdmin();

    const row = (await screen.findByText("lurker@siemens.com")).closest("tr");
    const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
    // Sign-ins is a real count; the search columns show an em dash rather than a 0 that
    // would read as "searched nothing" instead of "has not searched".
    expect(cells[1]).toBe("2");
    expect(cells[2]).toBe("—");
    expect(cells[3]).toBe("—");
    expect(cells[4]).toContain("2026-08-14");
  });
});
