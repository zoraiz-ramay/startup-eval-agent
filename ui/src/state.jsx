import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { ResearchProvider } from "./research.jsx";
import { api, setUnauthorizedHandler } from "./api.js";

// App-level UI state: watchlist, saved views, assistant dock. Persisted in
// localStorage (UI preferences only — never secrets).
const AppCtx = createContext(null);

// Identity lives in its own context, deliberately NOT merged into AppProvider. Page tests
// render components inside the real AppProvider, and src/test/setup.js makes any unstubbed
// fetch throw — folding the /api/auth/me call in here would break every one of them.
const AuthCtx = createContext({ status: "out", user: null, mode: "entra", signOut: () => {} });

function usePersistent(key, initial) {
  const [val, setVal] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch { /* quota */ }
  }, [key, val]);
  return [val, setVal];
}

const LEGACY_VIEWS_KEY = "se.savedViews";

/**
 * Whether the assistant starts open, decided once per load.
 *
 * Collapsed unless the reviewer deliberately left it open. Auto-opening it on every wide screen
 * squeezed the assessment beside it (the Scoring & Fit review found the fit panels overflowing
 * with the dock open), so the reviewer's own last explicit choice is what is remembered — and
 * only honoured above the shell's 1180px breakpoint. The dock is a 332px `position: fixed`
 * panel, so below that it would cover most of the page; there it opens on request only.
 */
const DOCK_AUTO_OPEN_QUERY = "(min-width: 1181px)";
const DOCK_PREF_KEY = "se.dockOpen.v1";

function dockOpenByDefault() {
  try {
    const wide = Boolean(globalThis.matchMedia?.(DOCK_AUTO_OPEN_QUERY)?.matches);
    return wide && localStorage.getItem(DOCK_PREF_KEY) === "open";
  } catch {
    return false;
  }
}

export function AppProvider({ children }) {
  const { user } = useContext(AuthCtx);
  const [watchlist, setWatchlist] = usePersistent("se.watchlist.v2", []);   // company names (stable across re-evaluations)
  // Views live on the server, keyed on the Entra oid, so they follow a reviewer between
  // machines instead of belonging to a browser profile. Loaded rather than persisted here.
  const [savedViews, setSavedViews] = useState([]);                         // {name, columns, filters}
  const [pins, setPins] = usePersistent("se.pins", ["Explore startups", "Solve a problem"]);
  // The department the reviewer is working for. Search, the Database grid and the profile's
  // department switch all read this one value: "my department" is something a reviewer has, not
  // a per-screen setting. Empty until they choose — a search cannot start without one.
  const [department, setDepartment] = usePersistent("se.department.v1", "");
  const [dockOpen, setDockOpenState] = useState(dockOpenByDefault);
  // Every open/close is a deliberate act (the rail toggle, the dock's close button, the Ask page),
  // so each one records the preference the next load starts from.
  const setDockOpen = useCallback((open) => {
    setDockOpenState(open);
    try { localStorage.setItem(DOCK_PREF_KEY, open ? "open" : "closed"); } catch { /* storage off */ }
  }, []);
  const [dockCtx, setDockCtx] = useState(null);                             // {runId, company}

  const toggleWatch = (company) =>
    setWatchlist((w) => (w.includes(company) ? w.filter((x) => x !== company) : [...w, company]));

  // `api.views?.()` rather than `api.views()`: page tests mock ../api.js with only the calls
  // the page under test makes, and src/test/setup.js makes any unstubbed fetch throw. The
  // optional call lets those tests mount the real provider and simply skip hydration.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve(api.views?.())
      .then(async (r) => {
        if (cancelled || !r) return;
        let views = r.views || [];
        // One-time lift of anything left in the old per-browser key, so a reviewer who had
        // views before this change does not silently lose them.
        let legacy = [];
        try { legacy = JSON.parse(localStorage.getItem(LEGACY_VIEWS_KEY) || "[]"); } catch { legacy = []; }
        const known = new Set(views.map((v) => v.name.toLowerCase()));
        for (const v of legacy) {
          if (!v?.name || known.has(String(v.name).toLowerCase())) continue;
          try {
            views = [...views, await api.saveView(v.name, v.columns || [], v.filters || {})];
          } catch { /* keep the local copy for the next attempt */ }
        }
        if (legacy.length) {
          try { localStorage.removeItem(LEGACY_VIEWS_KEY); } catch { /* ignore */ }
        }
        if (!cancelled) setSavedViews(views);
      })
      .catch(() => { /* signed out, or the API is down; the sidenav shows the empty state */ });
    return () => { cancelled = true; };
  }, []);

  const saveView = useCallback(async (name, columns, filters) => {
    const saved = await api.saveView(name, columns, filters);
    setSavedViews((v) => [...v.filter((x) => x.name !== saved.name), saved]);
    return saved;
  }, []);

  const removeView = useCallback(async (name) => {
    await api.deleteView(name);
    setSavedViews((v) => v.filter((x) => x.name !== name));
  }, []);

  return (
    <AppCtx.Provider value={{
      watchlist, toggleWatch,
      savedViews, saveView, removeView,
      pins, setPins,
      department, setDepartment,
      dockOpen, setDockOpen, dockCtx, setDockCtx,
    }}>
      <ResearchProvider key={user?.oid || "local"} userId={user?.oid}>{children}</ResearchProvider>
    </AppCtx.Provider>
  );
}

export const useApp = () => useContext(AppCtx);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null, mode: "entra" });

  const signedOut = useCallback(() => {
    // Idempotent on purpose. Several requests can 401 together — a page load fires three —
    // and each one calls this. Collapsing them into a single state transition is what stops
    // the app thrashing between screens.
    setState((s) => (s.status === "out" ? s : { ...s, status: "out", user: null }));
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signedOut);
    let cancelled = false;
    // StrictMode double-invokes this in development, so /api/auth/me is requested twice on
    // first paint. It is an idempotent read and the second response wins; leave it alone.
    api.me()
      .then((r) => {
        if (cancelled) return;
        setState({ status: r.authenticated ? "in" : "out", user: r.user || null, mode: r.mode });
      })
      .catch(() => { if (!cancelled) setState({ status: "out", user: null, mode: "entra" }); });
    return () => { cancelled = true; };
  }, [signedOut]);

  const signOut = useCallback(async () => {
    try { await api.logout(); } catch { /* already gone server-side; the UI still moves on */ }
    setState((s) => ({ ...s, status: "out", user: null }));
  }, []);

  return <AuthCtx.Provider value={{ ...state, signOut }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
