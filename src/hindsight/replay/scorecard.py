"""One row of honest numbers per method: accuracy, gain over a reference rule, win rate, bias, and whether the ranges held."""
import numpy as np

from hindsight.replay.engine import Replay
from hindsight.replay.intervals import IntervalReplay, conformal_intervals, coverage, relative_width
from hindsight.replay.metrics import bias, bootstrap_wape, paired_difference_ci, wape


def score(replay: Replay, values: np.ndarray, in_window: np.ndarray, reference: Replay | None = None, n_boot: int = 400, levels: tuple[float, ...] = (0.8, 0.9),
          ranges: dict[float, IntervalReplay] | None = None) -> dict:
    """Scorecard row for `replay` over the replay dates where `in_window` is true. Ranges are built on the full replay (using only what was
    known at each date) and then judged inside the window; pass `ranges` (level -> ranges for this same replay) to reuse ones already built.
    `reference` adds gain, win rate and a paired interval against that replay."""
    r = replay.where(in_window)
    row = {"method": replay.method, "wape": wape(r), "wape_ci95": list(bootstrap_wape(r, n_boot=n_boot)), "wape_days_1_7": wape(r, slice(0, 7)),
           "wape_days_8_28": wape(r, slice(7, 28)) if r.horizon > 7 else None, "bias": bias(r)}
    for level in levels:
        ir = ranges[level] if ranges and level in ranges else conformal_intervals(replay, values, level=level)
        w = IntervalReplay(r, level, ir.lower[in_window], ir.upper[in_window], ir.scale[in_window])
        key = int(round(level * 100))
        row[f"coverage_{key}"] = coverage(w)
        row[f"width_{key}"] = relative_width(w)
        row[f"share_with_range_{key}"] = float(w.available().any(axis=(1, 2)).mean())
    if reference is not None:
        ref = reference.where(in_window)
        per_m = np.abs(r.forecasts - r.actuals).sum(axis=(1, 2))
        per_r = np.abs(ref.forecasts - ref.actuals).sum(axis=(1, 2))
        row["win_rate_vs_reference"] = float((per_m < per_r).mean())
        diff, lo, hi = paired_difference_ci(r, ref, n_boot=n_boot)
        row["gain_vs_reference"], row["gain_ci95"] = diff, [lo, hi]
    return row
