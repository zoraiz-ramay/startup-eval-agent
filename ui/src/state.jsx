import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
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

export function AppProvider({ children }) {
  const [watchlist, setWatchlist] = usePersistent("se.watchlist.v2", []);   // company names (stable across re-evaluations)
  // Views live on the server, keyed on the Entra oid, so they follow a reviewer between
  // machines instead of belonging to a browser profile. Loaded rather than persisted here.
  const [savedViews, setSavedViews] = useState([]);                         // {name, columns, filters}
  const [pins, setPins] = usePersistent("se.pins", ["Explore startups", "Solve a problem"]);
  // Local what-if weighting for the six scoring dimensions, as points out of 100. null means the
  // reviewer has not overridden anything, which is what makes "reset" a single assignment rather
  // than a float comparison. Never sent to the API: the engine's score is the shared truth and
  // this is one person's sandbox.
  const [whatIfWeights, setWhatIfWeights] = usePersistent("se.whatIfWeights.v1", null);
  const [dockOpen, setDockOpen] = useState(false);
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
      whatIfWeights, setWhatIfWeights,
      dockOpen, setDockOpen, dockCtx, setDockCtx,
    }}>
      {children}
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
