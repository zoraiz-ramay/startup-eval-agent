import React, { useEffect, useRef, useState } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import {
  IxApplication, IxApplicationHeader, IxContent, IxMenu, IxMenuCategory, IxMenuItem,
} from "@siemens/ix-react";
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
// MIG-07: IxApplicationHeader replaces the hand-rolled <header class="topbar">. name/nameSuffix
// carry the brand text the header owns internally (no slot exists to attach a click-to-home
// handler to them, unlike the old <div className="brand" onClick>) — Home stays one tap away on
// the rail/menu, so that affordance isn't lost, just relocated. The command bar is deliberately
// NOT slotted in here (CLAUDE.md: command-bar-in-header is MIG-10, out of scope for this batch) —
// Shell renders it as its own row, outside the header. The right-side controls go in the
// header's default slot ("Place items on the right side of the header" — components.md).
function TopBar() {
  const { watchlist } = useApp();
  const { user } = useAuth();
  const nav = useNavigate();
  const account = user?.name || user?.email || "Account";
  return (
    <IxApplicationHeader slot="application-header" name="ScoutGrid"
      nameSuffix="Startup intelligence · Siemens for Startups">
      {/* title alone is not an accessible name for an icon-only button — scripts/ix_lint.mjs
          checks for aria-label, and a screen reader gets nothing from the glyph. */}
      <button className="icon-btn" aria-label="Advanced search" title="Advanced search"
        onClick={() => nav("/explore")}>
        <Icon icon={iconSearch} size={17} />
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
    </IxApplicationHeader>
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
  // Not a link: this is the one control for the assistant now that the command bar's
  // duplicate has gone. The dock opens itself on a wide screen, so without a way back the
  // close button in its header would be one-way for the rest of the session.
  { action: "dock", label: "Ask AI", icon: iconAi },
  { to: "/settings", label: "Settings", icon: iconCogwheel },
];
const ADMIN_RAIL = { to: "/admin", label: "Admin", icon: iconDashboard };

// MIG-08: IxMenu replaces the hand-rolled <nav class="rail">. IxMenu's default aria-label
// ("Application Navigation", i18nAriaLabelMenu) names the inner role="menubar" region, not the
// outer role="navigation" landmark — that landmark's accessible name is wired to
// `applicationName` instead (verified against the compiled source, ix/dist/collection/
// components/menu/menu.js, which components.md's prop table doesn't make clear). Set here so
// the pre-existing "Primary" navigation query keeps meaning what it always meant, rather than
// leaving the landmark unnamed or renaming the test to a string that says less.
//
// MIG-09 folds the old standalone <nav class="sidenav"> ("Quick access" / "Saved views") into
// this SAME IxMenu, as two IxMenuCategory groups, rather than a second IxMenu — the backlog row
// is explicit that a second instance is the wrong shape here. `showSecondary` is what `!noSidenav`
// used to gate the whole <SideNav/> element with; IxMenuCategory has no route-awareness of its
// own, so the conditional still has to live in the caller (Shell), just threaded through a prop
// instead of a sibling.
function Rail({ showSecondary }) {
  const { user } = useAuth();
  const { dockOpen, setDockOpen, savedViews, watchlist } = useApp();
  const nav = useNavigate();
  const loc = useLocation();
  // The route is guarded server-side by require_admin; this only decides whether a reviewer
  // is shown a door they cannot open.
  const items = user?.is_admin ? [...RAIL, ADMIN_RAIL] : RAIL;
  const isActive = (n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to));
  // The active view is the one named in the query string, not the pathname (every saved view
  // shares the /explore pathname).
  const view = new URLSearchParams(loc.search).get("view") || "";
  return (
    <IxMenu slot="menu" applicationName="Primary Navigation">
      {items.map((n) => (
        n.action === "dock" ? (
          // slot="bottom" per IxMenuItem's own prop note: `bottom` is documented as "no longer
          // working, use slot='bottom' instead" — this is the one control for the assistant now
          // that the command bar's duplicate has gone, so it stays reachable rather than a
          // one-way close.
          <IxMenuItem key={n.label} slot="bottom" icon={n.icon} label={n.label}
            aria-label={n.label} active={dockOpen} aria-expanded={dockOpen}
            onClick={() => setDockOpen(!dockOpen)} />
        ) : (
          <IxMenuItem key={n.to} icon={n.icon} label={n.label} active={isActive(n)}
            onClick={() => nav(n.to)} />
        )
      ))}
      {showSecondary && (
        <>
          {/* className="menu-secondary" (a plain DOM class on the host element, same mechanism
              as the old .sidenav) is what styles.css's <1180px media query hides — IxMenuCategory
              itself carries no breakpoint prop (verified against the compiled source). */}
          <IxMenuCategory className="menu-secondary" label="Quick access" icon={iconSearch}>
            <IxMenuItem label="Start a scouting query" onClick={() => nav("/?compose=1")} />
            <IxMenuItem label="Explore startups" active={loc.pathname === "/explore"}
              onClick={() => nav("/explore")} />
            <IxMenuItem label="Watchlist" notifications={watchlist.length}
              onClick={() => nav("/alerts")} />
          </IxMenuCategory>
          <IxMenuCategory className="menu-secondary" label="Saved views" icon={iconBookmark}>
            {savedViews.length === 0 ? (
              // `disabled`, not a styled-but-inert <div>: IxMenuItem's own prop note says
              // disabled "removes event handlers", which is what an unclickable placeholder needs.
              <IxMenuItem label="None yet — save one from Explore" disabled />
            ) : (
              savedViews.map((v) => (
                <IxMenuItem key={v.name} label={v.name} active={view === v.name}
                  onClick={() => nav(`/explore?view=${encodeURIComponent(v.name)}`)} />
              ))
            )}
          </IxMenuCategory>
        </>
      )}
    </IxMenu>
  );
}

/* ------------------------------------------------ shell */
// IxApplication is the single shell root (application-header/menu/content as children,
// per CLAUDE.md's design contract), replacing the hand-rolled fixed-position siblings this
// used to be. TopBar is now IxApplicationHeader (MIG-07); Rail is now IxMenu, and as of MIG-09
// carries the old SideNav's content too, as IxMenuCategory groups inside the same menu rather
// than a second one (MIG-08/09). AssistantDock is still the bespoke component built for the
// Tracxn-modelled shell, pending MIG-11.
function Shell() {
  const { dockOpen } = useApp();
  const loc = useLocation();
  const noSidenav = loc.pathname.startsWith("/startup/");
  return (
    <IxApplication>
      <TopBar />
      <Rail showSecondary={!noSidenav} />
      <IxContent>
        {/* Deliberately outside IxApplicationHeader — see TopBar's comment. Not moved into the
            header until MIG-10. */}
        <div className="cmdbar-row"><CommandBar /></div>
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
      </IxContent>
      <AssistantDock />
    </IxApplication>
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
