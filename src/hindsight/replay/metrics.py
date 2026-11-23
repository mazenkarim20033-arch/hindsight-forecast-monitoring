"""Accuracy measures that stay meaningful when many days have zero sales.

WAPE (total absolute error divided by total sales) is the headline: it is volume-weighted and defined whenever anything
sold. MASE compares with the in-sample same-weekday rule. Relative bias shows systematic over- or under-forecasting."""
import numpy as np

from hindsight.replay.engine import Replay


def _sl(arr: np.ndarray, days: slice | None) -> np.ndarray:
    return arr if days is None else arr[..., days]


def wape(replay: Replay, days: slice | None = None) -> float:
    f, a = _sl(replay.forecasts, days), _sl(replay.actuals, days)
    total = a.sum()
    return float(np.abs(f - a).sum() / total) if total > 0 else float("nan")


def bias(replay: Replay, days: slice | None = None) -> float:
    """(forecast - actual) / actual, summed: positive means over-forecasting."""
    f, a = _sl(replay.forecasts, days), _sl(replay.actuals, days)
    total = a.sum()
    return float((f - a).sum() / total) if total > 0 else float("nan")


def mae(replay: Replay, days: slice | None = None) -> float:
    return float(np.abs(_sl(replay.forecasts, days) - _sl(replay.actuals, days)).mean())


def rmse(replay: Replay, days: slice | None = None) -> float:
    return float(np.sqrt(((_sl(replay.forecasts, days) - _sl(replay.actuals, days)) ** 2).mean()))


def mase_per_series(replay: Replay, values: np.ndarray, period: int = 7, days: slice | None = None) -> np.ndarray:
    """Mean absolute error over the scale of the in-sample same-weekday rule, using only days before the first origin."""
    first = int(replay.origins[0])
    train = np.asarray(values, dtype=float)[:, : first + 1]
    scale = np.abs(train[:, period:] - train[:, :-period]).mean(axis=1)
    err = np.abs(_sl(replay.forecasts, days) - _sl(replay.actuals, days)).mean(axis=(0, 2))
    out = np.full(err.shape, np.nan)
    ok = scale > 0
    out[ok] = err[ok] / scale[ok]
    return out


def mase(replay: Replay, values: np.ndarray, period: int = 7, days: slice | None = None) -> float:
    """Median over series with a defined scale."""
    m = mase_per_series(replay, values, period, days)
    return float(np.nanmedian(m)) if np.isfinite(m).any() else float("nan")


def skill(model_error: float, baseline_error: float) -> float:
    """Share of the baseline's error removed (positive: better than the baseline, negative: worse)."""
    return float(1 - model_error / baseline_error) if baseline_error > 0 else float("nan")


def bootstrap_wape(replay: Replay, days: slice | None = None, n_boot: int = 1000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile interval for WAPE by resampling replay dates. Neighbouring dates overlap in what they forecast,
    so treat the interval as indicative."""
    f, a = _sl(replay.forecasts, days), _sl(replay.actuals, days)
    err = np.abs(f - a).sum(axis=(1, 2))
    tot = a.sum(axis=(1, 2))
    rng = np.random.default_rng(seed)
    n = len(err)
    stats = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        t = tot[idx].sum()
        stats.append(err[idx].sum() / t if t > 0 else np.nan)
    lo, hi = np.nanquantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def paired_difference_ci(model: Replay, baseline: Replay, days: slice | None = None, n_boot: int = 1000, seed: int = 0) -> tuple[float, float, float]:
    """WAPE(baseline) - WAPE(model) with a bootstrap interval over replay dates; an interval above zero means the model
    beat the baseline on those dates. Both replays must cover the same origins."""
    if not np.array_equal(model.origins, baseline.origins):
        raise ValueError("replays must use the same origins")
    a = _sl(model.actuals, days)
    em = np.abs(_sl(model.forecasts, days) - a).sum(axis=(1, 2))
    eb = np.abs(_sl(baseline.forecasts, days) - a).sum(axis=(1, 2))
    tot = a.sum(axis=(1, 2))
    rng = np.random.default_rng(seed)
    n = len(em)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        t = tot[idx].sum()
        diffs.append((eb[idx].sum() - em[idx].sum()) / t if t > 0 else np.nan)
    lo, hi = np.nanquantile(diffs, [0.025, 0.975])
    return float((eb.sum() - em.sum()) / tot.sum()), float(lo), float(hi)
