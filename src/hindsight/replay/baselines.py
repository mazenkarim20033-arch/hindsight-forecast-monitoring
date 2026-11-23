"""Simple forecasters. They are the yardstick every cleverer method has to beat, so they are kept deliberately obvious.

A forecaster receives only the history up to the forecast date (`history`, shape n_series x t) and returns the next
`horizon` days (n_series x horizon). It never sees anything after the date it is forecasting from."""
from typing import Protocol

import numpy as np
import pandas as pd


class Forecaster(Protocol):
    name: str

    def forecast(self, history: np.ndarray, dates: pd.DatetimeIndex, horizon: int) -> np.ndarray: ...


class Naive:
    """Tomorrow looks like today."""

    name = "last day"

    def forecast(self, history, dates, horizon):
        return np.repeat(history[:, -1:], horizon, axis=1)


class SeasonalNaive:
    """Each day looks like the same weekday last week."""

    def __init__(self, period: int = 7):
        self.period = period
        self.name = "same day last week" if period == 7 else f"same day {period} days ago"

    def forecast(self, history, dates, horizon):
        p = min(self.period, history.shape[1])
        cycle = history[:, -p:]
        return cycle[:, np.arange(horizon) % p]


class SeasonalAverage:
    """Each day looks like the average of the same weekday over the last k weeks."""

    def __init__(self, period: int = 7, weeks: int = 4):
        self.period, self.weeks = period, weeks
        self.name = f"average of the same weekday, last {weeks} weeks"

    def forecast(self, history, dates, horizon):
        n = history.shape[1]
        p = min(self.period, n)  # with under a week of history, repeat what exists
        seasons = max(1, min(self.weeks, n // p))
        block = history[:, n - seasons * p :].reshape(history.shape[0], seasons, p)
        cycle = block.mean(axis=1)
        return cycle[:, np.arange(horizon) % p]


class MovingAverage:
    """Every day looks like the recent average."""

    def __init__(self, window: int = 28):
        self.window = window
        self.name = f"average of the last {window} days"

    def forecast(self, history, dates, horizon):
        level = history[:, -min(self.window, history.shape[1]) :].mean(axis=1, keepdims=True)
        return np.repeat(level, horizon, axis=1)


BASELINES: list[Forecaster] = [Naive(), MovingAverage(28), SeasonalNaive(7), SeasonalAverage(7, 4)]
