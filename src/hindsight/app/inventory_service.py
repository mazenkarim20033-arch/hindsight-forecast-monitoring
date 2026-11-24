"""Order recommendations: joins the forecast (what is likely to sell over the cover period) with the inventory arithmetic.

The demand picture for one item is its latest forecast of the cover period multiplied by how earlier forecasts of the same length turned out
(actual sales divided by forecast, using only periods that had already ended when the live forecast was made). That is an empirical
approximation of the demand distribution, not a fitted model of it: it is only as good as the track record behind it, so the response also
reports how often each service level actually held on the replayed past (`calibration`)."""
import numpy as np

from hindsight.app.service import AUTO, Analysis, _round
from hindsight.inventory import newsvendor as nv
from hindsight.inventory.inputs import STRATEGIES, InventorySettings, StockLevel, resolve

MIN_RATIOS = 20  # fewer finished earlier periods than this and no honest spread can be given
KEEP_RATIOS = 120  # the newest finished periods are used, so old behaviour fades out


def _tables(a: Analysis, method: str, days: int):
    if method not in a.replays:
        raise KeyError(f"Unknown method {method!r}")
    if days > a.settings.horizon:
        raise ValueError(f"The cover period is {days} days but this analysis forecast only {a.settings.horizon}. Re-run it with a longer forecast.")
    r, n = a.replays[method], a.n_real
    fsum = r.forecasts[:n, :, :days].sum(axis=2)
    act = r.actuals[:n, :, :days].sum(axis=2)
    ratio = np.where(fsum > 0, act / np.where(fsum > 0, fsum, 1.0), np.nan)
    return r, fsum, act, ratio


def _known(ratio_col: np.ndarray, count: int) -> np.ndarray:
    k = ratio_col[:count]
    return k[np.isfinite(k)][-KEEP_RATIOS:]


def demand_samples(a: Analysis, method: str, days: int) -> tuple[np.ndarray, list[np.ndarray | None]]:
    """The live forecast of the next `days` days for every item, and for each one the equally likely demand outcomes (None: too little record)."""
    r, _, _, ratio = _tables(a, method, days)
    n = a.n_real
    point = r.forecasts[n, :, :days].sum(axis=1)  # the extra, last origin is the live forecast
    out: list[np.ndarray | None] = []
    for si in range(point.shape[0]):
        known = _known(ratio[:, si], n)  # every earlier period has finished by the last day of data
        out.append(point[si] * known if len(known) >= MIN_RATIOS else None)
    return point, out


def calibration(a: Analysis, method: str, days: int, levels: dict[str, float]) -> list[dict]:
    """Did a target service level hold on the replayed past? At each scored replay date, order up to the quantile of the ratios known by then
    and see whether demand stayed within it. Pooled over items; 'realized' should sit near 'target' if the approximation is sound."""
    r, fsum, act, ratio = _tables(a, method, days)
    n = a.n_real
    ends = r.origins[:n] + days
    qs = list(levels.values())
    hits = {k: [] for k in levels}
    for i in np.where(a.in_window[:n])[0]:
        count = int(np.searchsorted(ends, r.origins[i], side="right"))
        for si in range(fsum.shape[1]):
            known = _known(ratio[:, si], count)
            if len(known) < MIN_RATIOS:
                continue
            cover = fsum[i, si] * np.quantile(known, qs, method="inverted_cdf")
            for k, c in zip(levels, cover):
                hits[k].append(act[i, si] <= c + 1e-9)
    return [{"strategy": k, "target": round(levels[k], 4), "realized": round(float(np.mean(h)), 4) if h else None, "n_cases": len(h)} for k, h in hits.items()]


def recommend(a: Analysis, settings: InventorySettings, stock: dict[str, StockLevel] | None = None, method: str = AUTO, *,
              demand_factor: float = 1.0, with_calibration: bool = True, keep_orders: dict[str, dict[str, float]] | None = None) -> dict:
    """`demand_factor` scales every demand outcome (used only by what-if scenarios; 1.0 leaves the forecast as it is). `keep_orders` maps item ->
    strategy -> a quantity ordered earlier: each strategy then also reports what that order would mean under these inputs (`if_baseline_order`)."""
    res = resolve(settings)
    days = res.window_days
    point, samples = demand_samples(a, method, days)
    if demand_factor != 1.0:
        point = point * demand_factor
        samples = [None if x is None else x * demand_factor for x in samples]
    stock = stock or {}
    salvage = settings.salvage_value or 0.0
    hold_cycle = (settings.holding_cost_per_day or 0.0) * (days - (settings.lead_time_days or 0) if res.mode == "periodic_review" else days)
    items, totals = [], {k: {"order": 0.0, "investment": 0.0, "expected_cost": 0.0, "expected_leftover": 0.0, "expected_shortage": 0.0} for k in STRATEGIES}
    for si, sid in enumerate(a.data.ids):
        have = stock.get(sid) or StockLevel()
        flags = []
        if have.on_hand is None:
            flags.append("stock_missing")
        elif have.on_order is None:
            flags.append("on_order_missing")
        position = (have.on_hand or 0.0) + (have.on_order or 0.0)
        row = {"item": sid, "forecast_demand": round(float(point[si]), 2), "on_hand": have.on_hand, "on_order": have.on_order,
               "inventory_position": round(position, 2) if have.on_hand is not None else None, "flags": flags, "status": "ok", "by_strategy": {}}
        if samples[si] is None:
            row["status"] = "limited"
            items.append(row)
            continue
        row["demand_range"] = _round(np.quantile(samples[si], [0.1, 0.9]), 2)
        for key in STRATEGIES:
            p = nv.plan(samples[si], res.levels[key], position, settings.min_order_qty, settings.order_multiple)
            m = nv.money(p, p["order"], cu=res.cu if res.cost_based else None, co=res.co if res.cost_based else None, price=settings.price,
                         unit_cost=settings.unit_cost, salvage=salvage, holding_cycle=hold_cycle)
            row["by_strategy"][key] = {"service_target": round(res.levels[key], 4), "order_up_to": round(p["order_up_to"], 2), "order": round(p["order"], 2),
                                       "expected_leftover": round(p["expected_leftover"], 2), "expected_shortage": round(p["expected_shortage"], 2),
                                       "p_stockout": round(p["p_stockout"], 4), "fill_rate": round(p["fill_rate"], 4),
                                       **{k: None if v is None else round(v, 2) for k, v in m.items()}}
            earlier = (keep_orders or {}).get(sid, {}).get(key)
            if earlier is not None:
                o = nv.outcomes(samples[si], position + earlier)
                km = nv.money(o, earlier, cu=res.cu if res.cost_based else None, co=res.co if res.cost_based else None, price=settings.price,
                              unit_cost=settings.unit_cost, salvage=salvage, holding_cycle=hold_cycle)
                row["by_strategy"][key]["if_baseline_order"] = {"order": round(earlier, 2), "expected_leftover": round(o["expected_leftover"], 2),
                                                                "expected_shortage": round(o["expected_shortage"], 2), "p_stockout": round(o["p_stockout"], 4),
                                                                "fill_rate": round(o["fill_rate"], 4), **{k: None if v is None else round(v, 2) for k, v in km.items()}}
            t = totals[key]
            t["order"] += p["order"]
            t["expected_leftover"] += p["expected_leftover"]
            t["expected_shortage"] += p["expected_shortage"]
            for k in ("investment", "expected_cost"):
                t[k] = None if m[k] is None or t[k] is None else t[k] + m[k]
        items.append(row)
    ok = [x for x in items if x["status"] == "ok"]
    totals = {k: {kk: None if v is None else round(v, 2) for kk, v in t.items()} for k, t in totals.items()} if ok else {}
    return {"method": method, "mode": res.mode, "window_days": days, "cost_based": res.cost_based, "horizon": a.settings.horizon,
            "assumptions": [{"field": x.field, "value": x.value, "source": x.source} for x in res.assumptions], "missing": res.missing,
            "levels": {k: round(v, 4) for k, v in res.levels.items()}, "items": items, "totals": totals,
            "calibration": calibration(a, method, days, res.levels) if ok and with_calibration else [],
            "notes": ["not_guarantee", "approximation", "sales_not_demand"] + (["no_costs"] if not res.cost_based else [])}
