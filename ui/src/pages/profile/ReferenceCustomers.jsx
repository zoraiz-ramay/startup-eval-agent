import React from "react";
import Section from "./Section.jsx";
import { Sources } from "./scoring/TractionLookup.jsx";

/* Reference customers: only accounts the research ties to this startup, never a split of free
   text. It used to fall back to the application form's "Reference customers" box cut on line
   breaks, which put "Industries addressed:" and "For scale-up" on screen as customers.

   Named customers are the ones the traction rubric counted — grounded to this company, a
   customer relationship rather than an investor or partner, and a name rather than a fragment
   (core/traction.py, core/text.is_named_org) — with the source it was found in. The customer
   base as the research describes it sits apart, quoted, because it is a description and not an
   account. */
const ORIGIN = { verified: "Verified claim", research: "Company research", web: "Web research" };

const initials = (name) => String(name).replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean)
  .slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";

export function namedCustomers(res) {
  const division = (res?.traction?.divisions || []).find((d) => d.id === "customers");
  const counted = (division?.items || []).filter((i) => i.counted);
  if (counted.length) {
    return counted.map((i) => ({ name: i.name, big: i.size === "large_enterprise", url: i.source_url || "", origin: i.origin || "research" }));
  }
  return (res?.deep_profile?.reference_customers || []).filter((n) => typeof n === "string" && n.trim())
    .map((n) => ({ name: n.trim(), big: false, url: "", origin: "research" }));
}

export default function ReferenceCustomers({ res }) {
  const dp = res.deep_profile || {};
  const named = namedCustomers(res);
  const grade = dp.customer_segment_grade || {};
  return (
    <Section id="profile-reference-customers">
      <h3>Reference customers</h3>
      <p className="muted cust-lede">Accounts the research ties to {res.company || "this startup"}, each with where it was found.</p>
      {named.length ? (
        <ul className="cust-grid" aria-label="Named customers">
          {named.map((c) => (
            <li key={c.name} className={`cust-card${c.big ? " big" : ""}`}>
              <span className="cust-mark" aria-hidden="true">{initials(c.name)}</span>
              <span className="cust-body">
                <strong>{c.name}</strong>
                <span className="cust-meta">
                  {c.big && <span className="cust-tag">Big-name customer</span>}
                  {c.url ? <Sources items={[{ title: "", url: c.url }]} label="Source" />
                    : <span className="muted">{ORIGIN[c.origin] || "Company research"}</span>}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="muted cust-none">No named customer was found in the research.</p>}
      {dp.customer_segment && (
        <div className="cust-segment">
          <span className="eyebrow">Customer base, as described</span>
          <p>“{dp.customer_segment}”{grade.level ? <span className="muted"> · specificity level {grade.level} of 3</span> : null}</p>
          {(dp.customer_segment_source || grade.source_url) && <Sources items={[{ title: "", url: dp.customer_segment_source || grade.source_url }]} label="Source" />}
        </div>
      )}
    </Section>
  );
}
