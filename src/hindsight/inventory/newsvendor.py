"""The inventory arithmetic, with no knowledge of forecasting, files or screens: demand scenarios in, quantities and costs out.

Demand over the cover period is represented by `samples`, an array of equally likely outcomes (for Hindsight: the live forecast multiplied
by how the forecast's earlier ratios of actual-to-forecast turned out). With a fixed cost of ordering one unit too few (`cu`) and one unit
too many (`co`), the cheapest stock level is the demand quantile at the critical ratio cu / (cu + co) (the newsvendor result). For repeated
ordering the same quantile is the order-up-to level of a base-stock policy; the order is that level minus the inventory position."""
import math

import numpy as np


def critical_ratio(cu: float, co: float) -> float:
    if cu <= 0 or co <= 0:
        raise ValueError("both costs must be positive")
    return cu / (cu + co)


def quantile(samples: np.ndarray, q: float) -> float:
    """The smallest sampled demand covering at least a share `q` of outcomes (never rounds down into a lower service level)."""
    return float(np.quantile(np.asarray(samples, dtype=float), min(max(q, 0.0), 1.0), method="inverted_cdf"))


def round_order(raw: float, min_order_qty: float | None = None, multiple: float | None = None) -> float:
    """Apply supplier rules to a wanted quantity: nothing if no order is needed, at least the minimum, whole multiples rounded up."""
    if raw <= 1e-9:
        return 0.0
    qty = max(raw, min_order_qty or 0.0)
    if multiple:
        qty = math.ceil(qty / multiple - 1e-9) * multiple
    return float(qty)


def outcomes(samples: np.ndarray, level: float) -> dict:
    """What happens, on average and in how many cases, if stock available over the period is `level` units."""
    d = np.asarray(samples, dtype=float)
    left, short = np.maximum(level - d, 0.0), np.maximum(d - level, 0.0)
    sales = np.minimum(d, level)
    return {"expected_leftover": float(left.mean()), "expected_shortage": float(short.mean()), "p_stockout": float((d > level).mean()),
            "expected_sales": float(sales.mean()), "fill_rate": float(sales.mean() / d.mean()) if d.mean() > 0 else 1.0}


def plan(samples: np.ndarray, q: float, position: float, min_order_qty: float | None = None, multiple: float | None = None) -> dict:
    """Order enough to bring the inventory position up to the demand quantile `q`, then work out what that order means."""
    target = quantile(samples, q)
    order = round_order(target - position, min_order_qty, multiple)
    level = position + order
    return {"order_up_to": target, "order": order, "level": level, **outcomes(samples, level)}


def money(o: dict, order: float, *, cu: float | None, co: float | None, price: float | None, unit_cost: float | None, salvage: float, holding_cycle: float) -> dict:
    """Costs of an outcome. `cu`/`co` as in the module header; `holding_cycle` is the cost of carrying one leftover unit through the period.
    Expected profit is for this order only: stock already on hand is treated as sunk."""
    if cu is None or co is None:
        return {"investment": None, "expected_excess_cost": None, "expected_stockout_cost": None, "expected_cost": None, "expected_profit": None}
    excess, stockout = co * o["expected_leftover"], cu * o["expected_shortage"]
    profit = None
    if price is not None and unit_cost is not None:
        profit = price * o["expected_sales"] + salvage * o["expected_leftover"] - unit_cost * order - holding_cycle * o["expected_leftover"]
    return {"investment": (unit_cost or 0.0) * order, "expected_excess_cost": excess, "expected_stockout_cost": stockout, "expected_cost": excess + stockout, "expected_profit": profit}
