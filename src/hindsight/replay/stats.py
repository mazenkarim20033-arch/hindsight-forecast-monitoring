"""A classic statistical forecaster: Holt-Winters exponential smoothing with a damped trend and a weekly cycle."""
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from hindsight.replay.baselines import SeasonalAverage


class ExponentialSmoothingForecaster:
    """Fits each series on its most recent `window` days every time it is asked, so it only uses the visible history."""

    def __init__(self, window: int = 364, name: str = "exponential smoothing"):
        self.window, self.name = window, name
        self._fallback = SeasonalAverage(7, 4)

    def forecast(self, history: np.ndarray, dates: pd.DatetimeIndex, horizon: int) -> np.ndarray:
        s, n = history.shape
        backup = self._fallback.forecast(history, dates, horizon)
        if n < 28:
            return backup
        out = backup.copy()
        for i in range(s):
            y = history[i, -self.window :]
            if y.max() <= 0:
                continue
            seasonal = "mul" if y.min() > 0 else "add"
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal=seasonal, seasonal_periods=7, initialization_method="heuristic").fit()
                pred = np.asarray(fit.forecast(horizon), dtype=float)
                if np.isfinite(pred).all():
                    out[i] = np.maximum(pred, 0)
            except Exception:  # a failed fit falls back to the weekly average rather than breaking the replay
                continue
        return out
