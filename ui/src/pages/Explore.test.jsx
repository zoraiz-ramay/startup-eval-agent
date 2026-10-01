import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Explore from "./Explore.jsx";
import { AppProvider } from "../state.jsx";
import { api } from "../api.js";
// WeightSliders (shared with Profile's what-if panel, MIG-22) now renders each dimension as an
// IxSlider -- its native input[role=slider] lives in a shadow root, so finding it needs the same
// shadow-piercing helper Profile.test.jsx uses, and it only listens for the native `input` event.
import { findShadowRole, findShadowText } from "../test/shadow.js";

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
    departments: vi.fn(async () => ({departments:[]})),
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

  it("X-04: clicking outside the pane closes it, with no unlabelled backdrop element to click", async () => {
    const user = userEvent.setup();
    const { container } = renderExplore();
    await user.click(await screen.findByRole("button", { name: /customise columns/i }));
    expect(screen.getByRole("complementary", { name: /customise columns/i })).toBeInTheDocument();

    // MIG-14: IxPane's closeOnClickOutside replaces the old bare `.drawer-mask` div outright —
    // there is no backdrop element left for an unlabelled-control problem to attach to at all,
    // rather than one that is merely hidden from the accessibility tree.
    expect(container.querySelector(".drawer-mask")).toBeNull();
    await user.click(document.body);
    expect(screen.queryByRole("complementary", { name: /customise columns/i })).toBeNull();
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

  // UI-14 (pre-existing focus-trap gap): pane.js's onExpandedChange does call the library's own
  // addFocusTrap(hostElement, { trapFocusInShadowDom: 'both' }) while floating+expanded, which
  // reads as a real Tab-cycling implementation in the compiled source. Tried as a test here —
  // `user.tab()` repeatedly from inside the open pane — and empirically it does NOT hold in this
  // jsdom/Testing-Library environment: focus lands on document.body rather than staying inside
  // the pane or wrapping to another of its own controls. Left out of the committed suite because
  // an assertion that fails is not something to ship green by loosening it; UI-14 stays open.
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
    const { container } = renderWithNav();
    await screen.findByRole("button", { name: /customise columns/i });

    await user.click(screen.getByRole("link", { name: /open munich/i }));

    // The chip proves the view was recognised even when its columns match the defaults.
    expect(await screen.findByText(/View: Munich/)).toBeInTheDocument();
    // Filters were stored by saveView from the day it shipped and no reader ever applied them.
    // IxCategoryFilter (MIG-12) renders each active filter as its own ix-filter-chip inside its
    // shadow root, rather than the input holding the text as a value.
    expect(await findShadowText(container, "munich")).toBeInTheDocument();
    expect(await findShadowText(container, /pillar = pass/i)).toBeInTheDocument();
    // (getFilterChipLabel renders "Pillar = Pass" for the pillar category chip — components.md's
    // FILTER_CATEGORIES label paired with logical-filter-operator.js's "=" for LogicalFilterOperator.EQUAL.)
  });

  it("saving a view sends it to the server and opens it", async () => {
    const user = userEvent.setup();
    api.views.mockResolvedValueOnce({ views: [] });
    const { container } = renderWithNav();

    await user.click(await screen.findByRole("button", { name: /customise columns/i }));
    await user.type(screen.getByPlaceholderText(/view name/i), "My view");
    await user.click(await findShadowRole(container, "button", { name: /^save view$/i }));

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
describe("Explore canonical scores", () => {
  it("does not offer what-if weighting", async () => {
    renderExplore();
    await screen.findByRole("button", { name: /customise columns/i });
    expect(screen.queryByText(/Weighting:/i)).toBeNull();
  });
});

describe("Database rows per department", () => {
  const RUNS = [
    { id: 3, company: "Acme", department_id: "si", department_label: "Smart Infrastructure", legacy: false,
      final_score: 71.2, total_status: "complete", pillar: "Connect", created_at: "2026-09-02" },
    { id: 2, company: "Acme", department_id: "di", department_label: "Digital Industries", legacy: false,
      final_score: null, total_status: "pending", pillar: "Defer", created_at: "2026-09-01" },
    { id: 1, company: "Acme", department_id: "", department_label: "", legacy: true,
      final_score: 55, total_status: "", pillar: "Empower", created_at: "2026-08-01" },
  ];
  const rowsText = () => [...document.querySelectorAll("tbody tr")].map((tr) => tr.textContent);

  it("shows one row per company and department, labelled, with a pending total never shown as 0", async () => {
    api.myRuns.mockResolvedValueOnce({ runs: RUNS });
    renderExplore();
    await screen.findByText("Smart Infrastructure");
    const rows = rowsText();
    expect(rows).toHaveLength(3);
    expect(rows.find((t) => t.includes("Digital Industries"))).toMatch(/pending/);
    expect(rows.find((t) => t.includes("Legacy"))).toBeTruthy();
  });

  it("narrows to the reviewer's department", async () => {
    localStorage.setItem("se.department.v1", JSON.stringify("di"));
    api.myRuns.mockResolvedValueOnce({ runs: RUNS });
    renderExplore();
    await screen.findByText("Digital Industries");
    expect(rowsText()).toHaveLength(1);
    localStorage.removeItem("se.department.v1");
  });
});
