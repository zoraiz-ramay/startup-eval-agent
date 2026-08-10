import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Explore from "./Explore.jsx";
import { AppProvider } from "../state.jsx";

/**
 * EXP-02 / EXP-03 / EXP-08 — the column drawer.
 *
 * Replaces tests/test_esc_close_column_drawer.py, which asserted the literal string
 * `if (e.key === "Escape")` appeared in Explore.jsx. It had been failing for months because the
 * handler was never actually implemented — the string was the only thing anyone checked, and the
 * test could not tell the difference between a working keyboard exit and a missing one.
 */
vi.mock("../api.js", () => ({
  api: {
    runs: vi.fn(async () => ({ runs: [] })),
    search: vi.fn(async () => ({ results: [] })),
  },
}));

function renderExplore() {
  // Explore reads watchlist/saved views from AppProvider, so the real provider is used rather
  // than a stub — a stub would let the component drift from the contract it actually depends on.
  return render(
    <MemoryRouter initialEntries={["/explore"]}>
      <AppProvider>
        <Explore />
      </AppProvider>
    </MemoryRouter>,
  );
}

describe("Explore column drawer", () => {
  it("opens from the toolbar", async () => {
    const user = userEvent.setup();
    renderExplore();
    expect(screen.queryByRole("complementary", { name: /customise columns/i })).toBeNull();

    await user.click(await screen.findByRole("button", { name: /customise columns/i }));
    expect(screen.getByRole("complementary", { name: /customise columns/i })).toBeInTheDocument();
  });

  it("closes on Escape so a keyboard user is not trapped behind the mask", async () => {
    const user = userEvent.setup();
    renderExplore();
    await user.click(await screen.findByRole("button", { name: /customise columns/i }));
    expect(screen.getByRole("complementary", { name: /customise columns/i })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: /customise columns/i })).toBeNull();
  });

  it("gives every column control an accessible name", async () => {
    const user = userEvent.setup();
    renderExplore();
    await user.click(await screen.findByRole("button", { name: /customise columns/i }));

    // Reorder controls and add/remove checkboxes are icon-only; without names they are
    // unusable by screen reader and indistinguishable from each other.
    expect(screen.getAllByRole("button", { name: /move up/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /move down/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("checkbox", { name: /^(remove|add) /i }).length).toBeGreaterThan(0);
  });
});
