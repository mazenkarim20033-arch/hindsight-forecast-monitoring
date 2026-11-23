import numpy as np
import pandas as pd
import pytest

from hindsight.data.sales import SalesData
from hindsight.calendar_features import egypt_calendar
from hindsight.replay.engine import make_origins, run_replay
from hindsight.replay.metrics import wape
from hindsight.replay.ml import GlobalLightGBM, MIN_HISTORY, origin_features
from hindsight.replay.baselines import Naive, SeasonalAverage
from hindsight.replay.stats import ExponentialSmoothingForecaster
from conftest import make_dates, make_sales

FAST = dict(n_estimators=40, num_leaves=8, min_child_samples=10)


def weekly_data(n_days=260, n_series=3, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    shape = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])[t % 7]
    base = np.array([50.0, 120.0, 400.0][:n_series])[:, None]
    values = np.maximum(0, base * shape[None, :] * (1 + noise * rng.standard_normal((n_series, n_days))))
    return SalesData(make_dates(n_days), [f"s{i}" for i in range(n_series)], values)


def test_origin_features_by_hand():
    hist = np.tile(np.arange(1.0, 8.0), 8)[None, :]  # 1..7 repeating, 56 days; day 56 is a "7"
    feats = origin_features(hist, np.array([1, 2, 7]))
    assert feats["_level"][0] == pytest.approx(hist[0, -28:].mean())
    assert feats["cycle_ratio"][0].tolist() == pytest.approx([1 / 4, 2 / 4, 7 / 4])  # next days are 1, 2, 7 of the cycle; level is 4
    assert feats["last_week_same_day_ratio"][0].tolist() == pytest.approx([1 / 4, 2 / 4, 7 / 4])
    assert feats["last_day_ratio"][0, 0] == pytest.approx(7 / 4) and feats["horizon"][0].tolist() == [1, 2, 7]


def test_features_use_only_the_history_they_are_given():
    rng = np.random.default_rng(1)
    hist = rng.integers(0, 50, (3, 120)).astype(float)
    a = origin_features(hist[:, :100], np.arange(1, 8))
    b = origin_features(np.hstack([hist[:, :100], hist[:, 100:] * 99]).copy()[:, :100], np.arange(1, 8))
    assert all(np.array_equal(a[k], b[k]) for k in a)


def test_the_boosted_model_learns_a_weekly_pattern_across_series():
    d = weekly_data(noise=0.02)
    r = run_replay(d, GlobalLightGBM(params=FAST), 14, np.array([200, 230]))
    assert wape(r) < 0.06
    assert wape(r) < wape(run_replay(d, Naive(), 14, np.array([200, 230])))


def test_the_model_only_trains_on_outcomes_that_were_already_known():
    d = weekly_data(noise=0.02)
    model = GlobalLightGBM(params=FAST, refit_every=1000)
    t = 180
    model.forecast(d.values[:, : t + 1].copy(), d.dates[: t + 1], 7)
    assert model.last_training_target_index <= t


def test_retraining_happens_as_the_replay_moves_forward():
    d = weekly_data(noise=0.02)
    model = GlobalLightGBM(params=FAST, refit_every=20)
    model.forecast(d.values[:, :161].copy(), d.dates[:161], 7)
    first = model._fit_last_day
    model.forecast(d.values[:, :170].copy(), d.dates[:170], 7)
    assert model._fit_last_day == first  # not due yet
    model.forecast(d.values[:, :190].copy(), d.dates[:190], 7)
    assert model._fit_last_day == 189


@pytest.mark.parametrize("make", [lambda: GlobalLightGBM(params=FAST, refit_every=15), lambda: ExponentialSmoothingForecaster(window=120)], ids=["boosting", "smoothing"])
def test_changing_the_future_does_not_change_earlier_forecasts(make):
    d = weekly_data(noise=0.05, n_days=240)
    t = 190
    tampered = d.values.copy()
    tampered[:, t + 1 :] = tampered[:, t + 1 :] * 40 + 777
    other = SalesData(d.dates, d.ids, tampered)
    origins = np.array([150, 170, t])
    a, b = run_replay(d, make(), 14, origins), run_replay(other, make(), 14, origins)
    assert np.allclose(a.forecasts, b.forecasts)


def test_two_runs_give_identical_forecasts():
    d = weekly_data(noise=0.05)
    origins = np.array([180, 200])
    a, b = run_replay(d, GlobalLightGBM(params=FAST), 14, origins), run_replay(d, GlobalLightGBM(params=FAST), 14, origins)
    assert np.array_equal(a.forecasts, b.forecasts)


def test_short_history_falls_back_to_the_weekly_average():
    d = weekly_data(n_days=120)
    hist, dates = d.values[:, :40].copy(), d.dates[:40]
    assert 40 < MIN_HISTORY
    assert np.array_equal(GlobalLightGBM(params=FAST).forecast(hist, dates, 7), SeasonalAverage(7, 4).forecast(hist, dates, 7))
    assert np.array_equal(GlobalLightGBM(params=FAST, max_horizon=7).forecast(d.values[:, :100].copy(), d.dates[:100], 14),
                          SeasonalAverage(7, 4).forecast(d.values[:, :100].copy(), d.dates[:100], 14))


def test_a_series_that_never_sold_is_forecast_as_zero():
    d = weekly_data(n_days=200)
    values = np.vstack([d.values, np.zeros(200)])
    data = SalesData(d.dates, d.ids + ["dead"], values)
    r = run_replay(data, GlobalLightGBM(params=FAST), 7, np.array([150]))
    assert (r.forecasts[0, -1] == 0).all() and (r.forecasts[0, :-1] > 0).all()


def test_smoothing_follows_a_weekly_pattern_and_survives_awkward_series():
    d = weekly_data(noise=0.02)
    r = run_replay(d, ExponentialSmoothingForecaster(window=120), 14, np.array([200, 230]))
    assert wape(r) < 0.08
    odd = np.vstack([np.zeros(80), np.full(80, 5.0), np.arange(80.0) % 3 == 0])
    out = ExponentialSmoothingForecaster().forecast(odd.astype(float), make_dates(80), 7)
    assert out.shape == (3, 7) and np.isfinite(out).all() and (out >= 0).all() and (out[0] == 0).all()


def test_calendar_features_let_the_model_see_a_built_in_holiday_effect():
    """Synthetic data with a known +60% Ramadan effect. The model must find it when it is given the calendar and not otherwise."""
    dates = pd.date_range("2021-01-01", periods=900)
    cal = egypt_calendar(dates)
    t = np.arange(900)
    weekly = np.array([1.0, 0.9, 0.9, 1.0, 1.2, 1.3, 1.1])[t % 7]
    effect = 1 + 0.6 * cal["ramadan"].to_numpy()
    values = np.vstack([base * weekly * effect for base in (60.0, 150.0, 400.0)])
    data = SalesData(dates, ["a", "b", "c"], values)
    origins = np.array([i for i in range(700, 870, 10)])
    with_cal = run_replay(data, GlobalLightGBM(calendars=[egypt_calendar], params=FAST, refit_every=60, train_days=800), 14, origins)
    without = run_replay(data, GlobalLightGBM(params=FAST, refit_every=60, train_days=800), 14, origins)
    assert wape(with_cal) < wape(without)
