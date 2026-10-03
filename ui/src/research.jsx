import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const Context = createContext(null);
export const useResearch = () => useContext(Context);

export function ResearchProvider({ userId, children }) {
  const key = `research-jobs:${userId || "local"}`;
  const [jobs, setJobs] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(key) || "[]"); } catch { return []; }
  });
  const pendingStarts = useRef(new Map());
  const latest = useRef(jobs);
  latest.current = jobs;
  useEffect(() => {
    // Only opaque IDs/status/query labels are stored in the tab. Results live on the server.
    sessionStorage.setItem(key, JSON.stringify(jobs.map(({ id, kind, query, status }) => ({ id, kind, query, status }))));
  }, [jobs, key]);
  useEffect(() => {
    let stopped = false;
    let timer;
    const poll = async () => {
      const pending = latest.current.filter((j) => !j.result && j.status !== "error");
      const replies = await Promise.allSettled(pending.map(async (j) => {
        try { return await api.job(j.id); }
        catch (e) { return e.status === 404 ? { ...j, status: "error", error: "This research session expired. Start again." } : null; }
      }));
      if (stopped) return;
      const updates = new Map(replies.filter((r) => r.status === "fulfilled" && r.value).map((r) => [r.value.id, r.value]));
      if (updates.size) setJobs((old) => old.map((j) => updates.get(j.id) || j));
      timer = setTimeout(poll, 1500);
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, []);
  // No department: every evaluation is assessed for all of them (api/main._all_departments).
  const start = ({ names, problem, refresh = false }) => {
    const signature = JSON.stringify([names, problem, refresh]);
    if (pendingStarts.current.has(signature)) return pendingStarts.current.get(signature);
    const promise = api.startJobs({ kind: problem ? "solve" : "evaluate", names: names || [],
      problem: problem || "", refresh, request_id: crypto.randomUUID() }).then((result) => {
        setJobs((old) => [...result.jobs, ...old].slice(0, 100));
        return result.jobs;
      }).finally(() => pendingStarts.current.delete(signature));
    pendingStarts.current.set(signature, promise);
    return promise;
  };
  return <Context.Provider value={{ jobs, start }}>{children}</Context.Provider>;
}
