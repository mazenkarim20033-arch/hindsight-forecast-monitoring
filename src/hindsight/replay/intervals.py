"""Honest ranges around a forecast, learned from the forecaster's own track record.

At each replay date the range is built from the errors the same method made on *earlier* replay dates whose outcomes were
already known by then. Errors are measured relative to the series' recent level so that big and small series can share them.
This is conformal prediction applied to a rolling track record; it is calibrated on average, not guaranteed for every day."""
from dataclasses import dataclass

import numpy as np

from hindsight.replay.engine import Replay


@dataclass
class IntervalReplay:
    replay: Replay
    level: float
    lower: np.ndarray  # (n_origins, n_series, horizon); NaN where there was not enough track record yet
    upper: np.ndarray
    scale: np.ndarray  # (n_origins, n_series) recent level used to scale errors

    def hits(self) -> np.ndarray:
        """True where the actual sales landed inside the range (NaN-free only where a range exists)."""
        a = self.replay.actuals
        return (a >= self.lower) & (a <= self.upper)

    def available(self) -> np.ndarray:
        return np.isfinite(self.lower) & np.isfinite(self.upper)


def recent_level(values: np.ndarray, origins: np.ndarray, window: int = 28) -> np.ndarray:
    """Mean of the last `window` days up to and including each origin: shape (n_origins, n_series)."""
    return np.stack([values[:, max(0, t - window + 1) : t + 1].mean(axis=1) for t in origins])


def conformal_intervals(replay: Replay, values: np.ndarray, level: float = 0.8, bucket: int = 7, max_residuals: int = 4000, min_residuals: int = 60) -> IntervalReplay:
    """Range with nominal coverage `level` for every replay date, using only outcomes known by that date."""
    if not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    o, s, h = replay.forecasts.shape
    scale = recent_level(np.asarray(values, dtype=float), replay.origins)
    usable = scale > 0
    rel = np.full((o, s, h), np.nan)
    for i in range(o):
        ok = usable[i]
        rel[i, ok] = (replay.actuals[i, ok] - replay.forecasts[i, ok]) / scale[i, ok][:, None]
    lower = np.full((o, s, h), np.nan)
    upper = np.full((o, s, h), np.nan)
    a = (1 - level) / 2
    for b in range((h + bucket - 1) // bucket):
        ks = np.arange(b * bucket, min(h, (b + 1) * bucket))
        newest_day = int(ks[-1]) + 1  # a replay date's whole bucket must be resolved before its errors count
        for i in range(o):
            known = np.where(replay.origins + newest_day <= replay.origins[i])[0]
            if len(known) == 0:
                continue
            pool = rel[known][:, :, ks].reshape(-1)
            pool = pool[np.isfinite(pool)][-max_residuals:]
            if len(pool) < min_residuals:
                continue
            q_lo, q_hi = np.quantile(pool, [a, 1 - a], method="higher")
            lower[i][:, ks] = np.maximum(replay.forecasts[i][:, ks] + q_lo * scale[i][:, None], 0)
            upper[i][:, ks] = replay.forecasts[i][:, ks] + q_hi * scale[i][:, None]
    return IntervalReplay(replay, level, lower, upper, scale)


def coverage(ir: IntervalReplay, days: slice | None = None) -> float:
    """Share of (date, series, day) cases where the actual fell inside the range, over cases that have a range."""
    ok, hit = ir.available(), ir.hits()
    if days is not None:
        ok, hit = ok[..., days], hit[..., days]
    return float(hit[ok].mean()) if ok.any() else float("nan")


def relative_width(ir: IntervalReplay, days: slice | None = None) -> float:
    """Average range width divided by average actual sales (smaller is sharper)."""
    ok = ir.available()
    w = (ir.upper - ir.lower)
    a = ir.replay.actuals
    if days is not None:
        ok, w, a = ok[..., days], w[..., days], a[..., days]
    return float(w[ok].mean() / a[ok].mean()) if ok.any() and a[ok].mean() > 0 else float("nan")
