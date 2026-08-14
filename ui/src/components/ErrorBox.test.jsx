import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ErrorBox from "./ErrorBox.jsx";

/**
 * X-03 — the error state is announced, not merely drawn.
 *
 * Replaces tests/test_alert_error_accessibility.py, which was the most misleading test in the
 * repo: it read `tests/ui/src/pages/Alerts.jsx` — a stale COPY of the source that lived inside
 * the test tree — and asserted `role="alert"` against that. The copy had the attribute; the real
 * ui/src/pages/Alerts.jsx never did. The test passed for months while the shipped app had no
 * accessible error state at all.
 *
 * The lesson is in the fix: assert against the component the app actually renders.
 */
describe("ErrorBox", () => {
  it("announces failures to assistive tech", () => {
    render(<ErrorBox message="Backend unreachable" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Backend unreachable");
  });

  it("appends an optional hint", () => {
    render(<ErrorBox message="Failed to load" hint="is the API running?" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load — is the API running?");
  });

  it("renders nothing when there is no error", () => {
    const { container } = render(<ErrorBox message="" />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
