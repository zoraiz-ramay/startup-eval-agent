import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Loading } from "./widgets.jsx";

/* Admin: rows of siemens_tools.csv that Empower recommended and a web search could not find as a
   Siemens offering (core/tool_check.py). Each was replaced by another recommendation when it came
   up; listed here so someone can correct or remove the catalog row — a renamed product, a typo,
   an internal codename. A tool that simply could not be checked (no search) is not listed: that
   is no evidence against it. */
export default function UnverifiedTools() {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    let live = true;
    Promise.resolve().then(() => api.adminToolChecks("not_found"))
      .then((r) => { if (live) setState({ tools: r?.tools || [] }); })
      .catch((e) => { if (live) setState({ error: e.message }); });
    return () => { live = false; };
  }, []);
  return (
    <div className="panel" aria-labelledby="unverified-tools">
      <h3 id="unverified-tools">Siemens tools that could not be verified{state.tools ? ` (${state.tools.length})` : ""}</h3>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
        Entries in <code>siemens_tools.csv</code> that Empower recommended but a web search could not find as a Siemens
        product. Each was replaced by another tool when it came up; correct or remove the row in the catalog.
      </p>
      {state.loading && <Loading text="Loading tool checks…" />}
      {state.error && <p className="muted">Tool checks could not be loaded: {state.error}</p>}
      {state.tools && (state.tools.length === 0
        ? <p className="muted" style={{ fontSize: 12 }}>Every recommended tool checked so far was found.</p>
        : (
          <div style={{ overflowX: "auto" }}>
            <table className="dtable dense" aria-label="Unverified Siemens tools">
              <thead><tr><th>Tool (as in the catalog)</th><th>Category</th><th>Division</th><th>What the search found</th>
                <th>Recommended</th><th>Last checked</th></tr></thead>
              <tbody>
                {state.tools.map((t) => (
                  <tr key={t.tool_id} style={{ cursor: "default" }}>
                    <td><strong>{t.name}</strong></td>
                    <td>{t.category || "—"}</td>
                    <td>{t.division || "—"}</td>
                    <td className="muted">{t.note || "No Siemens offering by this name was found."}</td>
                    <td>{t.times_recommended}×</td>
                    <td>{(t.checked_at || "").slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  );
}
