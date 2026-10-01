import React, { useEffect, useState } from "react";
import { iconCogwheel, iconGroup, iconMoney, iconRocket, iconWarning } from "@siemens/ix-icons/icons";
import { api } from "../../api.js";
import ErrorBox from "../../components/ErrorBox.jsx";
import Icon from "../../components/Icon.jsx";
import Section from "./Section.jsx";
import { evidenceLabel } from "./scoring/presentation.js";

/* "How this startup works": the business as a short story a non-specialist can follow — the
   problem, what they offer, how it works, who buys it, how it makes money — one plain sentence
   each (core/business_flow.py). Every sentence cites the run's own research and is checked
   against it on the server; a step the research does not cover is simply not drawn. The cards
   carry no labels or source names; a small number on each points to one sources line below, and
   hovering a card shows the sentence it was written from. Written once per run, kept per visit. */
const ICON = { problem: iconWarning, offer: iconRocket, how: iconCogwheel, customers: iconGroup, money: iconMoney };
const cache = new Map();

function numberSources(steps) {
  const list = [];
  const index = new Map();
  const refs = steps.map((s) => s.sources.map((src) => {
    const label = evidenceLabel(src);
    const key = `${label}|${src.url || ""}`;
    if (!index.has(key)) { index.set(key, list.length + 1); list.push({ label, url: src.url || "" }); }
    return index.get(key);
  }));
  return { list, refs: refs.map((r) => [...new Set(r)]) };
}

export default function BusinessFlow({ res }) {
  const runId = res?.run_id ?? null;
  const [state, setState] = useState(() => (cache.has(runId) ? { data: cache.get(runId) } : { loading: runId != null }));
  useEffect(() => {
    if (runId == null || cache.has(runId)) return undefined;
    let live = true;
    setState({ loading: true });
    api.runBusinessFlow(runId)
      .then((data) => { cache.set(runId, data); if (live) setState({ data }); })
      .catch((e) => { if (live) setState({ error: e.message }); });
    return () => { live = false; };
  }, [runId]);

  const data = state.data;
  const steps = data?.status === "ok" ? data.steps : [];
  const { list, refs } = numberSources(steps);
  return (
    <Section id="profile-how-it-works">
      <h3>How this startup works</h3>
      {runId == null && <p className="muted">Available once the evaluation has finished.</p>}
      {state.loading && (
        <div className="biz-skeleton" role="status" aria-label="Writing how this startup works">
          {[0, 1, 2, 3, 4].map((i) => <span key={i} />)}
        </div>
      )}
      {state.error && <ErrorBox message={state.error} />}
      {data && data.status !== "ok" && <p className="muted" role="status">{data.message}</p>}
      {steps.length > 0 && <>
        <ol className="biz-story" aria-label="How this startup works, step by step">
          {steps.map((s, i) => (
            <li key={s.id} className={`biz-card biz-${s.id}`} title={s.sources.map((x) => x.quote).join("\n\n").slice(0, 600)}>
              <span className="biz-card-icon" aria-hidden="true"><Icon icon={ICON[s.id]} size={22} /></span>
              <span className="biz-card-label">{s.label}</span>
              <p className="biz-card-text">{s.text}
                {refs[i].map((n) => <sup key={n} className="biz-ref"><a href={`#biz-src-${n}`} aria-label={`Source ${n}`}>{n}</a></sup>)}</p>
            </li>
          ))}
        </ol>
        <p className="biz-sources">
          <span className="muted">Sources:</span>
          {list.map((s, i) => (
            <span key={i} id={`biz-src-${i + 1}`} className="biz-source">
              <span className="biz-source-n">{i + 1}</span>
              {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a> : s.label}
            </span>
          ))}
        </p>
      </>}
    </Section>
  );
}
