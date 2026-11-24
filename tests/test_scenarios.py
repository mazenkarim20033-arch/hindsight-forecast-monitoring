"""What-if scenarios: the pure arithmetic, then the API on a real replay (isolation from the baseline and from each other, refusals)."""
import copy

import pytest
from fastapi.testclient import TestClient

from hindsight.app.api import create_app
from hindsight.inventory.inputs import InventoryInputError, InventorySettings, StockLevel
from hindsight.scenarios.apply import Scenario, apply
from test_service_api import upload, wait, weekly_csv

BASE = InventorySettings(lead_time_days=3, review_days=7, price=10, unit_cost=6, holding_cost_per_day=0.05)
STOCK = {"a": StockLevel(on_hand=100, on_order=20), "b": StockLevel(on_hand=None, on_order=None)}


def sc(**kw) -> Scenario:
    return Scenario(name="t", **kw)


# ---- pure functions ----------------------------------------------------------------------------------------------------------------
def test_apply_never_changes_its_arguments():
    settings, stock = BASE.model_copy(deep=True), copy.deepcopy(STOCK)
    apply(sc(supplier_delay_days=4, stock_reduction_pct=50, price_change_pct=10, price_elasticity=-1.5, demand_change_pct=20), settings, stock)
    assert settings == BASE and stock == STOCK


def test_demand_factors_by_hand():
    assert apply(sc(demand_change_pct=20), BASE, STOCK).demand_factor == pytest.approx(1.2)
    assert apply(sc(demand_change_pct=-30), BASE, STOCK).demand_factor == pytest.approx(0.7)
    # a +30% promotion on 3 of the 10 cover days: 1 + 0.30 * 3/10
    assert apply(sc(promo_uplift_pct=30, promo_days=3), BASE, STOCK).demand_factor == pytest.approx(1.09)
    assert apply(sc(spike_pct=100, spike_days=2), BASE, STOCK).demand_factor == pytest.approx(1.2)
    assert apply(sc(seasonal_change_pct=-10, seasonal_days=10), BASE, STOCK).demand_factor == pytest.approx(0.9)
    # an effect longer than the cover period is cut to it, and the result says so
    long = apply(sc(promo_uplift_pct=10, promo_days=28), BASE, STOCK)
    assert long.demand_factor == pytest.approx(1.1) and long.effects[0].params["days_applied"] == 10
    # constant elasticity: price +10% with elasticity -1.5 gives demand 1.1 ** -1.5, and the price used for margins moves too
    p = apply(sc(price_change_pct=10, price_elasticity=-1.5), BASE, STOCK)
    assert p.demand_factor == pytest.approx(1.1 ** -1.5) and p.settings.price == pytest.approx(11)
    assert apply(sc(), BASE, STOCK).demand_factor == 1.0


def test_effects_multiply_rather_than_add():
    assert apply(sc(demand_change_pct=10, spike_pct=10, spike_days=10), BASE, STOCK).demand_factor == pytest.approx(1.21)


def test_delay_and_stock_reduction_change_the_copies_only():
    a = apply(sc(supplier_delay_days=4, stock_reduction_pct=25), BASE, STOCK)
    assert a.settings.lead_time_days == 7 and a.window_days == 14 and BASE.lead_time_days == 3
    assert a.stock["a"].on_hand == 75 and a.stock["a"].on_order == 20 and a.stock["b"].on_hand is None and STOCK["a"].on_hand == 100


def test_the_window_for_promotions_follows_a_delay():
    assert apply(sc(supplier_delay_days=10, promo_uplift_pct=50, promo_days=5), BASE, STOCK).demand_factor == pytest.approx(1 + 0.5 * 5 / 20)


@pytest.mark.parametrize("settings,kw,code", [
    (BASE, dict(price_change_pct=10), "elasticity_missing"),
    (BASE, dict(price_change_pct=10, price_elasticity=0.5), "elasticity_sign"),
    (BASE, dict(price_elasticity=-1), "elasticity_unused"),
    (InventorySettings(lead_time_days=3, unit_cost=6), dict(price_change_pct=10, price_elasticity=-1), "price_missing"),
    (BASE, dict(supplier_delay_days=20), "window_too_long"),
    (InventorySettings(mode="single_period", period_days=3, price=10, unit_cost=6), dict(supplier_delay_days=2), "delay_not_applicable"),
    (BASE, dict(promo_uplift_pct=20), "days_missing"),
    (BASE, dict(promo_days=3), "pct_missing"),
    (BASE, dict(price_change_pct=-45, price_elasticity=-1), "no_margin"),  # the price falls to 5.5, below the unit cost of 6
])
def test_scenarios_that_cannot_be_applied_honestly_are_refused(settings, kw, code):
    with pytest.raises(InventoryInputError) as e:
        apply(sc(**kw), settings, STOCK)
    assert e.value.code == code


def test_stock_reduction_needs_stock():
    with pytest.raises(InventoryInputError) as e:
        apply(sc(stock_reduction_pct=20), BASE, {})
    assert e.value.code == "stock_missing"


# ---- through the API ---------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def analysed():
    client = TestClient(create_app(serve_web=False))
    s = upload(client, weekly_csv(320))
    job = client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 14}).json()
    assert wait(client, job["id"])["state"] == "done"
    return client, s["id"]


COSTS = dict(lead_time_days=3, review_days=7, price=10, unit_cost=6, holding_cost_per_day=0.05)


def go(analysed, scenarios, **kw):
    client, ds = analysed
    r = client.post(f"/api/datasets/{ds}/scenarios", json={**COSTS, **kw, "scenarios": scenarios})
    assert r.status_code == 200, r.text
    return r.json()


def balanced(res, item=None):
    rows = res["items"]
    return {i["item"]: i["by_strategy"]["balanced"]["order"] for i in rows if i["status"] == "ok"} if item is None else None


def test_baseline_in_a_scenario_run_equals_the_plain_recommendation(analysed):
    client, ds = analysed
    plain = client.post(f"/api/datasets/{ds}/inventory", json=COSTS).json()
    out = go(analysed, [{"name": "up", "demand_change_pct": 25}, {"name": "slow", "supplier_delay_days": 3}])
    assert out["baseline"] == plain
    again = client.post(f"/api/datasets/{ds}/inventory", json=COSTS).json()
    assert again == plain  # running scenarios changed nothing for later requests


def test_an_empty_scenario_is_the_baseline(analysed):
    out = go(analysed, [{"name": "none"}])
    s = out["scenarios"][0]
    assert s["demand_factor"] == 1.0 and balanced(s["result"]) == balanced(out["baseline"])
    for item in s["result"]["items"]:
        kept = item["by_strategy"]["balanced"]["if_baseline_order"]
        assert kept["p_stockout"] == item["by_strategy"]["balanced"]["p_stockout"]


def test_more_demand_means_bigger_orders_and_the_old_order_runs_short_more_often(analysed):
    out = go(analysed, [{"name": "+25%", "demand_change_pct": 25}, {"name": "-25%", "demand_change_pct": -25}])
    base, up, down = balanced(out["baseline"]), balanced(out["scenarios"][0]["result"]), balanced(out["scenarios"][1]["result"])
    for k in base:
        assert down[k] < base[k] < up[k]
        assert up[k] == pytest.approx(base[k] * 1.25, rel=0.01)  # the quantile of scaled outcomes scales with them (no stock held)
    for i in out["scenarios"][0]["result"]["items"]:
        assert i["by_strategy"]["balanced"]["if_baseline_order"]["p_stockout"] > next(b for b in out["baseline"]["items"] if b["item"] == i["item"])["by_strategy"]["balanced"]["p_stockout"]
    kept = out["scenarios"][0]["comparison"]["if_baseline_order"]["balanced"]["expected_shortage"]
    assert kept["delta"] > 0
    kept_down = out["scenarios"][1]["comparison"]["if_baseline_order"]["balanced"]["expected_leftover"]
    assert kept_down["delta"] > 0  # ordering for normal demand when demand falls leaves more unsold


def test_a_supplier_delay_lengthens_cover_and_raises_the_order(analysed):
    out = go(analysed, [{"name": "late", "supplier_delay_days": 4}])
    s = out["scenarios"][0]
    assert s["window_days"] == 14 and out["baseline"]["window_days"] == 10
    base, late = balanced(out["baseline"]), balanced(s["result"])
    assert all(late[k] > base[k] for k in base)


def test_a_stock_reduction_adds_the_missing_units_to_the_order(analysed):
    client, ds = analysed
    items = [i["item"] for i in client.post(f"/api/datasets/{ds}/inventory", json=COSTS).json()["items"]]
    stock = {items[0]: {"on_hand": 40, "on_order": 0}}
    out = go(analysed, [{"name": "loss", "stock_reduction_pct": 50}], stock=stock)
    base = next(i for i in out["baseline"]["items"] if i["item"] == items[0])["by_strategy"]["balanced"]["order"]
    scen = next(i for i in out["scenarios"][0]["result"]["items"] if i["item"] == items[0])["by_strategy"]["balanced"]["order"]
    assert scen == pytest.approx(base + 20, abs=0.02)  # 20 fewer units on hand: 20 more to order, same target level


def test_a_price_rise_with_elastic_demand_lowers_demand_and_is_labelled_hypothetical(analysed):
    out = go(analysed, [{"name": "price up", "price_change_pct": 10, "price_elasticity": -1.5}])
    s = out["scenarios"][0]
    assert s["demand_factor"] == pytest.approx(1.1 ** -1.5, abs=1e-4) and "hypothetical" in out["notes"] and "not_validated" in out["notes"]
    assert s["result"]["calibration"] == [] and out["baseline"]["calibration"]  # only the baseline carries a measured track record
    assert {e["kind"] for e in s["effects"]} == {"price_change"} and s["effects"][0]["elasticity"] == -1.5


def test_scenario_results_do_not_depend_on_the_other_scenarios_in_the_request(analysed):
    spec = {"name": "x", "demand_change_pct": 15, "supplier_delay_days": 2}
    alone = go(analysed, [spec])["scenarios"][0]
    among = go(analysed, [{"name": "a", "demand_change_pct": 50}, spec, {"name": "b", "stock_reduction_pct": 10}])["scenarios"]
    assert among[1]["result"] == alone["result"] and among[1]["comparison"] == alone["comparison"]


def test_one_bad_scenario_does_not_stop_the_others(analysed):
    out = go(analysed, [{"name": "ok", "demand_change_pct": 10}, {"name": "bad", "price_change_pct": 10}, {"name": "long", "supplier_delay_days": 25}])
    ok, bad, long = out["scenarios"]
    assert "result" in ok and bad["error"]["code"] == "elasticity_missing" and long["error"]["code"] == "window_too_long"


def test_a_scenario_longer_than_the_forecast_is_reported_not_crashed(analysed):
    out = go(analysed, [{"name": "too far", "supplier_delay_days": 6}, {"name": "ok", "demand_change_pct": 5}])  # this replay forecast 14 days; 3 + 7 + 6 = 16
    assert out["scenarios"][0]["error"]["code"] == "beyond_forecast" and "result" in out["scenarios"][1]


def test_bad_baseline_is_refused_with_a_code(analysed):
    client, ds = analysed
    r = client.post(f"/api/datasets/{ds}/scenarios", json={"price": 10, "scenarios": [{"name": "x", "demand_change_pct": 5}]})
    assert r.status_code == 422 and r.json()["code"] == "lead_time_missing"


def test_requests_outside_the_allowed_ranges_are_rejected(analysed):
    client, ds = analysed
    for bad in ({"demand_change_pct": -100}, {"stock_reduction_pct": 120}, {"supplier_delay_days": 0}):
        assert client.post(f"/api/datasets/{ds}/scenarios", json={**COSTS, "scenarios": [{"name": "x", **bad}]}).status_code == 422
    assert client.post(f"/api/datasets/{ds}/scenarios", json={**COSTS, "scenarios": [{"name": "x"}] * 9}).status_code == 422
