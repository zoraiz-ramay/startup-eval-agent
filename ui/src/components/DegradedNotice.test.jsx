import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import DegradedNotice from "./DegradedNotice.jsx";

describe("DegradedNotice", () => {
  it("names each stage that ran without the model, and why", () => {
    render(<DegradedNotice degraded={[
      { stage: "fit", reason: "rate_limited", calls: 2 },
      { stage: "pillars", reason: "timeout", calls: 1 },
    ]} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Siemens tool fit: the model's rate limit was hit (2 calls)");
    expect(alert).toHaveTextContent("Pillar assessment: the model timed out");
    expect(alert).toHaveTextContent(/refresh to retry/);
  });

  it("renders nothing for a run where every call succeeded", () => {
    const { container } = render(<DegradedNotice degraded={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
