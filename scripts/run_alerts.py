"""Measure the odd-day alerts on M5 (store level, boosted forecaster) and print a sample explanation.

Recall is measured by injecting known one-day changes (spikes, slumps, closures) into the real sales and replaying again: the model
then sees the injected days in its history exactly as it would see real ones. False alarms are flagged days among the days we did not
touch. Injected days are synthetic by construction; everything else is real M5 data (US Walmart, not Egyptian shops)."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight.calendar_features import M5Events
from hindsight.data.m5 import at_level, load_m5
from hindsight.replay.alerts import find_odd_days, inject_anomalies, latest_forecast_per_day
from hindsight.replay.engine import Replay, make_origins, run_replay
from hindsight.replay.explain import explain_forecast
from hindsight.replay.intervals import conformal_intervals
from hindsight.replay.ml import GlobalLightGBM

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "extracted"
HORIZON, STEP, MIN_TRAIN, SCORE_DAYS = 28, 5, 365, 730
FACTORS = [1.3, 1.6, 2.2, 0.75, 0.5, 0.0]
N_INJECT = 60
LEVELS = (0.95, 0.98)


def labels_from(calendar: pd.DataFrame) -> pd.Series:
    cal = calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"])
    return cal.dropna(subset=["event_name_1"]).set_index("date")["event_name_1"]


def score(replay: Replay, values: np.ndarray, injected, level: float, n_days: int, window_start: int, labels) -> dict:
    ir = conformal_intervals(replay, values, level=level, min_residuals=200)
    f = latest_forecast_per_day(ir, n_days)
    in_window = np.zeros(n_days, dtype=bool)
    in_window[window_start:] = True
    covered = np.isfinite(f["high"]) & in_window[None, :]
    touched = np.zeros_like(covered)
    for x in injected:
        touched[x.series, x.day] = True
    odd = find_odd_days(ir, values, labels)
    flagged = np.zeros_like(covered)
    for r in odd.itertuples():
        flagged[replay.ids.index(r.series), int(np.searchsorted(replay.dates, r.date))] = True
    flagged &= covered
    clean = covered & ~touched
    per_factor = {}
    for k in sorted({x.factor for x in injected}):
        xs = [x for x in injected if x.factor == k and covered[x.series, x.day]]
        per_factor[str(k)] = {"n": len(xs), "caught": int(sum(flagged[x.series, x.day] for x in xs))}
    xs_all = [x for x in injected if covered[x.series, x.day]]
    return {"level": level, "injected_scored": len(xs_all), "recall": float(np.mean([flagged[x.series, x.day] for x in xs_all])) if xs_all else float("nan"),
            "recall_by_factor": per_factor, "clean_days": int(clean.sum()), "false_alarm_rate": float((flagged & clean).sum() / clean.sum()),
            "expected_false_alarm_rate": 1 - level, "_odd": odd}


def main() -> None:
    t0 = time.perf_counter()
    data = load_m5(RAW)
    events = M5Events(data.calendar)
    labels = labels_from(data.calendar)
    store = at_level(data, "store")
    origins = make_origins(store.n_days, HORIZON, MIN_TRAIN, STEP)
    window_start = store.n_days - SCORE_DAYS
    clean_replay = run_replay(store, GlobalLightGBM(calendars=[events], name="gradient boosting"), HORIZON, origins)
    print(f"clean replay done in {time.perf_counter() - t0:.0f}s", flush=True)
    bad, injected = inject_anomalies(store, np.arange(window_start + 30, store.n_days - 5), FACTORS, N_INJECT, seed=11)
    bad_replay = run_replay(bad, GlobalLightGBM(calendars=[events], name="gradient boosting"), HORIZON, origins)
    print(f"injected replay done in {time.perf_counter() - t0:.0f}s ({len(injected)} injected)", flush=True)

    results, lines = {}, ["# Odd-day alerts on M5 (generated)", "",
                          f"Store level (10 stores), boosted forecaster, {HORIZON}-day replay every {STEP} days. A day is flagged when sales fall outside the range of the latest forecast made before it. "
                          f"{len(injected)} one-day changes were injected into the real sales in the last {SCORE_DAYS} days (the injected days are synthetic; the rest is real US data). "
                          "False alarms are flagged days among days not touched, so some 'false alarms' may be genuinely unusual real days.", ""]
    lines += ["| Range level | Share of injected days caught | Flagged normal days | Flagged by chance if ranges were exact |", "|---|---|---|---|"]
    detail = []
    for level in LEVELS:
        res = score(bad_replay, bad.values, injected, level, store.n_days, window_start, labels)
        clean_res = score(clean_replay, store.values, [], level, store.n_days, window_start, labels)
        results[str(level)] = {k: v for k, v in res.items() if k != "_odd"} | {"clean_data_flag_rate": clean_res["false_alarm_rate"]}
        lines.append(f"| {level:.0%} | {res['recall']:.0%} ({res['injected_scored']} days) | {res['false_alarm_rate']:.1%} (on injected run), {clean_res['false_alarm_rate']:.1%} (on untouched data) | {1 - level:.0%} |")
        detail.append((level, res, clean_res))
    lines += ["", "## Share caught by size of change (injected days)", "", "| Change | " + " | ".join(f"{l:.0%} range" for l in LEVELS) + " |", "|---|" + "---|" * len(LEVELS)]
    names = {"1.3": "sales +30%", "1.6": "sales +60%", "2.2": "sales x2.2", "0.75": "sales -25%", "0.5": "sales -50%", "0.0": "closed (zero sales)"}
    for k in map(str, sorted({x.factor for x in injected})):
        cells = []
        for _, res, _ in detail:
            f = res["recall_by_factor"][k]
            cells.append(f"{f['caught']}/{f['n']}")
        lines.append(f"| {names.get(k, k)} | " + " | ".join(cells) + " |")
    odd_clean = detail[-1][2]["_odd"]
    top = odd_clean[odd_clean.date >= store.dates[window_start]].head(12)
    lines += ["", f"## The biggest surprises in the untouched real data, last {SCORE_DAYS} days ({LEVELS[-1]:.0%} range)", "",
              "| Store | Date | Actual | Expected | Direction | Known event that day |", "|---|---|---|---|---|---|"]
    lines += [f"| {r.series} | {r.date.date()} | {r.actual:.0f} | {r.expected:.0f} | {r.direction} | {'-' if pd.isna(r.known_event) else r.known_event} |" for r in top.itertuples()]

    total = at_level(data, "total")
    model = GlobalLightGBM(calendars=[events], name="gradient boosting")
    o = int(np.searchsorted(total.dates, pd.Timestamp("2015-11-20")))
    exp = explain_forecast(model, total.values[:, : o + 1].copy(), total.dates[: o + 1], HORIZON, total.ids)
    day = int(np.searchsorted(exp.dates, pd.Timestamp("2015-11-26")))
    actual = total.values[0, o + 1 + day]
    lines += ["", f"## Sample explanation: whole company, forecast made on {total.dates[o].date()} for {exp.dates[day].date()} (Thanksgiving)", "",
              f"Forecast {exp.forecast[0, day]:,.0f}; what actually happened: {actual:,.0f}. Reasons, in units sold:", "", "| Reason | Units |", "|---|---|"]
    lines += [f"| {r['reason']} | {r['units']:+,.0f} |" for r in exp.table(0, day)]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (ROOT / "experiments" / "runs" / f"alerts-m5-{stamp}.json").write_text(json.dumps({"n_injected": len(injected), "levels": results}, indent=2))
    (ROOT / "reports" / "alerts_m5.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    print(f"total {time.perf_counter() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
