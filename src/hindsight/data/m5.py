"""Loader for the public M5 (Walmart) data, CC BY 4.0: https://zenodo.org/records/12636070

Daily unit sales per item and store. Used here to prove the method; it is US retail data, not Egyptian."""
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight.data.sales import DataValidationError, SalesData

SOURCE_URL = "https://zenodo.org/records/12636070/files/m5-forecasting-accuracy.zip?download=1"
LEVELS = {
    "total": None,
    "state": ["state_id"],
    "store": ["store_id"],
    "store_category": ["store_id", "cat_id"],
    "store_department": ["store_id", "dept_id"],
    "item_store": "item_store",
}


def _require(root: Path, name: str) -> Path:
    path = root / name
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Download the M5 zip from {SOURCE_URL} and extract it into {root}.")
    return path


def load_m5(root: str | Path, file: str = "sales_train_evaluation.csv") -> SalesData:
    """Every item-store series with its calendar. `sales_train_evaluation.csv` has all 1,941 days of actual sales."""
    root = Path(root)
    head = pd.read_csv(_require(root, file), nrows=0)
    day_cols = [c for c in head.columns if c.startswith("d_")]
    id_cols = [c for c in head.columns if not c.startswith("d_")]
    sales = pd.read_csv(root / file, dtype={**{c: "int16" for c in day_cols}, **{c: "string" for c in id_cols}})
    cal = pd.read_csv(_require(root, "calendar.csv"))
    cal_day = cal.set_index("d")
    missing = [d for d in day_cols if d not in cal_day.index]
    if missing:
        raise DataValidationError(f"{len(missing)} sales days are missing from calendar.csv (first: {missing[0]})")
    cal = cal_day.loc[day_cols].reset_index()
    dates = pd.DatetimeIndex(pd.to_datetime(cal["date"]))
    meta = sales[[c for c in id_cols if c != "id"]].astype(str).reset_index(drop=True)
    return SalesData(
        dates=dates, ids=sales["id"].astype(str).tolist(), values=sales[day_cols].to_numpy(dtype=np.float32), meta=meta,
        calendar=cal[["date", "weekday", "month", "year", "event_name_1", "event_type_1", "event_name_2", "event_type_2"]].copy(), source="M5 (Walmart), CC BY 4.0",
    )


def at_level(data: SalesData, level: str, sample: int | None = None, seed: int = 0) -> SalesData:
    """One of the aggregation levels: total, state, store, store_category, store_department, item_store."""
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; choose one of {sorted(LEVELS)}")
    if level == "item_store":
        return data.sample(sample, seed) if sample else data
    return data.aggregate(LEVELS[level], name=level)
