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
    if ([404, 405].includes(res.status) && path === "/api/jobs") {
      throw new ApiError("The search service needs an update. Restart the API with the latest code, then try again.", res.status);
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

/**
 * A fresh evaluation, delivered in pieces as the engine produces them.
 *
 * A run takes a minute or two and all of it used to arrive at once, so the page held a skeleton
 * until routing finished even though the company profile had been ready for most of that time.
 *
 * `fetch` + a stream reader rather than `EventSource`: that is GET-only, and this has to be a POST
 * carrying the session cookie and the CSRF header. Falls back to the plain endpoint on any stream
 * failure, so a proxy that buffers `text/event-stream` costs the progressive render and nothing
 * else — `onDone` still fires with the same complete result either way.
 *
 * @param {(section: string, data: any) => void} onPartial
 * @returns {Promise<object>} the complete evaluation, identical to `api.evaluate`
 */
export async function evaluateStream(name, { doWeb = true, refresh = false, onPartial } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}/api/evaluate/stream`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": readCookie("sea_csrf") },
      body: JSON.stringify({ name, do_web: doWeb, refresh }),
    });
  } catch {
    return api.evaluate(name, doWeb, refresh);
  }
  if (res.status === 401) {
    onUnauthorized();
    throw new ApiError("Your session has ended.", 401);
  }
  if (!res.ok || !res.body) {
    // A non-streaming error response still carries a JSON detail; surface that rather than
    // re-running a minutes-long evaluation just to obtain the same message.
    const data = await res.json().catch(() => ({}));
    if ([404, 405].includes(res.status) && path === "/api/jobs") {
      throw new ApiError("The search service needs an update. Restart the API with the latest code, then try again.", res.status);
    }
    if (!res.ok) throw new ApiError(data.detail || `Request failed (${res.status})`, res.status);
    return api.evaluate(name, doWeb, refresh);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  let failure = null;

  // SSE frames are separated by a blank line, and a frame can straddle two network chunks — so
  // the buffer is only consumed up to the last complete separator.
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let split;
    while ((split = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const event = frame.match(/^event:\s*(.+)$/m)?.[1]?.trim();
      const raw = frame.match(/^data:\s*([\s\S]*)$/m)?.[1];
      if (!event || raw === undefined) continue;
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch {
        continue;                 // a frame we cannot read is skipped, never fatal
      }
      if (event === "partial") onPartial?.(payload.section, payload.data);
      else if (event === "done") result = payload;
      else if (event === "error") failure = payload;
    }
  }

  if (failure) throw new ApiError(failure.detail || "Evaluation failed.", failure.status || 500);
  // The stream ended without a verdict — the connection dropped mid-run. Ask for the result
  // outright rather than leaving the caller with a half-filled profile and no error.
  if (!result) return api.evaluate(name, doWeb, refresh);
  return result;
}

export const api = {
  health: () => request("/health"),
  search: (q) => request(`/api/search?q=${encodeURIComponent(q)}`),
  evaluate: (name, doWeb = true, refresh = false) =>
    request("/api/evaluate", { method: "POST", body: { name, do_web: doWeb, refresh }, timeoutMs: 240000 }),
  startJobs: (body) => request("/api/jobs", { method: "POST", body }),
  job: (id) => request(`/api/jobs/${encodeURIComponent(id)}`),
  departments: () => request("/api/departments"),
  department: (id) => request(`/api/departments/${encodeURIComponent(id)}`),
  addDepartmentCompany: (id, company) => request(`/api/departments/${encodeURIComponent(id)}/companies`, { method: "POST", body: { company } }),
  removeDepartmentCompany: (id, company) => request(`/api/departments/${encodeURIComponent(id)}/companies/${encodeURIComponent(company)}`, { method: "DELETE" }),
  tracxnStatus: () => request("/api/integrations/tracxn"),
  tracxnConnect: (returnTo = "workspace") => request(`/api/integrations/tracxn/connect?return_to=${encodeURIComponent(returnTo)}`, { method: "POST" }),
  tracxnDisconnect: () => request("/api/integrations/tracxn", { method: "DELETE" }),
  solve: (problem) =>
    request("/api/solve", { method: "POST", body: { problem }, timeoutMs: 180000 }),
  // The reviewer's own list. `runs` is the same row shape but spans everyone, so it is
  // admin-only — a non-admin calling it gets a 403, by design.
  myRuns: () => request("/api/my/searches"),
  runs: () => request("/api/runs"),
  run: (id) => request(`/api/runs/${encodeURIComponent(id)}`),
  adminOverview: () => request("/api/admin/overview"),
  adminSearches: () => request("/api/admin/searches"),
  adminList: () => request("/api/admin/admins"),
  adminGrant: (upn, note = "") =>
    request("/api/admin/admins", { method: "POST", body: { upn, note } }),
  adminRevoke: (upn) =>
    request(`/api/admin/admins/${encodeURIComponent(upn)}`, { method: "DELETE" }),
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
