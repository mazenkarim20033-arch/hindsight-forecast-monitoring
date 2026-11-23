import { describe, expect, it } from "vitest";
import type { Stage } from "../api/types";
import { addDays, day, pct, signedPoints } from "../lib/format";
import { firstDay, heldSoFar, lastDay, liveModel, niceMax, originFor, readoutAt, replayModel } from "../lib/models";

function stage(): Stage {
  const n = 30;
  const dates = Array.from({ length: n }, (_, i) => addDays("2024-01-01", i));
  return {
    item: "A", method: "m", level: 0.8, horizon: 3, first_day: 100, dates, actual: dates.map((_, i) => 10 + i),
    origins: [110, 115, 120], forecast: [[1, 2, 3], [4, 5, 6], [7, 8, 9]], low: [[0, 1, 2], [3, 4, 5], [6, 7, 8]], high: [[2, 3, 4], [5, 6, 7], [8, 9, 10]], chosen: ["m", "m", "m"],
    ribbon: { hit: dates.map((_, i) => (i < 5 ? null : i % 4 !== 0)), expected: [], low: [], high: [] }, coverage_80: null,
  };
}

describe("replay model", () => {
  it("finds the latest replay date on or before a day", () => {
    const s = stage();
    expect([109, 110, 114, 115, 130].map((d) => originFor(s, d))).toEqual([-1, 0, 0, 1, 2]);
  });
  it("covers days from just after the first replay date to the last day of data", () => {
    const s = stage();
    expect(firstDay(s)).toBe(111);
    expect(lastDay(s)).toBe(129);
  });
  it("reads the forecast that was made, how many days earlier, and what happened", () => {
    const s = stage();
    const r = readoutAt(s, 116)!;
    expect(r.daysAhead).toBe(1);
    expect([r.forecast, r.low, r.high]).toEqual([4, 3, 5]);
    expect(r.actual).toBe(26);
    expect(r.madeOn).toBe(s.dates[15]);
    expect(readoutAt(s, 105)).toBeNull();
    expect(readoutAt(s, 124)).toBeNull(); // beyond the 3-day horizon of the origin at 120
  });
  it("counts how often the range held up to a day", () => {
    const s = stage();
    expect(heldSoFar(s, 100)).toEqual({ held: 0, of: 0 });
    const h = heldSoFar(s, 109);
    expect(h.of).toBe(5);
    expect(h.held).toBe(4);
  });
  it("puts the forecast fan at the replay date, in local indices", () => {
    const m = replayModel(stage(), 117, 100);
    expect(m.fan?.origin).toBe(15);
    expect(m.cursor).toBe(17);
    expect(m.live).toBe(false);
  });
  it("builds the live model with the curtain starting after today", () => {
    const m = liveModel({
      item: "A", method: "m", method_in_use: "m", level: 0.8, last_day: "2024-01-03", history: { dates: ["2024-01-01", "2024-01-02", "2024-01-03"], actual: [1, 2, 3] },
      dates: ["2024-01-04", "2024-01-05"], forecast: [4, 5], low: [3, 4], high: [5, 6], range_note: null, total_next_7: 9, reasons: null,
    });
    expect(m.cursor).toBe(2);
    expect(m.actual).toEqual([1, 2, 3, null, null]);
    expect(m.fan?.origin).toBe(2);
  });
});

describe("formatting", () => {
  it("rounds axis maxima to friendly numbers", () => {
    expect([niceMax(7), niceMax(10300), niceMax(0)]).toEqual([10, 20000, 1]);
  });
  it("does days in local time and adds days across months", () => {
    expect(day("2024-03-15").getDate()).toBe(15);
    expect(addDays("2024-02-28", 2)).toBe("2024-03-01");
  });
  it("formats percentages and point differences", () => {
    expect(pct(0.0756, 1)).toBe("7.6%");
    expect(pct(null)).toBe("n/a");
    expect(signedPoints(0.023)).toBe("+2.3 pts");
    expect(signedPoints(-0.01)).toBe("−1.0 pts");
  });
});
