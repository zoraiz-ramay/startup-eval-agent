// Single API client: request timeouts, JSON handling, normalized errors.
// SECURITY: no tokens in the browser bundle — Vite exposes all VITE_* variables in
// client source. Sign-in happens entirely server-side (Entra ID via api/auth.py) and the
// browser holds nothing but an httpOnly session cookie it cannot read.
const BASE = import.meta.env.VITE_API_BASE || "";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function readCookie(name) {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1] ?? "";
}

// Set by AuthProvider. Kept as a module-level hook rather than a redirect inside request()
// because a 401 must NOT navigate: an evaluation runs for up to four minutes, and bouncing
// the whole page to the sign-in flow mid-request would discard whatever the reviewer was
// doing. Flipping React state instead lets the app swap to the sign-in screen in place.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = typeof fn === "function" ? fn : () => {};
}

async function request(path, { method = "GET", body, timeoutMs = 30000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      signal: ctrl.signal,
      credentials: "same-origin",
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        // Double-submit half of the CSRF defence. Reads are exempt; the server checks this
        // against the token it stored at sign-in, not against the cookie.
        ...(method === "GET" ? {} : { "X-CSRF-Token": readCookie("sea_csrf") }),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      onUnauthorized();
      throw new ApiError(data.detail || "Your session has ended.", 401);
    }
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
  // The reviewer's own list. `runs` is the same row shape but spans everyone, so it is
  // admin-only — a non-admin calling it gets a 403, by design.
  myRuns: () => request("/api/my/searches"),
  runs: () => request("/api/runs"),
  run: (id) => request(`/api/runs/${encodeURIComponent(id)}`),
  adminOverview: () => request("/api/admin/overview"),
  adminSearches: () => request("/api/admin/searches"),
  views: () => request("/api/my/views"),
  saveView: (name, columns, filters) =>
    request("/api/my/views", { method: "POST", body: { name, columns, filters } }),
  deleteView: (name) =>
    request(`/api/my/views/${encodeURIComponent(name)}`, { method: "DELETE" }),
  deleteRun: (id) => request(`/api/runs/${encodeURIComponent(id)}`, { method: "DELETE" }),
  challenges: () => request("/api/challenges"),
  ask: (question, runId = null) =>
    request("/api/ask", { method: "POST", body: { question, run_id: runId }, timeoutMs: 120000 }),
  // No reviewer argument on either of these: the server takes it from the session, so a
  // client cannot decide who gets credited for a routing change.
  override: (runId, newPillar, reason, evidenceNote = "") =>
    request(`/api/runs/${encodeURIComponent(runId)}/override`, {
      method: "POST",
      body: { new_pillar: newPillar, reason, evidence_note: evidenceNote },
    }),
  audit: (runId) => request(`/api/runs/${encodeURIComponent(runId)}/audit`),
  setChallengeStatus: (index, status) =>
    request(`/api/challenges/${encodeURIComponent(index)}`, {
      method: "PATCH", body: { status },
    }),
  me: () => request("/api/auth/me"),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  status: () => request("/api/status"),
};
export { ApiError };
