import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import ErrorBox from "../components/ErrorBox.jsx";
import { Loading } from "../components/widgets.jsx";

/**
 * Usage across the whole tenant, for whoever is listed in ADMIN_UPNS.
 *
 * Every reviewer's Explore is now their own searches only, which is what makes this page
 * necessary: without it nobody can see the team's coverage, and the shared evaluation cache
 * has no observable effect. Hence the cache-hit rate — it is the number that says whether
 * pooling the evaluations is actually saving anyone a pipeline run.
 *
 * The nav entry is hidden for non-admins, but that is cosmetic: every endpoint below is
 * behind require_admin, so a reviewer who types /admin gets the forbidden state, not data.
 */
function pct(x) {
  return `${Math.round((x || 0) * 100)}%`;
}

function Stat({ value, label }) {
  return (
    <div className="stat"><span className="v">{value}</span><span className="k">{label}</span></div>
  );
}

export default function Admin() {
  const nav = useNavigate();
  const [overview, setOverview] = useState(null);
  const [searches, setSearches] = useState(null);
  const [allRuns, setAllRuns] = useState(null);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.adminOverview(), api.adminSearches(), api.runs()])
      .then(([o, s, r]) => {
        if (cancelled) return;
        setOverview(o);
        setSearches(s.searches || []);
        setAllRuns(r.runs || []);
      })
      .catch((e) => {
        if (cancelled) return;
        // 403 is the expected answer for a reviewer who is not on the list, and it deserves
        // an explanation rather than a red error box that reads like a bug.
        if (e.status === 403) setForbidden(true);
        else setError(e.message);
      });
    return () => { cancelled = true; };
  }, []);

  const companies = useMemo(() => {
    if (!allRuns) return [];
    const seen = new Set();
    const out = [];
    for (const r of allRuns) {                     // newest first
      const k = (r.company || "").toLowerCase();
      if (k && !seen.has(k)) { seen.add(k); out.push(r); }
    }
    return out;
  }, [allRuns]);

  if (forbidden) {
    return (
      <div>
        <div className="crumb">Workspace &gt; Admin</div>
        <div className="page-head"><h1 className="page-title">Admin</h1></div>
        <div className="empty">
          <h4>You do not have administrator access</h4>
          <p>
            Access is granted by adding your sign-in name to the <code>ADMIN_UPNS</code>
            {" "}setting on the server. Ask whoever runs the deployment.
          </p>
          <button className="btn secondary" onClick={() => nav("/")}>Back to Home</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="crumb">Workspace &gt; Admin</div>
      <div className="page-head">
        <h1 className="page-title">Admin</h1>
        <span className="page-meta">
          {overview ? `Usage across all reviewers · last ${overview.window_days} days` : "Usage across all reviewers"}
        </span>
      </div>

      {error && <ErrorBox message={error} hint="is the API running?" />}
      {!overview && !error && <Loading text="Loading usage…" />}

      {overview && (
        <>
          <div className="stats-strip">
            <Stat value={overview.users.total} label="Reviewers" />
            <Stat value={overview.sessions.total} label="Sign-ins" />
            <Stat value={overview.searches.total} label="Searches" />
            <Stat value={overview.companies.searched} label="Companies searched" />
            <Stat value={overview.companies.evaluated} label="Companies evaluated" />
            <Stat value={pct(overview.cache_hit_rate)} label="Served from database" />
          </div>

          <div className="grid2">
            <div className="panel">
              <h3>Reviewers</h3>
              {overview.per_user.length === 0 ? (
                <p className="muted" style={{ fontSize: 12 }}>Nobody has searched yet.</p>
              ) : (
                <table className="dtable dense">
                  <thead>
                    <tr><th>Reviewer</th><th>Searches</th><th>Companies</th><th>Last active</th></tr>
                  </thead>
                  <tbody>
                    {overview.per_user.map((u) => (
                      <tr key={u.oid} style={{ cursor: "default" }}>
                        <td>{u.upn || u.oid}</td>
                        <td>{u.searches}</td>
                        <td>{u.companies}</td>
                        <td>{(u.last_seen || "").slice(0, 16).replace("T", " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="panel">
              <h3>Most-searched companies</h3>
              {overview.top_companies.length === 0 ? (
                <p className="muted" style={{ fontSize: 12 }}>Nothing searched yet.</p>
              ) : (
                <table className="dtable dense">
                  <thead><tr><th>Company</th><th>Searches</th></tr></thead>
                  <tbody>
                    {overview.top_companies.map((c) => (
                      <tr key={c.company} onClick={() => nav(`/startup/new?name=${encodeURIComponent(c.company)}`)}>
                        <td>{c.company}</td>
                        <td>{c.searches}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className="panel">
            <h3>All companies evaluated ({companies.length})</h3>
            {companies.length === 0 ? (
              <p className="muted" style={{ fontSize: 12 }}>No evaluations stored yet.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="dtable dense">
                  <thead>
                    <tr><th>Company</th><th>Pillar</th><th>Score</th><th>HQ</th><th>Evaluated</th></tr>
                  </thead>
                  <tbody>
                    {companies.map((r) => (
                      <tr key={r.id} onClick={() => nav(`/startup/${r.id}`)}>
                        <td>{r.company}</td>
                        <td>{r.pillar}</td>
                        <td>{r.final_score == null ? "—" : Math.round(r.final_score)}</td>
                        <td>{r.hq || "—"}</td>
                        <td>{(r.created_at || "").slice(0, 10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <h3>Recent activity ({searches?.length || 0})</h3>
            {!searches?.length ? (
              <p className="muted" style={{ fontSize: 12 }}>No searches recorded yet.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="dtable dense">
                  <thead>
                    <tr><th>When</th><th>Reviewer</th><th>Typed</th><th>Resolved to</th><th>Source</th></tr>
                  </thead>
                  <tbody>
                    {searches.map((s) => (
                      <tr key={s.id} style={{ cursor: "default" }}>
                        <td>{(s.created_at || "").slice(0, 16).replace("T", " ")}</td>
                        <td>{s.user_upn || s.user_oid}</td>
                        <td>{s.query}</td>
                        <td>{s.company || "—"}</td>
                        <td>
                          <span className="badge">
                            {s.served_from === "cache" ? "database" : "pipeline"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
