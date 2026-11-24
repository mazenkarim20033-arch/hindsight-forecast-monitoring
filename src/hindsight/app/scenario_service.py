"""Run what-if scenarios next to the baseline. The baseline is computed once and never changed; each scenario is its own `recommend` call on
modified copies of the inputs, so scenarios cannot affect each other or the baseline (the tests check this).

Besides the order a scenario would call for, each result also says what the *baseline* order would mean if the scenario happened: that is
usually the more useful question ("we ordered for normal demand: what if demand jumps 20%?")."""
from hindsight.app import inventory_service as inv
from hindsight.app.service import AUTO, Analysis
from hindsight.inventory.inputs import STRATEGIES, InventoryInputError, InventorySettings, StockLevel
from hindsight.scenarios.apply import Applied, Scenario, apply

TOTAL_KEYS = ("order", "investment", "expected_leftover", "expected_shortage", "expected_cost")
KEPT_KEYS = ("expected_leftover", "expected_shortage", "expected_cost")


def _pair(base: float | None, scen: float | None) -> dict:
    if base is None or scen is None:
        return {"baseline": base, "scenario": scen, "delta": None, "delta_pct": None}
    d = scen - base
    return {"baseline": base, "scenario": scen, "delta": round(d, 2), "delta_pct": round(d / base, 4) if abs(base) > 1e-9 else None}


def _orders(base: dict) -> dict[str, dict[str, float]]:
    return {i["item"]: {k: s["order"] for k, s in i["by_strategy"].items()} for i in base["items"] if i["status"] == "ok"}


def _kept_totals(res: dict) -> dict:
    """Sum, over items, of what the baseline order would mean under the scenario."""
    out = {}
    for key in STRATEGIES:
        rows = [i["by_strategy"][key]["if_baseline_order"] for i in res["items"] if key in i["by_strategy"] and "if_baseline_order" in i["by_strategy"][key]]
        if not rows:
            continue
        out[key] = {k: None if any(r[k] is None for r in rows) else round(sum(r[k] for r in rows), 2) for k in KEPT_KEYS}
    return out


def _compare(base: dict, res: dict) -> dict:
    totals = {k: {m: _pair((base["totals"].get(k) or {}).get(m), (res["totals"].get(k) or {}).get(m)) for m in TOTAL_KEYS} for k in STRATEGIES} if base["totals"] and res["totals"] else {}
    kept = _kept_totals(res)
    kept_cmp = {k: {m: _pair((base["totals"].get(k) or {}).get(m), v[m]) for m in KEPT_KEYS} for k, v in kept.items()}
    items = []
    by_item = {i["item"]: i for i in base["items"]}
    for i in res["items"]:
        b = by_item[i["item"]]
        if i["status"] != "ok" or b["status"] != "ok":
            items.append({"item": i["item"], "status": "limited"})
            continue
        items.append({"item": i["item"], "status": "ok", "forecast_demand": _pair(b["forecast_demand"], i["forecast_demand"]),
                      "by_strategy": {k: {"order": _pair(b["by_strategy"][k]["order"], s["order"]), "p_stockout": _pair(b["by_strategy"][k]["p_stockout"], s["p_stockout"]),
                                          "if_baseline_order": s.get("if_baseline_order")} for k, s in i["by_strategy"].items()}})
    return {"totals": totals, "if_baseline_order": kept_cmp, "items": items}


def _effects(applied: Applied) -> list[dict]:
    return [{"kind": e.kind, **e.params, **({"demand_factor": round(e.factor, 4)} if e.factor is not None else {})} for e in applied.effects]


def run(a: Analysis, settings: InventorySettings, stock: dict[str, StockLevel], method: str, scenarios: list[Scenario]) -> dict:
    """The baseline plus each scenario. A scenario that cannot be applied comes back with its `error` and does not stop the others."""
    baseline = inv.recommend(a, settings, stock, method)
    keep = _orders(baseline)
    results = []
    for sc in scenarios:
        entry: dict = {"name": sc.name, "spec": sc.model_dump(exclude_none=True, exclude={"name"})}
        try:
            applied = apply(sc, settings, stock)
            res = inv.recommend(a, applied.settings, applied.stock, method, demand_factor=applied.demand_factor, with_calibration=False, keep_orders=keep)
        except InventoryInputError as err:
            entry["error"] = {"message": str(err), "code": err.code, "params": err.params}
        except ValueError as err:  # the changed cover period is longer than this analysis forecast
            entry["error"] = {"message": str(err), "code": "beyond_forecast", "params": {}}
        else:
            entry |= {"effects": _effects(applied), "demand_factor": round(applied.demand_factor, 4), "window_days": res["window_days"], "result": res, "comparison": _compare(baseline, res)}
        results.append(entry)
    return {"baseline": baseline, "scenarios": results,
            "notes": ["hypothetical", "not_validated", "flat_daily_demand", "effects_multiply", "baseline_calibration_only"]}
