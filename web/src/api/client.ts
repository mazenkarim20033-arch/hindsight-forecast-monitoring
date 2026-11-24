import { snapshotApi } from "./snapshot";
import type { Alerts, AuditEvent, AuditList, AuditOutcome, AuditReviewRow, AnalysisSettings, Dashboard, DatasetSummary, Effects, Challenger, Health, Inventory, InventoryInputs, Job, ScenarioRun, ScenarioSpec, NextView, Overview, Scorecard, Stage, StockPlan } from "./types";

const OWNER_STORE = "hindsight.owner";
export const ownerKey = {
  get: (): string => { try { return sessionStorage.getItem(OWNER_STORE) ?? ""; } catch { return ""; } },
  set: (k: string) => { try { if (k) sessionStorage.setItem(OWNER_STORE, k); else sessionStorage.removeItem(OWNER_STORE); } catch { /* storage may be blocked */ } },
};

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
    const key = ownerKey.get();
    res = await fetch(`${BASE}${path}${query ? `?${query}` : ""}`, { ...init, headers: { ...(init?.headers as Record<string, string> | undefined), ...(key ? { "X-Owner-Key": key } : {}) }, signal });
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

export interface RemapBody {
  date?: string; value?: string | null; item?: string | null; item_columns?: string[] | null; item_cols?: string[] | null;
  business?: Record<string, string | null> | null; duplicates?: "sum" | "drop_exact"; adapter?: string;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const liveApi = {
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DatasetSummary>("/datasets", { method: "POST", body: form });
  },
  owner: (signal?: AbortSignal) => request<{ required: boolean; allowed: boolean }>("/owner", undefined, undefined, signal),
  sample: () => request<DatasetSummary>("/datasets/sample", { method: "POST" }),
  dataset: (id: string, signal?: AbortSignal) => request<DatasetSummary>(`/datasets/${id}`, undefined, undefined, signal),
  remap: (id: string, mapping: RemapBody) => request<DatasetSummary>(`/datasets/${id}/mapping`, json(mapping)),
  saveAdapter: (id: string, body: { name: string; description?: string; overwrite?: boolean }) => request<DatasetSummary>(`/datasets/${id}/adapters`, json(body)),
  analyze: (id: string, settings: AnalysisSettings) => request<Job>(`/datasets/${id}/analysis`, json(settings)),
  job: (id: string, signal?: AbortSignal) => request<Job>(`/jobs/${id}`, undefined, undefined, signal),
  overview: (id: string, signal?: AbortSignal) => request<Overview>(`/datasets/${id}/overview`, undefined, undefined, signal),
  scorecard: (id: string, signal?: AbortSignal) => request<Scorecard>(`/datasets/${id}/scorecard`, undefined, undefined, signal),
  stage: (id: string, p: { item?: string; method?: string; level?: number }, signal?: AbortSignal) => request<Stage>(`/datasets/${id}/stage`, undefined, p, signal),
  next: (id: string, p: { item?: string; method?: string; level?: number; day?: number }, signal?: AbortSignal) => request<NextView>(`/datasets/${id}/next`, undefined, p, signal),
  alerts: (id: string, p: { method?: string; item?: string }, signal?: AbortSignal) => request<Alerts>(`/datasets/${id}/alerts`, undefined, p, signal),
  dashboard: (id: string, p: { method?: string }, signal?: AbortSignal) => request<Dashboard>(`/datasets/${id}/dashboard`, undefined, p, signal),
  total: (id: string, p: { method?: string; level?: number }, signal?: AbortSignal) => request<NextView>(`/datasets/${id}/total`, undefined, p, signal),
  planner: (id: string, p: { item?: string; method?: string }, signal?: AbortSignal) => request<StockPlan>(`/datasets/${id}/planner`, undefined, p, signal),
  effects: (id: string, signal?: AbortSignal) => request<Effects>(`/datasets/${id}/effects`, undefined, undefined, signal),
  inventory: (id: string, body: InventoryInputs, signal?: AbortSignal) => request<Inventory>(`/datasets/${id}/inventory`, { ...json(body), signal }, undefined, signal),
  health: (id: string, method: string, signal?: AbortSignal) => request<Health>(`/datasets/${id}/health`, { ...json({ method }), signal }, undefined, signal),
  challenger: (id: string, method: string, signal?: AbortSignal) => request<Challenger>(`/datasets/${id}/health/challenger`, { ...json({ method }), signal }, undefined, signal),
  auditRecord: (id: string, body: InventoryInputs & { strategy: string; orders: Record<string, number>; note: string; scenario?: ScenarioSpec }) =>
    request<AuditEvent<unknown>>(`/datasets/${id}/audit/decisions`, json(body)),
  auditEvents: (signal?: AbortSignal) => request<AuditList>("/audit/events", undefined, undefined, signal),
  auditReview: (id: string) => request<{ decisions: AuditReviewRow[] }>(`/datasets/${id}/audit/review`, { method: "POST" }),
  auditOutcome: (id: string, decision_id: number) => request<AuditOutcome>(`/datasets/${id}/audit/outcomes`, json({ decision_id })),
  auditExport: () => request<unknown>("/audit/export"),
  scenarios: (id: string, body: InventoryInputs & { scenarios: ScenarioSpec[] }, signal?: AbortSignal) => request<ScenarioRun>(`/datasets/${id}/scenarios`, { ...json(body), signal }, undefined, signal),
};

/** The public demo plays back recorded answers; everywhere else the app talks to the local server. */
export const IS_SNAPSHOT = import.meta.env.VITE_SNAPSHOT === "1";
export const api: typeof liveApi = IS_SNAPSHOT ? (snapshotApi as unknown as typeof liveApi) : liveApi;
