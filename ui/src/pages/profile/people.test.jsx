import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/**
 * One founder, one row. Stored Radical Dot runs hold "Andreas Wagner" and "Dr. Andreas Wagner" side
 * by side; runs are never rewritten, so the profile collapses the spellings as it reads them.
 */
vi.mock("../../api.js", () => ({ api: { runBusinessFlow: vi.fn() } }));

import OverviewTab from "./OverviewTab.jsx";
import { dedupePeople, personKey } from "./people.js";

describe("personKey", () => {
  it("ignores titles, post-nominals, a role in brackets, accents and case", () => {
    expect(personKey("Dr. Andreas Wagner")).toBe("andreas wagner");
    expect(personKey("Prof. Dr.-Ing. Max Mustermann")).toBe("max mustermann");
    expect(personKey("Alexandre Krémer (CTO)")).toBe("alexandre kremer");
    expect(personKey("Jane Doe, PhD")).toBe("jane doe");
    expect(personKey("Jack Ma")).toBe("jack ma");                  // a surname is never an affix
  });

  it("keeps the first spelling and fills only its blanks from a duplicate", () => {
    expect(dedupePeople([{ name: "Andreas Wagner", role: "" }, { name: "Dr. Andreas Wagner", role: "CEO" }]))
      .toEqual([{ name: "Andreas Wagner", role: "CEO" }]);
  });
});

describe("Profile founders", () => {
  it("shows a founder spelled two ways once", () => {
    const res = { company: "Radical Dot", score: {}, deep_profile: { founders: [
      { name: "Andreas Wagner", role: "Co-founder" }, { name: "Alexandre Kremer", role: "Co-founder" },
      { name: "Dr. Andreas Wagner", role: "CEO", background: "PhD, Cambridge" }] } };
    render(<OverviewTab res={res} />);
    expect(screen.getAllByText(/Andreas Wagner/)).toHaveLength(1);
    expect(screen.getByText(/PhD, Cambridge/)).toBeInTheDocument();     // the duplicate's detail is kept
  });
});
