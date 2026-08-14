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
  users: { total: 2 }, sessions: { total: 5 }, searches: { total: 9 },
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
