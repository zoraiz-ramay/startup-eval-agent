import React from "react";
import { Link } from "react-router-dom";
import { PillarPill } from "../components/widgets.jsx";

/* The Database grid's columns: how each one renders, which are on by default, which sort.
   Kept apart from the page so the page is its behaviour (filters, views, selection) and this is
   its vocabulary. */
/* Stored evaluation columns. */
export const COLUMNS = {
  final_score: {
    label: "Total score",
    // A department run whose four components are not all scored has a pending total, not a 0.
    render: (r) => <span className="num">{typeof r.final_score === "number" ? r.final_score.toFixed(0)
      : r.total_status === "pending" ? <span className="muted">pending</span> : "—"}</span>,
  },
  department: {
    label: "Department",
    render: (r) => (r.legacy ? <span className="badge" title="Assessed before departments existed">Legacy</span>
      : r.department_label || r.department_id || "—"),
  },
  ...Object.fromEntries([['di_fit', 'DI', 'di'], ['si_fit', 'SI', 'si'], ['smo_fit', 'SMO', 'mobility']].map(([key, label, id]) => [key, {label, render: (r) => <Link onClick={(e) => e.stopPropagation()} to={`/startup/${r.id}?tab=Scoring+%26+Fit&department=${id}`}>{typeof r[key] === "number" ? r[key].toFixed(0) : "Not assessed"}</Link>}])),
  siemens_fit: { label: "Siemens Fit", render: (r) => <span className="num">{typeof r.siemens_fit === "number" ? r.siemens_fit.toFixed(0) : "—"}{r.siemens_fit_partial && <span className="muted"> partial</span>}</span> },
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
// di_fit / si_fit / smo_fit are the pre-department assessments, kept as optional legacy columns.
export const DEFAULT_COLS = ["department", "final_score", "siemens_fit", "summary", "hq", "stage", "funding",
  "evidence", "pillar", "sfs", "created_at"];
export const SORTABLE = new Set(["department", "final_score", "siemens_fit", "di_fit", "si_fit", "smo_fit", "founded_year", "created_at", "hq", "stage"]);
