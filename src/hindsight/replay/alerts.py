"""Odd-day alerts: days whose sales fell outside what the forecast had said was plausible.

For each day we take the *latest* forecast made before it (so everything the forecaster knew is already in it) and its range at a
high level, 98% by default. A day outside that range is flagged. If the ranges are honest, about 1 normal day in 50 is flagged
by chance; that false-alarm rate is measured, not assumed (see scripts/run_alerts.py)."""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from hindsight.data.sales import SalesData
from hindsight.replay.intervals import IntervalReplay


def latest_forecast_per_day(ir: IntervalReplay, n_days: int) -> dict[str, np.ndarray]:
    """For each (series, day): the forecast, range and age of the most recent forecast made before that day. NaN where none."""
    r = ir.replay
    s, h = r.forecasts.shape[1], r.horizon
    out = {k: np.full((s, n_days), np.nan) for k in ("expected", "low", "high", "age")}
    for i, o in enumerate(r.origins):  # origins ascend, so later (fresher) forecasts overwrite older ones
        days = o + 1 + np.arange(h)
        ok = days < n_days
        have = ir.available()[i][:, ok]
        for key, src in (("expected", r.forecasts[i]), ("low", ir.lower[i]), ("high", ir.upper[i])):
            cur = out[key][:, days[ok]]
            cur[have] = src[:, ok][have]
            out[key][:, days[ok]] = cur
        age = out["age"][:, days[ok]]
        age[have] = (np.arange(h)[ok] + 1)[None, :].repeat(s, 0)[have]
        out["age"][:, days[ok]] = age
    return out


def find_odd_days(ir: IntervalReplay, values: np.ndarray, labels: pd.Series | None = None) -> pd.DataFrame:
    """One row per flagged (series, day), biggest surprise first. `labels` optionally maps a date to a known event name."""
    r = ir.replay
    f = latest_forecast_per_day(ir, values.shape[1])
    rows = []
    for si in range(values.shape[0]):
        a, lo, hi, ex = values[si], f["low"][si], f["high"][si], f["expected"][si]
        ok = np.isfinite(lo) & np.isfinite(hi)
        for d in np.where(ok & ((a < lo) | (a > hi)))[0]:
            date = r.dates[d]
            up = a[d] > hi[d]
            rows.append({"series": r.ids[si], "date": date, "actual": float(a[d]), "expected": float(ex[d]), "low": float(lo[d]), "high": float(hi[d]),
                         "direction": "higher" if up else "lower", "deviation_pct": float((a[d] - ex[d]) / max(ex[d], 1.0)),
                         "units_outside_range": float(a[d] - hi[d] if up else lo[d] - a[d]), "forecast_age_days": int(f["age"][si, d]),
                         "known_event": (labels.get(date) if labels is not None else None)})
    cols = ["series", "date", "actual", "expected", "low", "high", "direction", "deviation_pct", "units_outside_range", "forecast_age_days", "known_event"]
    df = pd.DataFrame(rows, columns=cols)
    return df.sort_values("units_outside_range", ascending=False, ignore_index=True) if len(df) else df


@dataclass
class Injected:
    series: int
    day: int
    factor: float


def inject_anomalies(data: SalesData, days: np.ndarray, factors: list[float], n: int, seed: int = 0, min_gap: int = 14) -> tuple[SalesData, list[Injected]]:
    """Copy of the data with `n` known one-day changes: a day's sales multiplied by a factor (2.0 is a spike, 0.4 a slump, 0.0 a closure).
    Positions are random among `days`, never within `min_gap` days of each other in the same series. Used only for testing and the lab."""
    rng = np.random.default_rng(seed)
    values = np.array(data.values, dtype=float)
    taken: list[Injected] = []
    tries = 0
    while len(taken) < n and tries < n * 50:
        tries += 1
        s, d, k = int(rng.integers(values.shape[0])), int(rng.choice(days)), float(factors[len(taken) % len(factors)])
        if any(x.series == s and abs(x.day - d) < min_gap for x in taken) or values[s, d] <= 0:
            continue
        taken.append(Injected(s, d, k))
    for x in taken:
        values[x.series, x.day] *= x.factor
    return replace(data, values=values), taken
