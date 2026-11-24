"""Forecast health: is the forecast still doing as well as it did, and has the demand it is forecasting changed?

Everything is computed *as of a day* (default: the last day of data) from replay dates whose whole forecast horizon had already been
observed by that day, so a status never uses an outcome that was not yet known then. That makes the monitor testable on the past: the same
function can be run at every earlier day to see how often it would have raised an alarm (scripts/run_health_check.py).

Nothing here changes what the app forecasts. A challenger is evaluated on the past only and never deployed (`deployed` is always False)."""
import numpy as np

from hindsight.app.service import AUTO, REFERENCE, Analysis, _calendars
from hindsight.monitoring import drift
from hindsight.monitoring.rules import ORDER, Thresholds, grade_high, grade_low, worst
from hindsight.replay.engine import Replay, run_replay
from hindsight.replay.metrics import paired_difference_ci
from hindsight.replay.ml import GlobalLightGBM

TIMELINE_POINTS = 120
CHALLENGER_ORIGINS = 12
CHALLENGER_TRAIN_DAYS = 365
CHALLENGER_REFIT_EVERY = 14


class HealthInputError(ValueError):
    def __init__(self, message: str, code: str, **params):
        super().__init__(message)
        self.code, self.params = code, params


def _r(x: float | None, d: int = 4) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), d)


def _ratio(num: float | None, den: float | None) -> float | None:
    return None if num is None or den is None or den <= 0 else num / den


def _sums(x: np.ndarray, idx: np.ndarray) -> float:
    return float(x[idx].sum()) if len(idx) else 0.0


def _signals(T: Thresholds, e, t, b, ref_e, hit, avail, psi_value, rec, hist, is_ref: bool) -> list[dict]:
    """The five signals for one pool of replay dates. e, t, b, ref_e, hit, avail are 1-D over the known dates (already summed over items
    and days ahead): error of the method, sales, signed error, error of the simple rule, ranges that held, ranges that existed."""
    enough = len(hist) >= T.min_history_origins and len(rec) >= 1
    w_rec = _ratio(_sums(e, rec), _sums(t, rec))
    w_his = _ratio(_sums(e, hist), _sums(t, hist))
    ratio = _ratio(w_rec, w_his) if enough else None
    out = [{"key": "accuracy", "value": _r(ratio), "status": grade_high(ratio, T.wape_ratio_watch, T.wape_ratio_action), "watch": T.wape_ratio_watch, "action": T.wape_ratio_action,
            "recent": _r(w_rec), "earlier": _r(w_his)}]
    if not is_ref:
        ref_rec = _ratio(_sums(ref_e, rec), _sums(t, rec))
        vs = _ratio(w_rec, ref_rec) if enough else None
        out.append({"key": "vs_simple", "value": _r(vs), "status": grade_high(vs, T.vs_simple_watch, T.vs_simple_action), "watch": T.vs_simple_watch, "action": T.vs_simple_action,
                    "recent": _r(w_rec), "simple_rule": _r(ref_rec)})
    bias = _ratio(abs(_sums(b, rec)), _sums(t, rec))
    out.append({"key": "bias", "value": _r(_ratio(_sums(b, rec), _sums(t, rec))), "status": grade_high(bias if enough else None, T.bias_watch, T.bias_action), "watch": T.bias_watch, "action": T.bias_action})
    cov = _ratio(_sums(hit, rec), _sums(avail, rec))
    out.append({"key": "coverage", "value": _r(cov), "status": grade_low(cov if enough else None, T.coverage_watch, T.coverage_action), "watch": T.coverage_watch, "action": T.coverage_action})
    out.append({"key": "drift", "value": _r(psi_value), "status": grade_high(psi_value, T.psi_watch, T.psi_action, can_act=False), "watch": T.psi_watch, "action": T.psi_action})
    return out


def _status(signals: list[dict]) -> str:
    """Worst of the error-based signals. Demand drift is shown beside them but never counts: on M5 the usual PSI thresholds flag almost every
    store because sales grow, including when the forecast is perfectly accurate (see reports/health_m5.md)."""
    return worst([s["status"] for s in signals if s["key"] != "drift"])


def _drift(row: np.ndarray, day: int, T: Thresholds) -> dict:
    """Recent days against the stretch before them, ending at `day`. Both stretches are whole weeks."""
    rec_n = T.drift_recent_days
    ref_n = 7 * (min(T.drift_ref_days, day + 1 - rec_n) // 7)
    if ref_n < 56:
        return {"psi": None, "ks": None, "ks_p": None, "recent_mean": None, "earlier_mean": None}
    recent = row[day + 1 - rec_n: day + 1]
    ref = row[day + 1 - rec_n - ref_n: day + 1 - rec_n]
    k = drift.ks(ref, recent)
    return {"psi": drift.psi(ref, recent), "ks": _r(k[0]) if k else None, "ks_p": _r(k[1]) if k else None, "recent_mean": _r(recent.mean(), 2), "earlier_mean": _r(ref.mean(), 2)}


def health(a: Analysis, method: str = AUTO, T: Thresholds | None = None, day: int | None = None) -> dict:
    T = T or Thresholds()
    if method not in a.replays:
        raise KeyError(f"Unknown method {method!r}")
    d, n, h = a.data, a.n_real, a.settings.horizon
    day = d.n_days - 1 if day is None else day
    r, ref = a.replays[method], a.replays[REFERENCE]
    known = np.where(r.origins[:n] + h <= day)[0]
    rec = known[-T.recent_origins:]
    hist = known[max(0, len(known) - T.recent_origins - T.history_origins): max(0, len(known) - T.recent_origins)]
    values = np.asarray(d.values, dtype=float)
    ir = a.ranges[(method, 0.8)]
    avail = (np.isfinite(ir.lower) & np.isfinite(ir.upper))[:n]
    hit = ((r.actuals >= ir.lower) & (r.actuals <= ir.upper) & np.isfinite(ir.lower))[:n]
    diff = (r.forecasts - r.actuals)[:n]
    err = np.abs(diff).sum(axis=2)  # (origins, items)
    ref_err = np.abs(ref.forecasts - ref.actuals)[:n].sum(axis=2)
    tot = r.actuals[:n].sum(axis=2)
    bias = diff.sum(axis=2)
    hits, avails = hit.sum(axis=2), avail.sum(axis=2)
    is_ref = method == REFERENCE

    items = []
    for si, sid in enumerate(d.ids):
        dr = _drift(values[si], day, T)
        sig = _signals(T, err[:, si], tot[:, si], bias[:, si], ref_err[:, si], hits[:, si], avails[:, si], dr["psi"], rec, hist, is_ref)
        items.append({"item": sid, "status": _status(sig), "signals": sig, "drift": {k: _r(v) if k == "psi" else v for k, v in dr.items()}})
    total_row = values.sum(axis=0)
    dr_all = _drift(total_row, day, T)
    pooled = _signals(T, err.sum(1), tot.sum(1), bias.sum(1), ref_err.sum(1), hits.sum(1), avails.sum(1), dr_all["psi"], rec, hist, is_ref)
    overall = _status(pooled)

    tl_idx = known[-TIMELINE_POINTS:]
    e_all, t_all, re_all = err.sum(1), tot.sum(1), ref_err.sum(1)
    timeline = []
    for j in tl_idx:
        win = known[known <= j][-T.recent_origins:]
        timeline.append({"origin": str(d.dates[int(r.origins[j])].date()), "known": str(d.dates[int(r.origins[j]) + h].date()),
                         "wape": _r(_ratio(e_all[j], t_all[j])), "reference_wape": _r(_ratio(re_all[j], t_all[j])),
                         "rolling": _r(_ratio(_sums(e_all, win), _sums(t_all, win))), "rolling_reference": _r(_ratio(_sums(re_all, win), _sums(t_all, win)))})
    counts = {k: sum(1 for i in items if i["status"] == k) for k in ORDER}
    return {"method": method, "as_of": str(d.dates[day].date()), "horizon": h, "overall": {"status": overall, "signals": pooled, "drift": dr_all},
            "counts": counts, "items": items, "timeline": timeline, "thresholds": T.as_dict(),
            "windows": {"n_known": int(len(known)), "n_recent": int(len(rec)), "n_earlier": int(len(hist)),
                        "recent_from": str(d.dates[int(r.origins[rec[0]])].date()) if len(rec) else None, "recent_to": str(d.dates[int(r.origins[rec[-1]]) + h].date()) if len(rec) else None},
            "notes": ["not_prediction", "conventions", "overlap", "drift_info_only", "sales_not_demand"]}


def challenger(a: Analysis, method: str = AUTO, k: int = CHALLENGER_ORIGINS) -> dict:
    """Retrain the learning model on only the latest year of sales and replay the most recent dates against the current method.
    Uses the same replay engine as everything else, so the challenger sees only what was known at each date. Evaluation only: it is never deployed."""
    if method not in a.replays:
        raise KeyError(f"Unknown method {method!r}")
    if a.plan.tier != "full":
        raise HealthInputError("The learning model is only tested when the file covers at least two years, so there is nothing to retrain here.", "needs_full_tier")
    n, h = a.n_real, a.settings.horizon
    k = min(k, n)
    cand = GlobalLightGBM(calendars=_calendars(a.data, a.settings), name="challenger", train_days=CHALLENGER_TRAIN_DAYS, refit_every=CHALLENGER_REFIT_EVERY)
    rep = run_replay(a.data, cand, h, a.origins[-k:])
    c = a.replays[method]
    champ = Replay(c.method, h, c.origins[:n][-k:], c.forecasts[:n][-k:], c.actuals[:n][-k:], c.dates, c.ids)
    gain, lo, hi = paired_difference_ci(rep, champ)
    verdict = "promote_candidate" if lo > 0 else "keep_current" if hi < 0 else "inconclusive"
    tot = champ.actuals.sum()
    row = lambda x: {"wape": _r(np.abs(x.forecasts - x.actuals).sum() / tot), "bias": _r((x.forecasts - x.actuals).sum() / tot)}
    d = a.data.dates
    return {"method": method, "verdict": verdict, "deployed": False, "n_dates": int(k), "from": str(d[int(champ.origins[0])].date()), "to": str(d[int(champ.origins[-1]) + h].date()),
            "gain": _r(gain), "gain_ci95": [_r(lo), _r(hi)], "current": row(champ), "challenger": row(rep),
            "config": {"train_days": CHALLENGER_TRAIN_DAYS, "refit_every": CHALLENGER_REFIT_EVERY},
            "notes": ["challenger_never_deployed", "challenger_small_sample", "challenger_overlap"]}
