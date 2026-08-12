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

export function AppProvider({ children }) {
  const [watchlist, setWatchlist] = usePersistent("se.watchlist.v2", []);   // company names (stable across re-evaluations)
  const [savedViews, setSavedViews] = usePersistent("se.savedViews", []);   // {name, columns, filters}
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

  return (
    <AppCtx.Provider value={{
      watchlist, toggleWatch,
      savedViews, setSavedViews,
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
