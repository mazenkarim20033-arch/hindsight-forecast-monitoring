"""The rules that turn measurements into a health status. A signal fires only when it is past a fixed limit and also unusual for that item. Every threshold is here, visible and overridable. They are conventional round numbers, not fitted. One was revised after a first look at
stable synthetic data: "worse than the simple rule" first flagged at 1.00, which is noise when the method and the rule are near-identical, so it
now flags at 1.10 (watch) and 1.30 (action). reports/health_m5.md and tests/test_health.py show how often the rules fire.

The principle: *the data changing is not a failure; the forecast failing is.* The status comes from error-based signals only (accuracy,
systematic bias, ranges that stop holding, being worse than the simple rule). Demand drift (PSI, KS) is measured and shown, but does not
change the status: a forecaster can follow a level shift perfectly well, and on the M5 sample the conventional PSI limits flag almost every
store because sales grow, whether or not the forecast suffers."""
from dataclasses import asdict, dataclass

import numpy as np

ORDER = {"unknown": 0, "healthy": 1, "watch": 2, "action": 3}


@dataclass(frozen=True)
class Thresholds:
    recent_origins: int = 8  # how many of the latest replay dates count as "recent"
    min_history_origins: int = 20  # earlier replay dates needed before any comparison is made
    history_origins: int = 150  # at most this many earlier replay dates form the baseline
    wape_ratio_watch: float = 1.25  # recent error / earlier error
    wape_ratio_action: float = 1.5
    vs_simple_watch: float = 1.10  # recent error of the method / recent error of the simple rule
    vs_simple_action: float = 1.30
    bias_watch: float = 0.10  # |recent (forecast - actual) / actual|
    bias_action: float = 0.20
    coverage_watch: float = 0.70  # share of real sales inside the 80% range (nominal 0.80)
    coverage_action: float = 0.55
    psi_watch: float = 0.10
    psi_action: float = 0.25  # drift is shown as "shifted" above psi_watch; it never changes the status
    z_watch: float = 2.0  # a signal must also be this many robust deviations worse than that item's own earlier windows (see `unusual`)
    z_action: float = 3.0
    min_windows: int = 20  # earlier windows needed to judge what is usual for an item; with fewer, only the fixed limits apply
    drift_recent_days: int = 56  # whole weeks, so weekday patterns are compared fairly
    drift_ref_days: int = 364

    def as_dict(self) -> dict:
        return asdict(self)


def grade_high(value: float | None, watch: float, action: float, can_act: bool = True) -> str:
    """Status for a measure where larger is worse. `can_act=False` caps it at watch (used for drift)."""
    if value is None or value != value:
        return "unknown"
    if value > action and can_act:
        return "action"
    return "watch" if value > watch else "healthy"


def grade_low(value: float | None, watch: float, action: float) -> str:
    """Status for a measure where smaller is worse (range coverage)."""
    if value is None or value != value:
        return "unknown"
    return "action" if value < action else "watch" if value < watch else "healthy"


def robust_z(recent: float | None, earlier: list[float] | np.ndarray, bad_is_high: bool = True, min_windows: int = 20) -> float | None:
    """How unusual `recent` is among `earlier` values of the same measure for the same item, in robust standard deviations (median and scaled MAD), positive
    when worse. None when there are too few earlier values or they do not vary at all."""
    x = np.asarray(earlier, dtype=float)
    x = x[np.isfinite(x)]
    if recent is None or not np.isfinite(recent) or len(x) < min_windows:
        return None
    med = float(np.median(x))
    sd = 1.4826 * float(np.median(np.abs(x - med)))
    if sd <= 1e-9:
        return None
    return (recent - med) / sd if bad_is_high else (med - recent) / sd


def both(fixed: str, z: float | None, T: "Thresholds") -> str:
    """A signal fires only if it is past the fixed limit (big enough to matter) AND, when it can be judged, unusual for this item (not just its normal noise)."""
    if z is None or fixed in ("unknown", "healthy"):
        return fixed
    zgrade = "action" if z > T.z_action else "watch" if z > T.z_watch else "healthy"
    return fixed if ORDER[fixed] <= ORDER[zgrade] else zgrade


def worst(statuses: list[str]) -> str:
    known = [s for s in statuses if s != "unknown"]
    return max(known, key=ORDER.__getitem__) if known else "unknown"
