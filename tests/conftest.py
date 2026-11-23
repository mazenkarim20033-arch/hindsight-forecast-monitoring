"""Synthetic fixtures are for unit-testing code paths only; they are never used for results."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hindsight.data.sales import SalesData

REAL = Path(__file__).resolve().parents[1] / "data" / "raw" / "extracted"
real_data = pytest.mark.skipif(not (REAL / "sales_train_evaluation.csv").exists(), reason="M5 files not present")


def make_dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def make_sales(n_series: int = 4, n_days: int = 120, seed: int = 0, weekly: bool = True) -> SalesData:
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    base = 20 + 5 * np.arange(n_series)[:, None]
    season = (np.array([1.0, 0.9, 0.95, 1.0, 1.1, 1.4, 1.3])[t % 7] if weekly else np.ones(n_days))[None, :]
    values = np.maximum(0, np.round(base * season + rng.normal(0, 1.5, (n_series, n_days))))
    meta = pd.DataFrame({"store": ["A", "A", "B", "B"][:n_series], "cat": ["x", "y", "x", "y"][:n_series]})
    return SalesData(make_dates(n_days), [f"s{i}" for i in range(n_series)], values, meta)


@pytest.fixture
def sales() -> SalesData:
    return make_sales()
