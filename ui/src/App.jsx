import React, { useEffect, useRef, useState } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import { api } from "./api.js";
import { AppProvider, AuthProvider, useApp, useAuth } from "./state.jsx";
import AssistantDock from "./components/AssistantDock.jsx";
import { Loading } from "./components/widgets.jsx";
import SignIn from "./pages/SignIn.jsx";
import Home from "./pages/Home.jsx";
import Explore from "./pages/Explore.jsx";
import Profile from "./pages/Profile.jsx";
import Saved from "./pages/Saved.jsx";
import Alerts from "./pages/Alerts.jsx";
import AskAI from "./pages/AskAI.jsx";
import Settings from "./pages/Settings.jsx";

/* ------------------------------------------------ command bar (Ctrl/Cmd+K) */
function CommandBar() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [suggest, setSuggest] = useState([]);
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);
  const debounce = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    clearTimeout(debounce.current);
    if (q.trim().length < 1 || q.startsWith("/")) { setSuggest([]); return; }
    debounce.current = setTimeout(() => {
      api.search(q.trim())
        .then((d) => { setSuggest(d.results || []); setOpen(true); })
        .catch(() => setSuggest([]));
    }, 350);
    return () => clearTimeout(debounce.current);
  }, [q]);

  const submit = (name) => {
    const v = (name || q).trim();
    setOpen(false); setQ("");
    if (!v) return;
    if (v.startsWith("/solve")) return nav("/?compose=1");
    if (v.startsWith("/explore")) return nav("/explore");
    nav(`/startup/new?name=${encodeURIComponent(v)}`);
  };

  return (
    <div className="cmdbar suggest">
      <span className="lens">🔍</span>
      <input ref={inputRef} placeholder="Search a startup, or type / for commands…"
        value={q} onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        aria-label="Global search" />
      <span className="kbd">Ctrl K</span>
      {open && suggest.length > 0 && (
        <div className="suggest-list">
          {suggest.map((s, i) => (
            <div key={i} className="suggest-item" onMouseDown={() => submit(s.company_name)}>
              <strong>{s.company_name}</strong>
              {s.source === "applications" && <span className="badge" style={{ marginLeft: 6, fontSize: 11 }}>📄 Applications</span>}
              {s.hq && <span className="sub"> · {s.hq}</span>}
              <div className="sub">Evaluate through the full pipeline</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------ top bar */
function TopBar() {
  const { setDockOpen, dockOpen } = useApp();
  const nav = useNavigate();
  return (
    <header className="topbar">
      <div className="brand" role="link" style={{ cursor: "pointer" }} onClick={() => nav("/")}>
        <span className="name">Scout<b>Grid</b></span>
        <span className="sub">Startup intelligence · Siemens for Startups</span>
      </div>
      <CommandBar />
      <div className="top-actions">
        <button className="icon-btn" title="Advanced search" onClick={() => nav("/explore")}>⚲</button>
        <button className={"icon-btn ai"} title="AI assistant"
          onClick={() => setDockOpen(!dockOpen)}>✦ AI</button>
        <button className="icon-btn" title="Alerts" onClick={() => nav("/alerts")}>🔔</button>
        <button className="icon-btn" title="Export" onClick={() => nav("/explore")}>⤓</button>
        <button className="avatar-btn" title="Account" onClick={() => nav("/settings")}>Z</button>
      </div>
    </header>
  );
}

/* ------------------------------------------------ icon rail + secondary nav */
const RAIL = [
  { to: "/", label: "Home", icon: "⌂", end: true },
  { to: "/explore", label: "Explore", icon: "▦" },
  { to: "/saved", label: "Views", icon: "▤" },
  { to: "/alerts", label: "Tracking", icon: "◉" },
  { to: "/ask", label: "Ask AI", icon: "✦" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];

function Rail() {
  return (
    <nav className="rail" aria-label="Primary">
      {RAIL.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} title={n.label}
          className={({ isActive }) => "rail-item" + (isActive ? " active" : "")}>
          <span className="ri">{n.icon}</span>
          <span className="rl">{n.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function SideNav() {
  const { savedViews, watchlist } = useApp();
  const nav = useNavigate();
  return (
    <nav className="sidenav" aria-label="Secondary">
      <h4>Quick access</h4>
      <NavLink to="/explore" className={({ isActive }) => "snav-item" + (isActive ? " active" : "")}>
        Explore startups
      </NavLink>
      <NavLink to="/?compose=1" className="snav-item">Start a scouting query</NavLink>
      <NavLink to="/alerts" className="snav-item">
        Watchlist <span className="count">{watchlist.length}</span>
      </NavLink>

      <h4>Saved views</h4>
      {savedViews.length === 0 && (
        <div className="snav-item" style={{ color: "var(--text-3)", cursor: "default" }}>
          None yet — save one from Explore
        </div>
      )}
      {savedViews.map((v) => (
        <div key={v.name} className="snav-item"
          onClick={() => nav(`/explore?view=${encodeURIComponent(v.name)}`)}>
          {v.name}
        </div>
      ))}

      <h4>Pipeline</h4>
      <div className="snav-item" style={{ cursor: "default", color: "var(--text-2)", fontSize: 11.5 }}>
        Input → Enrich → Verify → Structure → Score → Review → Route
      </div>
    </nav>
  );
}

/* ------------------------------------------------ shell */
function Shell() {
  const { dockOpen } = useApp();
  const loc = useLocation();
  const noSidenav = loc.pathname.startsWith("/startup/");
  return (
    <>
      <TopBar />
      <Rail />
      {!noSidenav && <SideNav />}
      <main className={"content" + (noSidenav ? " no-sidenav" : "") + (dockOpen ? " with-dock" : "")}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/explore" element={<Explore />} />
          <Route path="/startup/:id" element={<Profile />} />
          <Route path="/saved" element={<Saved />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/ask" element={<AskAI />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <AssistantDock />
    </>
  );
}

/**
 * Decides whether anyone is signed in before the shell exists.
 *
 * The gate has to sit above <Shell/>, not inside it: CommandBar starts searching on a
 * debounce as soon as it mounts, so a shell rendered for an unauthenticated visitor fires
 * an API call that is guaranteed to 401. Keeping Shell unmounted until `status === "in"`
 * is what makes that impossible rather than merely unlikely.
 */
function AuthGate() {
  const { status, mode } = useAuth();
  if (status === "loading") {
    return (
      <div className="signin">
        <Loading text="Checking your session…" />
      </div>
    );
  }
  if (status !== "in") return <SignIn />;
  return (
    <>
      {/* If the stubbed sign-in ever reaches a real environment, it should be obvious in
          one second rather than after an incident review. */}
      {/* No live-region role on the banner: the text is present from first paint and never
          changes, so it reads in document order like any other content. role="status" would
          both misdescribe it and add a second live region to pages that already have one. */}
      {mode === "stub" && (
        <div className="stub-banner">
          Authentication is stubbed — this is not a real identity.
        </div>
      )}
      <Shell />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppProvider>
        <AuthGate />
      </AppProvider>
    </AuthProvider>
  );
}
