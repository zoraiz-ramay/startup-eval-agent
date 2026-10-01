import React from "react";
import { iconAddCircle, iconBarchart, iconBuilding1, iconCoins, iconLegal, iconTrendDownward, iconTrendUpward } from "@siemens/ix-icons/icons";
import Icon from "../../components/Icon.jsx";
import Section from "./Section.jsx";
import { Lookup, Sources } from "./scoring/TractionLookup.jsx";

/* Recent signals: momentum in the startup's market, in the four places momentum shows —
   investors, competitors, corporates and governments — looked up when the profile opens
   (core/market_signals.py: the market is understood from the run's research first, then each
   domain is searched on its own; Tracxn first, the model's web search second). Only signals
   specific to the market survive, so a domain may hold none. Every signal is dated, names who,
   carries its source and says which way it points; an adjacent one says so. Market-size
   forecasts are left to the Market section. */
const CATEGORIES = [
  { id: "funding", title: "VC funding & investor momentum", icon: iconCoins,
    blurb: "Sector funding and how it is changing: deal counts, round sizes, new investors, follow-ons." },
  { id: "competition", title: "Competitive momentum", icon: iconBarchart,
    blurb: "Competitor funding, new entrants, shutdowns, hiring, pricing, acquisitions and launches." },
  { id: "adoption", title: "Corporate & strategic adoption", icon: iconBuilding1,
    blurb: "Corporate pilots, procurement, partnerships, corporate VC, M&A and big-company launches." },
  { id: "policy", title: "Government & regulatory momentum", icon: iconLegal,
    blurb: "Subsidies, grants, regulation, public procurement, incentives and national priorities." },
];
const DIRECTION = {
  up: { icon: iconTrendUpward, label: "Growth" },
  down: { icon: iconTrendDownward, label: "Decline" },
  new: { icon: iconAddCircle, label: "New development" },
};

function Tally({ signals }) {
  const n = (d) => signals.filter((s) => s.direction === d).length;
  const parts = [["up", "growth"], ["down", "decline"], ["new", "new"]].filter(([d]) => n(d)).map(([d, w]) => ({ d, text: `${n(d)} ${w}` }));
  if (!parts.length) return null;
  return <span className="sig-tally">{parts.map((p) => <span key={p.d} className={`sig-tally-${p.d}`}>{p.text}</span>)}</span>;
}

function Signal({ s }) {
  const dir = DIRECTION[s.direction];
  return (
    <li className="sig-row">
      <span className="sig-date">{s.date || "Undated"}</span>
      <span className={`sig-dir ${s.direction || "none"}`} title={dir?.label} aria-label={dir?.label}>
        {dir && <Icon icon={dir.icon} size={16} />}
      </span>
      <span className="sig-body">
        <span className="sig-text">{s.who && !s.what.toLowerCase().includes(s.who.toLowerCase()) && <strong>{s.who} </strong>}{s.what}
          {s.figure && !s.what.includes(s.figure) && <span className="sig-figure">{s.figure}</span>}
          {s.relevance === "adjacent" && <span className="sig-adjacent" title="Relevant to this market, not specific to it">Adjacent</span>}</span>
        <Sources items={s.sources} />
      </span>
    </li>
  );
}

export default function MarketSignals({ res }) {
  return (
    <Section id="profile-recent-signals">
      <h3>Recent signals</h3>
      <p className="muted sig-lede">The most decision-relevant momentum in this startup's market over the last 24 months — only
        what is specific to the market, so a quiet area stays empty rather than filled.</p>
      <Lookup runId={res.run_id ?? null} kind="signals" title="" className="sig-lookup" loadingText="Understanding the market and searching for signals…">
        {(data) => (<>
          {data.market && <p className="sig-market"><span className="eyebrow">Market searched</span>{data.market}</p>}
          <div className="sig-grid">
            {CATEGORIES.map((c) => {
              const signals = (data.signals || []).filter((s) => s.category === c.id);
              return (
                <section key={c.id} className={`sig-card sig-${c.id}`} aria-labelledby={`sig-${c.id}`}>
                  <div className="sig-card-head">
                    <span className="sig-icon" aria-hidden="true"><Icon icon={c.icon} size={18} /></span>
                    <span className="sig-card-title"><h4 id={`sig-${c.id}`}>{c.title}</h4><span className="sig-blurb">{c.blurb}</span></span>
                    <Tally signals={signals} />
                  </div>
                  {signals.length
                    ? <ol className="sig-list">{signals.map((s, i) => <Signal key={i} s={s} />)}</ol>
                    : data.domains?.[c.id] === "failed"
                      ? <p className="sig-empty failed">This area could not be searched this time — use Refresh to try again.</p>
                      : <p className="sig-empty">Nothing specific to this market in the last 24 months.</p>}
                </section>
              );
            })}
          </div>
        </>)}
      </Lookup>
    </Section>
  );
}
