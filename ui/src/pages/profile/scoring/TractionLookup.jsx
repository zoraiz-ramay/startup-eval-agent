import React, { useCallback, useEffect, useState } from "react";
import ConfirmedTag from "../../../components/ConfirmedTag.jsx";
import { api } from "../../../api.js";
import ErrorBox from "../../../components/ErrorBox.jsx";
import { Loading } from "../../../components/widgets.jsx";

/* Traction facts looked up when a division's panel opens (core/traction_lookup.py): the
   reviewer's Tracxn first, the model's web search second, never the model's memory. Every row
   carries the sources it came from. Kept for the visit per run and kind, so opening and closing a
   panel does not repeat a lookup that costs a search. */
const cache = new Map();

export function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
}

/** Source links, one per site: grounding returns several redirect links to the same page. A
    source with no link (a database, the application form) is named, never left blank. */
export function Sources({ items, label = "Sources" }) {
  const seen = new Set();
  const list = (items || []).filter((s) => {
    const key = s.title || hostOf(s.url) || s.url;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (!list.length) return null;
  return (
    <span className="fd-sources"><span className="muted">{label}:</span>
      {list.map((s, i) => (s.url
        ? <a key={i} href={s.url} target="_blank" rel="noopener noreferrer">{/^https?:/.test(s.title || "") || !s.title ? hostOf(s.url) : s.title}</a>
        : <span key={i} className="kind-tag">{s.title}</span>))}
    </span>
  );
}

function useLookup(runId, kind) {
  const key = `${runId}:${kind}`;
  const [state, setState] = useState(() => (cache.has(key) ? { data: cache.get(key) } : { loading: runId != null }));
  const load = useCallback(async (refresh = false) => {
    if (runId == null) return;
    setState({ loading: true });
    try {
      const data = await api.runLookup(runId, kind, refresh);
      cache.set(key, data);
      setState({ data });
    } catch (e) {
      setState({ error: e.message });
    }
  }, [runId, kind, key]);
  useEffect(() => { if (runId != null && !cache.has(key)) load(); }, [runId, key, load]);
  return [state, load];
}

const PROVIDER = { tracxn: "From Tracxn", web: "From web search · verify figures" };

/* The chrome every lookup shares: its heading, where the answer came from, a refresh, and the
   loading, error and fallback states — so each division only draws its own rows. */
export function Lookup({ runId, kind, title, loadingText, className = "fd", children }) {
  const [state, load] = useLookup(runId, kind);
  const data = state.data;
  const id = `lookup-${kind}`;
  return (
    <section className={className} aria-labelledby={title ? id : undefined} aria-label={title ? undefined : loadingText}
      aria-busy={state.loading || undefined}>
      <div className="fd-head">
        {title && <h5 id={id}>{title}</h5>}
        {data && PROVIDER[data.provider] && <span className={`fd-provider ${data.provider}`}>{PROVIDER[data.provider]}</span>}
        {/* Served from the database: say when it was fetched, so a reviewer can judge its age. */}
        {data?.stored_at && <span className="fd-stored" title={data.stored_at}>Saved {String(data.stored_at).slice(0, 10)}</span>}
        {data && <button type="button" className="link-btn fd-refresh" onClick={() => load(true)}>Refresh</button>}
      </div>
      {runId == null && <p className="muted">Looked up for a saved run.</p>}
      {state.loading && <Loading text={loadingText} />}
      {state.error && <ErrorBox message={state.error} />}
      {data?.note && <p className="crit-note">{data.note}</p>}
      {data && children(data)}
    </section>
  );
}

function Round({ r }) {
  return (
    <li className="fd-round">
      <span className="fd-date">{r.date || "Date not disclosed"}</span>
      <div className="fd-round-body">
        <div className="fd-round-head">
          <strong className="fd-amount">{r.amount || "Amount not disclosed"}</strong>
          {r.stage && <span className="pill pill-neutral">{r.stage}</span>}
        </div>
        {r.lead_investors.length > 0 && <p><span className="muted">Led by</span> {r.lead_investors.join(", ")}</p>}
        {r.investors.length > 0 && <p><span className="muted">{r.lead_investors.length ? "With" : "Investors"}</span> {r.investors.join(", ")}</p>}
        <Sources items={r.sources} />
      </div>
    </li>
  );
}

function Investor({ i }) {
  return (
    <li className="fd-investor">
      <div className="fd-investor-head"><strong>{i.name}</strong>
        {i.type && <span className="kind-tag" title={i.type_detail || undefined}>{i.type}</span>}</div>
      {i.hq && <p className="muted">{i.hq}</p>}
      {i.focus && <p className="fd-focus">{i.focus}</p>}
      {i.portfolio.length > 0 && <p><span className="muted">Portfolio:</span> {i.portfolio.join(", ")}</p>}
      <Sources items={i.sources} />
    </li>
  );
}

export function FundingLookup({ runId, known = [] }) {
  return (
    <Lookup runId={runId} kind="funding" title="Funding rounds & investors" loadingText="Looking up funding rounds and investors…">
      {(data) => <>
        {data.rounds.length > 0
          ? <ol className="fd-rounds" aria-label="Funding rounds">{data.rounds.map((r, k) => <Round key={k} r={r} />)}</ol>
          : <p className="muted">No funding round with a source was found.</p>}
        {data.investors.length > 0 ? <>
          <h5>Investor profiles</h5>
          <ul className="fd-investors" aria-label="Investor profiles">{data.investors.map((i) => <Investor key={i.name} i={i} />)}</ul>
        </> : known.length > 0 && <>
          <h5>Investors on record</h5>
          <ul className="fd-investors" aria-label="Investors on record">{known.map((i) => (
            <li key={i.name} className="fd-investor"><div className="fd-investor-head"><strong>{i.name}</strong> <ConfirmedTag item={i} /></div>
              <Sources items={i.source_url ? [{ title: "", url: i.source_url }] : []} /></li>))}</ul>
        </>}
      </>}
    </Lookup>
  );
}

export function HeadcountLookup({ runId }) {
  return (
    <Lookup runId={runId} kind="headcount" title="Current headcount, sourced" loadingText="Looking up where the headcount is reported…">
      {(data) => (data.figures.length > 0
        ? <ul className="division-list" aria-label="Reported headcounts">{data.figures.map((f, k) => (
          <li key={k}>
            <span className="division-list-main"><strong>{f.count}</strong>{f.as_of && <span className="muted">{f.as_of}</span>}</span>
            {f.where && <span className="muted">{f.where}</span>}
            <Sources items={f.sources} label="Source" />
          </li>))}</ul>
        : <p className="muted">No reported headcount with a source was found.</p>)}
    </Lookup>
  );
}
