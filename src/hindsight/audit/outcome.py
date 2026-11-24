"""What actually happened after a decision, worked out from the decision's own record and the sales that followed. Pure arithmetic.

For each item: stock on hand and on order at the time, plus the quantity ordered, is the stock available over the cover window. Real sales over
that window then give the leftover and the shortage. The same is worked out for the quantity each of the three options would have ordered, so a
decision can be read against the alternatives: still one window, one item at a time, so it is an illustration, not a verdict."""


def _result(level: float, actual: float, cu: float | None, co: float | None) -> dict:
    leftover, shortage = max(level - actual, 0.0), max(actual - level, 0.0)
    cost = None if cu is None or co is None else cu * shortage + co * leftover
    return {"level": round(level, 2), "leftover": round(leftover, 2), "shortage": round(shortage, 2), "stocked_out": actual > level + 1e-9, "cost": None if cost is None else round(cost, 2)}


def evaluate(items: list[dict], actual: dict[str, float], cu: float | None, co: float | None) -> dict:
    out, totals = [], {"actual": 0.0, "forecast": 0.0, "leftover": 0.0, "shortage": 0.0, "cost": 0.0}
    alt = {}
    cost_known = cu is not None and co is not None
    for it in items:
        a = actual[it["item"]]
        position = it.get("position") or 0.0
        chosen = _result(position + it["chosen_order"], a, cu, co)
        by = {k: _result(position + s["order"], a, cu, co) | {"order": s["order"]} for k, s in it["by_strategy"].items()}
        err = None if a <= 0 else round((it["forecast_demand"] - a) / a, 4)
        out.append({"item": it["item"], "actual": round(a, 2), "forecast": it["forecast_demand"], "forecast_error": err, "chosen_order": it["chosen_order"], "chosen": chosen, "by_strategy": by})
        totals["actual"] += a
        totals["forecast"] += it["forecast_demand"]
        totals["leftover"] += chosen["leftover"]
        totals["shortage"] += chosen["shortage"]
        totals["cost"] += chosen["cost"] or 0.0
        for k, r in by.items():
            t = alt.setdefault(k, {"leftover": 0.0, "shortage": 0.0, "cost": 0.0})
            t["leftover"] += r["leftover"]
            t["shortage"] += r["shortage"]
            t["cost"] += r["cost"] or 0.0
    r2 = lambda d: {k: round(v, 2) for k, v in d.items()}
    best = min(alt, key=lambda k: alt[k]["cost"]) if cost_known and alt else None
    return {"items": out, "totals": r2(totals) | {"cost": round(totals["cost"], 2) if cost_known else None},
            "by_strategy": {k: r2(v) | ({} if cost_known else {"cost": None}) for k, v in alt.items()}, "best_in_hindsight": best, "cost_known": cost_known,
            "forecast_error": None if totals["actual"] <= 0 else round((totals["forecast"] - totals["actual"]) / totals["actual"], 4)}
