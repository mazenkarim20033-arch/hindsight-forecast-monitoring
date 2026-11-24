export type Level = 0.8 | 0.9;
export interface Note { level: "info" | "warning"; text: string; code?: string; params?: Record<string, unknown> }
export interface ColumnInfo { name: string; examples: string[]; numeric_share: number }
export interface Detection { layout: "long" | "wide"; date: string; value: string | null; item: string | null; item_columns: string[]; columns: ColumnInfo[] }
export interface ImportReport { layout: string; rows: number; n_series: number; first_date: string; last_date: string; n_days: number; notes: Note[] }
export interface DatasetSummary {
  id: string; filename: string; is_sample: boolean; report: ImportReport; detection: Detection;
  n_series: number; n_days: number; first_date: string; last_date: string; has_events: boolean; analyzed: boolean;
  plan: { tier: "full" | "simple" | "too_little"; text: string; params?: Record<string, unknown> };
}
export interface Job { id: string; dataset: string; state: "running" | "done" | "failed"; progress: number; message: string; error: string | null }

export interface Verdict { kind: "beats" | "tie" | "worse" | "reference_best"; method: string; wape: number; reference_wape: number; win_rate?: number; gain: number; gain_ci95?: [number, number]; text: string }
export interface Overview {
  tier: "full" | "simple"; tier_text: string; settings: { horizon: number; calendar: string };
  dates: { first: string; last: string; n_days: number }; replay: { n_dates: number; first_scored: string; step_days: number };
  series: { id: string; total: number; average_per_day: number }[];
  methods: { name: string; is_reference: boolean; is_auto: boolean }[]; verdict: Verdict; source: string;
}
export interface Stage {
  item: string; method: string; level: number; horizon: number; first_day: number; dates: string[]; actual: (number | null)[];
  origins: number[]; forecast: (number | null)[][]; low: (number | null)[][]; high: (number | null)[][]; chosen: string[];
  ribbon: { hit: (boolean | null)[]; expected: (number | null)[]; low: (number | null)[]; high: (number | null)[] };
  coverage_80: number | null;
}
export interface Reasons { day: number; date: string; forecast: number; items: { reason: string; units: number }[]; note: string }
export interface NextView {
  item: string; method: string; method_in_use: string; level: number; last_day: string;
  history: { dates: string[]; actual: (number | null)[] }; dates: string[]; forecast: (number | null)[]; low: (number | null)[]; high: (number | null)[];
  range_note: string | null; total_next_7: number; reasons: Reasons | null;
}
export interface MethodRow {
  method: string; wape: number; wape_ci95: [number, number]; wape_days_1_7: number; wape_days_8_28: number | null; bias: number;
  coverage_80: number | null; width_80: number | null; coverage_90: number | null; width_90: number | null;
  win_rate_vs_reference?: number; gain_vs_reference?: number; gain_ci95?: [number, number]; is_auto: boolean; is_reference: boolean;
}
export interface Scorecard {
  reference: string; best_method: string; verdict: Verdict; methods: MethodRow[];
  per_series: { series: string; reference_wape: number; best_wape: number; coverage_80: number | null; gain: number }[];
  window: { n_dates: number; horizon: number }; limits: string[];
}
export interface AlertItem { item: string; date: string; actual: number; expected: number; low: number; high: number; direction: "higher" | "lower"; deviation_pct: number }
export interface Alerts { level: number; method: string; count: number; items: AlertItem[]; note: string }
export interface DashItem { id: string; last_7: number; next_7: number; change: number | null; unusual_30d: number; reference_wape: number; best_wape: number; coverage_80: number | null; average_per_day: number }
export interface Dashboard {
  method: string; method_in_use: string; horizon: number; last_day: string;
  totals: { last_7: number; previous_7: number; next_7: number };
  trust: { coverage_80: number | null; wape: number; reference_wape: number; n_dates: number };
  verdict: Verdict; unusual_30d: number; items: DashItem[];
  recent_unusual: { item: string; date: string; actual: number; expected: number; direction: "higher" | "lower" }[];
}
export interface AnalysisSettings { horizon: number; calendar: "none" | "egypt" | "events" }
export interface PlanRow { key: "reference_guess" | "model_guess" | "upper_80" | "upper_90"; stockout_share: number; lost_share: number; leftover_share: number; average_order: number }
export interface StockPlan { item: string; method: string; days: number; n_dates: number; average_demand: number; strategies: PlanRow[]; note: string }
export interface Effect { kind: "egypt" | "event"; name: string; n_days: number; n_occurrences: number; ratio: number; ratio_low: number; ratio_high: number }
export interface Effects { effects: Effect[]; window_weeks: number; note: string }
