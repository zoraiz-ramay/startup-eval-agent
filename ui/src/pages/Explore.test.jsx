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
    myRuns: vi.fn(async () => ({ runs: [] })),
    search: vi.fn(async () => ({ results: [] })),
    saveView: vi.fn(async (name, columns, filters) => ({ name, columns, filters })),
    deleteView: vi.fn(async () => ({ deleted: true })),
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

  it("X-04: the click-outside backdrop is hidden from assistive tech rather than a fake unlabelled button", async () => {
    const user = userEvent.setup();
    const { container } = renderExplore();
    await user.click(await screen.findByRole("button", { name: /customise columns/i }));

    // The mask has no accessible name and duplicates a close that Escape already provides — it
    // must not be exposed to the accessibility tree as an actionable, unlabelled element.
    const mask = container.querySelector(".drawer-mask");
    expect(mask).toHaveAttribute("aria-hidden", "true");
  });

  it("X-04: opening the drawer moves focus into it, and closing it with Escape returns focus to the trigger", async () => {
    const user = userEvent.setup();
    renderExplore();
    const trigger = await screen.findByRole("button", { name: /customise columns/i });
    await user.click(trigger);

    // A screen-reader user who activates the trigger needs their focus — and so their announced
    // context — to actually move into the panel that just appeared, not stay behind on the button.
    const panel = screen.getByRole("complementary", { name: /customise columns/i });
    expect(panel).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: /customise columns/i })).toBeNull();
    // Closing must not drop focus into <body> — it belongs back on the control that opened it.
    expect(trigger).toHaveFocus();
  });
});
