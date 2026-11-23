import type { NextView, Stage } from "../api/types";
import { addDays } from "./format";

/** Everything the stage draws, in local day indices (0 = first date in `dates`). */
export interface StageModel {
  dates: string[];
  actual: (number | null)[]; // null where the day is not known
  fan: { origin: number; forecast: (number | null)[]; low: (number | null)[]; high: (number | null)[] } | null;
  cursor: number; // last revealed day
  hits: (boolean | null)[] | null;
  ymax: number;
  live: boolean;
}

export interface Readout {
  date: string;
  daysAhead: number;
  forecast: number | null;
  low: number | null;
  high: number | null;
  actual: number | null;
  hit: boolean | null;
  madeOn: string;
}

/** Index (into stage.origins) of the latest replay date on or before absolute day `d`, or -1 if there is none. */
export function originFor(stage: Pick<Stage, "origins">, d: number): number {
  let lo = 0;
  let hi = stage.origins.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (stage.origins[mid] <= d) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans;
}

export function firstDay(stage: Pick<Stage, "origins" | "first_day">): number {
  return Math.max(stage.origins[0] + 1, stage.first_day);
}

export function lastDay(stage: Pick<Stage, "first_day" | "dates">): number {
  return stage.first_day + stage.dates.length - 1;
}

export function niceMax(x: number): number {
  if (!(x > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(x));
  const m = x / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

export function stageYMax(stage: Stage): number {
  let m = 0;
  for (const v of stage.actual) if (v != null && v > m) m = v;
  for (const row of stage.high) for (const v of row) if (v != null && v > m) m = v;
  return niceMax(m * 1.04);
}

export function replayModel(stage: Stage, d: number, ymax = stageYMax(stage)): StageModel {
  const k = originFor(stage, d);
  const base = stage.first_day;
  const fan = k < 0 ? null : { origin: stage.origins[k] - base, forecast: stage.forecast[k], low: stage.low[k], high: stage.high[k] };
  return { dates: stage.dates, actual: stage.actual, fan, cursor: d - base, hits: stage.ribbon.hit, ymax, live: false };
}

export function readoutAt(stage: Stage, d: number): Readout | null {
  const k = originFor(stage, d);
  if (k < 0) return null;
  const h = d - stage.origins[k];
  if (h < 1 || h > stage.horizon) return null;
  const local = d - stage.first_day;
  const hit = stage.ribbon.hit[local];
  return {
    date: stage.dates[local], daysAhead: h, forecast: stage.forecast[k][h - 1], low: stage.low[k][h - 1], high: stage.high[k][h - 1],
    actual: stage.actual[local], hit: hit ?? null, madeOn: stage.dates[stage.origins[k] - stage.first_day] ?? addDays(stage.dates[local], -h),
  };
}

/** Share of days up to `d` (inside the shown period) whose real sales fell inside the range given for them. */
export function heldSoFar(stage: Stage, d: number): { held: number; of: number } {
  const end = d - stage.first_day;
  let held = 0;
  let of = 0;
  for (let i = 0; i <= end && i < stage.ribbon.hit.length; i++) {
    const h = stage.ribbon.hit[i];
    if (h == null) continue;
    of++;
    if (h) held++;
  }
  return { held, of };
}

export function liveModel(next: NextView, ymaxHint = 0): StageModel {
  const hist = next.history;
  const n = hist.dates.length;
  const dates = [...hist.dates, ...next.dates];
  const actual = [...hist.actual, ...next.dates.map(() => null)];
  let m = ymaxHint;
  for (const v of hist.actual) if (v != null && v > m) m = v;
  for (const v of next.high) if (v != null && v > m) m = v;
  for (const v of next.forecast) if (v != null && v > m) m = v;
  return { dates, actual, fan: { origin: n - 1, forecast: next.forecast, low: next.low, high: next.high }, cursor: n - 1, hits: null, ymax: niceMax(m * 1.04), live: true };
}
