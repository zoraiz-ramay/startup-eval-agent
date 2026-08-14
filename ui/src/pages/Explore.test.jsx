import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Explore from "./Explore.jsx";
import { AppProvider } from "../state.jsx";
import { api } from "../api.js";

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
    views: vi.fn(async () => ({ views: [] })),
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

/**
 * Saved views — the reported "views are not opening, once created".
 *
 * The cause was that ?view=… was read only in a useState lazy initializer. React Router does
 * not remount Explore when only the query string changes, so the commonest path of all —
 * save a view, then click it in the sidenav while still on /explore — changed the URL and ran
 * nothing. Every assertion below therefore navigates WITHOUT remounting; a test that rendered
 * a fresh tree at /explore?view=X would have passed against the broken code.
 */
describe("Explore saved views", () => {
  const HQ = "hq";

  function renderWithNav(initial = "/explore") {
    // A link inside the same tree is what makes this a same-mount navigation: react-router
    // updates the location in place, exactly as the real sidenav entry does.
    function Harness() {
      return (
        <>
          <Link to="/explore?view=Munich">open Munich</Link>
          <Explore />
        </>
      );
    }
    return render(
      <MemoryRouter initialEntries={[initial]}>
        <AppProvider>
          <Routes>
            <Route path="/explore" element={<Harness />} />
          </Routes>
        </AppProvider>
      </MemoryRouter>,
    );
  }

  it("applies a view's columns and filters when the URL changes without a remount", async () => {
    const user = userEvent.setup();
    api.views.mockResolvedValueOnce({
      views: [{ name: "Munich", columns: [HQ], filters: { q: "munich", pillar: "Pass" } }],
    });
    renderWithNav();
    await screen.findByRole("button", { name: /customise columns/i });

    await user.click(screen.getByRole("link", { name: /open munich/i }));

    // The chip proves the view was recognised even when its columns match the defaults.
    expect(await screen.findByText(/View: Munich/)).toBeInTheDocument();
    // Filters were stored by saveView from the day it shipped and no reader ever applied them.
    expect(screen.getByLabelText(/filter results/i)).toHaveValue("munich");
  });

  it("saving a view sends it to the server and opens it", async () => {
    const user = userEvent.setup();
    api.views.mockResolvedValueOnce({ views: [] });
    renderWithNav();

    await user.click(await screen.findByRole("button", { name: /customise columns/i }));
    await user.type(screen.getByPlaceholderText(/view name/i), "My view");
    await user.click(screen.getByRole("button", { name: /^save view$/i }));

    expect(api.saveView).toHaveBeenCalledWith("My view", expect.any(Array), expect.any(Object));
    expect(await screen.findByText(/View: My view/)).toBeInTheDocument();
  });

  it("closing the view chip restores the default grid", async () => {
    const user = userEvent.setup();
    api.views.mockResolvedValueOnce({
      views: [{ name: "Munich", columns: [HQ], filters: { q: "munich" } }],
    });
    renderWithNav("/explore?view=Munich");

    await user.click(await screen.findByRole("button", { name: /close the view munich/i }));
    expect(screen.queryByText(/View: Munich/)).toBeNull();
  });
});

/**
 * Portfolio re-weighting.
 *
 * The point is not that the arithmetic is right — ui/src/scoring/routing.test.js pins that
 * against real recorded runs. It is that the table applies it without ever presenting the
 * result as the evaluation: the engine's stored score has to stay on screen beside it.
 */
describe("Explore portfolio weighting", () => {
  const ROW = {
    id: 1, company: "Aeroview", pillar: "Pass", secondary: [], final_score: 40,
    sfs_relevant: false, created_at: "2026-08-01T00:00:00+00:00", summary: "", hq: "Munich",
    dimensions: { traction: 43.8, siemens_fit: 66.5, product: 85, market: 50, founder: 70, ecosystem: 100 },
    data_completeness: 0.25, fit_aligned: true,
  };

  function render1(runs = [ROW]) {
    api.myRuns.mockResolvedValueOnce({ runs });
    api.views.mockResolvedValueOnce({ views: [] });
    return render(
      <MemoryRouter initialEntries={["/explore"]}>
        <AppProvider><Explore /></AppProvider>
      </MemoryRouter>,
    );
  }

  it("leaves the grid on the engine's numbers until a weight is actually moved", async () => {
    const user = userEvent.setup();
    render1();
    await user.click(await screen.findByRole("button", { name: /weighting/i }));

    expect(screen.getByText(/move a slider to see what changes/i)).toBeInTheDocument();
    // No "(engine NN)" annotation yet: nothing has been re-weighted, so there is nothing to
    // distinguish it from.
    expect(screen.queryByText(/\(engine 40\)/)).toBeNull();
  });

  it("re-scores the table but keeps the engine's stored score on screen", async () => {
    const user = userEvent.setup();
    render1();
    await user.click(await screen.findByRole("button", { name: /weighting/i }));

    const slider = screen.getByLabelText("Product");
    fireEvent.change(slider, { target: { value: "80" } });

    // The re-weighted figure is shown WITH the stored one, never instead of it — this row's
    // engine score is 40 and must remain visible and labelled as the engine's.
    expect(await screen.findByText(/\(engine 40\)/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/companies change pillar|No companies change pillar/);
  });

  it("resets back to the engine weighting", async () => {
    const user = userEvent.setup();
    render1();
    await user.click(await screen.findByRole("button", { name: /weighting/i }));
    fireEvent.change(screen.getByLabelText("Product"), { target: { value: "80" } });
    await screen.findByText(/\(engine 40\)/);

    await user.click(screen.getByRole("button", { name: /reset to engine weights/i }));
    expect(screen.queryByText(/\(engine 40\)/)).toBeNull();
  });
});
