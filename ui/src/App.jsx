import React, { useEffect, useRef, useState } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  iconAi, iconAlarmBell, iconBookmark, iconCogwheel, iconDashboard, iconEye, iconHome,
  iconSearch, iconTable,
} from "@siemens/ix-icons/icons";
import { api } from "./api.js";
import { AppProvider, AuthProvider, useApp, useAuth } from "./state.jsx";
import AssistantDock from "./components/AssistantDock.jsx";
import Icon from "./components/Icon.jsx";
import { Loading } from "./components/widgets.jsx";
import SignIn from "./pages/SignIn.jsx";
import Home from "./pages/Home.jsx";
import Explore from "./pages/Explore.jsx";
import Profile from "./pages/Profile.jsx";
import Saved from "./pages/Saved.jsx";
import Alerts from "./pages/Alerts.jsx";
import AskAI from "./pages/AskAI.jsx";
import Settings from "./pages/Settings.jsx";
import Admin from "./pages/Admin.jsx";

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
      <span className="lens"><Icon icon={iconSearch} size={14} /></span>
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
  const { setDockOpen, dockOpen, watchlist } = useApp();
  const { user } = useAuth();
  const nav = useNavigate();
  const account = user?.name || user?.email || "Account";
  return (
    <header className="topbar">
      <div className="brand" role="link" style={{ cursor: "pointer" }} onClick={() => nav("/")}>
        <span className="name">Scout<b>Grid</b></span>
        <span className="sub">Startup intelligence · Siemens for Startups</span>
      </div>
      <CommandBar />
      {/* title alone is not an accessible name for an icon-only button — scripts/ix_lint.mjs
          checks for aria-label, and a screen reader gets nothing from the glyph. */}
      <div className="top-actions">
        <button className="icon-btn" aria-label="Advanced search" title="Advanced search"
          onClick={() => nav("/explore")}>
          <Icon icon={iconSearch} size={17} />
        </button>
        <button className="icon-btn ai" aria-label="AI assistant" title="AI assistant"
          aria-expanded={dockOpen} onClick={() => setDockOpen(!dockOpen)}>
          <Icon icon={iconAi} size={17} /><span className="label">AI</span>
        </button>
        <button className="icon-btn" title="Tracking"
          aria-label={watchlist.length
            ? `Tracking, ${watchlist.length} companies watched`
            : "Tracking"}
          onClick={() => nav("/alerts")}>
          <Icon icon={iconAlarmBell} size={17} />
          {watchlist.length > 0 && <span className="dot">{watchlist.length}</span>}
        </button>
        {/* The Export button that used to sit here navigated to /explore — the same place as
            Advanced search — and exported nothing. The real CSV export is Explore's own
            toolbar button, which knows what rows and columns are on screen. */}
        <button className="avatar-btn" aria-label={`Account: ${account}`} title={account}
          onClick={() => nav("/settings")}>{user?.initials || "?"}</button>
      </div>
    </header>
  );
}

/* ------------------------------------------------ icon rail + secondary nav */
// iX icons rather than Unicode box-drawing glyphs: ▦ (Explore) and ▤ (Views) were the same
// shape at 17px, and 🔔 rendered as a colour emoji in otherwise monochrome chrome.
const RAIL = [
  { to: "/", label: "Home", icon: iconHome, end: true },
  { to: "/explore", label: "Explore", icon: iconTable },
  { to: "/saved", label: "Views", icon: iconBookmark },
  { to: "/alerts", label: "Tracking", icon: iconEye },
  { to: "/ask", label: "Ask AI", icon: iconAi },
  { to: "/settings", label: "Settings", icon: iconCogwheel },
];
const ADMIN_RAIL = { to: "/admin", label: "Admin", icon: iconDashboard };

function Rail() {
  const { user } = useAuth();
  // The route is guarded server-side by require_admin; this only decides whether a reviewer
  // is shown a door they cannot open.
  const items = user?.is_admin ? [...RAIL, ADMIN_RAIL] : RAIL;
  return (
    <nav className="rail" aria-label="Primary">
      {items.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} title={n.label}
          className={({ isActive }) => "rail-item" + (isActive ? " active" : "")}>
          <span className="ri"><Icon icon={n.icon} size={18} /></span>
          <span className="rl">{n.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function SideNav() {
  const { savedViews, watchlist } = useApp();
  // NavLink's own isActive compares pathnames only, so every view link would light up at
  // once on /explore. The active view is the one named in the query string.
  const view = new URLSearchParams(useLocation().search).get("view") || "";
  return (
    <nav className="sidenav" aria-label="Secondary">
      <h4>Quick access</h4>
      <NavLink to="/?compose=1" className="snav-item">Start a scouting query</NavLink>
      <NavLink to="/explore" className={({ isActive }) => "snav-item" + (isActive ? " active" : "")}>
        Explore startups
      </NavLink>
      <NavLink to="/alerts" className="snav-item">
        Watchlist <span className="count">{watchlist.length}</span>
      </NavLink>

      <h4>Saved views</h4>
      {savedViews.length === 0 && (
        <div className="snav-item" style={{ color: "var(--text-3)", cursor: "default" }}>
          None yet — save one from Explore
        </div>
      )}
      {/* NavLinks, not <div onClick>: as divs these were unreachable by keyboard and could
          never pick up the .snav-item.active styling that already exists for them. */}
      {savedViews.map((v) => (
        <NavLink key={v.name} to={`/explore?view=${encodeURIComponent(v.name)}`}
          className={"snav-item" + (view === v.name ? " active" : "")}>
          {v.name}
        </NavLink>
      ))}
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
          {/* Registered for everyone: the page renders its own explanation when the API
              answers 403, which beats a blank 404 for a reviewer who was sent the link. */}
          <Route path="/admin" element={<Admin />} />
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
