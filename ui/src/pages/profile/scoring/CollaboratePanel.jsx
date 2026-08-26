import React from "react";
import { ExtLink } from "../../../components/widgets.jsx";

/* Collaborate, per department — and, for now, an honest account of what is not loaded yet.
 *
 * Collaborate is a venture-client programme: Siemens becomes an early customer, so the real
 * question is not "is this a good startup" but "does some department want to buy this". The five
 * published innovation domains answer only the half that is public. The per-department half needs
 * Siemens' own criteria, and `core/departments.py` ships with an empty registry.
 *
 * `configured: false` is therefore rendered as "not yet configured", never as an empty result.
 * An empty department list drawn as departments-that-do-not-match would tell a reviewer that
 * every department was asked and declined — the same lie `employees_history_status` and the SFS
 * `unassessed` state exist to prevent.
 */
const FIT_CLASS = { strong: "met", possible: "unknown", weak: "unmet" };

export default function CollaboratePanel({ departments, detail }) {
  const domains = departments?.domains || detail?.domains || [];
  const configured = Boolean(departments?.configured);
  const rows = departments?.departments || [];

  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 4px", fontSize: 13 }}>Innovation domains</h4>
      {domains.length ? (
        <div>
          {domains.map((d) => (
            <span key={d.id} className="chip" title={d.note}>{d.label}</span>
          ))}
        </div>
      ) : (
        <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
          Outside all five domains Siemens takes Collaborate applications under.{" "}
          <ExtLink href="https://www.siemens.com/en-us/company/innovation/startups/collaborate/">
            the five domains
          </ExtLink>
        </p>
      )}
      {detail?.division && (
        <div className="spec" style={{ marginTop: 6 }}>
          <div className="k">Sponsoring unit</div>
          <div className="v">{detail.division}</div>
        </div>
      )}

      <h4 style={{ margin: "14px 0 4px", fontSize: 13 }}>Department view</h4>
      {!configured ? (
        <div className="info-box">
          <strong>Not yet configured.</strong> Per-department criteria — what each Siemens
          department is looking for in a startup — have not been supplied, so no department verdict
          is shown. The domain match above is what this run can currently evidence. Adding the
          criteria to <code>core/departments.py</code> populates this section; nothing here is
          inferred in the meantime.
        </div>
      ) : rows.length === 0 ? (
        <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
          No department in the registry names a domain this startup falls in.
        </p>
      ) : rows.map((d) => (
        <div key={d.id} className={`crit ${FIT_CLASS[d.fit] || "unknown"}`}>
          <span className="mark" aria-hidden="true">{d.fit === "strong" ? "▲" : d.fit === "possible" ? "•" : "·"}</span>
          <span className="body">
            <span className="label">{d.unit}{d.department ? ` · ${d.department}` : ""}</span>
            <span className="sr-only"> — {d.fit} match</span>
            {d.looking_for && <span className="why">{d.looking_for}</span>}
            {d.missing?.length > 0 && (
              <span className="why">Still to evidence: {d.missing.map((m) => m.label).join("; ")}</span>
            )}
            {/^https?:\/\//.test(d.source_url || "") && <ExtLink href={d.source_url}>criteria</ExtLink>}
          </span>
        </div>
      ))}
    </div>
  );
}
