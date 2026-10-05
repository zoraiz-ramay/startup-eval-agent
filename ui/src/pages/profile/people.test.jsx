import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/**
 * One founder, one row. Stored Radical Dot runs hold "Andreas Wagner" and "Dr. Andreas Wagner" side
 * by side; runs are never rewritten, so the profile collapses the spellings as it reads them.
 */
vi.mock("../../api.js", () => ({ api: { runBusinessFlow: vi.fn() } }));

import OverviewTab from "./OverviewTab.jsx";
import { dedupePeople, personKey, personResolver, samePerson, withoutListed } from "./people.js";

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

describe("samePerson", () => {
  it("matches one person spelled with initials or sharing a profile link", () => {
    expect(samePerson({ name: "KD Kutadgu Gokalp Demirci" }, { name: "Kutadgu Gokalp Demirci" })).toBe(true);
    expect(samePerson({ name: "Andy Wagner", linkedin: "https://www.linkedin.com/in/wagner-andreas/" },
      { name: "Andreas Wagner", source_url: "https://linkedin.com/in/wagner-andreas" })).toBe(true);
  });

  it("keeps different people apart, even when research gave one the other's link", () => {
    expect(samePerson({ name: "Christian Piechnick" }, { name: "Maria Piechnick" })).toBe(false);
    expect(samePerson({ name: "Florian Zahn", source_url: "https://www.linkedin.com/in/anna-winiwarter" },
      { name: "Anna Winiwarter", linkedin: "https://www.linkedin.com/in/anna-winiwarter" })).toBe(false);
    expect(samePerson({ name: "Jack Ma" }, { name: "Jack" })).toBe(false);
  });

  it("gives one id to every spelling of a person", () => {
    const id = personResolver();
    expect(id({ name: "KD Kutadgu Gokalp Demirci" })).toBe(id("Kutadgu Gokalp Demirci"));
    expect(id({ name: "Maria Piechnick" })).not.toBe(id({ name: "Christian Piechnick" }));
  });

  it("drops an advisor already listed as a founder", () => {
    expect(withoutListed([{ name: "Trevor Amanya" }, { name: "Jane Roe" }], [{ name: "Trevor Amanya" }]))
      .toEqual([{ name: "Jane Roe" }]);
  });
});

describe("Profile founders", () => {
  it("shows Phena's co-founder, stored with and without his initials, once", () => {
    const res = { company: "Phena", score: {}, deep_profile: { founders: [
      { name: "KD Kutadgu Gokalp Demirci", role: "Co-Founder" }, { name: "Kutadgu Gokalp Demirci", role: "Co-Founder" }],
      advisors: [{ name: "Kutadgu Gokalp Demirci" }] } };
    render(<OverviewTab res={res} />);
    expect(screen.getAllByText(/Kutadgu Gokalp Demirci/)).toHaveLength(1);
  });


  it("shows a founder spelled two ways once", () => {
    const res = { company: "Radical Dot", score: {}, deep_profile: { founders: [
      { name: "Andreas Wagner", role: "Co-founder" }, { name: "Alexandre Kremer", role: "Co-founder" },
      { name: "Dr. Andreas Wagner", role: "CEO", background: "PhD, Cambridge" }] } };
    render(<OverviewTab res={res} />);
    expect(screen.getAllByText(/Andreas Wagner/)).toHaveLength(1);
    expect(screen.getByText(/PhD, Cambridge/)).toBeInTheDocument();     // the duplicate's detail is kept
  });
});
