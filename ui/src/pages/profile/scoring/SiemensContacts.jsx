import React from "react";
import { Lookup } from "./TractionLookup.jsx";

/* "Relevant Siemens Contact" under Empower → Tool fit: people the Siemens Directory lists in each
   cited tool's department (core/siemens_contacts.py). The department is shown as the catalogue
   gives it; a contact is ranked by the app from department match, which shows organisational
   relevance, not that the person owns the tool — the lookup's note says so above the list. */
function ToolContacts({ row }) {
  return (
    <li className="contact-tool">
      <span className="crit-catalog-name">{row.tool}
        <span className="kind-tag">{row.department || "Department not available"}</span></span>
      {row.translated && <span className="muted">Searched as {row.department_query}: the app's reading of the department.</span>}
      {row.contacts.length > 0
        ? <ul className="contact-list">
          {row.contacts.map((p) => (
            <li key={p.email || p.name}>
              <strong>{p.name || "Name not available"}</strong>
              <span className="muted"> · {p.department || "Department not available"}</span>
              {p.email && <> · <a href={`mailto:${p.email}`}>{p.email}</a></>}
            </li>
          ))}
        </ul>
        : <span className="muted">{row.note || "No contact found."}</span>}
    </li>
  );
}

export default function SiemensContacts({ runId }) {
  return (
    <Lookup runId={runId} kind="contacts" title="Relevant Siemens Contact" loadingText="Looking up Siemens contacts…"
      className="fd contacts">
      {(data) => (data.tools?.length
        ? <ul className="contact-tools">{data.tools.map((row) => <ToolContacts key={row.tool} row={row} />)}</ul>
        : !data.note && <p className="muted">No contact to show.</p>)}
    </Lookup>
  );
}
