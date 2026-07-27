import React, { createContext, useContext, useEffect, useState } from "react";

// App-level UI state: watchlist, saved views, assistant dock. Persisted in
// localStorage (UI preferences only — never secrets).
const AppCtx = createContext(null);

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
  const [dockOpen, setDockOpen] = useState(false);
  const [dockCtx, setDockCtx] = useState(null);                             // {runId, company}

  const toggleWatch = (company) =>
    setWatchlist((w) => (w.includes(company) ? w.filter((x) => x !== company) : [...w, company]));

  return (
    <AppCtx.Provider value={{
      watchlist, toggleWatch,
      savedViews, setSavedViews,
      pins, setPins,
      dockOpen, setDockOpen, dockCtx, setDockCtx,
    }}>
      {children}
    </AppCtx.Provider>
  );
}

export const useApp = () => useContext(AppCtx);
