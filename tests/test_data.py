import numpy as np
import pandas as pd
import pytest

from hindsight.data.m5 import SOURCE_URL, at_level, load_m5
from hindsight.data.sales import DataValidationError, SalesData
from conftest import REAL, make_dates, make_sales, real_data


def test_valid_data_reports_its_shape(sales):
    assert (sales.n_series, sales.n_days) == (4, 120)


@pytest.mark.parametrize("mutate,message", [
    (lambda v: v[:, :-1], "does not match"),
    (lambda v: v - 1000, "negative"),
    (lambda v: np.where(v > 0, np.nan, v), "missing"),
    (lambda v: np.where(v > 0, np.inf, v), "infinite"),
])
def test_bad_values_are_rejected(sales, mutate, message):
    with pytest.raises(DataValidationError, match=message):
        SalesData(sales.dates, sales.ids, mutate(sales.values), sales.meta)


def test_dates_must_be_consecutive_days_and_ordered(sales):
    dates = list(make_dates(121))
    del dates[50]  # a missing day: 120 dates, but one gap
    with pytest.raises(DataValidationError, match="not consecutive"):
        SalesData(pd.DatetimeIndex(dates), sales.ids, sales.values, sales.meta)
    with pytest.raises(DataValidationError, match="increasing"):
        SalesData(sales.dates[::-1], sales.ids, sales.values, sales.meta)


def test_duplicate_ids_and_meta_mismatch_are_rejected(sales):
    with pytest.raises(DataValidationError, match="unique"):
        SalesData(sales.dates, ["a", "a", "b", "c"], sales.values, sales.meta)
    with pytest.raises(DataValidationError, match="one row per series"):
        SalesData(sales.dates, sales.ids, sales.values, sales.meta.iloc[:2])


def test_aggregation_sums_series_and_keeps_labels(sales):
    total = sales.aggregate(None)
    assert total.n_series == 1 and np.allclose(total.values[0], sales.values.sum(axis=0))
    by_store = sales.aggregate(["store"])
    assert by_store.ids == ["A", "B"]
    assert np.allclose(by_store.values[0], sales.values[:2].sum(axis=0)) and np.allclose(by_store.values[1], sales.values[2:].sum(axis=0))
    both = sales.aggregate(["store", "cat"])
    assert both.n_series == 4 and np.allclose(both.values.sum(), sales.values.sum())
    with pytest.raises(DataValidationError, match="unknown columns"):
        sales.aggregate(["colour"])


def test_sampling_is_reproducible_and_a_true_subset(sales):
    a, b = sales.sample(2, seed=3), sales.sample(2, seed=3)
    assert a.ids == b.ids and a.n_series == 2
    for i, name in enumerate(a.ids):
        assert np.array_equal(a.values[i], sales.values[sales.ids.index(name)])
    assert sales.sample(99).n_series == 4


def write_m5(root, days=30):
    cal = pd.DataFrame({"date": make_dates(days, "2015-01-01").strftime("%Y-%m-%d"), "wm_yr_wk": 11500, "weekday": "x", "wday": 1, "month": 1, "year": 2015,
                        "d": [f"d_{i + 1}" for i in range(days)], "event_name_1": [None] * days, "event_type_1": [None] * days,
                        "event_name_2": [None] * days, "event_type_2": [None] * days})
    cal.loc[5, ["event_name_1", "event_type_1"]] = ["Eid al-Fitr", "Religious"]
    cal.to_csv(root / "calendar.csv", index=False)
    rows = []
    for i, (store, dept) in enumerate([("CA_1", "FOODS_1"), ("CA_1", "FOODS_2"), ("TX_1", "FOODS_1")]):
        rows.append({"id": f"ITEM_{i}_{store}_evaluation", "item_id": f"ITEM_{i}", "dept_id": dept, "cat_id": "FOODS", "store_id": store, "state_id": store[:2],
                     **{f"d_{d + 1}": (i + 1) * (d % 5) for d in range(days)}})
    pd.DataFrame(rows).to_csv(root / "sales_train_evaluation.csv", index=False)


def test_m5_loader_on_a_small_file(tmp_path):
    write_m5(tmp_path)
    data = load_m5(tmp_path)
    assert (data.n_series, data.n_days) == (3, 30) and data.dates[0] == pd.Timestamp("2015-01-01")
    assert data.calendar["event_name_1"].iloc[5] == "Eid al-Fitr"
    assert at_level(data, "store").ids == ["CA_1", "TX_1"]
    assert at_level(data, "total").values.shape == (1, 30) and np.isclose(at_level(data, "total").values.sum(), data.values.sum())
    assert at_level(data, "item_store", sample=2).n_series == 2


def test_m5_loader_errors_are_actionable(tmp_path):
    with pytest.raises(FileNotFoundError, match="zenodo"):
        load_m5(tmp_path)
    assert "zenodo.org" in SOURCE_URL
    write_m5(tmp_path, days=30)
    cal = pd.read_csv(tmp_path / "calendar.csv").iloc[:20]
    cal.to_csv(tmp_path / "calendar.csv", index=False)
    with pytest.raises(DataValidationError, match="missing from calendar"):
        load_m5(tmp_path)
    with pytest.raises(ValueError, match="unknown level"):
        at_level(make_sales(), "galaxy")


@real_data
def test_real_m5_files_match_the_published_structure():
    data = load_m5(REAL)
    assert (data.n_series, data.n_days) == (30490, 1941)
    assert str(data.dates[0].date()) == "2011-01-29" and str(data.dates[-1].date()) == "2016-05-22"
    assert data.meta["store_id"].nunique() == 10
    stores = at_level(data, "store")
    assert stores.n_series == 10 and np.isclose(stores.values.sum(), data.values.sum())
    assert at_level(data, "state").n_series == 3 and at_level(data, "store_department").n_series == 70
    assert (data.calendar["event_name_1"] == "Ramadan starts").sum() >= 4
