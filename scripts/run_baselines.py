"""Replay the four simple baselines on M5 at every aggregation level and report how well each would have done.

Replay: every 7th day over the last 730 days is an origin; at each origin a forecaster sees only earlier days and predicts the next 28.
Nothing here is tuned, and the numbers describe Walmart US data, not Egyptian shops."""
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hindsight.data.m5 import at_level, load_m5
from hindsight.replay.baselines import BASELINES
from hindsight.replay.engine import make_origins, run_replay
from hindsight.replay.metrics import bias, bootstrap_wape, mase, paired_difference_ci, skill, wape

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "extracted"
HORIZON, STEP, MIN_TRAIN, LAST_DAYS = 28, 5, 365, 730  # a step that is not a multiple of 7, so replay dates visit every weekday
LEVELS = [("total", None), ("state", None), ("store", None), ("store_category", None), ("store_department", None), ("item_store", 1000)]
REFERENCE = "same day last week"


def main() -> None:
    t0 = time.perf_counter()
    data = load_m5(RAW)
    print(f"loaded {data.n_series} series x {data.n_days} days in {time.perf_counter() - t0:.0f}s", flush=True)
    origins = make_origins(data.n_days, HORIZON, MIN_TRAIN, STEP, LAST_DAYS)
    out = {"setup": {"horizon": HORIZON, "step": STEP, "min_train_days": MIN_TRAIN, "replay_window_days": LAST_DAYS, "n_origins": int(len(origins)),
                     "first_origin": str(data.dates[origins[0]].date()), "last_origin": str(data.dates[origins[-1]].date()),
                     "origins_per_weekday": {n: int((data.dates[origins].dayofweek == i).sum()) for i, n in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])},
                     "hardware": {"processor": platform.processor(), "python": platform.python_version()}}, "levels": {}}
    per_day = out["setup"]["origins_per_weekday"]
    lines = ["# Baseline replay on M5 (generated)", "",
             f"Every {STEP}th day over the last {LAST_DAYS} days is a replay date ({len(origins)} dates, {out['setup']['first_origin']} to {out['setup']['last_origin']}, "
             f"{min(per_day.values())} to {max(per_day.values())} dates per weekday, so no weekday is favoured); "
             f"at each, a forecaster sees only earlier days and predicts the next {HORIZON}. Nothing is tuned. M5 is US Walmart data. "
             "WAPE = total absolute error / total sales (lower is better); bias > 0 means over-forecasting; MASE < 1 beats the in-sample weekly rule.", ""]
    for level, sample in LEVELS:
        d = at_level(data, level, sample=sample, seed=0)
        zero = float((d.values == 0).mean())
        rows = []
        replays = {}
        for f in BASELINES:
            r = run_replay(d, f, HORIZON, origins)
            replays[f.name] = r
            lo, hi = bootstrap_wape(r, n_boot=500)
            rows.append({"method": f.name, "wape": wape(r), "wape_ci95": [lo, hi], "wape_days_1_7": wape(r, slice(0, 7)), "wape_days_8_28": wape(r, slice(7, 28)),
                         "bias": bias(r), "mase": mase(r, d.values)})
        best = min(rows, key=lambda x: x["wape"])
        ref = replays[REFERENCE]
        comparison = None
        if best["method"] != REFERENCE:
            diff, lo, hi = paired_difference_ci(replays[best["method"]], ref, n_boot=500)
            comparison = {"best": best["method"], "reference": REFERENCE, "wape_gain": diff, "ci95": [lo, hi]}
        out["levels"][level] = {"n_series": d.n_series, "share_zero_days": zero, "methods": rows, "best": best["method"], "best_vs_reference": comparison}
        lines += [f"## {level} ({d.n_series} series{', random sample' if sample else ''}; {zero:.0%} of days have zero sales)", "",
                  "| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |", "|---|---|---|---|---|---|---|"]
        for x in sorted(rows, key=lambda x: x["wape"]):
            lines.append(f"| {x['method']} | {x['wape']:.3f} | {x['wape_ci95'][0]:.3f}-{x['wape_ci95'][1]:.3f} | {x['wape_days_1_7']:.3f} | {x['wape_days_8_28']:.3f} | {x['bias']:+.3f} | {x['mase']:.2f} |")
        lines.append("")
        if comparison:
            lines.append(f"Best: {best['method']}. Against '{REFERENCE}' it removes {comparison['wape_gain']:.3f} of total sales in error (95% interval {comparison['ci95'][0]:.3f} to {comparison['ci95'][1]:.3f}).")
        else:
            lines.append(f"Best: {REFERENCE}, so no other baseline beat the weekly rule at this level.")
        lines.append("")
        print(level, d.n_series, "series; best:", best["method"], f"wape {best['wape']:.3f}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (ROOT / "experiments" / "runs").mkdir(parents=True, exist_ok=True)
    (ROOT / "experiments" / "runs" / f"baselines-m5-{stamp}.json").write_text(json.dumps(out, indent=2))
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "baselines_m5.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("report:", ROOT / "reports" / "baselines_m5.md")


if __name__ == "__main__":
    main()
