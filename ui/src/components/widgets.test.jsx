import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Loading } from "./widgets.jsx";

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
