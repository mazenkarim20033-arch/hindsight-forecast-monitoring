"""Everything the interface needs, as plain data: run the replay for an uploaded file, then answer questions about it.

An `Analysis` holds, for one dataset and one set of settings, the replay of every method, their ranges, the scorecard and the
forecast for the days after the last one in the file. Nothing here changes the numbers the research code produces; it only
chooses sensible defaults for a business owner (how much history needs which methods) and shapes the results for display."""
import hashlib
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from hindsight.calendar_features import M5Events, egypt_calendar
from hindsight.data.sales import SalesData
from hindsight.replay.alerts import find_odd_days, latest_forecast_per_day
from hindsight.replay.baselines import BASELINES, SeasonalAverage
from hindsight.replay.engine import Replay, make_origins, run_replay
from hindsight.replay.explain import explain_forecast
from hindsight.replay.intervals import IntervalReplay, conformal_intervals
from hindsight.replay.metrics import wape
from hindsight.replay.ml import GlobalLightGBM
from hindsight.replay.scorecard import score
from hindsight.replay.select import select_online

REFERENCE = SeasonalAverage(7, 4).name
AUTO = "best method so far"
LEVELS = (0.8, 0.9)
ALERT_LEVEL = 0.98
SCORE_DAYS = 730
CALENDARS = {"none": "No holiday calendar", "egypt": "Egyptian holidays (Ramadan, Eids, Coptic Christmas, national days)", "events": "Events listed with the file"}


@dataclass
class Settings:
    horizon: int = 28
    calendar: str = "none"

    def validate(self, data: SalesData) -> None:
        if not 7 <= self.horizon <= 28:
            raise ValueError("The forecast length must be between 7 and 28 days.")
        if self.calendar not in CALENDARS:
            raise ValueError(f"Unknown calendar {self.calendar!r}.")
        if self.calendar == "events" and "event_name_1" not in data.calendar.columns:
            raise ValueError("This file has no event list to use.")


@dataclass
class Plan:
    tier: str  # "full", "simple" or "too_little"
    min_train: int
    step: int
    explanation: str
    params: dict = field(default_factory=dict)  # numbers behind the explanation, so a client can say it in another language


def plan_for(n_days: int, horizon: int) -> Plan:
    if n_days < 120:
        more_days, more_months = max(0, 120 - n_days), max(0, 730 - n_days) // 30
        return Plan("too_little", 0, 0, f"Your file covers {n_days} days. Hindsight needs at least 120 days (about 4 months) to replay anything; two years is better. "
                                          f"Add {more_days} more days of daily sales, or about {more_months} more months for the full comparison.", {"days": n_days, "more_days": more_days, "more_months": more_months})
    if n_days < 730:
        more_months = max(0, 730 - n_days) // 30 + 1
        return Plan("simple", 60, 3, f"Your file covers {n_days} days ({n_days / 30:.0f} months). That is enough to compare simple rules, but not to trust a learning model. "
                                     f"With about {more_months} more months the app will also test a machine-learning forecast.", {"days": n_days, "months": round(n_days / 30), "more_months": more_months})
    return Plan("full", 365, 5, f"Your file covers {n_days / 365:.1f} years, enough to compare simple rules against a learning model.", {"years": round(n_days / 365, 1)})


@dataclass
class Analysis:
    data: SalesData
    settings: Settings
    plan: Plan
    origins: np.ndarray  # replay dates (index of the last visible day)
    in_window: np.ndarray  # over origins + the pending one: which replay dates are scored
    replays: dict[str, Replay]  # each has one extra final origin (the live forecast) with unknown actuals
    chosen: list[str]  # method picked by "best method so far" at each origin, the pending one last
    ranges: dict[tuple[str, float], IntervalReplay] = field(default_factory=dict)
    forecasters: dict = field(default_factory=dict)
    rows: list[dict] = field(default_factory=list)
    reference: str = REFERENCE

    @property
    def n_real(self) -> int:
        return len(self.origins)


def _calendars(data: SalesData, settings: Settings) -> list:
    if settings.calendar == "egypt":
        return [egypt_calendar]
    if settings.calendar == "events":
        return [M5Events(data.calendar)]
    return []


def _with_pending(replay: Replay, final: np.ndarray, n_days: int) -> Replay:
    """The replay plus one more origin at the last day of data, whose actuals are not yet known."""
    f = np.maximum(np.asarray(final, dtype=float), 0.0)
    return Replay(replay.method, replay.horizon, np.append(replay.origins, n_days - 1), np.concatenate([replay.forecasts, f[None]]),
                  np.concatenate([replay.actuals, np.full((1,) + f.shape, np.nan)]), replay.dates, replay.ids)


CACHE_VERSION = 1  # bump when the research code changes what an analysis contains


def analysis_key(data: SalesData, settings: Settings) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(data.values, dtype=np.float64).tobytes())
    h.update(",".join([*data.ids, str(data.dates[0]), str(data.dates[-1]), str(settings), str(CACHE_VERSION)]).encode())
    if settings.calendar == "events":
        h.update(data.calendar.to_csv(index=False).encode())
    return h.hexdigest()[:24]


def run_analysis(data: SalesData, settings: Settings, progress: Callable[[float, str], None] | None = None, cache_dir: Path | None = None) -> Analysis:
    """Replay every method and score it. With `cache_dir`, an identical earlier analysis is loaded from disk instead of recomputed
    (only used for the bundled sample: uploaded files are never written to disk). The cache holds pickles this program wrote itself."""
    data.validate()
    settings.validate(data)
    plan = plan_for(data.n_days, settings.horizon)
    if plan.tier == "too_little":
        raise ValueError(plan.explanation)
    cached = cache_dir / f"{analysis_key(data, settings)}.pkl" if cache_dir else None
    if cached is not None and cached.exists():
        try:
            with cached.open("rb") as f:
                loaded = pickle.load(f)
            if progress:
                progress(1.0, "Done")
            return loaded
        except Exception:  # noqa: BLE001 - a damaged or outdated cache file just means we recompute
            cached.unlink(missing_ok=True)
    result = _compute(data, settings, plan, progress)
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".tmp")
        with tmp.open("wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(cached)
    return result


def _compute(data: SalesData, settings: Settings, plan: Plan, progress: Callable[[float, str], None] | None) -> Analysis:
    origins = make_origins(data.n_days, settings.horizon, plan.min_train, plan.step)
    forecasters = list(BASELINES)
    if plan.tier == "full":
        forecasters.append(GlobalLightGBM(calendars=_calendars(data, settings), name="learning model"))
    weights = [1.0 if isinstance(f, GlobalLightGBM) else 0.05 for f in forecasters]
    done_before = np.concatenate([[0], np.cumsum(weights)]) / sum(weights)
    replays, held = {}, {}
    for k, f in enumerate(forecasters):
        def tick(i, n, k=k, f=f):
            if progress:
                progress(done_before[k] + (done_before[k + 1] - done_before[k]) * i / n, f"Replaying the past with the method '{f.name}'")
        r = run_replay(data, f, settings.horizon, origins, progress=tick)
        final = f.forecast(np.asarray(data.values, dtype=float).copy(), data.dates, settings.horizon)
        replays[f.name] = _with_pending(r, final, data.n_days)
        held[f.name] = f
    if progress:
        progress(0.97, "Scoring")
    sel = select_online(replays, default=REFERENCE, window=8)
    replays[AUTO] = sel.replay
    in_window = np.append(origins >= data.n_days - SCORE_DAYS - 1, False)
    a = Analysis(data, settings, plan, origins, in_window, replays, sel.chosen, forecasters=held)
    values = np.asarray(data.values, dtype=float)
    for name, r in replays.items():
        for lv in (*LEVELS, ALERT_LEVEL):
            a.ranges[(name, lv)] = conformal_intervals(r, values, level=lv, min_residuals=200 if lv == ALERT_LEVEL else 60)
    ref = replays[REFERENCE]
    a.rows = [score(r, values, in_window, ref, n_boot=300, levels=LEVELS, ranges={lv: a.ranges[(name, lv)] for lv in LEVELS}) | {"is_auto": name == AUTO, "is_reference": name == REFERENCE}
              for name, r in replays.items()]
    if progress:
        progress(1.0, "Done")
    return a


def _series_index(a: Analysis, series: str | int | None) -> int:
    if series is None:
        return 0
    if isinstance(series, int):
        return series
    if series not in a.data.ids:
        raise KeyError(f"Unknown item {series!r}")
    return a.data.ids.index(series)


def _round(x: np.ndarray, digits: int = 1) -> list:
    return [None if not np.isfinite(v) else round(float(v), digits) for v in np.asarray(x, dtype=float).reshape(-1)]


def verdict(a: Analysis) -> dict:
    """A plain answer to 'is the clever method worth it?', with the numbers behind it."""
    rows = {r["method"]: r for r in a.rows}
    ref = rows[REFERENCE]
    candidates = [r for r in a.rows if not r["is_reference"] and not r["is_auto"]]
    best = min(candidates + [ref], key=lambda r: r["wape"])
    if best["is_reference"]:
        return {"kind": "reference_best", "method": REFERENCE, "wape": ref["wape"], "reference_wape": ref["wape"], "gain": 0.0,
                "text": f"The simple rule was the most accurate: it was off by {ref['wape']:.0%} of sales on average. Nothing cleverer earned its place on your history."}
    lo, hi = best["gain_ci95"]
    gain = best["gain_vs_reference"]
    if lo > 0:
        kind, text = "beats", (f"'{best['method']}' beat the simple weekday rule: off by {best['wape']:.1%} of sales against {ref['wape']:.1%}, "
                               f"and ahead on {best['win_rate_vs_reference']:.0%} of replay dates.")
    elif hi < 0:
        kind, text = "worse", f"'{best['method']}' was no better than the simple weekday rule here."
    else:
        kind, text = "tie", (f"'{best['method']}' and the simple weekday rule were too close to call ({best['wape']:.1%} against {ref['wape']:.1%}). Prefer the simple rule: it is easier to explain.")
    return {"kind": kind, "method": best["method"], "wape": best["wape"], "reference_wape": ref["wape"], "win_rate": best["win_rate_vs_reference"], "gain": gain, "gain_ci95": [lo, hi], "text": text}


def overview(a: Analysis) -> dict:
    d = a.data
    totals = d.values.sum(axis=1)
    win_start = d.dates[a.origins[a.in_window[: a.n_real]][0]] if a.in_window[: a.n_real].any() else d.dates[a.origins[0]]
    return {"tier": a.plan.tier, "tier_text": a.plan.explanation, "settings": {"horizon": a.settings.horizon, "calendar": a.settings.calendar},
            "dates": {"first": str(d.dates[0].date()), "last": str(d.dates[-1].date()), "n_days": d.n_days},
            "replay": {"n_dates": int(a.in_window.sum()), "first_scored": str(win_start.date()), "step_days": a.plan.step},
            "series": [{"id": s, "total": float(t), "average_per_day": float(t / d.n_days)} for s, t in zip(d.ids, totals)],
            "methods": [{"name": r["method"], "is_reference": r["is_reference"], "is_auto": r["is_auto"]} for r in a.rows],
            "verdict": verdict(a), "source": d.source}


def _sub(r: Replay, i: int) -> Replay:
    return Replay(r.method, r.horizon, r.origins, r.forecasts[:, [i]], r.actuals[:, [i]], r.dates, [r.ids[i]])


def scorecard(a: Analysis) -> dict:
    values = np.asarray(a.data.values, dtype=float)
    per_series = []
    best_name = verdict(a)["method"]
    for i, sid in enumerate(a.data.ids):
        row = {"series": sid}
        for tag, name in (("reference", REFERENCE), ("best", best_name)):
            r = _sub(a.replays[name], i).where(a.in_window)
            ir = a.ranges[(name, 0.8)]
            hit = ((r.actuals >= ir.lower[a.in_window][:, [i]]) & (r.actuals <= ir.upper[a.in_window][:, [i]]))
            ok = np.isfinite(ir.lower[a.in_window][:, [i]])
            row[f"{tag}_wape"] = wape(r)
            if tag == "best":
                row["coverage_80"] = float(hit[ok].mean()) if ok.any() else None
        row["gain"] = row["reference_wape"] - row["best_wape"]
        per_series.append(row)
    return {"reference": REFERENCE, "best_method": best_name, "verdict": verdict(a), "methods": a.rows, "per_series": per_series,
            "window": {"n_dates": int(a.in_window.sum()), "horizon": a.settings.horizon},
            "limits": ["Replay dates overlap, so the intervals shown are indicative.",
                       "A good record on the past does not guarantee the future, especially after a change in the business."]}


def _track(a: Analysis, si: int, name: str, level: float) -> dict:
    ir = a.ranges[(name, level)]
    f = latest_forecast_per_day(ir, a.data.n_days)
    actual = np.asarray(a.data.values, dtype=float)[si]
    lo, hi, ex = f["low"][si], f["high"][si], f["expected"][si]
    have = np.isfinite(lo)
    hit = np.where(have, (actual >= lo) & (actual <= hi), False)
    return {"expected": ex, "low": lo, "high": hi, "have": have, "hit": hit}


def stage(a: Analysis, series: str | int | None = None, method: str = AUTO, level: float = 0.8, last_days: int = 420) -> dict:
    """What the replay stage draws for one item: the real line, the forecast made at each replay date and its range, and a hit/miss ribbon."""
    if method not in a.replays:
        raise KeyError(f"Unknown method {method!r}")
    if level not in LEVELS:
        raise ValueError("level must be 0.8 or 0.9")
    si = _series_index(a, series)
    d = a.data
    first_day = max(0, d.n_days - last_days)
    r, ir = a.replays[method], a.ranges[(method, level)]
    idx = np.where((r.origins >= first_day - a.settings.horizon) & (np.arange(len(r.origins)) < a.n_real))[0]
    tr = _track(a, si, method, level)
    days = np.arange(first_day, d.n_days)
    return {"item": d.ids[si], "method": method, "level": level, "horizon": a.settings.horizon, "first_day": int(first_day),
            "dates": [str(x.date()) for x in d.dates[first_day:]],
            "actual": _round(np.asarray(d.values, dtype=float)[si, first_day:]),
            "origins": [int(r.origins[i]) for i in idx],
            "forecast": [_round(r.forecasts[i, si]) for i in idx], "low": [_round(ir.lower[i, si]) for i in idx], "high": [_round(ir.upper[i, si]) for i in idx],
            "chosen": [a.chosen[i] for i in idx],
            "ribbon": {"hit": [None if not tr["have"][x] else bool(tr["hit"][x]) for x in days],
                       "expected": _round(tr["expected"][days]), "low": _round(tr["low"][days]), "high": _round(tr["high"][days])},
            "coverage_80": float(tr["hit"][tr["have"] & (np.arange(d.n_days) >= first_day)].mean()) if (tr["have"][first_day:]).any() else None}


def next_view(a: Analysis, series: str | int | None = None, method: str = AUTO, level: float = 0.8, reasons_for_day: int = 0, history_days: int = 60) -> dict:
    si = _series_index(a, series)
    d = a.data
    name = method
    picked = a.chosen[-1] if method == AUTO else method
    r, ir = a.replays[method], a.ranges[(method, level)]
    future = pd.date_range(d.dates[-1] + pd.Timedelta(days=1), periods=a.settings.horizon)
    out = {"item": d.ids[si], "method": name, "method_in_use": picked, "level": level, "last_day": str(d.dates[-1].date()),
           "history": {"dates": [str(x.date()) for x in d.dates[-history_days:]], "actual": _round(np.asarray(d.values, dtype=float)[si, -history_days:])},
           "dates": [str(x.date()) for x in future], "forecast": _round(r.forecasts[-1, si]), "low": _round(ir.lower[-1, si]), "high": _round(ir.upper[-1, si]),
           "range_note": None if np.isfinite(ir.lower[-1, si]).any() else "There is not enough track record yet to give a range.",
           "total_next_7": float(np.nansum(r.forecasts[-1, si, :7])), "reasons": None}
    f = a.forecasters.get("learning model")
    if f is not None and picked == "learning model":
        hist = np.asarray(d.values, dtype=float).copy()
        day = int(np.clip(reasons_for_day, 0, a.settings.horizon - 1))
        exp = explain_forecast(f, hist, d.dates, a.settings.horizon, d.ids)
        out["reasons"] = {"day": day, "date": str(exp.dates[day].date()), "forecast": float(exp.forecast[si, day]), "items": exp.table(si, day),
                          "note": "These are the inputs the model leaned on, not proven causes."}
    return out


def alerts(a: Analysis, method: str = AUTO, last_days: int = 365) -> dict:
    ir = a.ranges[(method, ALERT_LEVEL)]
    values = np.asarray(a.data.values, dtype=float)
    odd = find_odd_days(ir, values)
    odd = odd[odd.date >= a.data.dates[max(0, a.data.n_days - last_days)]]
    rows = [{"item": r.series, "date": str(r.date.date()), "actual": r.actual, "expected": r.expected, "low": r.low, "high": r.high, "direction": r.direction,
             "deviation_pct": r.deviation_pct} for r in odd.head(50).itertuples()]
    return {"level": ALERT_LEVEL, "method": method, "count": int(len(odd)), "items": rows,
            "note": "An alert means sales fell outside the range the forecast gave for that day (about 1 normal day in 50 will do so by chance). Small changes cannot be seen this way."}
