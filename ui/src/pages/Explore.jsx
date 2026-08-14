import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import WeightSliders, { useWeighting } from "../components/WeightSliders.jsx";
import { DEFAULT_WEIGHTS, reweight } from "../scoring/index.js";
import { whatIfRouting } from "../scoring/routing.js";

/* Column registry — every explorer column in one place.
 *
 * `render(row, weighted)` — `weighted` is the row's re-scored figures when the reviewer has a
 * portfolio weighting applied, and undefined otherwise. Only two columns care; the rest ignore
 * the second argument. The engine's stored value stays on screen next to the re-weighted one
 * rather than being replaced by it: they are not the same claim, and only one of them is what
 * the database holds. */
const COLUMNS = {
  final_score: {
    label: "Fit Score",
    render: (r, w) => (
      <span>
        <span className="num">{Number((w ? w.score : r.final_score) || 0).toFixed(0)}</span>
        {w && (
          <span className="muted" style={{ fontSize: 11, marginLeft: 5 }}>
            (engine {Number(r.final_score || 0).toFixed(0)})
          </span>
        )}
      </span>
    ),
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
    render: (r, w) => (
      <span>
        <span className={`pill ${r.pillar}`}>{r.pillar}</span>{" "}
        {w?.moved && (
          <>
            <span className="muted">→</span>{" "}
            <span className={`pill ghost ${w.pillar}`}>{w.pillar}</span>{" "}
          </>
        )}
        {(r.secondary || []).map((s) => <span key={s} className={`pill ghost ${s}`}>+{s}</span>)}
      </span>
    ),
  },
  sfs: { label: "SFS", render: (r) => (r.sfs_relevant ? <span className="pill sfs">SFS</span> : "") },
  confidence: { label: "Confidence", render: (r) => (r.confidence !== "" ? `${Math.round((r.confidence || 0) * 100)}%` : "—") },
  created_at: { label: "Evaluated", render: (r) => <span className="muted">{String(r.created_at).slice(0, 10)}</span> },
};
const DEFAULT_COLS = ["final_score", "siemens_fit", "summary", "hq", "stage", "funding",
  "evidence", "pillar", "sfs", "created_at"];
const SORTABLE = new Set(["final_score", "siemens_fit", "founded_year", "created_at", "hq", "stage"]);

function ColumnDrawer({ open, onClose, cols, setCols, onSaveView }) {
  const [viewName, setViewName] = useState("");
  const asideRef = useRef(null);
  // Escape closes the drawer. It overlays the table behind a mask, so without a keyboard exit a
  // keyboard-only user is trapped: the mask is a div and cannot be activated with a key.
  // Registered before the early return below — hooks must run on every render.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  // Opening the drawer doesn't move the trigger button out of the DOM, so without this a
  // keyboard/screen-reader user who activates it hears nothing change — their focus stays put
  // while a whole panel appears behind them. tabIndex=-1 makes the panel a valid focus target
  // without adding it to the normal Tab order (it isn't a control itself).
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
    <>
      {/* Click-outside-to-close is a mouse convenience, not a control: closing is already fully
          keyboard-reachable via Escape (below) and doesn't need a second, redundant path. Giving
          this div role="button"+tabIndex would add a tab stop that a screen reader announces as
          an actionable "button" with no real label — worse than leaving it out of the
          accessibility tree entirely, which aria-hidden does. */}
      <div className="drawer-mask" aria-hidden="true" onClick={onClose} />
      <aside ref={asideRef} tabIndex={-1} className="drawer" aria-label="Customise columns">
        <h2>Customise columns</h2>
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
      </aside>
    </>
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
  const [weightingOn, setWeightingOn] = useState(false);
  const { active: weights, modified, reset: resetWeights } = useWeighting();
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

  /* Portfolio re-weighting.
   *
   * The what-if on a profile answers "would THIS company re-route". The question a scout
   * actually has is "under my business unit's priorities, who should we be talking to" —
   * which is a property of the whole table, not one row. Every row carries the eight numbers
   * needed to re-score it (store.list_runs), so this is arithmetic in the browser, not a
   * round trip per company.
   *
   * The engine's score is never overwritten: whatIf lives beside it, and the columns keep
   * showing the stored value with the re-weighted one next to it. */
  const weighted = useMemo(() => {
    if (!runs || !weightingOn || !modified) return null;
    const out = new Map();
    for (const r of runs) {
      if (!r.dimensions || !Object.keys(r.dimensions).length) continue;
      const scoreLike = { dimensions: r.dimensions, data_completeness: r.data_completeness };
      const re = reweight(scoreLike, weights);
      const rt = whatIfRouting(scoreLike, { aligned: r.fit_aligned }, weights);
      if (!re || !rt) continue;
      const base = whatIfRouting(scoreLike, { aligned: r.fit_aligned }, DEFAULT_WEIGHTS);
      out.set(r.id, {
        score: re.finalScore,
        pillar: rt.pillar,
        // Compared against the RE-DERIVED baseline, not the stored pillar: a human override or
        // an older engine would otherwise be reported as an effect of the reviewer's weighting.
        from: base ? base.pillar : r.pillar,
        moved: Boolean(base && base.pillar !== rt.pillar),
      });
    }
    return out;
  }, [runs, weightingOn, modified, weights]);

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
      // Filter on what the reviewer can see: with a weighting applied, the pillar chips must
      // select the re-weighted pillar or the two controls contradict each other on screen.
      (!pillar || (weighted?.get(r.id)?.pillar ?? r.pillar) === pillar));
    out.sort((a, b) => {
      if (sortKey === "final_score" && weighted) {
        const va = weighted.get(a.id)?.score ?? a.final_score ?? 0;
        const vb = weighted.get(b.id)?.score ?? b.final_score ?? 0;
        return (va - vb) * sortDir;
      }
      const va = a[sortKey] ?? "", vb = b[sortKey] ?? "";
      return (va > vb ? 1 : va < vb ? -1 : 0) * sortDir;
    });
    return out;
  }, [runs, q, pillar, sortKey, sortDir, weighted]);

  const moved = useMemo(
    () => (weighted ? rows.filter((r) => weighted.get(r.id)?.moved) : []),
    [rows, weighted],
  );

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
          : k === "sfs" ? (r.sfs_relevant ? "yes" : "")
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
      <div className="crumb">Explore &gt; Companies</div>
      <div className="page-head">
        <h1 className="page-title">Companies Covered</h1>
        <span className="page-meta">{rows.length} results</span>
        {/* Without this a view whose columns happen to match the defaults opens invisibly,
            which is indistinguishable from it not opening at all. */}
        {activeView && (
          <span className="fchip">
            View: {activeView.name}
            <button onClick={clearView} aria-label={`Close the view ${activeView.name}`}>✕</button>
          </span>
        )}
      </div>

      {stats && (
        <div className="stats-strip">
          <div className="stat"><span className="v">{stats.total}</span><span className="k">Companies</span></div>
          <div className="stat"><span className="v">{stats.avg}</span><span className="k">Avg Fit Score</span></div>
          <div className="stat"><span className="v">{stats.aligned}</span><span className="k">Siemens-aligned</span></div>
          <div className="stat"><span className="v">{stats.sfs}</span><span className="k">SFS relevant</span></div>
        </div>
      )}

      {error && <ErrorBox message={error} hint="is the API running?" />}

      <div className="toolbar">
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12.5 }}>
          <input type="checkbox" checked={allSelected} aria-label="Select all"
            onChange={() => setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.id)))} />
          Select all
        </label>
        <button ref={drawerTriggerRef} className="tool-btn" onClick={() => setDrawer(true)}>⚙ Customise columns</button>
        <button className={"tool-btn" + (dense ? " active" : "")}
          onClick={() => setParam("density", dense ? "comfortable" : "")}>
          ☰ {dense ? "Compact" : "Comfortable"}
        </button>
        <button className={"tool-btn" + (weightingOn ? " active" : "")}
          aria-expanded={weightingOn} onClick={() => setWeightingOn((v) => !v)}>
          ⚖ Weighting: {weightingOn && modified ? "mine" : "engine"}
        </button>
        <span className="spacer" />
        {selected.size > 0 && <span className="muted" style={{ fontSize: 12 }}>{selected.size} selected</span>}
        <button className="tool-btn" onClick={exportCsv}>⤓ Export</button>
      </div>

      {weightingOn && (
        <div className="panel" style={{ marginBottom: 10 }}>
          <h3>Score this table under your own weighting</h3>
          <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>
            Re-scores every row in your browser only. The stored engine score is what the
            database holds and what every export and every other reviewer sees — it is shown
            next to the re-weighted one, never replaced by it.
          </p>
          <WeightSliders idPrefix="explore-w" />
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
            <span role="status" aria-live="polite" style={{ fontSize: 12.5 }}>
              {!modified
                ? "Engine weighting — move a slider to see what changes."
                : moved.length === 0
                  ? `No companies change pillar under this weighting (${rows.length} shown).`
                  : `${moved.length} of ${rows.length} companies change pillar under this weighting.`}
            </span>
            <button type="button" className="btn secondary" disabled={!modified}
              onClick={resetWeights}>
              Reset to engine weights
            </button>
          </div>
        </div>
      )}

      <div className="filter-row">
        <input className="input" style={{ maxWidth: 240, padding: "4px 9px" }}
          placeholder="Filter results…" value={q}
          onChange={(e) => setParam("q", e.target.value)} aria-label="Filter results" />
        {["Connect", "Collaborate", "Empower", "Pass"].map((p) => (
          <button key={p}
            className={"tool-btn" + (pillar === p ? " active" : "")}
            style={{ padding: "3px 10px", fontSize: 11.5 }}
            onClick={() => setParam("pillar", pillar === p ? "" : p)}>
            {p}
          </button>
        ))}
        {(q || pillar) && (
          <>
            {q && <span className="fchip">“{q}”<button onClick={() => setParam("q", "")} aria-label="Clear text filter">✕</button></span>}
            {pillar && <span className="fchip">{pillar}<button onClick={() => setParam("pillar", "")} aria-label="Clear pillar filter">✕</button></span>}
            <button className="clear-link" onClick={() => setParams({}, { replace: true })}>Clear all</button>
          </>
        )}
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
                  {cols.map((k) => <td key={k}>{COLUMNS[k].render(r, weighted?.get(r.id))}</td>)}
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
