import React from "react";
import { Spec, ExtLink } from "../../components/widgets.jsx";
import Section from "./Section.jsx";

/* Market & Risk, as one column of addressable sections.
 *
 * Each section states its own absence rather than disappearing. A run evaluated before the market
 * landscape wave existed has no competitors, and a rail entry that silently vanishes is
 * indistinguishable from a company with no competitors at all — one is a fact about our run, the
 * other a fact about the market, and they are opposite conclusions.
 */
function Empty({ children }) {
  return <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>{children}</p>;
}

function SourcedList({ items, empty, render }) {
  if (!items?.length) return <Empty>{empty}</Empty>;
  return items.map((item, i) => (
    <div key={i} className="list-row" style={{ padding: "6px 0", fontSize: 12.5 }}>
      <div className="list-main">
        {render(item)}
        {/^https?:\/\//.test(item.source_url || "") && (
          <> <ExtLink href={item.source_url}>source</ExtLink></>
        )}
      </div>
    </div>
  ));
}

export default function MarketTab({ res }) {
  const t = res.trend || {}, rt = res.routing || {};
  if (!t.label || t.method === "disabled") {
    return (
      <div className="empty"><div className="big">◔</div><h4>No market analysis</h4>
        <p>Trend analysis was disabled or returned nothing for this run.</p></div>
    );
  }
  const landscape = t.landscape || {};
  const competitors = landscape.competitors || [];
  const peers = landscape.funded_peers || [];
  const size = landscape.market_size || null;
  const investors = landscape.active_investors || [];
  // A run from before the landscape wave has none of the four keys at all, which is a different
  // statement from a wave that ran and found nothing.
  const searched = Boolean(t.landscape);

  return (
    <>
      <Section id="market-trend">
        <h3>Market trend</h3>
        <div className="metric-row">
          <div className="metric"><div className="k">Verdict</div>
            <div className="v" style={{ fontSize: 14 }}>{t.label}</div></div>
          <div className="metric"><div className="k">Momentum</div>
            <div className="v">{t.momentum ?? "—"}</div></div>
        </div>
        {t.niche && <Spec k="Niche">{t.niche}</Spec>}
        {/* The counted evidence behind the number. The momentum rubric asks for it precisely so a
            reviewer can see whether 85 rests on four cited rounds or on enthusiasm; it has been
            stored since the calibration work and displayed nowhere. */}
        {t.basis && <Spec k="Basis">{t.basis}</Spec>}
        <p style={{ marginBottom: 0 }}>{t.summary}</p>
      </Section>

      <Section id="market-competitors">
        <h3>Competitors</h3>
        <SourcedList
          items={competitors}
          empty={searched
            ? "The landscape search named no competitor that could be tied to this niche."
            : "Not researched on this run — competitors were added after it was evaluated. Re-evaluate to populate this."}
          render={(c) => (
            <>
              <strong>{c.name}</strong>
              {c.note && <span className="muted"> — {c.note}</span>}
            </>
          )}
        />
      </Section>

      <Section id="market-peers">
        <h3>Funded peers</h3>
        <p className="muted" style={{ fontSize: 12, margin: "0 0 6px" }}>
          Who else has raised in this niche — the closest thing to a market-clearing price for the
          space this startup is in.
        </p>
        <SourcedList
          items={peers}
          empty={searched
            ? "No funding round in this niche was cited in the results."
            : "Not researched on this run. Re-evaluate to populate this."}
          render={(p) => (
            <>
              <strong>{p.company}</strong>
              {p.round && <span className="badge">{p.round}</span>}
              {p.amount && <span className="badge">{p.amount}</span>}
              {p.date && <span className="badge">{p.date}</span>}
              {p.investors && <div className="muted">Investors: {p.investors}</div>}
            </>
          )}
        />
      </Section>

      <Section id="market-size">
        <h3>Market size</h3>
        {size?.value || size?.cagr ? (
          <>
            <div className="metric-row">
              {size.value && (
                <div className="metric"><div className="k">Size</div>
                  <div className="v" style={{ fontSize: 15 }}>{size.value}</div></div>
              )}
              {size.cagr && (
                <div className="metric"><div className="k">CAGR</div>
                  <div className="v" style={{ fontSize: 15 }}>{size.cagr}</div></div>
              )}
              {size.as_of && (
                <div className="metric"><div className="k">As of</div>
                  <div className="v" style={{ fontSize: 15 }}>{size.as_of}</div></div>
              )}
            </div>
            {/^https?:\/\//.test(size.source_url || "") && <ExtLink href={size.source_url}>source</ExtLink>}
          </>
        ) : (
          <Empty>{searched
            ? "No market size or CAGR figure was cited in the results."
            : "Not researched on this run. Re-evaluate to populate this."}</Empty>
        )}
        {investors.length > 0 && (
          <>
            <h4 style={{ margin: "14px 0 4px", fontSize: 13 }}>Investors active in this niche</h4>
            <SourcedList items={investors} empty=""
              render={(inv) => (
                <>
                  <strong>{inv.name}</strong>
                  {inv.note && <span className="muted"> — {inv.note}</span>}
                </>
              )} />
          </>
        )}
      </Section>

      <Section id="market-signals">
        <h3>Signals &amp; risks</h3>
        {(t.signals || []).length
          ? t.signals.map((s, i) => <div key={i} className="reason">{s}</div>)
          : <Empty>No discrete signals extracted.</Empty>}
        {(rt.risks || []).map((r, i) => <div key={i} className="risk">{r}</div>)}
      </Section>

      {(t.evidence || []).length > 0 && (
        <Section id="market-evidence">
          <h3>Market evidence</h3>
          {t.evidence.slice(0, 12).map((e, i) => (
            <div key={i} className="list-row" style={{ fontSize: 12.5 }}>
              <div className="list-main">
                <ExtLink href={e.url || e.href}>{e.title || e.url || e.href}</ExtLink>
                <div className="muted">{(e.snippet || e.body || "").slice(0, 140)}</div>
              </div>
            </div>
          ))}
        </Section>
      )}
    </>
  );
}
