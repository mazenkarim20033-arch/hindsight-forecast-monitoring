export type Level = 0.8 | 0.9;
export interface Note { level: "info" | "warning"; text: string; code?: string; params?: Record<string, unknown> }
export interface ColumnInfo { name: string; examples: string[]; numeric_share: number }
export type BusinessKind = "price" | "unit_cost" | "on_hand" | "on_order";
export interface Detection { layout: "long" | "wide"; date: string; value: string | null; item: string | null; item_columns: string[]; item_cols: string[]; business: Partial<Record<BusinessKind, string>>; duplicates: "sum" | "drop_exact"; columns: ColumnInfo[] }
export interface ImportReport { layout: string; rows: number; n_series: number; first_date: string; last_date: string; n_days: number; notes: Note[]; business?: { columns: Partial<Record<BusinessKind, string>>; values: Record<string, Partial<Record<BusinessKind, number>>> } }
export interface QualityFinding { code: string; level: "info" | "warning"; n_items: number; items: string[]; params: Record<string, unknown>; examples?: { item: string; date: string; value: number; usual: number }[] }
export interface AdapterHint { name: string; description: string; applied: boolean }
export interface DatasetSummary {
  quality: QualityFinding[]; adapter: AdapterHint | null;
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

export type StrategyKey = "conservative" | "balanced" | "high_availability";
export interface InventoryInputs {
  mode: "periodic_review" | "single_period"; lead_time_days?: number; review_days?: number; period_days?: number; price?: number; unit_cost?: number;
  holding_cost_per_day?: number; stockout_penalty?: number; salvage_value?: number; service_level?: number; min_order_qty?: number; order_multiple?: number;
  method?: string; stock?: Record<string, { on_hand?: number; on_order?: number }>;
}
export interface StrategyResult {
  service_target: number; order_up_to: number; order: number; expected_leftover: number; expected_shortage: number; p_stockout: number; fill_rate: number;
  investment: number | null; expected_excess_cost: number | null; expected_stockout_cost: number | null; expected_cost: number | null; expected_profit: number | null;
}
export interface InventoryItem {
  item: string; forecast_demand: number; on_hand: number | null; on_order: number | null; inventory_position: number | null; flags: string[];
  status: "ok" | "limited"; demand_range?: (number | null)[]; by_strategy: Partial<Record<StrategyKey, StrategyResult>>;
}
export interface Inventory {
  method: string; mode: string; window_days: number; cost_based: boolean; horizon: number;
  assumptions: { field: string; value: number | string; source: "user" | "default" }[]; missing: string[];
  levels: Record<StrategyKey, number>; items: InventoryItem[];
  totals: Partial<Record<StrategyKey, { order: number; investment: number | null; expected_cost: number | null; expected_leftover: number; expected_shortage: number }>>;
  calibration: { strategy: StrategyKey; target: number; realized: number | null; n_cases: number }[]; notes: string[];
}

/** What-if scenarios (percentages are in percent: 20 means +20%). Every field left out is not applied. */
export interface ScenarioSpec {
  name: string; demand_change_pct?: number; promo_uplift_pct?: number; promo_days?: number; seasonal_change_pct?: number; seasonal_days?: number;
  spike_pct?: number; spike_days?: number; supplier_delay_days?: number; stock_reduction_pct?: number; price_change_pct?: number; price_elasticity?: number;
}
export interface Pair { baseline: number | null; scenario: number | null; delta: number | null; delta_pct: number | null }
export type KeptOrder = Pick<StrategyResult, "order" | "expected_leftover" | "expected_shortage" | "p_stockout" | "fill_rate" | "expected_cost" | "expected_excess_cost" | "expected_stockout_cost" | "investment" | "expected_profit">;
export interface ScenarioItemCompare {
  item: string; status: "ok" | "limited"; forecast_demand?: Pair;
  by_strategy?: Partial<Record<StrategyKey, { order: Pair; p_stockout: Pair; if_baseline_order?: KeptOrder }>>;
}
export interface ScenarioResult {
  name: string; spec: Omit<ScenarioSpec, "name">; error?: { message: string; code?: string; params?: Record<string, unknown> };
  effects?: ({ kind: string; demand_factor?: number } & Record<string, number | string>)[]; demand_factor?: number; window_days?: number; result?: Inventory;
  comparison?: {
    totals: Partial<Record<StrategyKey, Record<"order" | "investment" | "expected_leftover" | "expected_shortage" | "expected_cost", Pair>>>;
    if_baseline_order: Partial<Record<StrategyKey, Record<"expected_leftover" | "expected_shortage" | "expected_cost", Pair>>>;
    items: ScenarioItemCompare[];
  };
}
export interface ScenarioRun { baseline: Inventory; scenarios: ScenarioResult[]; notes: string[] }

/** Forecast health. */
export type HealthStatus = "healthy" | "watch" | "action" | "unknown";
export interface HealthSignal { key: "accuracy" | "vs_simple" | "bias" | "coverage" | "drift"; value: number | null; status: HealthStatus; watch: number; action: number; recent?: number | null; earlier?: number | null; simple_rule?: number | null }
export interface DriftInfo { psi: number | null; ks: number | null; ks_p: number | null; recent_mean: number | null; earlier_mean: number | null }
export interface Health {
  method: string; as_of: string; horizon: number;
  overall: { status: HealthStatus; signals: HealthSignal[]; drift: DriftInfo };
  counts: Record<HealthStatus, number>;
  items: { item: string; status: HealthStatus; signals: HealthSignal[]; drift: DriftInfo }[];
  timeline: { origin: string; known: string; wape: number | null; reference_wape: number | null; rolling: number | null; rolling_reference: number | null }[];
  thresholds: Record<string, number>;
  windows: { n_known: number; n_recent: number; n_earlier: number; recent_from: string | null; recent_to: string | null };
  notes: string[];
}
export interface Challenger {
  method: string; verdict: "promote_candidate" | "keep_current" | "inconclusive"; deployed: false; n_dates: number; from: string; to: string; gain: number; gain_ci95: [number, number];
  current: { wape: number; bias: number }; challenger: { wape: number; bias: number }; config: { train_days: number; refit_every: number }; notes: string[];
}

/** Decision audit. */
export interface AuditItemRecord {
  item: string; forecast_demand: number; on_hand: number | null; on_order: number | null; position: number; chosen_order: number; overridden: boolean;
  by_strategy: Partial<Record<StrategyKey, { order: number; order_up_to: number; p_stockout: number; expected_cost: number | null; expected_leftover: number; expected_shortage: number }>>;
}
export interface AuditDecisionPayload {
  dataset: { filename: string; n_days: number; as_of: string; as_of_index: number; fingerprint: string }; method: string; mode: string; window_days: number; cost_based: boolean;
  cu: number | null; co: number | null; strategy: StrategyKey; scenario: Omit<ScenarioSpec, "name"> & { name: string } | null; demand_factor: number; health: HealthStatus | null;
  items: AuditItemRecord[]; skipped: string[]; total_ordered: number; note: string;
}
export interface OutcomeResult { level: number; leftover: number; shortage: number; stocked_out: boolean; cost: number | null }
export interface OutcomeEvaluation {
  items: { item: string; actual: number; forecast: number; forecast_error: number | null; chosen_order: number; chosen: OutcomeResult; by_strategy: Partial<Record<StrategyKey, OutcomeResult & { order: number }>> }[];
  totals: { actual: number; forecast: number; leftover: number; shortage: number; cost: number | null }; by_strategy: Partial<Record<StrategyKey, { leftover: number; shortage: number; cost: number | null }>>;
  best_in_hindsight: StrategyKey | null; cost_known: boolean; forecast_error: number | null; window: { from: string; to: string; days: number };
}
export interface AuditEvent<P> { id: number; ts: string; kind: "decision" | "outcome"; ref: number | null; hash: string; payload: P }
export type AuditOutcome = AuditEvent<OutcomeEvaluation & { decision: number; dataset: { filename: string; last_day: string; n_days: number }; notes: string[] }>;
export interface AuditDecision extends AuditEvent<AuditDecisionPayload> { outcome: AuditOutcome | null }
export interface AuditList { decisions: AuditDecision[]; verify: { ok: boolean; n: number; bad_id: number | null; reason: "link" | "content" | null } }
export interface AuditReviewRow { decision_id: number; status: "ready" | "not_yet" | "recorded" | "items_missing" | "different_data"; params: Record<string, unknown>; preview?: OutcomeEvaluation }
