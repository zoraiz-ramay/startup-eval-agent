import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExtLink, Loading, Radar } from "./widgets.jsx";

/**
 * X-03 / PROF-11 — loading state is announced, not just drawn.
 *
 * Replaces tests/test_accessible_loading.py, which regex-matched `aria-live` in the JSX source.
 * That assertion passed while the attribute sat in a comment and failed the moment the file was
 * reformatted; it never once proved a screen reader would hear anything.
 */
describe("Loading", () => {
  it("exposes the message as a live status region", () => {
    render(<Loading text="Evaluating Phena…" />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Evaluating Phena…");
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("hides the decorative spinner from assistive tech", () => {
    const { container } = render(<Loading text="Working…" />);
    expect(container.querySelector(".spinner")).toHaveAttribute("aria-hidden", "true");
    // The accessible name must be the message alone, with no spinner noise in it.
    expect(screen.getByRole("status").textContent.trim()).toBe("Working…");
  });
});

/**
 * Radar — the score chart, previously untested.
 *
 * The overlay exists because re-weighting does not change a dimension's score, only how much it
 * counts. Drawing the evidence polygon somewhere new would misrepresent evidence, so these assert
 * the evidence shape is untouched and the contribution arrives as a distinct second series.
 */
const DIMS = { traction: 60, siemens_fit: 70, product: 80, market: 50, founder: 55, ecosystem: 65 };

const dataPolygons = (c) =>
  [...c.querySelectorAll("polygon")].filter((p) => p.getAttribute("stroke-width") === "2");

describe("Radar", () => {
  it("draws one data polygon when given no overlay", () => {
    const { container } = render(<Radar dimensions={DIMS} />);
    expect(dataPolygons(container)).toHaveLength(1);
  });

  it("draws the contribution as a second, dashed series", () => {
    const overlay = { ...DIMS, ecosystem: 90 };
    const { container } = render(<Radar dimensions={DIMS} overlay={overlay} />);
    const polys = dataPolygons(container);
    expect(polys).toHaveLength(2);
    // Dashed rather than a second colour, so the two series are distinguishable without colour
    // vision and without adding a token.
    expect(polys[1]).toHaveAttribute("stroke-dasharray");
    expect(polys[0]).not.toHaveAttribute("stroke-dasharray");
  });

  it("leaves the evidence polygon exactly where it was when an overlay is added", () => {
    const { container: a } = render(<Radar dimensions={DIMS} />);
    const before = dataPolygons(a)[0].getAttribute("points");
    const { container: b } = render(<Radar dimensions={DIMS} overlay={{ ...DIMS, product: 120 }} />);
    expect(dataPolygons(b)[0].getAttribute("points")).toBe(before);
  });

  it("pins an over-scale contribution to the ring instead of drawing outside the chart", () => {
    const { container } = render(
      <Radar dimensions={DIMS} overlay={{ ...DIMS, siemens_fit: 260 }} size={260} />,
    );
    const r = 260 / 2 - 34;
    for (const poly of dataPolygons(container)) {
      for (const pair of poly.getAttribute("points").trim().split(/\s+/)) {
        const [x, y] = pair.split(",").map(Number);
        expect(Math.hypot(x - 130, y - 130)).toBeLessThanOrEqual(r + 0.001);
      }
    }
  });

  it("names both series and discloses the clamp, rather than clipping silently", () => {
    render(<Radar dimensions={DIMS} overlay={{ ...DIMS, siemens_fit: 260 }} />);
    const label = screen.getByRole("img").getAttribute("aria-label");
    expect(label).toMatch(/solid/i);
    expect(label).toMatch(/dashed/i);
    expect(label).toMatch(/past the outer ring/i);
  });
});

/**
 * ExtLink — what counts as a link.
 *
 * The regression: `core/data.py` stores a website exactly as the extraction returned it, and that
 * is routinely a bare host. ExtLink required `^https?://` and otherwise rendered NOTHING, so
 * Bliro's profile showed an empty Website row while `runs.db` held "bliro.io" the whole time.
 *
 * The opposite failure is the reason the fix has to stay narrow. `Fact.source_url` legitimately
 * carries labels rather than URLs — "GlassDollar" for a database fact, a filename for a pitch
 * deck — and a component that prefixes those manufactures a link to a host that does not exist.
 * Plain text is the honest rendering there, so both directions are pinned.
 */
describe("ExtLink", () => {
  it("links a stored bare domain, the case that rendered blank", () => {
    render(<ExtLink href="bliro.io" />);
    expect(screen.getByRole("link", { name: "bliro.io" })).toHaveAttribute("href", "https://bliro.io");
  });

  it("keeps a domain with a path intact", () => {
    render(<ExtLink href="bliro.io/en/pricing">site</ExtLink>);
    expect(screen.getByRole("link", { name: "site" }))
      .toHaveAttribute("href", "https://bliro.io/en/pricing");
  });

  it("leaves an absolute URL exactly as given", () => {
    render(<ExtLink href="https://www.linkedin.com/company/bliro/">LinkedIn</ExtLink>);
    expect(screen.getByRole("link", { name: "LinkedIn" }))
      .toHaveAttribute("href", "https://www.linkedin.com/company/bliro/");
  });

  it("renders a non-URL source label as text, never as a link", () => {
    render(<ExtLink href="GlassDollar">GlassDollar</ExtLink>);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("GlassDollar")).toBeInTheDocument();
  });

  it("does not turn a filename into a host", () => {
    render(<ExtLink href="phena_deck.pdf">deck</ExtLink>);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("refuses a scheme that is not http(s)", () => {
    // eslint-disable-next-line no-script-url
    render(<ExtLink href="javascript:alert(1)">click</ExtLink>);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("opens externally without leaking the referrer", () => {
    render(<ExtLink href="bliro.io" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noreferrer");
  });

  it("renders nothing at all for an empty value", () => {
    const { container } = render(<ExtLink href="" />);
    expect(container).toBeEmptyDOMElement();
  });
});
