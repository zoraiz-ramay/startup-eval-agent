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

/**
 * Who can administer this deployment, and the control for changing that.
 *
 * Two sources of admin rights, and the difference matters to whoever is looking at this
 * table. An `env` row comes from the ADMIN_UPNS setting and cannot be revoked from here —
 * it is the recovery path that keeps a deployment from ending up with nobody able to
 * administer it. So those rows carry no revoke control at all, rather than one that would
 * fail: an action you are offered and which then refuses reads as a bug.
 */
function Administrators({ data, onChange }) {
  const [upn, setUpn] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const value = upn.trim();
    if (!value || busy) return;
    setBusy(true);
    setErr("");
    try {
      await api.adminGrant(value);
      setUpn("");
      await onChange();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (target) => {
    setBusy(true);
    setErr("");
    try {
      await api.adminRevoke(target);
      await onChange();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  const admins = data?.admins || [];

  return (
    <div className="panel">
      <h3>Administrators ({admins.length})</h3>
      <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
        Administrators can see every reviewer&apos;s activity and grant access to others.
        Everyone else gets an &ldquo;access required&rdquo; message.
      </p>

      {err && <ErrorBox message={err} hint="the change was not saved" />}

      {admins.length === 0 ? (
        <p className="muted" style={{ fontSize: 12 }}>
          Nobody is an administrator. Set <code>ADMIN_UPNS</code> on the server to grant the
          first one.
        </p>
      ) : (
        <table className="dtable dense">
          <thead>
            <tr><th>Sign-in name</th><th>Source</th><th>Granted by</th><th /></tr>
          </thead>
          <tbody>
            {admins.map((a) => (
              <tr key={a.upn} style={{ cursor: "default" }}>
                <td>
                  {a.upn}
                  {a.upn === data?.you && <span className="badge" style={{ marginLeft: 6 }}>you</span>}
                </td>
                <td>
                  <span className="muted">{a.source === "env" ? "Server setting" : "Granted in app"}</span>
                </td>
                <td className="muted">{a.granted_by || "—"}</td>
                <td style={{ textAlign: "right" }}>
                  {a.source === "db" && (
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={busy}
                      aria-label={`Remove administrator access for ${a.upn}`}
                      onClick={() => revoke(a.upn)}
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form onSubmit={submit} style={{ display: "flex", gap: 6, marginTop: 10 }}>
        {/* Visible label, not a placeholder: the placeholder disappears on focus, and this
            field is one where getting the exact string right is the whole difficulty. */}
        <label htmlFor="admin-grant-upn" className="muted" style={{ fontSize: 12, alignSelf: "center" }}>
          Sign-in name
        </label>
        <input
          id="admin-grant-upn"
          className="input"
          type="email"
          placeholder="name@siemens.com"
          value={upn}
          disabled={busy}
          onChange={(e) => setUpn(e.target.value)}
          style={{ flex: 1, maxWidth: 320 }}
        />
        <button type="submit" className="btn" disabled={busy || !upn.trim()}>
          {busy ? "Working…" : "Grant access"}
        </button>
      </form>
      <p className="muted" style={{ fontSize: 11.5, marginTop: 6, marginBottom: 0 }}>
        Use the person&apos;s full Microsoft sign-in name. It must match exactly — they can read
        theirs from the account menu after signing in once.
      </p>
    </div>
  );
}

export default function Admin() {
  const nav = useNavigate();
  const [overview, setOverview] = useState(null);
  const [searches, setSearches] = useState(null);
  const [allRuns, setAllRuns] = useState(null);
  const [admins, setAdmins] = useState(null);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState(false);

  const reloadAdmins = React.useCallback(
    () => api.adminList().then(setAdmins).catch((e) => setError(e.message)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.adminOverview(), api.adminSearches(), api.runs(), api.adminList()])
      .then(([o, s, r, a]) => {
        if (cancelled) return;
        setOverview(o);
        setSearches(s.searches || []);
        setAllRuns(r.runs || []);
        setAdmins(a);
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
          <h4>Administrator access required</h4>
          <p>
            This page shows activity across every reviewer, so it is limited to
            administrators. Ask one of them to grant your sign-in name access from this page.
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

      {admins && <Administrators data={admins} onChange={reloadAdmins} />}

      {overview && (
        <>
          <div className="stats-strip">
            {/* Three sign-in numbers, adjacent because each is meaningless without the others:
                how many people have ever signed in, how many times in total, and how many of
                those people came back inside the window. Adoption is the third one. */}
            <Stat value={overview.users.total} label="Reviewers" />
            <Stat value={overview.sessions.total} label="Sign-ins" />
            <Stat value={overview.users.recent} label={`Signed in (${overview.window_days}d)`} />
            <Stat value={overview.searches.total} label="Searches" />
            <Stat value={overview.companies.searched} label="Companies searched" />
            <Stat value={overview.companies.evaluated} label="Companies evaluated" />
            <Stat value={pct(overview.cache_hit_rate)} label="Served from database" />
          </div>

          <div className="grid2">
            <div className="panel">
              <h3>Reviewers</h3>
              {overview.per_user.length === 0 ? (
                <p className="muted" style={{ fontSize: 12 }}>Nobody has signed in yet.</p>
              ) : (
                <table className="dtable dense">
                  <thead>
                    <tr><th>Reviewer</th><th>Sign-ins</th><th>Searches</th><th>Companies</th>
                      <th>Last sign-in</th></tr>
                  </thead>
                  <tbody>
                    {overview.per_user.map((u) => (
                      <tr key={u.oid} style={{ cursor: "default" }}>
                        <td>{u.upn || u.oid}</td>
                        <td>{u.sign_ins || 0}</td>
                        {/* Someone who signed in and never searched is a real row now, so the
                            search columns need an empty state rather than a misleading 0. */}
                        <td>{u.searches || "—"}</td>
                        <td>{u.companies || "—"}</td>
                        <td>{(u.last_sign_in || "").slice(0, 16).replace("T", " ") || "—"}</td>
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
