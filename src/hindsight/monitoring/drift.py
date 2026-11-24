"""How far the recent values of a series have moved from an earlier stretch of the same series. Pure functions, no forecasting.

PSI (population stability index) bins the earlier stretch into deciles and compares the share of recent values in each bin. The usual reading in
industry is below 0.10 stable, 0.10 to 0.25 some shift, above 0.25 a large shift; these are conventions, not statistical tests. The
Kolmogorov-Smirnov statistic is the largest gap between the two cumulative distributions and comes with a p-value."""
import numpy as np
from scipy.stats import ks_2samp

MIN_VALUES = 20  # fewer values than this in either stretch and no honest comparison can be made


def psi(reference: np.ndarray, recent: np.ndarray, bins: int = 10, eps: float = 1e-4) -> float | None:
    ref, rec = np.asarray(reference, dtype=float), np.asarray(recent, dtype=float)
    if len(ref) < MIN_VALUES or len(rec) < MIN_VALUES:
        return None
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)[1:-1]))  # ties collapse (many zero days give fewer bins)
    pr = np.bincount(np.searchsorted(edges, ref, side="left"), minlength=len(edges) + 1) / len(ref)
    pc = np.bincount(np.searchsorted(edges, rec, side="left"), minlength=len(edges) + 1) / len(rec)
    pr, pc = np.clip(pr, eps, None), np.clip(pc, eps, None)
    return float(np.sum((pc - pr) * np.log(pc / pr)))


def ks(reference: np.ndarray, recent: np.ndarray) -> tuple[float, float] | None:
    if len(reference) < MIN_VALUES or len(recent) < MIN_VALUES:
        return None
    r = ks_2samp(np.asarray(reference, dtype=float), np.asarray(recent, dtype=float))
    return float(r.statistic), float(r.pvalue)
