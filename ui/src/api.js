// Single API client: request timeouts, JSON handling, normalized errors.
// SECURITY: no tokens in the browser bundle — Vite exposes all VITE_* variables in
// client source. Auth (if enabled) is enforced server-side; the browser reaches the
// API only through the same-origin nginx proxy.
const BASE = import.meta.env.VITE_API_BASE || "";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, timeoutMs = 30000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      signal: ctrl.signal,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(data.detail || `Request failed (${res.status})`, res.status);
    return data;
  } catch (e) {
    if (e.name === "AbortError") throw new ApiError("Request timed out.", 0);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request("/health"),
  search: (q) => request(`/api/search?q=${encodeURIComponent(q)}`),
  evaluate: (name, doWeb = true, refresh = false) =>
    request("/api/evaluate", { method: "POST", body: { name, do_web: doWeb, refresh }, timeoutMs: 240000 }),
  solve: (problem) =>
    request("/api/solve", { method: "POST", body: { problem }, timeoutMs: 180000 }),
  runs: () => request("/api/runs"),
  run: (id) => request(`/api/runs/${encodeURIComponent(id)}`),
  deleteRun: (id) => request(`/api/runs/${encodeURIComponent(id)}`, { method: "DELETE" }),
  challenges: () => request("/api/challenges"),
  ask: (question, runId = null) =>
    request("/api/ask", { method: "POST", body: { question, run_id: runId }, timeoutMs: 120000 }),
  override: (runId, newPillar, reason, evidenceNote = "", reviewer = "") =>
    request(`/api/runs/${encodeURIComponent(runId)}/override`, {
      method: "POST",
      body: { new_pillar: newPillar, reason, evidence_note: evidenceNote, reviewer },
    }),
  audit: (runId) => request(`/api/runs/${encodeURIComponent(runId)}/audit`),
  setChallengeStatus: (index, status, reviewer = "") =>
    request(`/api/challenges/${encodeURIComponent(index)}`, {
      method: "PATCH", body: { status, reviewer },
    }),
};
export { ApiError };
