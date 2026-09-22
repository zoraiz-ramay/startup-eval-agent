import React, { useEffect, useRef, useState } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import {
  IxApplication, IxApplicationHeader, IxContent, IxMenu, IxMenuItem,
} from "@siemens/ix-react";
import {
  iconAi, iconBookmark, iconBulb, iconDatabase, iconExplore, iconHome,
  iconSearch, iconStar, iconUserManagement,
} from "@siemens/ix-icons/icons";
import { api } from "./api.js";
import { AppProvider, AuthProvider, useApp, useAuth } from "./state.jsx";
import AssistantDock from "./components/AssistantDock.jsx";
import Icon from "./components/Icon.jsx";
import { Loading } from "./components/widgets.jsx";
import SignIn from "./pages/SignIn.jsx";
import Home from "./pages/Home.jsx";
import SearchHome from "./pages/SearchHome.jsx";
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
    if (v.startsWith("/solve")) return nav("/workspace?compose=1");
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

/* ------------------------------------------------ search landing (route "/")
 * "/" is a search page, not a dashboard: one centred field whose only job is to name a startup and
 * evaluate it. The scouting workspace it replaced now lives at /workspace ("Solve a Problem").
 * The command-bar row is hidden here (Shell) so the hero is the only search field on the page —
 * two identical inputs stacked would be a coin-flip for both a reviewer and a test locator. The
 * hero therefore has to carry the Ctrl/Cmd+K binding itself, or the shortcut would do nothing on
 * the one route where searching is the whole point.
 */
/* ------------------------------------------------ mobile menu launcher
 * The reference Siemens shell has no top bar, so the header is hidden on every width where the
 * rail is visible (md and up — styles.css). It survives ONLY at the sm breakpoint, where iX's
 * IxMenu collapses its items and offers no toggle of its own: the application header is the only
 * thing that renders the hamburger that reopens the menu, so a phone would otherwise have no way
 * to navigate. Empty of slotted controls — the brand, account and Tracking count all live in the
 * rail; this is just the launcher.
 */
function MobileHeader() {
  return <IxApplicationHeader slot="application-header" name="ScoutGrid" />;
}

/* ------------------------------------------------ icon rail + secondary nav */
// iX icons rather than Unicode box-drawing glyphs: ▦ (Explore) and ▤ (Views) were the same
// shape at 17px, and 🔔 rendered as a colour emoji in otherwise monochrome chrome.
// Home is now the search landing; "Solve a Problem" names the problem-solving workspace that used to be Home
// (/workspace), and the companies grid keeps its /explore route under the name "Databases" — the
// route is unchanged deliberately, so every saved-view link and visual baseline pointing at
// /explore still resolves to the grid it always did.
const RAIL = [
  { to: "/", label: "Explore a startup", icon: iconHome, end: true },
  { to: "/workspace", label: "Solve a Problem", icon: iconBulb },
  { to: "/explore", label: "Database", icon: iconDatabase },
  { to: "/saved", label: "Saved views", icon: iconBookmark },
  // Tracking is the watchlist — the same ★ affordance the Explore/Home rows use to add a
  // company — so iconStar names the destination directly and is distinct from the header's
  // alarm-bell (notifications) that shared the old iconEye's ambiguous "watching" meaning.
  { to: "/alerts", label: "Tracking", icon: iconStar },
  // Not a link: this is the one control for the assistant now that the command bar's
  // duplicate has gone. The dock opens itself on a wide screen, so without a way back the
  // close button in its header would be one-way for the rest of the session.
  { action: "dock", label: "Ask AI", icon: iconAi },

];
// Admin manages reviewers and access, so iconUserManagement names it; iconDashboard read as a
// second, generic "overview" glyph next to Home.
const ADMIN_RAIL = { to: "/admin", label: "Admin", icon: iconUserManagement };

// MIG-08: IxMenu replaces the hand-rolled <nav class="rail">. IxMenu's default aria-label
// ("Application Navigation", i18nAriaLabelMenu) names the inner role="menubar" region, not the
// outer role="navigation" landmark — that landmark's accessible name is wired to
// `applicationName` instead (verified against the compiled source, ix/dist/collection/
// components/menu/menu.js, which components.md's prop table doesn't make clear). Set here so
// the pre-existing "Primary" navigation query keeps meaning what it always meant, rather than
// leaving the landmark unnamed or renaming the test to a string that says less.
//
// href + an intercepted click is what makes a routed IxMenuItem a real anchor (middle-click,
// ctrl/cmd-click, right-click "copy link address") while keeping navigation client-side for a
// plain left click — a modified click is left alone so it falls through to the browser's own
// open-in-new-tab/-window handling instead of being hijacked.
function routeClick(nav, to) {
  return (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    nav(to);
  };
}

function Rail() {
  const { user } = useAuth();
  const { dockOpen, setDockOpen, watchlist } = useApp();
  const nav = useNavigate();
  const loc = useLocation();
  const account = user?.name || user?.email || "Account";
  // The route is guarded server-side by require_admin; this only decides whether a reviewer
  // is shown a door they cannot open.
  const items = user?.is_admin ? [...RAIL, ADMIN_RAIL] : RAIL;
  const isActive = (n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to));
  return (
    <IxMenu slot="menu" applicationName="Primary Navigation">
      {/* Visible brand at the top of the rail. `ix-menu-avatar` is the only slot iX renders above
          the Home item (verified against the compiled menu.js), so the app identity now lives in
          the sidebar rather than the application header. It is a real link to Home; the nav
          landmark's accessible name stays `applicationName` (asserted by the shell tests),
          separate from this visible mark. Collapsed rail shows just the scouting icon; the name
          appears when the menu is expanded (styles.css keys off ix-menu.expanded). */}
      <a slot="ix-menu-avatar" className="menu-brand" href="/" onClick={routeClick(nav, "/")}
        aria-label="ScoutGrid — Home">
        <span className="brand-mark" aria-hidden="true"><Icon icon={iconExplore} size={22} /></span>
        <span className="brand-text">ScoutGrid</span>
      </a>
      {items.map((n) => (
        n.action === "dock" ? (
          // slot="bottom" per IxMenuItem's own prop note: `bottom` is documented as "no longer
          // working, use slot='bottom' instead" — this is the one control for the assistant now
          // that the command bar's duplicate has gone, so it stays reachable rather than a
          // one-way close. Not a route, so no href: there is nothing to link to, only a panel
          // to toggle.
          <IxMenuItem key={n.label} slot="bottom" icon={n.icon} label={n.label}
            aria-label={n.label} active={dockOpen} aria-expanded={dockOpen}
            onClick={() => setDockOpen(!dockOpen)} />
        ) : (
          // home: Home is the one item TopBar's comment says is "relocated, not lost" from the
          // old clickable brand — the home slot (menu.js) renders unconditionally, ahead of the
          // isHiddenFromViewport() check that hides everything else behind the mobile toggle, so
          // this is what actually keeps a click-to-home reachable without opening the menu first.
          <IxMenuItem key={n.to} className={n.to === "/" ? "menu-first-destination" : undefined} icon={n.icon} label={n.label} active={isActive(n)}
            href={n.to} home={n.to === "/"} onClick={routeClick(nav, n.to)}
            notifications={n.to === "/alerts" && watchlist.length ? watchlist.length : undefined} />
        )
      ))}
      {/* Account at the very bottom of the rail (Siemens shell reference puts identity at the
          sidebar foot). Opens Settings; initials + name come from the authenticated principal.
          slot="bottom" lands it below the primary items and the Ask AI toggle. Collapsed rail
          shows the initials disc only; the name appears when the menu is expanded. */}
      <button slot="bottom" className="menu-account" onClick={() => nav("/settings")}
        aria-label={`Account: ${account}`} title={account}>
        <span className="acct-avatar" aria-hidden="true">{user?.initials || "?"}</span>
        <span className="acct-name">{account}</span>
      </button>
    </IxMenu>
  );
}

/* ------------------------------------------------ shell */
// IxApplication is the single shell root (application-header/menu/content as children,
// per CLAUDE.md's design contract), replacing the hand-rolled fixed-position siblings this
// used to be. TopBar is now IxApplicationHeader (MIG-07); Rail is now IxMenu, and as of MIG-09
// carries the old SideNav's content too, as IxMenuCategory groups inside the same menu rather
// than a second one (MIG-08/09); AssistantDock is now IxPane (MIG-11). The command bar is the
// one piece still rendered as its own row rather than through an iX primitive — that's MIG-10,
// explicitly out of scope for this batch.
function Shell() {
  const loc = useLocation();
  const { dockOpen } = useApp();
  const noSidenav = loc.pathname.startsWith("/startup/");
  // "/" is itself a search page — its hero field is the same control, so the row would only
  // duplicate it (and make "the" search box ambiguous).
  const isSearchHome = loc.pathname === "/";
  return (
    <IxApplication>
      <MobileHeader />
      <Rail />
      <IxContent>
        {/* The command bar is the app's own row at the top of the content area (the application
            header is hidden on every width where the rail shows). */}
        {!isSearchHome && <div className="cmdbar-row"><CommandBar /></div>}
        {/* "with-dock" reserved margin for the old fixed dock; MIG-06 already deleted its CSS
            (there was never layout to reserve once the shell stopped fixed-positioning things
            by hand), so this dropped the now-inert class rather than keep threading dead state
            through the className. */}
        <main className={"content" + (noSidenav ? " no-sidenav" : "") + (dockOpen ? " with-dock" : "")}>
          <Routes>
            <Route path="/" element={<SearchHome />} />
            {/* pages/Home.jsx is the scouting workspace the rail now calls "Solve a Problem". The file
                keeps its name; only the route and the label moved. */}
            <Route path="/workspace" element={<Home />} />
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
