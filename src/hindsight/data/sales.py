"""The one data shape the whole app works with, whatever the source (M5 today, a shop's Excel file later)."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    pass


@dataclass
class SalesData:
    """Daily sales for several series. `values` is (n_series, n_days) and column j belongs to `dates[j]`."""

    dates: pd.DatetimeIndex
    ids: list[str]
    values: np.ndarray
    meta: pd.DataFrame = field(default_factory=pd.DataFrame)  # one row per series (store, category, ...)
    calendar: pd.DataFrame = field(default_factory=pd.DataFrame)  # one row per date (events, ...)
    source: str = ""

    def __post_init__(self) -> None:
        self.validate()

    @property
    def n_series(self) -> int:
        return self.values.shape[0]

    @property
    def n_days(self) -> int:
        return self.values.shape[1]

    def validate(self) -> None:
        if self.values.ndim != 2:
            raise DataValidationError("values must be a 2-D array (series x days)")
        if self.values.shape != (len(self.ids), len(self.dates)):
            raise DataValidationError(f"values shape {self.values.shape} does not match {len(self.ids)} ids and {len(self.dates)} dates")
        if len(set(self.ids)) != len(self.ids):
            raise DataValidationError("series ids must be unique")
        if len(self.dates) < 2:
            raise DataValidationError("need at least two days")
        if not self.dates.is_monotonic_increasing:
            raise DataValidationError("dates must be in increasing order")
        gaps = np.diff(self.dates.values).astype("timedelta64[D]").astype(int)
        if (gaps != 1).any():
            first = int(np.where(gaps != 1)[0][0])
            raise DataValidationError(f"dates are not consecutive days (gap after {self.dates[first].date()}); fill or aggregate the missing days first")
        v = np.asarray(self.values, dtype=float)
        if np.isnan(v).any():
            raise DataValidationError("sales contain missing values")
        if not np.isfinite(v).all():
            raise DataValidationError("sales contain infinite values")
        if (v < 0).any():
            raise DataValidationError("sales contain negative values (returns must be netted out before forecasting)")
        if len(self.meta) and len(self.meta) != len(self.ids):
            raise DataValidationError("meta must have one row per series")
        if len(self.calendar) and len(self.calendar) != len(self.dates):
            raise DataValidationError("calendar must have one row per date")

    def aggregate(self, by: list[str] | None, name: str = "total") -> "SalesData":
        """Sum series that share the same value(s) of the `meta` columns in `by`; `by=None` sums everything."""
        if by is None:
            return SalesData(self.dates, [name], self.values.sum(axis=0, keepdims=True), pd.DataFrame(), self.calendar, self.source)
        missing = [c for c in by if c not in self.meta.columns]
        if missing:
            raise DataValidationError(f"cannot aggregate by unknown columns {missing}")
        keys = self.meta[by].astype(str).agg("|".join, axis=1).to_numpy()
        order = list(dict.fromkeys(keys))
        out = np.zeros((len(order), self.n_days))
        for i, k in enumerate(order):
            out[i] = self.values[keys == k].sum(axis=0)
        meta = self.meta.drop_duplicates(subset=by)[by].reset_index(drop=True) if len(self.meta) else pd.DataFrame()
        meta = meta.set_index(pd.Index(order)).loc[order].reset_index(drop=True)
        return SalesData(self.dates, order, out, meta, self.calendar, self.source)

    def sample(self, n: int, seed: int = 0) -> "SalesData":
        """A reproducible random subset of series (used to keep the heavy item-level level fast)."""
        n = min(n, self.n_series)
        idx = np.sort(np.random.default_rng(seed).choice(self.n_series, size=n, replace=False))
        meta = self.meta.iloc[idx].reset_index(drop=True) if len(self.meta) else self.meta
        return SalesData(self.dates, [self.ids[i] for i in idx], self.values[idx], meta, self.calendar, self.source)
