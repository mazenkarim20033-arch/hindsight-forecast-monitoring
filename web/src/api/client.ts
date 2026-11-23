import type { Alerts, AnalysisSettings, DatasetSummary, Job, NextView, Overview, Scorecard, Stage } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code = "", public params: Record<string, unknown> = {}) {
    super(message);
  }
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
export const API_DOWN = "Hindsight cannot reach its server. Start it with: python -m uvicorn hindsight.app.api:app --port 8100";

type Params = Record<string, string | number | undefined>;

async function request<T>(path: string, init?: RequestInit, params?: Params, signal?: AbortSignal): Promise<T> {
  const query = Object.entries(params ?? {})
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${query ? `?${query}` : ""}`, { ...init, signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, API_DOWN, "server_down");
  }
  if (!res.ok) {
    let message = `The request failed (${res.status}).`;
    let code = "";
    let params: Record<string, unknown> = {};
    try {
      const body = await res.json();
      if (typeof body.message === "string") message = body.message;
      else if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || message;
      if (typeof body.code === "string") { code = body.code; params = body.params ?? {}; }
    } catch {
      /* keep the generic message */
    }
    if (!code && res.status === 404 && message.includes("no longer loaded")) code = "gone";
    if (!code && res.status === 409) code = "run_first";
    throw new ApiError(res.status, message, code, params);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DatasetSummary>("/datasets", { method: "POST", body: form });
  },
  sample: () => request<DatasetSummary>("/datasets/sample", { method: "POST" }),
  dataset: (id: string, signal?: AbortSignal) => request<DatasetSummary>(`/datasets/${id}`, undefined, undefined, signal),
  remap: (id: string, mapping: { date: string; value?: string | null; item?: string | null; item_columns?: string[] | null }) =>
    request<DatasetSummary>(`/datasets/${id}/mapping`, json(mapping)),
  analyze: (id: string, settings: AnalysisSettings) => request<Job>(`/datasets/${id}/analysis`, json(settings)),
  job: (id: string, signal?: AbortSignal) => request<Job>(`/jobs/${id}`, undefined, undefined, signal),
  overview: (id: string, signal?: AbortSignal) => request<Overview>(`/datasets/${id}/overview`, undefined, undefined, signal),
  scorecard: (id: string, signal?: AbortSignal) => request<Scorecard>(`/datasets/${id}/scorecard`, undefined, undefined, signal),
  stage: (id: string, p: { item?: string; method?: string; level?: number }, signal?: AbortSignal) => request<Stage>(`/datasets/${id}/stage`, undefined, p, signal),
  next: (id: string, p: { item?: string; method?: string; level?: number; day?: number }, signal?: AbortSignal) => request<NextView>(`/datasets/${id}/next`, undefined, p, signal),
  alerts: (id: string, p: { method?: string }, signal?: AbortSignal) => request<Alerts>(`/datasets/${id}/alerts`, undefined, p, signal),
};
