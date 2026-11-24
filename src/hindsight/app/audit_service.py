"""Decision Audit: write down what was recommended, what was decided and why, then later what happened.

The server recomputes the recommendation itself when a decision is recorded, so the log holds what Hindsight actually said at that time, not
numbers a browser sent. The data is identified by a fingerprint of every value up to the decision day. An outcome can only be recorded from a
file that still has exactly that history (the same numbers, extended with later days), and only once the whole cover window has been observed."""
import hashlib

import numpy as np

from hindsight.app import health_service, inventory_service as inv
from hindsight.app.service import AUTO, Analysis
from hindsight.audit import outcome as outcome_math
from hindsight.audit.store import AuditError, AuditLog
from hindsight.data.sales import SalesData
from hindsight.inventory.inputs import STRATEGIES, InventorySettings, StockLevel, resolve
from hindsight.scenarios.apply import Scenario, apply

MAX_NOTE = 500
SCORED = ("order", "order_up_to", "p_stockout", "expected_cost", "expected_leftover", "expected_shortage")


def fingerprint(data: SalesData, upto: int) -> str:
    """Identifies the sales history up to day index `upto`, whatever order the items were listed in."""
    order = sorted(range(data.n_series), key=lambda i: data.ids[i])
    h = hashlib.sha256()
    h.update("\n".join([*(data.ids[i] for i in order), str(data.dates[0].date()), str(upto)]).encode("utf-8"))
    h.update(np.ascontiguousarray(np.asarray(data.values, dtype=np.float64)[order][:, : upto + 1]).tobytes())
    return h.hexdigest()


def record_decision(log: AuditLog, a: Analysis, filename: str, settings: InventorySettings, stock: dict[str, StockLevel], method: str, strategy: str,
                    orders: dict[str, float], note: str, scenario: Scenario | None) -> dict:
    if strategy not in STRATEGIES:
        raise AuditError(f"Unknown option {strategy!r}.", "bad_strategy")
    eff_settings, eff_stock, factor = settings, stock, 1.0
    if scenario is not None:
        applied = apply(scenario, settings, stock)
        eff_settings, eff_stock, factor = applied.settings, applied.stock, applied.demand_factor
    res = resolve(eff_settings)
    rec = inv.recommend(a, eff_settings, eff_stock, method, demand_factor=factor, with_calibration=False)
    ok = [i for i in rec["items"] if i["status"] == "ok"]
    if not ok:
        raise AuditError("There is not enough track record for any item, so there is no recommendation to record.", "nothing_to_record")
    unknown = sorted(set(orders) - {i["item"] for i in ok})
    if unknown or any(v < 0 for v in orders.values()):
        raise AuditError("Orders can only be changed for items that have a recommendation, and cannot be negative.", "bad_override", items=", ".join(unknown))
    items = []
    for i in ok:
        chosen = float(orders.get(i["item"], i["by_strategy"][strategy]["order"]))
        items.append({"item": i["item"], "forecast_demand": i["forecast_demand"], "on_hand": i["on_hand"], "on_order": i["on_order"], "position": i["inventory_position"] or 0.0,
                      "by_strategy": {k: {m: s[m] for m in SCORED} for k, s in i["by_strategy"].items()},
                      "chosen_order": round(chosen, 2), "overridden": i["item"] in orders and abs(chosen - i["by_strategy"][strategy]["order"]) > 1e-9})
    try:
        status = health_service.health(a, method)["overall"]["status"]
    except Exception:  # noqa: BLE001 - the decision is still worth recording without it
        status = None
    d = a.data
    payload = {"dataset": {"filename": filename, "n_days": d.n_days, "as_of": str(d.dates[-1].date()), "as_of_index": d.n_days - 1, "fingerprint": fingerprint(d, d.n_days - 1)},
               "method": method, "mode": res.mode, "window_days": res.window_days, "cost_based": res.cost_based, "cu": res.cu, "co": res.co, "strategy": strategy,
               "settings": eff_settings.model_dump(exclude_none=True), "assumptions": rec["assumptions"], "scenario": scenario.model_dump(exclude_none=True) if scenario else None,
               "demand_factor": round(factor, 4), "health": status, "items": items, "skipped": [i["item"] for i in rec["items"] if i["status"] != "ok"],
               "total_ordered": round(sum(i["chosen_order"] for i in items), 2), "note": (note or "").strip()[:MAX_NOTE]}
    return log.append("decision", payload)


def _status(payload: dict, data: SalesData, has_outcome: bool) -> tuple[str, dict]:
    ds = payload["dataset"]
    ids = {i["item"] for i in payload["items"]}
    if has_outcome:
        return "recorded", {}
    if not ids <= set(data.ids):
        return "items_missing", {"items": ", ".join(sorted(ids - set(data.ids)))}
    day = np.flatnonzero(data.dates == np.datetime64(ds["as_of"]))
    if day.size == 0 or int(day[0]) != ds["as_of_index"] or fingerprint(data, ds["as_of_index"]) != ds["fingerprint"]:
        return "different_data", {}  # the history up to the decision day is not the history the decision was made on
    missing = ds["as_of_index"] + payload["window_days"] - (data.n_days - 1)
    if missing > 0:
        return "not_yet", {"days": int(missing)}
    return "ready", {}


def _evaluate(payload: dict, data: SalesData) -> dict:
    s, w = payload["dataset"]["as_of_index"] + 1, payload["window_days"]
    rows = {i: k for k, i in enumerate(data.ids)}
    actual = {it["item"]: float(np.asarray(data.values, dtype=float)[rows[it["item"]], s: s + w].sum()) for it in payload["items"]}
    ev = outcome_math.evaluate(payload["items"], actual, payload["cu"], payload["co"])
    return ev | {"window": {"from": str(data.dates[s].date()), "to": str(data.dates[s + w - 1].date()), "days": w}}


def review(log: AuditLog, data: SalesData) -> list[dict]:
    """For every recorded decision: can its outcome be worked out from this file? Nothing is written."""
    out = []
    for ev in log.events("decision", limit=500):
        p = ev["payload"]
        have = log.outcome_of(ev["id"]) is not None
        status, params = _status(p, data, have)
        row = {"decision_id": ev["id"], "status": status, "params": params}
        if status == "ready":
            row["preview"] = _evaluate(p, data)
        out.append(row)
    return out


def record_outcome(log: AuditLog, data: SalesData, filename: str, decision_id: int) -> dict:
    ev = log.get(decision_id)
    if ev is None or ev["kind"] != "decision":
        raise AuditError("That decision is not in the log.", "no_such_decision", id=decision_id)
    status, params = _status(ev["payload"], data, log.outcome_of(decision_id) is not None)
    if status != "ready":
        messages = {"recorded": ("An outcome is already recorded for this decision. The log does not allow it to be replaced.", "outcome_exists"),
                    "items_missing": ("This file does not contain all the items of the decision.", "items_missing"),
                    "different_data": ("This file's history up to the decision day differs from the data the decision was made on, so it cannot be used to judge it.", "different_data"),
                    "not_yet": (f"The cover window is not finished in this file: {params.get('days')} more days of sales are needed.", "not_yet")}
        msg, code = messages[status]
        raise AuditError(msg, code, id=decision_id, **params)
    ev_data = _evaluate(ev["payload"], data)
    payload = {"decision": decision_id, "dataset": {"filename": filename, "last_day": str(data.dates[-1].date()), "n_days": data.n_days}, **ev_data,
               "notes": ["one_window", "sales_not_demand", "not_a_verdict"]}
    return log.append("outcome", payload, ref=decision_id)
