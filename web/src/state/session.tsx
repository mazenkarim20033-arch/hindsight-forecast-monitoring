import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ownerKey } from "../api/client";
import type { AnalysisSettings, DatasetSummary, Job, Overview } from "../api/types";
import { toProblem, type Problem } from "../hooks/useAsync";

export const AUTO = "best method so far";
const KEY = "hindsight.dataset";
const DEFAULTS: AnalysisSettings = { horizon: 28, calendar: "events" };

interface Session {
  dataset: DatasetSummary | null;
  overview: Overview | null;
  /** True while the first dataset is being found or prepared; the app shows a loading page until it is ready. */
  booting: boolean;
  job: Job | null;
  problem: Problem | null;
  owner: { required: boolean; allowed: boolean };
  /** Check a key with the server and remember it for this browser tab if it is accepted. */
  unlock: (key: string) => Promise<boolean>;
  method: string;
  level: 0.8 | 0.9;
  setDataset: (d: DatasetSummary | null) => void;
  setMethod: (m: string) => void;
  setLevel: (l: 0.8 | 0.9) => void;
  /** Run the analysis for the current dataset, then make it the one the app shows. */
  analyze: (settings: AnalysisSettings, dataset?: DatasetSummary) => Promise<boolean>;
  useSample: () => Promise<boolean>;
  clearProblem: () => void;
}

const Ctx = createContext<Session | null>(null);

function remembered(): string | null {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
}
function remember(id: string | null) {
  try { if (id) sessionStorage.setItem(KEY, id); else sessionStorage.removeItem(KEY); } catch { /* storage may be blocked */ }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [dataset, setDatasetState] = useState<DatasetSummary | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [booting, setBooting] = useState(true);
  const [owner, setOwner] = useState({ required: false, allowed: false });
  const [job, setJob] = useState<Job | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [method, setMethod] = useState(AUTO);
  const [level, setLevel] = useState<0.8 | 0.9>(0.8);
  const alive = useRef(true);
  const bootStarted = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const refreshOwner = useCallback(async () => {
    try { const o = await api.owner(); setOwner(o); return o.allowed; } catch { setOwner({ required: false, allowed: false }); return false; }
  }, []);
  const unlock = useCallback(async (key: string) => {
    ownerKey.set(key.trim());
    const ok = await refreshOwner();
    if (!ok) ownerKey.set("");
    return ok;
  }, [refreshOwner]);

  const setDataset = useCallback((d: DatasetSummary | null) => {
    setDatasetState(d);
    remember(d?.id ?? null);
    if (!d || !d.analyzed) setOverview(null);
    setMethod(AUTO);
  }, []);

  const analyze = useCallback(async (settings: AnalysisSettings, ds?: DatasetSummary): Promise<boolean> => {
    const target = ds ?? dataset;
    if (!target) return false;
    setProblem(null);
    try {
      let j = await api.analyze(target.id, settings);
      setJob(j);
      while (j.state === "running" && alive.current) {
        await new Promise((r) => setTimeout(r, 500));
        j = await api.job(j.id);
        setJob(j);
      }
      if (j.state === "failed") { setProblem({ message: j.error ?? "The analysis stopped unexpectedly." }); setJob(null); return false; }
      const ov = await api.overview(target.id);
      setDatasetState({ ...target, analyzed: true });
      remember(target.id);
      setOverview(ov);
      setMethod(AUTO);
      setJob(null);
      return true;
    } catch (e) {
      setProblem(toProblem(e));
      setJob(null);
      return false;
    }
  }, [dataset]);

  const useSample = useCallback(async () => {
    setProblem(null);
    try {
      const d = await api.sample();
      setDatasetState(d);
      return await analyze({ ...DEFAULTS, calendar: d.has_events ? "events" : "none" }, d);
    } catch (e) {
      setProblem(toProblem(e));
      return false;
    }
  }, [analyze]);

  // On first load: pick up where this browser tab left off, otherwise open the sample so the app is never empty.
  useEffect(() => {
    if (bootStarted.current) return; // React runs effects twice in development; one boot is enough
    bootStarted.current = true;
    void refreshOwner();
    let cancelled = false;
    (async () => {
      const id = remembered();
      if (id) {
        try {
          const d = await api.dataset(id);
          if (d.analyzed) {
            const ov = await api.overview(id);
            if (!cancelled) { setDatasetState(d); setOverview(ov); setBooting(false); }
            return;
          }
        } catch { remember(null); }
      }
      if (!cancelled) { await useSample(); if (!cancelled) setBooting(false); }
    })();
    return () => { cancelled = false; }; // the boot is allowed to finish even if the effect is re-run
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<Session>(() => ({
    dataset, overview, booting, job, problem, owner, unlock, method, level, setDataset, setMethod, setLevel, analyze, useSample, clearProblem: () => setProblem(null),
  }), [dataset, overview, booting, job, problem, owner, unlock, method, level, setDataset, analyze, useSample]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession must be used inside SessionProvider");
  return v;
}
