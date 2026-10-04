import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TeamEvidence, { EvidencePreview, resolveEvidence } from "./TeamEvidence.jsx";

/**
 * A Team & Ecosystem criterion's evidence drawn as the people and organisations it rests on — not
 * as record quotes — each citation checked against the run. Every entity of a cited kind that the
 * run holds is listed, cited ones first and marked: listing only the cited ones made a refresh
 * look like lost data when the model simply cited a different two of fifteen investors.
 */
const DP = {
  founders: [
    { name: "Andreas Wagner", role: "Co-founder, Co-CEO, CTO", background: "PhD from University of Cambridge; previously Hydrogen Lead at ETC",
      linkedin: "https://www.linkedin.com/in/aw", source_url: "https://www.crunchbase.com/person/aw" },
    { name: "Alexandre Kremer", role: "Co-founder", background: "Chemical engineer", linkedin: "", source_url: "https://fr.linkedin.com/in/ak", photo_url: "https://img.test/ak.jpg" },
    { name: "Not Cited", role: "Advisor" }],
  programs: [{ name: "XPRENEURS accelerator", type: "accelerator", confidence: "corroborated", source_url: "https://indexed.vc/r" },
    { name: "Circular Valley", type: "accelerator", confidence: "self_asserted", source_url: "https://pb.test" }],
  commercial: { investors: [{ name: "UVC Partners", source_url: "https://munich-startup.de/a" },
    { name: "Accenture Ventures", source_url: "https://press.test/a", last_confirmed_at: "2026-08-22T03:00:00+00:00" }] },
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
    expect(cards).toHaveLength(3);                                       // the two cited, then the one on record
    expect(cards.map((c) => c.querySelector(".person-name").textContent)).toEqual(["Andreas Wagner", "Alexandre Kremer", "Not Cited"]);
    expect(cards[0]).toHaveTextContent("Cited in this assessment");
    expect(cards[2]).not.toHaveTextContent("Cited in this assessment");
    expect(screen.getByText(/2 cited of 3 on record/)).toBeInTheDocument();
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

  it("lists every investor on record, not only the ones the model happened to cite", () => {
    render(<TeamEvidence criterion={VALIDATION} res={{ deep_profile: DP }} />);
    const investors = within(screen.getByRole("list", { name: "Investors" })).getAllByRole("listitem");
    expect(investors.map((li) => li.querySelector("strong").textContent)).toEqual(["UVC Partners", "Accenture Ventures"]);
    expect(investors[0]).toHaveTextContent("Cited in this assessment");
    // Carried over from an earlier run, and says when it was last found.
    expect(investors[1]).toHaveTextContent("last confirmed 22 Aug 2026");
    expect(screen.getByText(/1 cited of 2 on record/)).toBeInTheDocument();
  });

  it("shows a customer an earlier run sourced with that source and its date", () => {
    const dp = { reference_customers: ["LANXESS"],
      customer_evidence: { LANXESS: { source_url: "https://lanxess.test/case", last_confirmed_at: "2026-09-01T00:00:00+00:00" } } };
    const crit = { id: "strategic_network", label: "Strategic network", evidence: [ev("deep_profile.reference_customers[0]", "LANXESS")] };
    render(<TeamEvidence criterion={crit} res={{ deep_profile: dp }} />);
    const card = within(screen.getByRole("list", { name: "Customers" })).getByText("LANXESS").closest("li");
    expect(card).toHaveTextContent(/last confirmed 1 Sept? 2026/);   // en-GB writes "Sept" on newer ICU
    expect(within(card).getByRole("link", { name: "lanxess.test" })).toBeInTheDocument();
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

  it("does not repeat programmes and investors an earlier criterion already shows", () => {
    const network = { id: "strategic_network", label: "Strategic network", evidence: [
      ev("deep_profile.programs[0].name", "XPRENEURS accelerator"), ev("deep_profile.commercial.investors[0].name", "UVC Partners"),
      ev("summary", "Partners with chemical producers.")] };
    const opened = [];
    render(<TeamEvidence criterion={network} res={{ deep_profile: DP }} criteria={[FOUNDER, VALIDATION, network]}
      onOpen={(id) => opened.push(id)} />);
    expect(screen.queryByText("XPRENEURS accelerator")).toBeNull();
    expect(screen.queryByText("UVC Partners")).toBeNull();
    expect(screen.getByText(/Also rests on 1 programme and 1 investor shown under/)).toBeInTheDocument();
    screen.getByRole("button", { name: "External validation" }).click();
    expect(opened).toEqual(["external_validation"]);
    expect(screen.getByText("Partners with chemical producers.")).toBeInTheDocument();
  });

  it("shows domain expertise as the founders' background, not their cards again", () => {
    const domain = { id: "domain_expertise", label: "Domain expertise", evidence: [
      ev("deep_profile.founders[0].background", "PhD from University of Cambridge")] };
    render(<TeamEvidence criterion={domain} res={{ deep_profile: DP }} criteria={[FOUNDER, domain]} />);
    expect(screen.queryByRole("list", { name: "Founders" })).toBeNull();
    expect(screen.getByText(/Also rests on 1 founder shown under Founder experience/)).toBeInTheDocument();
    expect(screen.getByText("PhD from University of Cambridge")).toBeInTheDocument();
  });

  it("previews only names no earlier box shows", () => {
    const network = { id: "strategic_network", label: "Strategic network", evidence: [
      ev("deep_profile.programs[0].name", "XPRENEURS accelerator")] };
    const { container } = render(<EvidencePreview criterion={network} res={{ deep_profile: DP }} criteria={[VALIDATION, network]} />);
    expect(container.textContent).toBe("");
  });

  it("lists a founder spelled two ways once", () => {
    const dp = { ...DP, founders: [...DP.founders, { name: "Dr. Andreas Wagner", role: "CEO" }] };
    render(<TeamEvidence criterion={FOUNDER} res={{ deep_profile: dp }} />);
    const names = [...document.querySelectorAll(".person-name")].map((n) => n.textContent);
    expect(names).toEqual(["Andreas Wagner", "Alexandre Kremer", "Not Cited"]);
  });

  it("resolves a name citation only while the name still matches", () => {
    const { entities } = resolveEvidence([ev("deep_profile.founders[0].name", "Someone Else")], DP);
    expect(entities.founders).toBeUndefined();
  });
});
