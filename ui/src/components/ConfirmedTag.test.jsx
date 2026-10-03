import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ConfirmedTag, { confirmedLabel } from "./ConfirmedTag.jsx";

describe("ConfirmedTag", () => {
  it("dates an item carried over from an earlier evaluation", () => {
    render(<ConfirmedTag item={{ name: "UVC Partners", last_confirmed_at: "2026-08-22T03:00:00+00:00" }} />);
    expect(screen.getByText("last confirmed 22 Aug 2026")).toHaveAttribute("title", expect.stringMatching(/did not find it again/));
  });

  it("renders nothing for an item this run found, or an unreadable date", () => {
    const { container } = render(<><ConfirmedTag item={{ name: "HTGF" }} /><ConfirmedTag item={{ last_confirmed_at: "soon" }} /></>);
    expect(container).toBeEmptyDOMElement();
    expect(confirmedLabel("not a date")).toBe("");
  });
});
