import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { IxCategoryFilter, IxContentHeader, IxKpi, IxPane, IxToggleButton } from "@siemens/ix-react";
import { iconTableRows } from "@siemens/ix-icons/icons";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import { PillarPill } from "../components/widgets.jsx";
import "./Explore.css";

// MIG-12: the one category this filter row ever offered is the pillar, so it maps onto
// IxCategoryFilter's single-category-hash shape (components.md) with one entry. Free text still
// goes in as a token — IxCategoryFilter's own input, not a second control next to it.
const FILTER_CATEGORIES = { pillar: { label: "Pillar", options: ["Connect", "Collaborate", "Empower", "Pass"] } };

/* Stored evaluation columns. */
const COLUMNS = {
  final_score: {
    label: "Fit Score",
    render: (r) => <span className="num">{Number(r.final_score || 0).toFixed(0)}</span>,
  },
  siemens_fit: { label: "Siemens Fit", render: (r) => <span className="num">{r.siemens_fit !== "" ? Number(r.siemens_fit).toFixed(0) : "—"}</span> },
  summary: { label: "Short Description", render: (r) => <span className="desc-clip" title={r.summary}>{r.summary || "—"}</span> },
  hq: { label: "Location", render: (r) => r.hq || "—" },
  founded_year: { label: "Founded", render: (r) => r.founded_year || "—" },
  stage: { label: "Stage", render: (r) => r.stage || "—" },
  funding: { label: "Funding", render: (r) => <span className="desc-clip" style={{ maxWidth: 140 }} title={r.funding}>{r.funding || "—"}</span> },
  founders: { label: "Founder Highlights", render: (r) => <span className="desc-clip" style={{ maxWidth: 180 }} title={r.founders}>{r.founders || "—"}</span> },
  evidence: {
    label: "Evidence Strength",
    render: (r) => r.evidence_count
      ? <span><span className="num">{r.verified_facts}</span><span className="muted">/{r.evidence_count} verified</span></span>
      : <span className="muted">—</span>,
  },
  trend: { label: "Market Signal", render: (r) => r.trend || "—" },
  pillar: {
    label: "Route",
    render: (r) => (
      <span>
        <PillarPill pillar={r.pillar} />{" "}
        {(r.secondary || []).map((s) => <PillarPill key={s} pillar={s} ghost>+{s}</PillarPill>)}
      </span>
    ),
  },
  /* Names the line, not just the flag. "SFS" on every row was the old behaviour and it was true of
     every row — the useful question is which of leasing, vendor finance, project finance or
     corporate lending applies, and rows evaluated before that was determined stay blank rather
     than claiming a line nobody established. */
  sfs: {
    label: "SFS",
    render: (r) => (r.sfs_relevant
      ? <span className="pill sfs" title={r.sfs_line || "Siemens Financial Services relevant"}>
          {r.sfs_line || "SFS"}
        </span>
      : ""),
  },
  confidence: { label: "Confidence", render: (r) => (r.confidence !== "" ? `${Math.round((r.confidence || 0) * 100)}%` : "—") },
  /* Portfolio stance — complementary, integrates, adjacent, or competes. Off by default: it is a
     filtering tool for a specific question ("who overlaps our own products"), not a number a
     scout reads on every row. */
  stance: {
    label: "Portfolio Stance",
    render: (r) => (r.stance
      ? <span className={r.competes ? "pill sfs" : "badge"}>{r.stance}</span>
      : <span className="muted">—</span>),
  },
  created_at: { label: "Evaluated", render: (r) => <span className="muted">{String(r.created_at).slice(0, 10)}</span> },
};
const DEFAULT_COLS = ["final_score", "siemens_fit", "summary", "hq", "stage", "funding",
  "evidence", "pillar", "sfs", "created_at"];
const SORTABLE = new Set(["final_score", "siemens_fit", "founded_year", "created_at", "hq", "stage"]);

function ColumnDrawer({ open, onClose, cols, setCols, onSaveView }) {
  const [viewName, setViewName] = useState("");
  const asideRef = useRef(null);
  // MIG-14: IxPane's own Escape handler (pane.js's registerEscapeListener) is attached to the
  // host element itself, and only fires while focus is inside it — kept here too, on window,
  // as a second path that doesn't depend on where focus happens to be. Both call the same
  // onClose, which is idempotent, so there is no double-close to guard against.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  // IxPane moves focus into itself on its own (pane.js's focusFirstSlottedElement), but only
  // after its open animation's completion callback fires — real in a browser, not guaranteed in
  // a test environment that doesn't run animation frames the same way. Doing it here too, plain
  // and synchronous, means the "focus lands inside" contract holds regardless of the pane's own
  // animation timing.
  useEffect(() => {
    if (open) asideRef.current?.focus();
  }, [open]);
  if (!open) return null;
  const move = (i, d) => {
    const next = [...cols];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    setCols(next);
  };
  const inactive = Object.keys(COLUMNS).filter((k) => !cols.includes(k));
  return (
    // variant="floating" + composition="right" is the same overlay shape AssistantDock (MIG-11)
    // already uses; .explore-drawer-pane forces position:fixed the same way .assistant-pane
    // does, since IxPane defaults every composition to position:relative (verified against
    // pane.css). closeOnClickOutside replaces the old bare `.drawer-mask` div outright — X-04's
    // complaint was a mouse-only control invisible to assistive tech, and there is now no
    // backdrop element at all for that problem to attach to; a plain window click listener
    // (pane.js's onExpandedChange, gated on event.composedPath()) closes it instead.
    <IxPane
      className="explore-drawer-pane"
      variant="floating"
      composition="right"
      size="320px"
      expanded
      closeOnClickOutside
      heading="Customise columns"
      ariaLabelCollapseCloseButton="Close customise columns"
      onExpandedChanged={(e) => { if (!e.detail.expanded) onClose(); }}
    >
      {/* IxPane's <aside> carries no aria-labelledby/aria-label wired to `heading` (verified
          against the compiled source, same gap AssistantDock's own comment documents) — the
          "Customise columns" landmark name has to come from a light-DOM wrapper we slot in. */}
      <div ref={asideRef} tabIndex={-1} role="complementary" aria-label="Customise columns">
        <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>Reorder, remove, or add columns.</p>
        {cols.map((k, i) => (
          <div key={k} className="drow">
            <input type="checkbox" checked readOnly aria-label={`Remove ${COLUMNS[k].label}`}
              onClick={() => setCols(cols.filter((c) => c !== k))} />
            {COLUMNS[k].label}
            <span className="mv">
              <button onClick={() => move(i, -1)} aria-label="Move up">↑</button>
              <button onClick={() => move(i, 1)} aria-label="Move down">↓</button>
            </span>
          </div>
        ))}
        {inactive.length > 0 && <h4 className="muted" style={{ margin: "14px 0 4px", fontSize: 11 }}>AVAILABLE</h4>}
        {inactive.map((k) => (
          <div key={k} className="drow">
            <input type="checkbox" checked={false} readOnly aria-label={`Add ${COLUMNS[k].label}`}
              onClick={() => setCols([...cols, k])} />
            {COLUMNS[k].label}
          </div>
        ))}
        <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
          <button className="btn secondary" onClick={() => setCols(DEFAULT_COLS)}>Restore defaults</button>
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
          <input className="input" placeholder="View name…" value={viewName}
            onChange={(e) => setViewName(e.target.value)} />
          <button className="btn" disabled={!viewName.trim()}
            onClick={() => { onSaveView(viewName.trim(), cols); setViewName(""); }}>
            Save view
          </button>
        </div>
      </div>
    </IxPane>
  );
}

export default function Explore() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const { watchlist, toggleWatch, savedViews, saveView: persistView } = useApp();

  const [runs, setRuns] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [drawer, setDrawer] = useState(false);
  const [cols, setCols] = useState(DEFAULT_COLS);
  const drawerTriggerRef = useRef(null);
  const drawerWasOpen = useRef(false);
  // Whatever path closed the drawer — Escape, backdrop click, or "Save view" — focus should land
  // back on the control that opened it, not fall through to <body> when the panel unmounts.
  useEffect(() => {
    if (drawerWasOpen.current && !drawer) drawerTriggerRef.current?.focus();
    drawerWasOpen.current = drawer;
  }, [drawer]);

  const q = params.get("q") || "";
  const pillar = params.get("pillar") || "";
  const sortKey = params.get("sort") || "final_score";
  const sortDir = params.get("dir") === "asc" ? 1 : -1;
  const dense = params.get("density") !== "comfortable";
  const viewName = params.get("view") || "";
  const activeView = savedViews.find((v) => v.name === viewName) || null;
  // category-filter.js's `@Watch('filterState')` re-syncs the component's internal chips whenever
  // this prop changes (not just on first load), so deriving it fresh from the URL params on every
  // render — rather than tracking it as separate component state — keeps a saved view, a
  // browser back/forward, or a manually edited URL in sync with what's on screen.
  const filterState = useMemo(() => ({
    tokens: q ? [q] : [],
    categories: pillar ? [{ id: "pillar", value: pillar, operator: "Equal" }] : [],
  }), [q, pillar]);

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  /* Opening a saved view.
   *
   * This used to be a useState lazy initializer, which is why views "did not open": React
   * Router does not remount Explore when only the query string changes, so the commonest
   * path of all — save a view from the drawer, then click it in the sidenav while already on
   * /explore — set ?view=… and ran nothing. An effect keyed on the name fires every time.
   *
   * It also applies view.filters, which saveView has always stored and no reader ever used:
   * a view saved as "Munich passes" opened unfiltered while the Saved page advertised the
   * filter in its list row.
   *
   * appliedRef stops the effect fighting the reviewer. Once a view is applied its filters are
   * theirs to change; re-running on every params tick would snap the grid back mid-typing. */
  const appliedRef = useRef(null);
  useEffect(() => {
    if (!viewName) { appliedRef.current = null; return; }
    if (appliedRef.current === viewName) return;
    if (!activeView) return;                 // views may still be loading from the server
    appliedRef.current = viewName;
    setCols(activeView.columns?.length ? activeView.columns : DEFAULT_COLS);
    const f = activeView.filters || {};
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("view", viewName);
      for (const key of ["q", "pillar", "sort"]) {
        if (f[key]) next.set(key, f[key]); else next.delete(key);
      }
      return next;
    }, { replace: true });
  }, [viewName, activeView, setParams]);

  const clearView = () => {
    appliedRef.current = null;
    setCols(DEFAULT_COLS);
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("view");
      return next;
    }, { replace: true });
  };

  useEffect(() => {
    api.myRuns().then((d) => setRuns(d.runs)).catch((e) => setError(e.message));
  }, []);

  const rows = useMemo(() => {
    if (!runs) return [];
    // one row per COMPANY (latest run) — history stays in the DB, reachable via profile
    const latest = [];
    const seen = new Set();
    for (const r of runs) {                      // runs arrive newest-first
      const k = r.company.toLowerCase();
      if (!seen.has(k)) { seen.add(k); latest.push(r); }
    }
    const f = q.trim().toLowerCase();
    const out = latest.filter((r) =>
      (!f || r.company.toLowerCase().includes(f) || (r.summary || "").toLowerCase().includes(f) ||
        (r.hq || "").toLowerCase().includes(f)) &&
      (!pillar || r.pillar === pillar));
    out.sort((a, b) => {
      const va = a[sortKey] ?? "", vb = b[sortKey] ?? "";
      return (va > vb ? 1 : va < vb ? -1 : 0) * sortDir;
    });
    return out;
  }, [runs, q, pillar, sortKey, sortDir]);

  const stats = useMemo(() => {
    if (!runs?.length) return null;
    return {
      total: runs.length,
      avg: (runs.reduce((s, r) => s + (r.final_score || 0), 0) / runs.length).toFixed(0),
      aligned: runs.filter((r) => r.pillar !== "Pass").length,
      sfs: runs.filter((r) => r.sfs_relevant).length,
    };
  }, [runs]);

  const toggleSel = (id) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  const exportCsv = () => {
    const header = ["company", ...cols].join(",");
    const lines = rows.map((r) =>
      [r.company, ...cols.map((k) => {
        const v = k === "pillar" ? [r.pillar, ...(r.secondary || [])].join("+")
          : k === "evidence" ? `${r.verified_facts}/${r.evidence_count}`
          : k === "sfs" ? (r.sfs_relevant ? (r.sfs_line || "yes") : "")
          : r[k] ?? "";
        return `"${String(v).replace(/"/g, '""')}"`;
      })].join(","));
    const blob = new Blob([header + "\n" + lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "startup_explorer.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const saveView = (name, columns) => {
    setDrawer(false);
    persistView(name, columns, { q, pillar, sort: sortKey })
      // Land on the view just saved, so "Save view" visibly produces something rather than
      // just closing the drawer.
      .then(() => { appliedRef.current = name; setParam("view", name); })
      .catch((e) => setError(e.message));
  };

  return (
    <div>
      <div className="crumb">Workspace &gt; Companies</div>
      {/* MIG-13: IxContentHeader replaces the hand-rolled page head, matching Profile's own use
          (MIG-18). headerSubtitle is plain text (components.md), so it carries the result count;
          the saved-view chip — not a title/subtitle concept — goes in the default slot instead. */}
      <IxContentHeader headerTitle="Companies Covered" headerSubtitle={`${rows.length} results`}>
        {/* Without this a view whose columns happen to match the defaults opens invisibly,
            which is indistinguishable from it not opening at all. */}
        {activeView && (
          <span className="fchip">
            View: {activeView.name}
            <button onClick={clearView} aria-label={`Close the view ${activeView.name}`}>✕</button>
          </span>
        )}
      </IxContentHeader>

      {stats && (
        <div className="stats-strip">
          <IxKpi label="Companies" value={stats.total} />
          <IxKpi label="Avg Fit Score" value={stats.avg} />
          <IxKpi label="Siemens-aligned" value={stats.aligned} />
          <IxKpi label="SFS relevant" value={stats.sfs} />
        </div>
      )}

      {error && <ErrorBox message={error} hint="is the API running?" />}

      <div className="toolbar">
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12.5 }}>
          <input type="checkbox" checked={allSelected} aria-label="Select all"
            onChange={() => setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.id)))} />
          Select all
        </label>
        {/* stopPropagation: IxPane's closeOnClickOutside registers its own window click listener
            synchronously as the pane mounts, which happens inside this same click's dispatch —
            without this, the browser delivers the very click that opens the drawer to that
            listener too (the pane isn't in this event's composedPath() yet, so it reads as
            "outside"), and the drawer closes itself in the same tick it opened. */}
        <button ref={drawerTriggerRef} className="tool-btn"
          onClick={(e) => { e.stopPropagation(); setDrawer(true); }}>⚙ Customise columns</button>
        {/* MIG-16: IxToggleButton's own `pressed` reflects aria-pressed automatically
            (toggle-button.js), which is the correct semantics for a two-state toggle — the
            hand-rolled ".active" class carried no such signal to assistive tech at all.
            aria-label is explicit rather than left to default: toggle-button.js always sets one
            (inherited, or else a fallback derived from the icon name alone, e.g. "Scale"), which
            would silently replace the slotted label text as the accessible name otherwise. */}
        <IxToggleButton variant="secondary" icon={iconTableRows} pressed={dense}
          aria-label={dense ? "Compact density" : "Comfortable density"}
          onPressedChange={(e) => setParam("density", e.detail ? "" : "comfortable")}>
          {dense ? "Compact" : "Comfortable"}
        </IxToggleButton>
        <span className="spacer" />
        {selected.size > 0 && <span className="muted" style={{ fontSize: 12 }}>{selected.size} selected</span>}
        <button className="tool-btn" onClick={exportCsv}>⤓ Export</button>
      </div>

      <div className="filter-row">
        <IxCategoryFilter
          categories={FILTER_CATEGORIES}
          filterState={filterState}
          uniqueCategories
          staticOperator="Equal"
          placeholder="Filter results…"
          ariaLabelFilterInput="Filter results"
          ariaLabelResetButton="Clear all filters"
          ariaLabelOperatorButton="Filter operator"
          onFilterChanged={(e) => {
            const fs = e.detail;
            const pillarToken = fs.categories.filter((c) => c.id === "pillar").pop();
            setParams((prev) => {
              const next = new URLSearchParams(prev);
              const text = fs.tokens.join(" ");
              if (text) next.set("q", text); else next.delete("q");
              if (pillarToken) next.set("pillar", pillarToken.value); else next.delete("pillar");
              return next;
            }, { replace: true });
          }}
          onFilterCleared={() => setParams({}, { replace: true })}
        />
      </div>

      <div className="grid-shell">
        {!runs && !error && (
          <div style={{ padding: 12 }}>
            {Array.from({ length: 8 }).map((_, i) => <div key={i} className="skel skel-row" />)}
          </div>
        )}
        {runs && rows.length === 0 && (
          <div className="empty" style={{ border: "none" }}>
            <div className="big">◎</div>
            <h4>No companies match</h4>
            <p>Adjust the filters, or evaluate a startup from the search bar above (Ctrl K).</p>
          </div>
        )}
        {runs && rows.length > 0 && (
          <table className={"dtable" + (dense ? " dense" : "")}>
            <thead>
              <tr>
                <th style={{ width: 30 }} aria-label="Select" />
                <th style={{ width: 26 }} aria-label="Watch" />
                <th className="sticky-col" onClick={() => { setParam("sort", "company"); setParam("dir", sortDir === 1 ? "" : "asc"); }}>
                  Company Name
                </th>
                {cols.map((k) => (
                  <th key={k}
                    onClick={() => {
                      if (!SORTABLE.has(k)) return;
                      if (sortKey === k) setParam("dir", sortDir === -1 ? "asc" : "");
                      else { setParam("sort", k); setParam("dir", ""); }
                    }}>
                    {COLUMNS[k].label}{sortKey === k ? (sortDir === -1 ? " ↓" : " ↑") : ""}
                  </th>
                ))}
                <th style={{ width: 30 }} aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={selected.has(r.id) ? "selected" : ""}
                  onClick={() => nav(`/startup/${r.id}`)}>
                  <td onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggleSel(r.id)}
                      aria-label={`Select ${r.company}`} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className={"star-btn" + (watchlist.includes(r.company) ? " on" : "")}
                      onClick={() => toggleWatch(r.company)}
                      aria-label={`Watch ${r.company}`}>★</button>
                  </td>
                  <td className="sticky-col">
                    <div className="co-cell">
                      <span className="logo-chip">{(r.company || "?").slice(0, 1).toUpperCase()}</span>
                      <strong>{r.company}</strong>
                      {r.parent_group && <span className="badge">Part of {r.parent_group}</span>}
                    </div>
                  </td>
                  {cols.map((k) => <td key={k}>{COLUMNS[k].render(r)}</td>)}
                  <td onClick={(e) => e.stopPropagation()} style={{ whiteSpace: "nowrap" }}>
                    <button className="kebab" title="Re-evaluate with fresh data"
                      aria-label={`Re-evaluate ${r.company}`}
                      onClick={() => nav(`/startup/new?name=${encodeURIComponent(r.company)}&refresh=1`)}>⟳</button>
                    <button className="kebab" aria-label={`Open ${r.company}`}
                      onClick={() => nav(`/startup/${r.id}`)}>⋮</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ColumnDrawer open={drawer} onClose={() => setDrawer(false)}
        cols={cols} setCols={setCols} onSaveView={saveView} />
    </div>
  );
}
