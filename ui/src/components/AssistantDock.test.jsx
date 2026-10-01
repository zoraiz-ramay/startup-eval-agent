import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The assistant is a chat: a field that sends on Enter, a conversation carried into each request,
 * and every reply labelled with where it came from — Tracxn, the model's web search, or the
 * model's memory, which must never read like a searched answer.
 */
vi.mock("../api.js", () => ({
  api: { ask: vi.fn(), tracxnStatus: vi.fn(), tracxnConnect: vi.fn() },
}));
vi.mock("../state.jsx", () => ({
  useApp: () => ({ dockOpen: true, setDockOpen: vi.fn(), dockCtx: { runId: 44, company: "Radical Dot" } }),
}));

import { api } from "../api.js";
import AssistantDock from "./AssistantDock.jsx";

const field = () => screen.getByRole("textbox", { name: "Message the assistant" });
const say = (text) => { fireEvent.change(field(), { target: { value: text } }); fireEvent.keyDown(field(), { key: "Enter" }); };

beforeEach(() => {
  vi.clearAllMocks();
  api.tracxnStatus.mockResolvedValue({ connected: false, configured: true });
});

describe("AssistantDock", () => {
  it("says which source answers before the first question", async () => {
    api.tracxnStatus.mockResolvedValue({ connected: true });
    render(<AssistantDock />);
    expect(await screen.findByText("Tracxn connected.")).toBeInTheDocument();
    expect(screen.getByText(/Answers come from Tracxn first, then web search/)).toBeInTheDocument();
  });

  it("offers a Tracxn connection when there is none, and says replies use web search", async () => {
    render(<AssistantDock />);
    expect(await screen.findByText("Tracxn not connected.")).toBeInTheDocument();
    expect(screen.getByText(/Answers use AI web search/)).toBeInTheDocument();
    expect(document.querySelector("ix-button")).toHaveTextContent("Connect Tracxn");
  });

  it("sends on Enter, keeps Shift+Enter for a new line, and carries the conversation into a follow-up", async () => {
    api.ask.mockResolvedValueOnce({ answer: "Its competitors are **Plastic Energy** and Mura.", provider: "web",
      source: "Web search (AI)", note: "", evidence: [{ title: "plasticenergy.com", url: "https://vertexaisearch.cloud.google.com/r/1" }] });
    render(<AssistantDock />);
    fireEvent.change(field(), { target: { value: "Who competes?" } });
    fireEvent.keyDown(field(), { key: "Enter", shiftKey: true });
    expect(api.ask).not.toHaveBeenCalled();
    fireEvent.keyDown(field(), { key: "Enter" });
    await waitFor(() => expect(api.ask).toHaveBeenCalledWith("Who competes?", 44, []));
    const reply = (await screen.findByText("Web search")).closest(".dock-msg");
    expect(within(reply).getByText("Plastic Energy").tagName).toBe("STRONG");      // markdown, not asterisks
    expect(within(reply).getByRole("link", { name: "plasticenergy.com" })).toHaveAttribute("target", "_blank");

    api.ask.mockResolvedValueOnce({ answer: "Plastic Energy.", provider: "tracxn", source: "Tracxn", note: "", evidence: [] });
    say("Which raised the most?");
    await waitFor(() => expect(api.ask).toHaveBeenCalledTimes(2));
    expect(api.ask.mock.calls[1][2]).toEqual([
      { role: "user", text: "Who competes?" },
      { role: "assistant", text: "Its competitors are **Plastic Energy** and Mura." }]);
    expect(await screen.findByText("Tracxn")).toBeInTheDocument();
  });

  it("labels an answer from the model's memory as unverified, with the reason", async () => {
    api.ask.mockResolvedValue({ answer: "Probably large.", provider: "model", source: "AI knowledge (unverified)",
      note: "Web search is not available for this model, so nothing here was checked against a source.", evidence: [] });
    render(<AssistantDock />);
    say("Market size?");
    expect(await screen.findByText("AI knowledge · unverified")).toBeInTheDocument();
    expect(screen.getByText(/nothing here was checked against a source/)).toBeInTheDocument();
  });

  it("clears the conversation", async () => {
    api.ask.mockResolvedValue({ answer: "Hello.", provider: "web", source: "Web search (AI)", note: "", evidence: [] });
    render(<AssistantDock />);
    say("Hi");
    await screen.findByText("Hello.");
    // ix-icon-button moves its aria-label onto the button inside its shadow root, so the host has
    // no label to query by here; the clear control is the second of the two field actions.
    const [send, clear] = document.querySelectorAll(".dock-actions ix-icon-button");
    expect(send.classList.contains("disabled")).toBe(true);                  // nothing typed
    fireEvent.click(clear);
    expect(screen.queryByText("Hello.")).toBeNull();
    expect(screen.getByText("Who are its closest competitors?")).toBeInTheDocument();
  });
});
