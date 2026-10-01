import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TeamEvidence, { EvidencePreview, resolveEvidence } from "./TeamEvidence.jsx";

/**
 * A Team & Ecosystem criterion's evidence drawn as the people and organisations it cites — not
 * as record quotes — and only those it cites, each checked against the run.
 */
const DP = {
  founders: [
    { name: "Andreas Wagner", role: "Co-founder, Co-CEO, CTO", background: "PhD from University of Cambridge; previously Hydrogen Lead at ETC",
      linkedin: "https://www.linkedin.com/in/aw", source_url: "https://www.crunchbase.com/person/aw" },
    { name: "Alexandre Kremer", role: "Co-founder", background: "Chemical engineer", linkedin: "", source_url: "https://fr.linkedin.com/in/ak", photo_url: "https://img.test/ak.jpg" },
    { name: "Not Cited", role: "Advisor" }],
  programs: [{ name: "XPRENEURS accelerator", type: "accelerator", confidence: "corroborated", source_url: "https://indexed.vc/r" },
    { name: "Circular Valley", type: "accelerator", confidence: "self_asserted", source_url: "https://pb.test" }],
  commercial: { investors: [{ name: "UVC Partners", source_url: "https://munich-startup.de/a" }] },
};
const ev = (source, quote) => ({ id: source, source, quote, url: "" });
const FOUNDER = { id: "founder_experience", label: "Founder experience", evidence: [
  ev("deep_profile.founders[0].name", "Andreas Wagner"), ev("deep_profile.founders[0].background", "PhD from University of Cambridge"),
  ev("deep_profile.founders[1].name", "Alexandre Kremer"), ev("summary", "Radical Dot is led by two founders.")] };
const VALIDATION = { id: "external_validation", label: "External validation", evidence: [
  ev("deep_profile.programs[0].name", "XPRENEURS accelerator"), ev("deep_profile.programs[1].type", "accelerator"),
  ev("deep_profile.commercial.investors[0].name", "UVC Partners"), ev("deep_profile.programs[7].name", "Ghost Programme")] };

describe("TeamEvidence", () => {
  it("shows founders as profile cards — photo when recorded, else initials — with background lines and profile links", () => {
    render(<TeamEvidence criterion={FOUNDER} res={{ deep_profile: DP }} />);
    const people = screen.getByRole("list", { name: "Founders" });
    const cards = within(people).getAllByRole("listitem").filter((li) => li.classList.contains("person-card"));
    expect(cards).toHaveLength(2);                                       // "Not Cited" is not drawn
    expect(cards[0]).toHaveTextContent("Andreas Wagner");
    expect(cards[0]).toHaveTextContent("Co-founder, Co-CEO, CTO");
    expect(within(cards[0]).getByText("PhD from University of Cambridge")).toBeInTheDocument();
    expect(within(cards[0]).getByText("previously Hydrogen Lead at ETC")).toBeInTheDocument();
    expect(within(cards[0]).getByRole("link", { name: "LinkedIn" })).toHaveAttribute("href", "https://www.linkedin.com/in/aw");
    expect(cards[0].querySelector(".team-avatar")).toHaveTextContent("AW");
    expect(within(cards[1]).getByRole("img", { name: "Photo of Alexandre Kremer" })).toHaveAttribute("src", "https://img.test/ak.jpg");
    expect(screen.getByText("Radical Dot is led by two founders.")).toBeInTheDocument();   // the non-entity evidence stays as a quote
  });

  it("shows programmes and investors as organisation cards with their corroboration, and skips an entity the run no longer holds", () => {
    render(<TeamEvidence criterion={VALIDATION} res={{ deep_profile: DP }} />);
    const programmes = screen.getByRole("list", { name: "Programmes" });
    expect(within(programmes).getByText("XPRENEURS accelerator").closest("li")).toHaveTextContent("Independently corroborated");
    expect(within(programmes).getByText("Circular Valley").closest("li")).toHaveTextContent("Company-claimed");
    expect(within(screen.getByRole("list", { name: "Investors" })).getByRole("link", { name: "munich-startup.de" })).toBeInTheDocument();
    expect(screen.queryByText("Ghost Programme")).toBeNull();
  });

  it("falls back to the quotes when nothing cited is an entity", () => {
    render(<TeamEvidence criterion={{ evidence: [ev("summary", "A strong team.")] }} res={{ deep_profile: DP }} />);
    expect(screen.getByText("Startup evidence")).toBeInTheDocument();
    expect(screen.getByText("A strong team.")).toBeInTheDocument();
  });

  it("previews people as initials and organisations by name in the box", () => {
    const { container, unmount } = render(<EvidencePreview criterion={FOUNDER} res={{ deep_profile: DP }} />);
    expect(container.textContent).toBe("AWAndreas WagnerAKAlexandre Kremer");
    unmount();
    const org = render(<EvidencePreview criterion={VALIDATION} res={{ deep_profile: DP }} />);
    expect([...org.container.querySelectorAll(".preview-org")].map((e) => e.textContent)).toEqual(["XPRENEURS accelerator", "Circular Valley", "UVC Partners"]);
  });

  it("resolves a name citation only while the name still matches", () => {
    const { entities } = resolveEvidence([ev("deep_profile.founders[0].name", "Someone Else")], DP);
    expect(entities.founders).toBeUndefined();
  });
});
