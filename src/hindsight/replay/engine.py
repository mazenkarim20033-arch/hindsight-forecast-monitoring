"""The replay engine: stand at a past date, forecast forward using only what was known then, compare with what happened.

An *origin* is the index of the last day the forecaster is allowed to see. The history handed to a forecaster is a
copy of the first origin+1 days, so nothing after the origin can reach it."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from hindsight.data.sales import SalesData
from hindsight.replay.baselines import Forecaster


@dataclass
class Replay:
    method: str
    horizon: int
    origins: np.ndarray  # index of the last visible day for each replay step
    forecasts: np.ndarray  # (n_origins, n_series, horizon)
    actuals: np.ndarray  # (n_origins, n_series, horizon), revealed after the fact
    dates: pd.DatetimeIndex  # all dates of the data
    ids: list[str]

    @property
    def origin_dates(self) -> pd.DatetimeIndex:
        return self.dates[self.origins]

    def where(self, mask: np.ndarray) -> "Replay":
        """The same replay restricted to the replay dates where `mask` is true."""
        return Replay(self.method, self.horizon, self.origins[mask], self.forecasts[mask], self.actuals[mask], self.dates, self.ids)


def make_origins(n_days: int, horizon: int, min_train: int = 365, step: int = 7, last_days: int | None = None) -> np.ndarray:
    """Origins spaced `step` days apart. The last origin leaves exactly `horizon` known days after it; the first leaves
    `min_train` days of history. `last_days` keeps only origins inside the final stretch of the data."""
    if horizon < 1 or step < 1:
        raise ValueError("horizon and step must be at least 1")
    last = n_days - 1 - horizon
    first = min_train - 1
    if last < first:
        raise ValueError(f"not enough days: {n_days} days cannot give {min_train} training days plus a {horizon}-day horizon")
    if last_days is not None:
        first = max(first, n_days - last_days - 1)
    return np.arange(last, first - 1, -step)[::-1]


def run_replay(data: SalesData, forecaster: Forecaster, horizon: int, origins: np.ndarray) -> Replay:
    values = np.asarray(data.values, dtype=float)
    forecasts = np.empty((len(origins), data.n_series, horizon))
    actuals = np.empty_like(forecasts)
    for i, t in enumerate(origins):
        if t + horizon > data.n_days - 1:
            raise ValueError(f"origin {t} has fewer than {horizon} days of actuals after it")
        history = values[:, : t + 1].copy()  # a copy: the forecaster cannot reach the rest of the array
        out = np.asarray(forecaster.forecast(history, data.dates[: t + 1], horizon), dtype=float)
        if out.shape != (data.n_series, horizon):
            raise ValueError(f"{forecaster.name}: expected a forecast of shape {(data.n_series, horizon)}, got {out.shape}")
        if not np.isfinite(out).all():
            raise ValueError(f"{forecaster.name}: forecast contains missing or infinite values")
        forecasts[i] = np.maximum(out, 0.0)  # sales cannot be negative
        actuals[i] = values[:, t + 1 : t + 1 + horizon]
    return Replay(forecaster.name, horizon, np.asarray(origins), forecasts, actuals, data.dates, list(data.ids))
