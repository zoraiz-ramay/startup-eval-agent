import React from "react";
import { Spec, ExtLink } from "../../components/widgets.jsx";
import Section from "./Section.jsx";

/* A value the DB did not have, filled in from web research. Marked so it is never mistaken
   for application data — the source link is the evidence for it.
   `field` names which metric this badge sources (e.g. "employees"), so that when several of
   these sit in the same row a screen reader hears which figure each one backs, not just "web"
   repeated (UI-01). The visible text stays "web" — this is a dense data canvas and the label
   isn't meant to grow — but WCAG 2.5.3 requires the accessible name to still start with the
   visible word, so speech-input users saying "click web" keep matching. */
function WebSourced({ src, field }) {
  if (!src) return null;
  const title = src.url ? `Web-sourced: ${src.url}` : "Web-sourced (no direct link captured)";
  const label = field ? `web — ${field} source` : "web";
  // The no-URL span is inert (no href to follow, nothing to activate), so it gets no role or
  // tabstop — giving it an aria-label would announce a "control" that does nothing. Its visible
  // "web" text plus the title tooltip is all the non-interactive case needs.
  return src.url
    ? <a className="chip" href={src.url} target="_blank" rel="noreferrer" title={title} aria-label={label}>web</a>
    : <span className="chip" title={title}>web</span>;
}

// PROF-12. `deep_profile.employees_over_time` is either [] or >=2 cited points, sorted
// ascending by year (core/profile.py's _clean_employee_series refuses a single-dot series, and
// every point is guaranteed an http(s) source_url). A length-1 array is a contract violation
// upstream, not something this component needs to guard against — but it still only renders the
// list when there's enough to call a trend, matching the engine's own bar.
// An empty series has three different causes and they are not interchangeable to a reviewer:
// one is a fact about the company, one is a fact about the evidence, and one is a fact about
// our run. Reporting all three as "no cited headcount history" told people a young company had
// been checked and a throttled search had found nothing.
const EMPTY_HEADCOUNT = {
  too_young: "Too new for a headcount trend — a company needs at least two calendar years "
    + "for two datable points.",
  not_found: "No cited headcount history — fewer than two independently sourced data points.",
  unavailable: "Headcount history could not be retrieved on this run. Re-evaluate to try again.",
};

/* Where the displayed headcount actually came from.
   A reviewer opens LinkedIn, reads a different number, and concludes the app is wrong. It is not:
   the figure is cited, and the aggregators that publish a citable count (Growjo, Latka) lag
   LinkedIn by months. Naming the year the citation is FROM turns "wrong" into "stale", which is
   the true and actionable reading. Only claimed when the series genuinely backs the number on
   screen — a year attached to a figure it did not produce would be worse than no year at all. */
function reportedAsOf(headline, points) {
  const pts = points || [];
  if (!pts.length || !String(headline || "").trim()) return null;
  const last = pts[pts.length - 1];
  return String(last.count) === String(headline).trim() ? last : null;
}

function HeadcountTrend({ points, status, band, bandSource }) {
  const pts = points || [];
  return (
    <>
      <h3>Headcount trend</h3>
      {pts.length >= 2 ? (
      <>
        <p style={{ marginTop: 0 }}>
          <strong>{pts[0].count}</strong> → <strong>{pts[pts.length - 1].count}</strong> employees
          <span className="muted"> ({pts[0].year}–{pts[pts.length - 1].year})</span>
        </p>
        {pts.map((pt, i) => (
          <div key={i} className="list-row" style={{ padding: "5px 0", fontSize: 12.5 }}>
            <div className="list-main">{pt.year} · {pt.count} employees</div>
            <ExtLink href={pt.source_url}>{`source (${pt.year})`}</ExtLink>
          </div>
        ))}
      </>
      ) : (
      <p className="muted" style={{ margin: 0 }}>{EMPTY_HEADCOUNT[status] || EMPTY_HEADCOUNT.not_found}</p>
      )}
      {/* LinkedIn's own figure, when a result snippet carried it. Shown BESIDE the cited series
        rather than replacing it: LinkedIn is the freshest public number and the one a reviewer
        will check, but it is a self-reported band on a page we cannot cite per-datapoint, so it
        does not get to overwrite a sourced count. Where the two disagree, that disagreement is
        the finding. */}
      {band && (
      <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 0" }}>
        LinkedIn lists <strong>{band}</strong> employees.{" "}
        {bandSource && <ExtLink href={bandSource}>LinkedIn</ExtLink>}{" "}
        Company pages update faster than the aggregators cited above, so a higher figure here
        usually means the citation has aged rather than that it is wrong.
      </p>
      )}
    </>
  );
}

export default function OverviewTab({ res }) {
  const p = res.profile || {}, sc = res.score || {}, dp = res.deep_profile || {};
  const trend = res.trend || {};
  const psrc = res.profile_sources || {};
  const founders = (dp.founders || []).filter((f) => f?.name);
  const advisors = (dp.advisors || []).filter((a) => a?.name);
  const programs = (dp.programs || []).filter((x) => x?.name);
  const customers = dp.reference_customers?.length ? dp.reference_customers
    : String(p.customers || p["Reference customers"] || "").split(/[,;|\n]+/).map((s) => s.trim()).filter(Boolean);
  const hasSignals = (trend.signals || []).length > 0;
  const headcount = dp.employees || p.employees_count || p.employee_band || "";
  const asOf = reportedAsOf(headcount, dp.employees_over_time);

  /* A single column of sections, and that is load-bearing. This was a two-column `grid2`: a table
     of contents needs a reading order, and in two columns "Team & ecosystem" sits beside
     "Executive summary" at the same scroll position, so there is no single current section to mark
     and the rail's indicator flickers between the pair. The rail itself lives in ProfileLayout —
     it navigates the whole profile now, not this view alone. */
  return (
    <>
      <Section id="profile-key-metrics" className="metric-row">
        {/* An em dash while scoring is still running. A literal 0 in this tile reads as a company
            that scored nothing, which is the opposite of "not computed yet" — and on a streamed
            evaluation it would sit there for the whole first half of the run. */}
        <div className="metric"><div className="k">Fit Score</div>
          <div className="v">{typeof sc.final_score === "number"
            ? Number(sc.final_score).toFixed(0) : "—"}</div></div>
        <div className="metric"><div className="k">Employees</div>
          <div className="v">{headcount || "—"} <WebSourced src={psrc.employees_count} field="employees" /></div>
          {asOf && (
            <div className="s">as reported {asOf.year} · <ExtLink href={asOf.source_url}>source</ExtLink></div>
          )}</div>
        <div className="metric"><div className="k">Founded</div>
          <div className="v">{p.founded_year || "—"} <WebSourced src={psrc.founded_year} field="founded year" /></div></div>
        {/* Funding and location, not completeness and trend: this row answers "what is this
            company" for a reviewer scanning it, and both of those are elsewhere — completeness
            inside the score derivation below, the trend verdict on the Market tab. */}
        <div className="metric"><div className="k">Funding</div>
          <div className="v" style={{ fontSize: 13 }} title={p.funding || ""}>
            {p.funding || "—"}{p.funding && <> <WebSourced src={psrc.funding} field="funding" /></>}</div></div>
        <div className="metric"><div className="k">Verified customers</div><div className="v">{sc.verified_customers ?? "—"}</div></div>
        <div className="metric"><div className="k">Location</div>
          <div className="v" style={{ fontSize: 13 }} title={p.hq || ""}>{p.hq || "—"}</div></div>
      </Section>

      <Section id="profile-executive-summary">
        <h3>Executive summary</h3>
        <p style={{ marginTop: 0 }}>{res.summary || <span className="muted">No summary.</span>}</p>
        <Spec k="Headquarters">{p.hq}</Spec>
        <Spec k="Stage">{p["Development stage of your solution"]}</Spec>
        <Spec k="Business model">{p["Business model"]}</Spec>
        <Spec k="Funding">{p.funding}{p.funding && <> <WebSourced src={psrc.funding} field="funding" /></>}</Spec>
        <Spec k="Website"><ExtLink href={p.website} /></Spec>
        <Spec k="LinkedIn"><ExtLink href={p.linkedin_url} /></Spec>
        <Spec k="Crunchbase"><ExtLink href={p.crunchbase_url} /></Spec>
        {dp.parent_group && <Spec k="Part of group">{dp.parent_group}</Spec>}
      </Section>

      <Section id="profile-team-ecosystem">
        <h3>Team &amp; ecosystem</h3>
        {founders.length === 0 && advisors.length === 0 && programs.length === 0 && (
          <p className="muted" style={{ margin: 0 }}>No researched team data.</p>
        )}
        {founders.map((f, i) => (
          <Spec key={i} k="Founder">
            {f.name} — {f.role || "founder"}
            {f.background && <span className="muted"> · {f.background}</span>}{" "}
            {f.linkedin && <ExtLink href={f.linkedin}>LinkedIn</ExtLink>}
          </Spec>
        ))}
        {advisors.map((a, i) => (
          <Spec key={i} k="Advisor">{a.name} — {a.role || "advisor"}{a.affiliation ? `, ${a.affiliation}` : ""}</Spec>
        ))}
        {programs.length > 0 && (
          <div style={{ marginTop: 6 }}>
            {programs.map((x, i) => {
              // A membership found only on the company's own site is a claim, not a
              // verified fact — several such programs publish no searchable member
              // directory, so it is shown but explicitly marked as uncorroborated.
              const claimed = String(x.confidence || "").toLowerCase() === "self_asserted";
              return (
                <span key={i} className="chip"
                      title={claimed
                        ? `${x.type} — company-claimed, not independently corroborated`
                        : `${x.type} — independently corroborated`}>
                  {x.name}{claimed && <span className="muted"> · claimed</span>}
                </span>
              );
            })}
          </div>
        )}
      </Section>

      <Section id="profile-reference-customers">
        <h3>Reference customers</h3>
        {customers.length
          ? customers.map((c, i) => <span key={i} className="chip">{c}</span>)
          : <p className="muted" style={{ margin: 0 }}>
              {dp.customer_segment ? "None named on record." : "None on record."}
            </p>}
        {dp.customer_segment && (
          <p className="muted" style={{ margin: "8px 0 0" }}>
            Customer profile: {dp.customer_segment}
          </p>
        )}
      </Section>

      <Section id="profile-headcount-trend">
        <HeadcountTrend points={dp.employees_over_time} status={dp.employees_history_status}
          band={dp.linkedin_size_band} bandSource={dp.linkedin_size_source || p.linkedin_url} />
      </Section>

      {hasSignals && (
        <Section id="profile-recent-signals">
          <h3>Recent signals</h3>
          {trend.signals.map((s, i) => <div key={i} className="reason">{s}</div>)}
        </Section>
      )}
    </>
  );
}
