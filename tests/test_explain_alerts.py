import numpy as np
import pandas as pd
import pytest

from hindsight.calendar_features import egypt_calendar
from hindsight.data.sales import SalesData
from hindsight.replay.alerts import find_odd_days, inject_anomalies, latest_forecast_per_day
from hindsight.replay.baselines import SeasonalAverage
from hindsight.replay.engine import make_origins, run_replay
from hindsight.replay.explain import BASE, EVENTS, GROUPS, WEEKLY, explain_forecast
from hindsight.replay.intervals import conformal_intervals
from hindsight.replay.ml import GlobalLightGBM
from conftest import make_dates

FAST = dict(n_estimators=80, num_leaves=8, min_child_samples=10)


def noisy(n_days=700, n_series=3, sigma=0.15, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    base = np.array([80.0, 200.0, 500.0][:n_series])[:, None] * np.array([1, .9, .9, 1, 1.1, 1.5, 1.4])[t % 7][None, :]
    values = np.maximum(0, base * (1 + sigma * rng.standard_normal((n_series, n_days))))
    return SalesData(make_dates(n_days), [f"s{i}" for i in range(n_series)], values)


def ramadan_data():
    dates = pd.date_range("2021-01-01", periods=900)
    t = np.arange(900)
    weekly = np.array([1.0, 0.9, 0.9, 1.0, 1.2, 1.3, 1.1])[t % 7]
    effect = 1 + 0.6 * egypt_calendar(dates)["ramadan"].to_numpy()
    return SalesData(dates, ["a", "b", "c"], np.vstack([b * weekly * effect for b in (60.0, 150.0, 400.0)]))


def test_the_reasons_add_up_to_the_forecast():
    d = ramadan_data()
    model = GlobalLightGBM(calendars=[egypt_calendar], params=FAST, train_days=600)
    hist, dates = d.values[:, :500].copy(), d.dates[:500]
    exp = explain_forecast(model, hist, dates, 14, d.ids)
    assert exp.groups == GROUPS and exp.parts.shape == (3, 14, len(GROUPS))
    assert np.allclose(exp.parts.sum(axis=2), exp.unclipped)
    assert np.allclose(exp.forecast, model.forecast(hist, dates, 14))
    assert exp.dates[0] == dates[-1] + pd.Timedelta(days=1)


def test_the_holiday_reason_shows_up_in_ramadan_and_not_outside_it():
    """Synthetic data with a built-in +60% Ramadan lift: the 'holidays and events' reason must carry it."""
    d = ramadan_data()
    t = 450  # history ends 26 Mar 2022; Ramadan starts 2 Apr, so forecast days 7-14 are inside it
    model = GlobalLightGBM(calendars=[egypt_calendar], params=FAST, train_days=600)
    exp = explain_forecast(model, d.values[:, : t + 1 - 1].copy(), d.dates[:t], 14, d.ids)
    in_ramadan = egypt_calendar(exp.dates)["ramadan"].to_numpy().astype(bool)
    assert 0 < in_ramadan.sum() < 14
    level = d.values[:, t - 28 : t].mean(axis=1)
    ev = exp.parts[:, :, GROUPS.index(EVENTS)] / level[:, None]
    assert ev[:, in_ramadan].mean() > ev[:, ~in_ramadan].mean() + 0.25
    assert abs(ev[:, ~in_ramadan].mean()) < 0.1


def test_the_weekly_pattern_reason_tells_busy_days_from_quiet_ones():
    d = ramadan_data()
    model = GlobalLightGBM(calendars=[egypt_calendar], params=FAST, train_days=600)
    exp = explain_forecast(model, d.values[:, :300].copy(), d.dates[:300], 14, d.ids)
    weekly = exp.parts[2, :, GROUPS.index(WEEKLY)]
    friday_like = np.argmax(exp.forecast[2] * (np.arange(14) < 7))  # busiest of the first week
    assert weekly[friday_like] > weekly[:7].min()
    row = exp.table("c", friday_like)
    assert row[0]["reason"] == BASE and abs(row[1]["units"]) >= abs(row[-1]["units"])


def test_explaining_with_too_little_history_says_so():
    d = ramadan_data()
    with pytest.raises(ValueError, match="nothing to explain"):
        explain_forecast(GlobalLightGBM(params=FAST), d.values[:, :40].copy(), d.dates[:40], 7)


def replay_with_ranges(d, level=0.98, step=3, min_train=150, horizon=14, seed=None):
    r = run_replay(d, SeasonalAverage(7, 4), horizon, make_origins(d.n_days, horizon, min_train, step))
    return r, conformal_intervals(r, d.values, level=level, min_residuals=200)


def test_the_freshest_forecast_is_used_for_each_day():
    d = noisy(n_days=400)
    r, ir = replay_with_ranges(d)
    f = latest_forecast_per_day(ir, d.n_days)
    seen = np.isfinite(f["expected"][0])
    assert f["age"][0][seen].max() <= 14 and f["age"][0][np.isfinite(f["age"][0])].min() >= 1
    day = r.origins[-6] + 2  # late enough to have ranges; origins are 3 days apart, so a forecast at most 3 days old exists
    assert f["age"][0, day] <= 3


def test_an_injected_spike_and_an_injected_slump_are_flagged_and_normal_days_mostly_are_not():
    d = noisy(n_days=700, sigma=0.1)
    bad, injected = inject_anomalies(d, days=np.arange(400, 650), factors=[3.0, 0.2], n=6, seed=1)
    _, ir = replay_with_ranges(bad)
    flagged = find_odd_days(ir, bad.values)
    hit = {(x.series, x.day) for x in injected}
    got = {(bad.ids.index(r.series), int(np.where(bad.dates == r.date)[0][0])) for r in flagged.itertuples()}
    assert hit <= got, f"missed {hit - got}"
    row = flagged[(flagged.series == bad.ids[injected[0].series]) & (flagged.date == bad.dates[injected[0].day])].iloc[0]
    assert row.direction == ("higher" if injected[0].factor > 1 else "lower")
    covered = np.isfinite(latest_forecast_per_day(ir, bad.n_days)["high"])
    false_alarms = len(got - hit) / covered.sum()
    assert false_alarms < 0.05, false_alarms


def test_alerts_for_a_day_never_depend_on_later_data():
    d = noisy(n_days=500, sigma=0.1)
    day = 420
    later = d.values.copy()
    later[:, day + 1 :] = later[:, day + 1 :] * 9 + 100
    other = SalesData(d.dates, d.ids, later)
    a = find_odd_days(replay_with_ranges(d)[1], d.values)
    b = find_odd_days(replay_with_ranges(other)[1], other.values)
    upto = d.dates[day]
    cols = ["series", "date", "actual", "expected", "low", "high"]
    a, b = a[a.date <= upto][cols], b[b.date <= upto][cols]
    assert a.sort_values(["series", "date"], ignore_index=True).equals(b.sort_values(["series", "date"], ignore_index=True))


def test_injection_changes_exactly_the_chosen_days_and_keeps_them_apart():
    d = noisy(n_days=300)
    out, inj = inject_anomalies(d, days=np.arange(100, 250), factors=[2.0, 0.0], n=8, seed=3, min_gap=14)
    assert len(inj) == 8
    changed = np.argwhere(out.values != d.values)
    assert {tuple(c) for c in changed} == {(x.series, x.day) for x in inj}
    for s in range(3):
        days = sorted(x.day for x in inj if x.series == s)
        assert all(b - a >= 14 for a, b in zip(days, days[1:]))
    assert d.values.min() >= 0 and np.array_equal(d.values, noisy(n_days=300).values)  # the original is untouched
