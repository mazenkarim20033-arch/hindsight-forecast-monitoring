"""Replay every method on M5 and score it: accuracy against the simple weekday rule, whether the 80% and 90% ranges held, and
whether choosing the best method so far would have paid off. Replay dates run from day 365 to the end; scoring covers the last
730 days. Nothing is tuned. M5 is US Walmart data: these numbers say nothing about Egyptian shops."""
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hindsight.calendar_features import M5Events
from hindsight.data.m5 import at_level, load_m5
from hindsight.replay.baselines import BASELINES
from hindsight.replay.engine import make_origins, run_replay
from hindsight.replay.intervals import IntervalReplay, conformal_intervals, coverage, relative_width
from hindsight.replay.metrics import bias, bootstrap_wape, paired_difference_ci, wape
from hindsight.replay.ml import GlobalLightGBM
from hindsight.replay.select import select_online
from hindsight.replay.stats import ExponentialSmoothingForecaster

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "extracted"
HORIZON, STEP, MIN_TRAIN, SCORE_DAYS = 28, 5, 365, 730
REFERENCE = "average of the same weekday, last 4 weeks"
PLAN = [("total", True), ("state", True), ("store", True), ("store_category", False), ("store_department", False)]  # (level, also run exponential smoothing)


def score(replay, values, in_window, reference=None):
    r = replay.where(in_window)
    row = {"method": replay.method, "wape": wape(r), "wape_ci95": list(bootstrap_wape(r, n_boot=400)), "wape_days_1_7": wape(r, slice(0, 7)),
           "wape_days_8_28": wape(r, slice(7, 28)), "bias": bias(r)}
    for level in (0.8, 0.9):
        ir = conformal_intervals(replay, values, level=level)
        w = IntervalReplay(r, level, ir.lower[in_window], ir.upper[in_window], ir.scale[in_window])
        row[f"coverage_{int(level * 100)}"] = coverage(w)
        row[f"width_{int(level * 100)}"] = relative_width(w)
        row[f"share_with_range_{int(level * 100)}"] = float(w.available().any(axis=(1, 2)).mean())
    if reference is not None:
        ref = reference.where(in_window)
        per_m = np.abs(r.forecasts - r.actuals).sum(axis=(1, 2))
        per_r = np.abs(ref.forecasts - ref.actuals).sum(axis=(1, 2))
        row["win_rate_vs_reference"] = float((per_m < per_r).mean())
        diff, lo, hi = paired_difference_ci(r, ref, n_boot=400)
        row["gain_vs_reference"], row["gain_ci95"] = diff, [lo, hi]
    return row


def main() -> None:
    t0 = time.perf_counter()
    data = load_m5(RAW)
    events = M5Events(data.calendar)
    origins = make_origins(data.n_days, HORIZON, MIN_TRAIN, STEP)
    in_window = origins >= data.n_days - SCORE_DAYS - 1
    print(f"loaded in {time.perf_counter() - t0:.0f}s; {len(origins)} replay dates, {int(in_window.sum())} in the scoring window", flush=True)
    out = {"setup": {"horizon": HORIZON, "step": STEP, "min_train_days": MIN_TRAIN, "score_days": SCORE_DAYS, "n_replay_dates": int(len(origins)),
                     "n_scored_dates": int(in_window.sum()), "reference": REFERENCE, "hardware": {"processor": platform.processor(), "python": platform.python_version()}}, "levels": {}}
    lines = ["# Models on M5 (generated)", "",
             f"Replay dates every {STEP} days from day {MIN_TRAIN} to the end ({len(origins)} dates); scored on the last {SCORE_DAYS} days ({int(in_window.sum())} dates), each forecasting the next {HORIZON} days. "
             f"Nothing is tuned. Gain is measured against '{REFERENCE}' (the best simple rule): WAPE points saved, with a 95% bootstrap interval over replay dates. "
             "Win rate is the share of replay dates on which the method had less total error than that rule. Coverage is the share of days whose actual sales fell inside the range "
             "(the target is 0.80 and 0.90); width is the average range width divided by average sales. US retail data only.", ""]
    artifact_dir = ROOT / "artifacts" / "replays"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for level, with_ets in PLAN:
        d = at_level(data, level)
        replays, seconds = {}, {}
        methods = list(BASELINES)
        if with_ets:
            methods.append(ExponentialSmoothingForecaster())
        methods.append(GlobalLightGBM(calendars=[events], name="gradient boosting"))
        for f in methods:
            t1 = time.perf_counter()
            replays[f.name] = run_replay(d, f, HORIZON, origins)
            seconds[f.name] = time.perf_counter() - t1
            print(f"  {level}: {f.name} done in {seconds[f.name]:.0f}s (wape {wape(replays[f.name].where(in_window)):.3f})", flush=True)
        sel = select_online(replays, default=REFERENCE, window=8)
        replays[sel.replay.method] = sel.replay
        reference = replays[REFERENCE]
        rows = [{**score(r, d.values, in_window, reference), "seconds": seconds.get(name)} for name, r in replays.items()]
        chosen = np.array(sel.chosen)[in_window]
        share = {m: float((chosen == m).mean()) for m in sorted(set(chosen))}
        out["levels"][level] = {"n_series": d.n_series, "methods": rows, "selection_share": share}
        for name, r in replays.items():
            np.savez_compressed(artifact_dir / f"{level}__{name.replace(' ', '_').replace(',', '')}.npz", origins=r.origins, forecasts=r.forecasts.astype(np.float32), actuals=r.actuals.astype(np.float32))
        lines += [f"## {level} ({d.n_series} series)", "", "| Method | WAPE | Gain vs rule (95% interval) | Win rate | Bias | 80% range: coverage / width | 90% range: coverage / width |", "|---|---|---|---|---|---|---|"]
        for x in sorted(rows, key=lambda x: x["wape"]):
            lines.append(f"| {x['method']} | {x['wape']:.3f} | {x['gain_vs_reference']:+.3f} ({x['gain_ci95'][0]:+.3f} to {x['gain_ci95'][1]:+.3f}) | {x['win_rate_vs_reference']:.0%} | {x['bias']:+.3f} | "
                         f"{x['coverage_80']:.2f} / {x['width_80']:.2f} | {x['coverage_90']:.2f} / {x['width_90']:.2f} |")
        lines += ["", "Which method 'best so far' chose over the scored dates: " + ", ".join(f"{m} {s:.0%}" for m, s in sorted(share.items(), key=lambda kv: -kv[1])) + ".", ""]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (ROOT / "experiments" / "runs" / f"models-m5-{stamp}.json").write_text(json.dumps(out, indent=2))
    (ROOT / "reports" / "models_m5.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report written; total {time.perf_counter() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
