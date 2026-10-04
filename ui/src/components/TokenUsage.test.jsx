import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

vi.mock("../api.js", () => ({
  api: {
    adminTokenUsage: vi.fn(),
    adminTokenUsageRun: vi.fn(),
  },
}));

import { api } from "../api.js";
import TokenUsage from "./TokenUsage.jsx";

const RUN = { run_id: 41, company: "Wandelbots", created_at: "2026-10-03T12:46:21+00:00", scope: "all departments",
  requested_by: "e2e.reviewer@siemens.com", calls: 3, cached_calls: 1, failed_calls: 1, input_tokens: 21000,
  output_tokens: 1500, reasoning_tokens: 9000, total_tokens: 31500, duration_ms: 64200 };

beforeEach(() => {
  vi.clearAllMocks();
  api.adminTokenUsage.mockResolvedValue({ runs: [RUN], unlogged_runs: 52, totals: { runs: 1, ...RUN } });
  api.adminTokenUsageRun.mockResolvedValue({ run_id: 41, calls: [
    { seq: 0, stage: "fit", kind: "completion", model: "gemini-2.5-flash", cached: false, ok: true, attempts: 2,
      input_tokens: 9000, output_tokens: 300, reasoning_tokens: 6000, total_tokens: 15300, duration_ms: 36200 },
    { seq: 1, stage: "summary", kind: "completion", model: "gemini-2.5-flash", cached: true, ok: true, attempts: 1,
      input_tokens: 0, output_tokens: 0, reasoning_tokens: 0, total_tokens: 0, duration_ms: 3 },
    { seq: 2, stage: "pillars", kind: "completion", model: "gemini-2.5-flash", cached: false, ok: false,
      reason: "rate_limited", attempts: 3, input_tokens: 0, output_tokens: 0, reasoning_tokens: 0, total_tokens: 0, duration_ms: 28000 },
  ] });
});

describe("TokenUsage", () => {
  it("lists each evaluation's tokens and says how many older runs have no log", async () => {
    render(<TokenUsage />);
    const row = (await screen.findByText("Wandelbots")).closest("tr");
    expect(row).toHaveTextContent("e2e.reviewer@siemens.com");
    expect(row).toHaveTextContent("2026-10-03 12:46 UTC");
    expect(row).toHaveTextContent("3 (1 cached) · 1 failed");
    expect(row).toHaveTextContent("31,500");
    expect(row).toHaveTextContent("64.2s");
    expect(screen.getByText(/52 older runs were saved before token logging/)).toBeInTheDocument();
  });

  it("opens a run's call log, stage by stage, and closes it again", async () => {
    render(<TokenUsage />);
    const toggle = await screen.findByRole("button", { name: /Show log for Wandelbots/ });
    fireEvent.click(toggle);
    const log = await screen.findByRole("table", { name: "Model calls of run 41" });
    const rows = within(log).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Siemens tool fit");
    expect(rows[0]).toHaveTextContent("15,300");
    expect(rows[0]).toHaveTextContent("OK after 2 attempts");
    expect(rows[1]).toHaveTextContent("From cache");
    expect(rows[2]).toHaveTextContent("Failed (rate_limited, 3 attempts)");
    expect(api.adminTokenUsageRun).toHaveBeenCalledWith(41);
    fireEvent.click(screen.getByRole("button", { name: /Hide log for Wandelbots/ }));
    expect(screen.queryByRole("table", { name: "Model calls of run 41" })).toBeNull();
  });

  it("says when nothing has been logged, rather than showing an empty table", async () => {
    api.adminTokenUsage.mockResolvedValue({ runs: [], unlogged_runs: 0, totals: { runs: 0 } });
    render(<TokenUsage />);
    expect(await screen.findByText("No evaluation has been logged yet.")).toBeInTheDocument();
  });
});
