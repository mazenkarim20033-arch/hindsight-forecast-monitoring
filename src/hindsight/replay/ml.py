"""A global gradient-boosted forecaster.

One LightGBM model learns from every series at once. For each (series, forecast date, days ahead) it sees only numbers
computed from the days up to the forecast date, plus the calendar of the day being predicted (holidays are known in advance).
It predicts the target as a ratio of the series' recent level, so large and small series share one model.

The model is retrained as the replay moves forward (every `refit_every` days), always on rows whose outcome was already known."""
from typing import Callable

import lightgbm as lgb
import numpy as np
import pandas as pd

from hindsight.calendar_features import basic_calendar
from hindsight.replay.baselines import SeasonalAverage

Calendar = Callable[[pd.DatetimeIndex], pd.DataFrame]
MIN_HISTORY = 90
DEFAULT_PARAMS = dict(n_estimators=250, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1,
                      colsample_bytree=0.8, reg_lambda=1.0, n_jobs=2, verbose=-1, random_state=0)


def origin_features(hist: np.ndarray, horizons: np.ndarray) -> dict[str, np.ndarray]:
    """Features for forecasting `horizons` days (1-based) after the last column of `hist`. Uses nothing but `hist`.
    Returns arrays of shape (n_series, n_horizons) plus the (n_series,) level used to rescale the target."""
    s, n = hist.shape
    level = hist[:, -min(28, n) :].mean(axis=1)
    seasons = max(1, min(4, n // 7))
    cycle = hist[:, n - seasons * 7 :].reshape(s, seasons, 7).mean(axis=1)
    phase = (horizons - 1) % 7
    last_week = hist[:, n - 7 :]
    last7 = last_week.mean(axis=1)
    older = hist[:, max(0, n - 56) : max(1, n - 28)].mean(axis=1) if n >= 56 else level
    denom = (level + 1e-9)[:, None]
    shape = (s, len(horizons))
    feats = {
        "cycle_ratio": cycle[:, phase] / denom,
        "last_week_same_day_ratio": last_week[:, phase] / denom,
        "last7_ratio": np.broadcast_to((last7 / denom[:, 0])[:, None], shape),
        "last_day_ratio": np.broadcast_to((hist[:, -1] / denom[:, 0])[:, None], shape),
        "trend_ratio": np.broadcast_to((level / (older + 1e-9))[:, None], shape),
        "log_level": np.broadcast_to(np.log1p(level)[:, None], shape),
        "horizon": np.broadcast_to(horizons[None, :], shape).astype(float),
    }
    feats["_level"] = level
    return feats


class GlobalLightGBM:
    def __init__(self, calendars: list[Calendar] | None = None, max_horizon: int = 28, refit_every: int = 28, train_days: int = 730, origin_step: int = 7,
                 params: dict | None = None, name: str = "gradient boosting"):
        self.calendars = [basic_calendar, *(calendars or [])]
        self.max_horizon, self.refit_every, self.train_days, self.origin_step = max_horizon, refit_every, train_days, origin_step
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.name = name
        self._model: lgb.LGBMRegressor | None = None
        self._fit_last_day = -10**9  # index of the last day the current model was allowed to see
        self.last_training_target_index = -1  # newest day any training target came from (for tests)
        self._fallback = SeasonalAverage(7, 4)
        self._columns: list[str] = []

    def _calendar_rows(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        return pd.concat([c(dates) for c in self.calendars], axis=1)

    def _frame(self, feats: dict, cal: pd.DataFrame) -> pd.DataFrame:
        s, h = feats["cycle_ratio"].shape
        cols = {k: v.reshape(-1) for k, v in feats.items() if not k.startswith("_")}
        base = pd.DataFrame(cols)
        calendar = pd.DataFrame(np.tile(cal.to_numpy(), (s, 1)), columns=cal.columns)  # same calendar for every series
        return pd.concat([base, calendar], axis=1)

    def _fit(self, history: np.ndarray, dates: pd.DatetimeIndex) -> None:
        n = history.shape[1]
        full_cal = self._calendar_rows(pd.date_range(dates[0], periods=n))
        first = max(MIN_HISTORY - 1, n - 1 - self.train_days)
        frames, targets = [], []
        for t in range(n - 2, first - 1, -self.origin_step):  # origins whose first target is known
            hs = np.arange(1, min(self.max_horizon, n - 1 - t) + 1)
            feats = origin_features(history[:, : t + 1], hs)  # only days up to t
            y = history[:, t + hs]
            level = feats["_level"]
            keep = np.repeat(level > 0, len(hs))
            frames.append(self._frame(feats, full_cal.iloc[t + hs]).loc[keep])
            targets.append((y / (level[:, None] + 1e-9)).reshape(-1)[keep])
            self.last_training_target_index = max(self.last_training_target_index, int(t + hs[-1]))
        X, y = pd.concat(frames, ignore_index=True), np.concatenate(targets)
        self._columns = list(X.columns)
        cats = [c for c in ("dow", "month", "event", "event_type", "hijri_month") if c in X.columns]
        self._model = lgb.LGBMRegressor(**self.params).fit(X, y, categorical_feature=cats)
        self._fit_last_day = n - 1

    def can_model(self, n_days: int, horizon: int) -> bool:
        return n_days >= MIN_HISTORY and horizon <= self.max_horizon

    def _design(self, history: np.ndarray, dates: pd.DatetimeIndex, horizon: int) -> tuple[pd.DataFrame, np.ndarray]:
        """Refit if due, then build the model inputs for the next `horizon` days. Uses only `history`."""
        n = history.shape[1]
        if self._model is None or n - 1 - self._fit_last_day >= self.refit_every:
            self.last_training_target_index = -1
            self._fit(history, dates)
        hs = np.arange(1, horizon + 1)
        feats = origin_features(history, hs)
        target_dates = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=horizon)
        return self._frame(feats, self._calendar_rows(target_dates))[self._columns], feats["_level"]

    def forecast(self, history: np.ndarray, dates: pd.DatetimeIndex, horizon: int) -> np.ndarray:
        if not self.can_model(history.shape[1], horizon):
            return self._fallback.forecast(history, dates, horizon)
        X, level = self._design(history, dates, horizon)
        ratio = self._model.predict(X).reshape(history.shape[0], horizon)
        return np.maximum(ratio, 0) * level[:, None]

    def contributions(self, history: np.ndarray, dates: pd.DatetimeIndex, horizon: int) -> tuple[list[str], np.ndarray, np.ndarray]:
        """Exact per-input contributions (TreeSHAP) to the forecast, in units of sales: (columns, array of shape
        (n_series, horizon, n_columns + 1) whose last slot is the model's typical-day base value, level). Row sums equal the
        unclipped forecast."""
        if not self.can_model(history.shape[1], horizon):
            raise ValueError("not enough history (or too long a horizon) for the boosted model, so there is nothing to explain")
        X, level = self._design(history, dates, horizon)
        raw = self._model.predict(X, pred_contrib=True).reshape(history.shape[0], horizon, -1)
        return list(self._columns), raw * level[:, None, None], level
