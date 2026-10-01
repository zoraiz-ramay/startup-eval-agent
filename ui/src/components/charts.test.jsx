import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BandScale, HeatStrip, MiniBar, RadarChart, RingGauge, StackedBar } from "./charts.jsx";

/* Each chart states its numbers in its accessible name, and draws a missing value as missing. */
describe("RingGauge", () => {
  it("fills in proportion to the value and names it", () => {
    render(<RingGauge value={75} label="Traction 75 of 100" />);
    const svg = screen.getByRole("img", { name: "Traction 75 of 100" });
    const arcs = svg.querySelectorAll("circle");
    const [done, total] = arcs[1].getAttribute("stroke-dasharray").split(" ").map(Number);
    expect(done / total).toBeCloseTo(0.75, 2);
    expect(svg.querySelector(".ring-value").textContent).toBe("75");
  });

  it("draws no arc and a dash for a missing value, never 0", () => {
    render(<RingGauge value={null} label="not scored" />);
    const svg = screen.getByRole("img", { name: "not scored" });
    expect(svg.querySelectorAll("circle")).toHaveLength(1);
    expect(svg.querySelector(".ring-value").textContent).toBe("—");
  });

  it("clamps an out-of-range value to the ring", () => {
    render(<RingGauge value={140} label="over" />);
    const [done, total] = screen.getByRole("img", { name: "over" }).querySelectorAll("circle")[1]
      .getAttribute("stroke-dasharray").split(" ").map(Number);
    expect(done).toBeCloseTo(total, 5);
  });
});

describe("StackedBar", () => {
  it("sizes each part by its points and hatches an unscored part at its capacity", () => {
    render(<StackedBar label="Total" segments={[
      { key: "a", value: 19.7, color: "red" }, { key: "b", value: 35, color: "blue" },
      { key: "c", value: null, capacity: 15, color: "green" }]} />);
    const segs = screen.getByRole("img", { name: "Total" }).querySelectorAll(".stacked-seg");
    expect([...segs].map((s) => s.style.width)).toEqual(["19.7%", "35%", "15%"]);
    expect(segs[2].classList.contains("pending")).toBe(true);
  });
});

describe("MiniBar", () => {
  it("is an empty hatched track when there is no value", () => {
    render(<MiniBar value={null} label="Revenue: excluded" />);
    const bar = screen.getByRole("img", { name: "Revenue: excluded" });
    expect(bar.classList.contains("pending")).toBe(true);
    expect(bar.children).toHaveLength(0);
  });
});

describe("RadarChart", () => {
  it("plots every axis, names it without its value on the picture, and marks the opened axis", () => {
    render(<RadarChart active={1} axes={[{ label: "Founder", value: 4 }, { label: "Domain", value: 5 },
      { label: "Validation", value: 3 }, { label: "Network", value: 3 }]} />);
    const svg = screen.getByRole("img", { name: "Founder 4 of 5, Domain 5 of 5, Validation 3 of 5, Network 3 of 5" });
    expect(svg.querySelectorAll("circle")).toHaveLength(4);
    const labels = [...svg.querySelectorAll("text")];
    expect(labels.map((t) => t.textContent)).toEqual(["Founder", "Domain", "Validation", "Network"]);
    expect(labels.map((t) => t.classList.contains("on"))).toEqual([false, true, false, false]);
  });
});

describe("BandScale", () => {
  it("highlights the band the engine scored and marks the value on a log scale", () => {
    render(<BandScale edges={[1e8, 1e9, 5e9, 2e10, 1e11]} min={1e7} max={1e12} log value={2.31e10} active={4}
      format={(v) => String(v)} label="Market size" />);
    const scale = screen.getByRole("img", { name: "Market size" });
    const on = scale.querySelectorAll(".band-seg.on");
    expect(on).toHaveLength(1);
    expect(parseFloat(on[0].style.left)).toBeCloseTo(66.02, 1);          // log10(2e10): 10.301 of 7..12
    expect(parseFloat(scale.querySelector(".band-marker").style.left)).toBeCloseTo(67.27, 1);
  });
});

describe("HeatStrip", () => {
  it("makes each criterion a disclosure named by its level and anchor", () => {
    const onToggle = vi.fn();
    render(<HeatStrip name="Empower" idPrefix="cell" controls="detail" openId="b" onToggle={onToggle}
      cells={[{ id: "a", label: "Tool fit", score: 3, anchor: "Direct" },
        { id: "b", label: "Actionability", score: 1, anchor: "Theoretical only" }]} />);
    const tool = screen.getByRole("button", { name: "Tool fit: 3 of 3, Direct" });
    expect(tool).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "Actionability: 1 of 3, Theoretical only" })).toHaveAttribute("aria-controls", "detail");
    fireEvent.click(tool);
    expect(onToggle).toHaveBeenCalledWith("a");
  });
});
