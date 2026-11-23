from datetime import date

import numpy as np
import pandas as pd
import pytest

from hindsight.calendar_features import EGYPT_COLUMNS, M5Events, basic_calendar, egypt_calendar, orthodox_easter


def on(df, d):
    return df.loc[pd.Timestamp(d)]


def near(df, col, true_date, within=1):
    """True if the flag is on for the announced date or within a day of it (Umm al-Qura versus local moon sighting)."""
    t = pd.Timestamp(true_date)
    days = [t + pd.Timedelta(days=k) for k in range(-within, within + 1)]
    return any(df.loc[d, col] == 1 for d in days)


def test_orthodox_easter_known_dates():
    assert orthodox_easter(2023) == date(2023, 4, 16)
    assert orthodox_easter(2024) == date(2024, 5, 5)
    assert orthodox_easter(2025) == date(2025, 4, 20)


def test_islamic_and_coptic_events_fall_on_known_dates():
    cal = egypt_calendar(pd.date_range("2023-01-01", "2025-12-31"))
    assert list(cal.columns) == EGYPT_COLUMNS
    assert near(cal, "ramadan", "2023-03-23") and near(cal, "ramadan", "2024-03-11") and near(cal, "ramadan", "2025-03-01")
    assert on(cal, "2023-03-15").ramadan == 0 and on(cal, "2023-04-10").ramadan == 1 and on(cal, "2023-04-25").ramadan == 0
    assert near(cal, "eid_fitr", "2023-04-21") and near(cal, "eid_fitr", "2024-04-10")
    assert near(cal, "eid_adha", "2023-06-28") and near(cal, "eid_adha", "2024-06-16")
    assert on(cal, "2023-04-17").sham_el_nessim == 1 and on(cal, "2024-05-06").sham_el_nessim == 1
    assert on(cal, "2023-01-07").coptic_christmas == 1 and on(cal, "2023-01-08").coptic_christmas == 0
    assert all(on(cal, d).national_holiday == 1 for d in ("2023-01-25", "2023-04-25", "2023-05-01", "2023-07-23", "2023-10-06"))


def test_ramadan_moves_about_eleven_days_earlier_each_year():
    cal = egypt_calendar(pd.date_range("2022-01-01", "2026-12-31"))
    starts = [cal.index[(cal.ramadan == 1) & (cal.ramadan.shift(1, fill_value=0) == 0) & (cal.index.year == y)][0] for y in range(2022, 2027)]
    shifts = [(starts[i].dayofyear - starts[i + 1].dayofyear) % 365 for i in range(4)]
    assert all(9 <= s <= 12 for s in shifts), shifts


def test_distance_features_count_down_to_the_event_and_are_clipped():
    cal = egypt_calendar(pd.date_range("2023-01-01", "2023-12-31"))
    start = cal.index[cal.ramadan == 1][0]
    assert cal.loc[start - pd.Timedelta(days=7), "days_to_ramadan"] == 7
    assert cal.loc[start, "days_to_ramadan"] == 0 and cal.loc[start + pd.Timedelta(days=5), "days_to_ramadan"] == -5
    assert cal["days_to_ramadan"].between(-30, 45).all() and cal["days_to_eid_fitr"].between(-10, 21).all()
    assert cal["ramadan_last10"].sum() == 10 or cal["ramadan_last10"].sum() == 9


def test_features_exist_for_future_dates_without_any_sales_data():
    future = egypt_calendar(pd.date_range("2030-01-01", "2030-12-31"))
    assert not future.isna().any().any()
    run = (future["ramadan"].diff().fillna(0) != 0).cumsum()
    first_run = future["ramadan"].groupby(run).agg(["first", "size"]).query("first == 1")["size"].iloc[0]
    assert first_run in (29, 30)  # a lunar month
    assert future.loc["2030-12-31", "ramadan"] == 1  # Ramadan falls twice in the Gregorian year 2030


def test_basic_calendar_columns():
    b = basic_calendar(pd.date_range("2024-02-26", periods=7))
    assert list(b["dow"]) == [0, 1, 2, 3, 4, 5, 6] and (b["month"].iloc[:4] == 2).all() and b["doy_sin"].between(-1, 1).all()


def test_m5_events_lookup_and_unknown_dates():
    cal = pd.DataFrame({"date": ["2015-01-01", "2015-01-02", "2015-01-03"], "event_name_1": ["NewYear", None, "Eid al-Fitr"],
                        "event_type_1": ["National", None, "Religious"], "event_name_2": [None, None, "Easter"], "event_type_2": [None, None, "Religious"]})
    ev = M5Events(cal)
    out = ev(pd.DatetimeIndex(["2015-01-01", "2015-01-02", "2015-01-03", "2020-01-01"]))
    assert out["has_event"].tolist() == [1, 0, 1, 0] and out["event"].iloc[1] == 0 and out["event"].iloc[0] > 0
    assert out["event_type"].iloc[0] != out["event_type"].iloc[2]
