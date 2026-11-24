import type { Alerts, Dashboard, DatasetSummary, Job, NextView, Overview, Scorecard, Stage } from "./types";

/** The public demo has no server: it plays back answers the real code recorded for the bundled sample (see scripts/export_snapshot.py). */
const BASE = `${import.meta.env.BASE_URL}snapshot/`;

export class SnapshotError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

async function load<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new SnapshotError(res.status, "That view was not recorded for the public demo. Run Hindsight locally to see it.");
  return (await res.json()) as T;
}

const level = (l?: number) => Math.round((l ?? 0.8) * 100);
const done: Job = { id: "snapshot", dataset: "snapshot", state: "done", progress: 1, message: "Done", error: null };

export const snapshotApi = {
  upload: async (): Promise<DatasetSummary> => { throw new SnapshotError(0, "Loading your own file is not available in the public demo. Run Hindsight locally to use your data."); },
  sample: (): Promise<DatasetSummary> => load("dataset.json"),
  dataset: (_id: string, signal?: AbortSignal): Promise<DatasetSummary> => load("dataset.json", signal),
  remap: async (): Promise<DatasetSummary> => { throw new SnapshotError(0, "Loading your own file is not available in the public demo."); },
  analyze: async (): Promise<Job> => done,
  job: async (): Promise<Job> => done,
  overview: (_id: string, signal?: AbortSignal): Promise<Overview> => load("overview.json", signal),
  scorecard: (_id: string, signal?: AbortSignal): Promise<Scorecard> => load("scorecard.json", signal),
  stage: (_id: string, p: { item?: string; method?: string; level?: number }, signal?: AbortSignal): Promise<Stage> =>
    load(`stage/${p.item}__${slug(p.method ?? "")}__${level(p.level)}.json`, signal),
  next: async (_id: string, p: { item?: string; method?: string; level?: number; day?: number }, signal?: AbortSignal): Promise<NextView> => {
    const n = await load<NextView & { reasons_all?: NextView["reasons"][] }>(`next/${p.item}__${slug(p.method ?? "")}__${level(p.level)}.json`, signal);
    return { ...n, reasons: n.reasons_all ? n.reasons_all[Math.min(p.day ?? 0, n.reasons_all.length - 1)] : n.reasons };
  },
  alerts: (_id: string, p: { method?: string; item?: string }, signal?: AbortSignal): Promise<Alerts> =>
    load(p.item ? `alerts/${slug(p.method ?? "")}__${p.item}.json` : `alerts/${slug(p.method ?? "")}.json`, signal),
  dashboard: (_id: string, p: { method?: string }, signal?: AbortSignal): Promise<Dashboard> => load(`dashboard/${slug(p.method ?? "")}.json`, signal),
  total: (_id: string, p: { method?: string; level?: number }, signal?: AbortSignal): Promise<NextView> => load(`total/${slug(p.method ?? "")}__${level(p.level)}.json`, signal),
};
