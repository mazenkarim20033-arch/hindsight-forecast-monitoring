import numpy as np
import pytest

from hindsight.data.sales import SalesData
from hindsight.replay.baselines import Naive, SeasonalAverage, SeasonalNaive
from hindsight.replay.engine import Replay, make_origins, run_replay
from hindsight.replay.intervals import IntervalReplay, conformal_intervals, coverage, recent_level, relative_width
from hindsight.replay.metrics import wape
from hindsight.replay.select import select_online
from conftest import make_dates, make_sales


def noisy(n_days=700, n_series=3, sigma=0.15, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    base = np.array([80.0, 200.0, 500.0][:n_series])[:, None] * np.array([1, .9, .9, 1, 1.1, 1.5, 1.4])[t % 7][None, :]
    values = np.maximum(0, base * (1 + sigma * rng.standard_normal((n_series, n_days))))
    return SalesData(make_dates(n_days), [f"s{i}" for i in range(n_series)], values)


def test_recent_level_uses_only_days_up_to_each_origin():
    v = np.arange(1.0, 101.0)[None, :]
    lv = recent_level(v, np.array([27, 99]), window=28)
    assert lv[0, 0] == pytest.approx(np.mean(np.arange(1, 29))) and lv[1, 0] == pytest.approx(np.mean(np.arange(73, 101)))


@pytest.mark.parametrize("level", [0.8, 0.9])
def test_ranges_cover_close_to_their_nominal_level_on_stable_data(level):
    d = noisy()
    r = run_replay(d, SeasonalAverage(7, 4), 14, make_origins(700, 14, 120, 3))
    ir = conformal_intervals(r, d.values, level=level)
    late = np.arange(len(r.origins)) > len(r.origins) // 2  # judge coverage once the track record is mature
    cov = coverage(IntervalReplay(r.where(late), level, ir.lower[late], ir.upper[late], ir.scale[late]))
    assert abs(cov - level) < 0.06, cov
    assert 0 < relative_width(ir) < 3


def test_a_higher_level_gives_wider_ranges():
    d = noisy()
    r = run_replay(d, SeasonalAverage(7, 4), 14, make_origins(700, 14, 120, 3))
    assert relative_width(conformal_intervals(r, d.values, 0.9)) > relative_width(conformal_intervals(r, d.values, 0.6))


def test_no_range_until_enough_track_record_exists():
    d = noisy()
    r = run_replay(d, SeasonalAverage(7, 4), 14, make_origins(700, 14, 120, 3))
    ir = conformal_intervals(r, d.values, 0.8, min_residuals=60)
    assert not ir.available()[0].any()  # the very first replay date has no track record
    assert ir.available()[-1].all()
    assert (ir.lower[ir.available()] >= 0).all() and (ir.upper[ir.available()] >= ir.lower[ir.available()]).all()


def test_ranges_never_use_outcomes_that_were_not_yet_known():
    d = noisy()
    horizon = 14
    r = run_replay(d, SeasonalAverage(7, 4), horizon, make_origins(700, horizon, 120, 3))
    i0 = len(r.origins) // 2
    today = r.origins[i0]
    spoiled = np.array(r.actuals)
    for j in range(len(r.origins)):
        for k in range(horizon):
            if r.origins[j] + k + 1 > today:  # this day had not happened yet at origin i0
                spoiled[j, :, k] = 1e6
    r2 = Replay(r.method, r.horizon, r.origins, r.forecasts, spoiled, r.dates, r.ids)
    a, b = conformal_intervals(r, d.values), conformal_intervals(r2, d.values)
    assert np.allclose(a.lower[: i0 + 1], b.lower[: i0 + 1], equal_nan=True) and np.allclose(a.upper[: i0 + 1], b.upper[: i0 + 1], equal_nan=True)


def test_interval_validation():
    d = noisy()
    r = run_replay(d, Naive(), 7, make_origins(700, 7, 120, 5))
    with pytest.raises(ValueError):
        conformal_intervals(r, d.values, level=1.5)


def test_selection_picks_the_method_that_has_been_winning():
    d = noisy(sigma=0.05)
    origins = make_origins(700, 14, 120, 5)
    replays = {"weekly rule": run_replay(d, SeasonalNaive(), 14, origins), "last day": run_replay(d, Naive(), 14, origins)}
    sel = select_online(replays, default="last day", window=8)
    assert sel.chosen[0] == "last day"  # nothing known yet, so the default
    assert set(sel.chosen[10:]) == {"weekly rule"}
    assert wape(sel.replay) < wape(replays["last day"])
    assert sel.replay.forecasts.shape == replays["weekly rule"].forecasts.shape


def test_selection_never_looks_at_unresolved_outcomes():
    d = noisy(sigma=0.05)
    horizon = 14
    origins = make_origins(700, horizon, 120, 5)
    base = {"weekly rule": run_replay(d, SeasonalNaive(), horizon, origins), "last day": run_replay(d, Naive(), horizon, origins)}
    i0 = len(origins) // 2
    today = origins[i0]
    spoiled = {}
    for n, r in base.items():
        a = np.array(r.actuals)
        for j in range(len(origins)):
            for k in range(horizon):
                if origins[j] + k + 1 > today:
                    a[j, :, k] = 5e5 if n == "weekly rule" else 0
        spoiled[n] = Replay(r.method, r.horizon, r.origins, r.forecasts, a, r.dates, r.ids)
    one, two = select_online(base, "last day"), select_online(spoiled, "last day")
    assert one.chosen[: i0 + 1] == two.chosen[: i0 + 1]


def test_selection_requires_matching_replays():
    d = noisy()
    a = run_replay(d, Naive(), 7, make_origins(700, 7, 120, 5))
    b = run_replay(d, Naive(), 7, make_origins(700, 7, 120, 7))
    with pytest.raises(ValueError, match="same dates"):
        select_online({"a": a, "b": b}, "a")
