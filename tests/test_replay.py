import numpy as np
import pandas as pd
import pytest

from hindsight.data.sales import SalesData
from hindsight.replay.baselines import BASELINES, MovingAverage, Naive, SeasonalAverage, SeasonalNaive
from hindsight.replay.engine import make_origins, run_replay
from hindsight.replay.metrics import bias, bootstrap_wape, mae, mase, mase_per_series, paired_difference_ci, rmse, skill, wape
from conftest import make_dates, make_sales


def one(values, **kw):
    v = np.asarray([values], dtype=float)
    return SalesData(make_dates(v.shape[1]), ["s"], v, **kw)


def hist(rows):
    return np.asarray(rows, dtype=float)


def test_baselines_by_hand():
    h = hist([list(range(1, 15))])  # 1..14, two full weeks
    d = make_dates(14)
    assert Naive().forecast(h, d, 3).tolist() == [[14, 14, 14]]
    assert SeasonalNaive().forecast(h, d, 9).tolist() == [[8, 9, 10, 11, 12, 13, 14, 8, 9]]
    avg = SeasonalAverage(7, 2).forecast(h, d, 3)  # mean of (1,8), (2,9), (3,10)
    assert avg.tolist() == [[4.5, 5.5, 6.5]]
    assert MovingAverage(4).forecast(h, d, 2).tolist() == [[12.5, 12.5]]


def test_baselines_cope_with_short_histories():
    h = hist([[5, 6, 7]])
    d = make_dates(3)
    for f in BASELINES:
        out = f.forecast(h, d, 10)
        assert out.shape == (1, 10) and np.isfinite(out).all()
    assert SeasonalNaive().forecast(h, d, 4).tolist() == [[5, 6, 7, 5]]


def test_baselines_handle_several_series_independently():
    h = hist([[1, 1, 1, 1, 1, 1, 9], [2, 2, 2, 2, 2, 2, 2]])
    out = SeasonalNaive().forecast(h, make_dates(7), 2)
    assert out.tolist() == [[1, 1], [2, 2]]


def test_origins_spacing_and_bounds():
    o = make_origins(n_days=200, horizon=28, min_train=100, step=7)
    assert o[-1] == 200 - 1 - 28 and o[0] >= 99 and set(np.diff(o)) == {7}
    last = make_origins(200, 28, min_train=100, step=7, last_days=60)
    assert last[0] >= 200 - 60 - 1 and last[-1] == o[-1]
    with pytest.raises(ValueError, match="not enough days"):
        make_origins(100, 28, min_train=90)
    with pytest.raises(ValueError):
        make_origins(100, 0)


def test_a_step_that_is_not_a_multiple_of_seven_visits_every_weekday():
    dates = make_dates(800)
    same_day = dates[make_origins(800, 28, 365, 7)].dayofweek
    varied = dates[make_origins(800, 28, 365, 5)].dayofweek
    assert len(set(same_day)) == 1  # the trap: weekly steps always land on one weekday
    assert set(varied) == set(range(7))
    counts = np.bincount(varied, minlength=7)
    assert counts.min() >= counts.max() - 1


def test_replay_aligns_forecasts_with_what_happened_next(sales):
    origins = np.array([60, 80])
    r = run_replay(sales, Naive(), horizon=5, origins=origins)
    assert r.forecasts.shape == r.actuals.shape == (2, 4, 5)
    assert np.array_equal(r.actuals[0, :, 0], sales.values[:, 61]) and np.array_equal(r.actuals[1, :, 4], sales.values[:, 85])
    assert np.array_equal(r.forecasts[0, :, 3], sales.values[:, 60])
    assert list(r.origin_dates) == [sales.dates[60], sales.dates[80]]


def test_replay_rejects_origins_without_enough_future_and_bad_forecasters(sales):
    with pytest.raises(ValueError, match="fewer than"):
        run_replay(sales, Naive(), 10, np.array([115]))

    class Wrong:
        name = "wrong"

        def forecast(self, history, dates, horizon):
            return np.zeros((1, horizon))

    class Broken:
        name = "broken"

        def forecast(self, history, dates, horizon):
            return np.full((history.shape[0], horizon), np.nan)

    with pytest.raises(ValueError, match="expected a forecast of shape"):
        run_replay(sales, Wrong(), 3, np.array([50]))
    with pytest.raises(ValueError, match="missing or infinite"):
        run_replay(sales, Broken(), 3, np.array([50]))


def test_negative_forecasts_are_clipped_to_zero(sales):
    class Down:
        name = "down"

        def forecast(self, history, dates, horizon):
            return np.full((history.shape[0], horizon), -5.0)

    assert (run_replay(sales, Down(), 3, np.array([50])).forecasts == 0).all()


def test_forecaster_only_ever_sees_the_past(sales):
    seen = []

    class Spy:
        name = "spy"

        def forecast(self, history, dates, horizon):
            seen.append((history.shape[1], len(dates), history.base is None, dates[-1]))
            return np.zeros((history.shape[0], horizon))

    origins = np.array([40, 70, 100])
    run_replay(sales, Spy(), 7, origins)
    for (n_hist, n_dates, no_base, last_date), t in zip(seen, origins):
        assert n_hist == n_dates == t + 1 and no_base and last_date == sales.dates[t]


@pytest.mark.parametrize("forecaster", BASELINES, ids=lambda f: f.name)
def test_changing_the_future_does_not_change_earlier_forecasts(sales, forecaster):
    t = 70
    tampered = sales.values.copy()
    tampered[:, t + 1 :] = tampered[:, t + 1 :] * 50 + 999
    other = SalesData(sales.dates, sales.ids, tampered, sales.meta)
    origins = np.array([30, 50, t])
    a, b = run_replay(sales, forecaster, 14, origins), run_replay(other, forecaster, 14, origins)
    assert np.array_equal(a.forecasts, b.forecasts)
    assert not np.array_equal(a.actuals, b.actuals)  # the tampering only changes what is revealed afterwards


def test_a_weekly_pattern_is_forecast_perfectly_by_the_weekly_rule():
    t = np.arange(70)
    pattern = np.array([5, 6, 7, 8, 9, 20, 18])[t % 7]
    r = run_replay(one(pattern), SeasonalNaive(), 14, np.array([30, 40]))
    assert wape(r) == 0 and mae(r) == 0 and rmse(r) == 0 and bias(r) == 0


def test_metrics_by_hand():
    r = run_replay(one(np.arange(1, 31)), Naive(), horizon=3, origins=np.array([19]))
    # forecast 20,20,20; actual 21,22,23
    assert wape(r) == pytest.approx(6 / 66) and mae(r) == pytest.approx(2.0) and rmse(r) == pytest.approx(np.sqrt((1 + 4 + 9) / 3))
    assert bias(r) == pytest.approx(-6 / 66)
    assert wape(r, days=slice(0, 1)) == pytest.approx(1 / 21)
    assert skill(0.5, 1.0) == 0.5 and skill(1.5, 1.0) == -0.5 and np.isnan(skill(1.0, 0.0))


def test_wape_and_bias_are_undefined_when_nothing_sold():
    r = run_replay(one(np.zeros(40)), Naive(), 3, np.array([20]))
    assert np.isnan(wape(r)) and np.isnan(bias(r)) and mae(r) == 0


def test_mase_scales_by_the_weekly_rule_and_ignores_flat_series():
    # a series that rises by 1 each day: the weekly rule is off by 7 every time, so the scale is 7
    r = run_replay(one(np.arange(1, 61)), Naive(), horizon=1, origins=np.array([40]))
    assert mase_per_series(r, np.arange(1, 61)[None, :], 7)[0] == pytest.approx(1 / 7)
    flat = run_replay(one(np.full(60, 3.0)), Naive(), 1, np.array([40]))
    assert np.isnan(mase_per_series(flat, np.full((1, 60), 3.0), 7)[0]) and np.isnan(mase(flat, np.full((1, 60), 3.0)))


def test_bootstrap_interval_contains_the_estimate_and_is_reproducible(sales):
    r = run_replay(sales, Naive(), 7, make_origins(120, 7, 40, 3))
    lo, hi = bootstrap_wape(r, n_boot=300, seed=1)
    assert lo <= wape(r) <= hi and (lo, hi) == bootstrap_wape(r, n_boot=300, seed=1)


def test_paired_difference_favours_the_better_method(sales):
    origins = make_origins(120, 7, 40, 3)
    good, bad = run_replay(sales, SeasonalNaive(), 7, origins), run_replay(sales, Naive(), 7, origins)
    diff, lo, hi = paired_difference_ci(good, bad, n_boot=300)
    assert diff > 0 and lo > 0 and lo <= diff <= hi
    d2, lo2, hi2 = paired_difference_ci(bad, good, n_boot=300)
    assert d2 < 0 and hi2 < 0
    with pytest.raises(ValueError, match="same origins"):
        paired_difference_ci(good, run_replay(sales, Naive(), 7, origins[:-1]))
