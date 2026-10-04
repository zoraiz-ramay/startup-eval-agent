import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Loading } from "./widgets.jsx";

/* Admin: what each evaluation cost in model tokens, and where it went.

   Every model call a research run makes is logged (core/llm.py): its pipeline stage, model,
   input / output / reasoning tokens, time, attempts, and whether the cache answered it. The table
   lists runs newest first; opening one shows its calls in the order they finished. Cache hits
   are listed at zero tokens because they cost nothing — counting them shows how much of a re-run
   the cache answered. Runs saved before the log existed are counted but have no log. */

const n = (v) => (v || 0).toLocaleString("en-GB");
const secs = (ms) => `${((ms || 0) / 1000).toFixed(1)}s`;
const STAGE = {
  input: "Company lookup", enrich: "Enrichment", verification: "Fact verification", summary: "Summary",
  fit: "Siemens tool fit", profile: "Deep profile", trend: "Market trend", score: "Model score",
  pillars: "Pillar assessment", team_ecosystem: "Team & Ecosystem", market: "Market rubric",
};

function CallLog({ runId }) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    let live = true;
    api.adminTokenUsageRun(runId)
      .then((r) => { if (live) setState({ calls: r?.calls || [] }); })
      .catch((e) => { if (live) setState({ error: e.message }); });
    return () => { live = false; };
  }, [runId]);
  if (state.loading) return <Loading text="Loading the call log…" />;
  if (state.error) return <p className="muted">The call log could not be loaded: {state.error}</p>;
  return (
    <table className="dtable dense" aria-label={`Model calls of run ${runId}`}>
      <thead><tr><th>#</th><th>Stage</th><th>Call</th><th>Model</th><th>Input</th><th>Output</th>
        <th>Reasoning</th><th>Total</th><th>Time</th><th>Result</th></tr></thead>
      <tbody>
        {state.calls.map((c) => (
          <tr key={c.seq} style={{ cursor: "default" }}>
            <td>{c.seq + 1}</td>
            <td>{STAGE[c.stage] || c.stage}</td>
            <td>{c.kind === "web_search" ? "Web search" : "Completion"}</td>
            <td>{c.model || "—"}</td>
            <td>{n(c.input_tokens)}</td>
            <td>{n(c.output_tokens)}</td>
            <td>{n(c.reasoning_tokens)}</td>
            <td><strong>{n(c.total_tokens)}</strong></td>
            <td>{secs(c.duration_ms)}</td>
            <td>{c.cached ? "From cache" : c.ok ? (c.attempts > 1 ? `OK after ${c.attempts} attempts` : "OK")
              : `Failed (${c.reason || "error"}, ${c.attempts} attempts)`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function TokenUsage() {
  const [state, setState] = useState({ loading: true });
  const [open, setOpen] = useState(null);
  useEffect(() => {
    let live = true;
    Promise.resolve().then(() => api.adminTokenUsage())
      .then((r) => { if (live) setState({ data: r }); })
      .catch((e) => { if (live) setState({ error: e.message }); });
    return () => { live = false; };
  }, []);
  const data = state.data;
  return (
    <div className="panel" aria-labelledby="token-usage">
      <h3 id="token-usage">Token usage per evaluation{data ? ` (${data.runs.length})` : ""}</h3>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
        Model tokens each research run used, newest first. Open a run for its call log.
        {data?.unlogged_runs > 0 && ` ${data.unlogged_runs} older runs were saved before token logging and have no log.`}
      </p>
      {state.loading && <Loading text="Loading token usage…" />}
      {state.error && <p className="muted">Token usage could not be loaded: {state.error}</p>}
      {data && data.runs.length === 0 && <p className="muted" style={{ fontSize: 12 }}>No evaluation has been logged yet.</p>}
      {data && data.runs.length > 0 && (
        <>
          <p className="token-totals">
            All logged runs: <strong>{n(data.totals.total_tokens)}</strong> tokens over {n(data.totals.calls)} calls
            ({n(data.totals.input_tokens)} input · {n(data.totals.output_tokens)} output · {n(data.totals.reasoning_tokens)} reasoning)
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="dtable dense" aria-label="Token usage per evaluation">
              <thead><tr><th>Company</th><th>When</th><th>Requested by</th><th>Calls</th><th>Input</th><th>Output</th>
                <th>Reasoning</th><th>Total</th><th>Model time</th><th></th></tr></thead>
              <tbody>
                {data.runs.map((r) => (
                  <React.Fragment key={r.run_id}>
                    <tr style={{ cursor: "default" }}>
                      <td><strong>{r.company}</strong><div className="muted" style={{ fontSize: 11 }}>{r.scope}</div></td>
                      <td>{r.created_at ? `${r.created_at.slice(0, 16).replace("T", " ")} UTC` : "—"}</td>
                      <td>{r.requested_by || "—"}</td>
                      <td>{r.calls}{r.cached_calls ? ` (${r.cached_calls} cached)` : ""}{r.failed_calls ? ` · ${r.failed_calls} failed` : ""}</td>
                      <td>{n(r.input_tokens)}</td>
                      <td>{n(r.output_tokens)}</td>
                      <td>{n(r.reasoning_tokens)}</td>
                      <td><strong>{n(r.total_tokens)}</strong></td>
                      <td>{secs(r.duration_ms)}</td>
                      <td>
                        <button type="button" className="link-btn" aria-expanded={open === r.run_id}
                          aria-controls={`token-log-${r.run_id}`}
                          onClick={() => setOpen(open === r.run_id ? null : r.run_id)}>
                          {open === r.run_id ? "Hide log" : "Show log"}<span className="sr-only"> for {r.company}</span>
                        </button>
                      </td>
                    </tr>
                    {open === r.run_id && (
                      <tr id={`token-log-${r.run_id}`} style={{ cursor: "default" }}>
                        <td colSpan={10}><CallLog runId={r.run_id} /></td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
