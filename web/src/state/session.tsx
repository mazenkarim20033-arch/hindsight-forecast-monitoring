import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { DatasetSummary, Overview } from "../api/types";

interface Session {
  dataset: DatasetSummary | null;
  overview: Overview | null;
  item: string | undefined;
  method: string;
  level: 0.8 | 0.9;
  restoring: boolean;
  setDataset: (d: DatasetSummary | null) => void;
  setOverview: (o: Overview | null) => void;
  setItem: (i: string) => void;
  setMethod: (m: string) => void;
  setLevel: (l: 0.8 | 0.9) => void;
  forget: () => void;
}

const Ctx = createContext<Session | null>(null);
const KEY = "hindsight.dataset";
export const AUTO = "best method so far";

function remembered(): string | null {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
}
function remember(id: string | null) {
  try { if (id) sessionStorage.setItem(KEY, id); else sessionStorage.removeItem(KEY); } catch { /* storage may be blocked */ }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [dataset, setDatasetState] = useState<DatasetSummary | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [item, setItem] = useState<string | undefined>();
  const [method, setMethod] = useState(AUTO);
  const [level, setLevel] = useState<0.8 | 0.9>(0.8);
  const [restoring, setRestoring] = useState(() => remembered() !== null);

  const setDataset = useCallback((d: DatasetSummary | null) => {
    setDatasetState(d);
    remember(d?.id ?? null);
    if (!d || !d.analyzed) setOverview(null);
    setItem(undefined);
    setMethod(AUTO);
  }, []);

  useEffect(() => {
    const id = remembered();
    if (!id) return;
    const ctl = new AbortController();
    (async () => {
      try {
        const d = await api.dataset(id, ctl.signal);
        setDatasetState(d);
        if (d.analyzed) setOverview(await api.overview(id, ctl.signal));
      } catch {
        remember(null);
      } finally {
        if (!ctl.signal.aborted) setRestoring(false);
      }
    })();
    return () => ctl.abort();
  }, []);

  const value = useMemo<Session>(() => ({
    dataset, overview, item: item ?? overview?.series[0]?.id, method, level, restoring,
    setDataset, setOverview, setItem, setMethod, setLevel, forget: () => setDataset(null),
  }), [dataset, overview, item, method, level, restoring, setDataset]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession must be used inside SessionProvider");
  return v;
}
