"""Plain-language reasons for a boosted forecast.

Every input of the model is put into one of a few groups a shop owner can read ("usual weekly pattern", "recent change",
"holidays and events"). The pieces come from exact tree contributions (TreeSHAP), so they add up to the forecast. They
describe what the model leaned on, not what caused sales."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from hindsight.calendar_features import EGYPT_COLUMNS
from hindsight.replay.ml import GlobalLightGBM

BASE = "a typical day at the recent level"
WEEKLY, RECENT, SEASON, EVENTS, OTHER = "usual weekly pattern", "recent change in sales", "time of year", "holidays and events", "how far ahead and how big"
GROUP_OF = {
    "cycle_ratio": WEEKLY, "last_week_same_day_ratio": WEEKLY, "dow": WEEKLY,
    "last7_ratio": RECENT, "last_day_ratio": RECENT, "trend_ratio": RECENT,
    "month": SEASON, "dom": SEASON, "doy_sin": SEASON, "doy_cos": SEASON,
    "horizon": OTHER, "log_level": OTHER,
    **{c: EVENTS for c in EGYPT_COLUMNS}, "event": EVENTS, "event_type": EVENTS, "has_event": EVENTS,
}
GROUPS = [BASE, WEEKLY, RECENT, SEASON, EVENTS, OTHER]


@dataclass
class Explanation:
    ids: list[str]
    dates: pd.DatetimeIndex  # the forecast days
    groups: list[str]
    parts: np.ndarray  # (n_series, horizon, len(groups)) in units of sales; the first group is the typical-day base
    forecast: np.ndarray  # (n_series, horizon), never below zero
    unclipped: np.ndarray  # parts summed; equals forecast except where the model went below zero

    def table(self, series: int | str, day: int) -> list[dict]:
        """Reasons for one series and one forecast day (0-based), the biggest first. Each item says how many units it added."""
        s = self.ids.index(series) if isinstance(series, str) else series
        rows = [{"reason": g, "units": float(self.parts[s, day, i])} for i, g in enumerate(self.groups) if i > 0]
        return [{"reason": BASE, "units": float(self.parts[s, day, 0])}] + sorted(rows, key=lambda r: -abs(r["units"]))


def explain_forecast(model: GlobalLightGBM, history: np.ndarray, dates: pd.DatetimeIndex, horizon: int, ids: list[str] | None = None) -> Explanation:
    """Explain the model's forecast for the `horizon` days after the last day of `history` (which is all it may use)."""
    columns, contrib, _ = model.contributions(history, dates, horizon)
    unknown = [c for c in columns if c not in GROUP_OF]
    if unknown:
        raise ValueError(f"no plain-language group for inputs: {unknown}")
    parts = np.zeros(contrib.shape[:2] + (len(GROUPS),))
    parts[..., 0] = contrib[..., -1]
    for j, c in enumerate(columns):
        parts[..., GROUPS.index(GROUP_OF[c])] += contrib[..., j]
    unclipped = parts.sum(axis=2)
    future = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=horizon)
    return Explanation(ids or [f"series {i}" for i in range(history.shape[0])], future, list(GROUPS), parts, np.maximum(unclipped, 0), unclipped)
