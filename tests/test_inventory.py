"""The Decision Optimizer: the arithmetic against textbook results, the input rules, and the API on a real replay."""
import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.stats import norm

from hindsight.app.api import create_app
from hindsight.inventory import newsvendor as nv
from hindsight.inventory.inputs import InventoryInputError, InventorySettings, resolve
from test_service_api import upload, wait, weekly_csv

UNIFORM = np.arange(1, 101, dtype=float)  # demand 1..100, each equally likely: every quantity below can be checked by hand


# ---- arithmetic --------------------------------------------------------------------------------------------------------------------
def test_critical_ratio():
    assert nv.critical_ratio(3, 1) == pytest.approx(0.75)
    assert nv.critical_ratio(1, 1) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        nv.critical_ratio(0, 1)


def test_newsvendor_quantile_is_the_cheapest_stock_level():
    """The result the method rests on: among all stock levels, the demand quantile at cu/(cu+co) has the lowest expected cost."""
    for cu, co in [(3, 1), (1, 1), (1, 4), (9, 1)]:
        q = nv.critical_ratio(cu, co)
        costs = []
        for level in range(0, 101):
            o = nv.outcomes(UNIFORM, level)
            costs.append(cu * o["expected_shortage"] + co * o["expected_leftover"])
        assert costs[int(nv.quantile(UNIFORM, q))] == pytest.approx(min(costs))


def test_hand_computed_outcomes():
    o = nv.outcomes(UNIFORM, 75)
    assert o["expected_leftover"] == pytest.approx(27.75)  # sum over demand 1..74 of (75-d), divided by 100
    assert o["expected_shortage"] == pytest.approx(3.25)  # sum over demand 76..100 of (d-75), divided by 100
    assert o["p_stockout"] == pytest.approx(0.25)
    assert o["expected_sales"] + o["expected_shortage"] == pytest.approx(UNIFORM.mean())
    assert o["fill_rate"] == pytest.approx(1 - 3.25 / 50.5)


def test_normal_demand_matches_the_closed_form():
    d = np.random.default_rng(1).normal(100, 20, 200_000)
    for q in (0.5, 0.8, 0.95):
        assert nv.quantile(d, q) == pytest.approx(norm.ppf(q, 100, 20), abs=0.4)
    o = nv.outcomes(d, nv.quantile(d, 0.9))
    assert o["p_stockout"] == pytest.approx(0.1, abs=0.002)


def test_higher_underage_cost_means_more_stock_and_a_higher_service_level():
    levels = [nv.quantile(UNIFORM, nv.critical_ratio(cu, 2)) for cu in (1, 2, 4, 8)]
    assert levels == sorted(levels) and levels[0] < levels[-1]
    assert [nv.quantile(UNIFORM, q) for q in (0.8, 0.9, 0.95)] == [80, 90, 95]


def test_inventory_position_is_netted_off_the_order():
    assert nv.plan(UNIFORM, 0.75, position=0)["order"] == 75
    p = nv.plan(UNIFORM, 0.75, position=40)
    assert p["order"] == 35 and p["level"] == 75
    over = nv.plan(UNIFORM, 0.75, position=90)  # already holding more than the target: order nothing, and say what that stock means
    assert over["order"] == 0 and over["level"] == 90
    assert over["expected_shortage"] < nv.plan(UNIFORM, 0.75, position=0)["expected_shortage"]


def test_minimum_order_and_multiples():
    assert nv.round_order(35, min_order_qty=50) == 50
    assert nv.round_order(35, multiple=12) == 36
    assert nv.round_order(35, min_order_qty=50, multiple=12) == 60
    assert nv.round_order(36, multiple=12) == 36  # an exact multiple is not pushed up
    assert nv.round_order(0) == 0 and nv.round_order(-5, min_order_qty=50) == 0  # no need, no minimum order
    p = nv.plan(UNIFORM, 0.75, 40, min_order_qty=50, multiple=12)
    assert p["order"] == 60 and p["level"] == 100  # rounding up can only raise the service level


def test_edge_cases():
    zero = nv.outcomes(np.zeros(30), 10)
    assert zero["expected_shortage"] == 0 and zero["fill_rate"] == 1.0 and zero["expected_leftover"] == 10
    const = nv.plan(np.full(30, 12.0), 0.95, 0)
    assert const["order"] == 12 and const["p_stockout"] == 0
    assert nv.plan(UNIFORM, 0.0, 0)["order_up_to"] == 1 and nv.plan(UNIFORM, 1.0, 0)["order_up_to"] == 100


def test_money():
    o = nv.outcomes(UNIFORM, 75)
    m = nv.money(o, 75, cu=4, co=0.35, price=10, unit_cost=6, salvage=0, holding_cycle=0.35)
    assert m["expected_stockout_cost"] == pytest.approx(4 * 3.25) and m["expected_excess_cost"] == pytest.approx(0.35 * 27.75)
    assert m["expected_cost"] == pytest.approx(13 + 9.7125) and m["investment"] == 450
    assert m["expected_profit"] == pytest.approx(10 * o["expected_sales"] - 450 - 0.35 * 27.75)
    assert all(v is None for v in nv.money(o, 75, cu=None, co=None, price=None, unit_cost=None, salvage=0, holding_cycle=0).values())


# ---- inputs ------------------------------------------------------------------------------------------------------------------------
def sources(r):
    return {a.field: a.source for a in r.assumptions}


def test_costs_give_cost_based_levels_in_order():
    r = resolve(InventorySettings(lead_time_days=3, price=10, unit_cost=6, holding_cost_per_day=0.05))
    assert r.cost_based and r.window_days == 10  # 3 days lead time + the default 7-day review
    assert r.cu == pytest.approx(4) and r.co == pytest.approx(0.35)
    assert r.levels["balanced"] == pytest.approx(4 / 4.35)
    assert r.levels["conservative"] < r.levels["balanced"] <= r.levels["high_availability"]
    assert sources(r)["review_days"] == "default" and sources(r)["lead_time_days"] == "user"


def test_single_period_uses_cost_less_salvage():
    r = resolve(InventorySettings(mode="single_period", period_days=2, price=10, unit_cost=6, salvage_value=2))
    assert (r.cu, r.co) == (4, 4) and r.levels["balanced"] == pytest.approx(0.5) and r.window_days == 2
    assert sources(r)["stockout_penalty"] == "default"


def test_missing_costs_are_reported_never_invented():
    r = resolve(InventorySettings(lead_time_days=2))
    assert not r.cost_based and r.cu is None and set(r.missing) == {"price", "unit_cost"}
    assert r.levels["balanced"] == 0.90 and sources(r)["level_balanced"] == "default"
    r2 = resolve(InventorySettings(lead_time_days=2, price=10, unit_cost=6))  # no holding cost: periodic review cannot weigh leftovers
    assert not r2.cost_based and "holding_cost_per_day" in r2.missing


@pytest.mark.parametrize("kw,code", [
    (dict(), "lead_time_missing"),
    (dict(lead_time_days=25, review_days=7), "window_too_long"),
    (dict(lead_time_days=1, price=5, unit_cost=6, holding_cost_per_day=0.1), "no_margin"),
    (dict(lead_time_days=1, price=10, unit_cost=6, salvage_value=7), "salvage_above_cost"),
    (dict(mode="single_period"), "period_missing"),
    (dict(lead_time_days=1, price=10, unit_cost=6, holding_cost_per_day=0), "no_overage_cost"),
])
def test_unusable_inputs_are_refused_with_a_code(kw, code):
    with pytest.raises(InventoryInputError) as e:
        resolve(InventorySettings(**kw))
    assert e.value.code == code


# ---- through the API, on a real replay ---------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def analysed():
    client = TestClient(create_app(serve_web=False))
    s = upload(client, weekly_csv(320))
    job = client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 14}).json()
    assert wait(client, job["id"])["state"] == "done"
    return client, s["id"]


COSTS = dict(lead_time_days=3, review_days=7, price=10, unit_cost=6, holding_cost_per_day=0.05)


def ask(analysed, **kw):
    client, ds = analysed
    return client.post(f"/api/datasets/{ds}/inventory", json=kw)


def test_recommendation_has_every_required_output(analysed):
    r = ask(analysed, **COSTS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cost_based"] and body["window_days"] == 10
    for item in body["items"]:
        assert item["status"] == "ok" and item["forecast_demand"] > 0 and item["inventory_position"] is None and "stock_missing" in item["flags"]
        c, b, h = (item["by_strategy"][k] for k in ("conservative", "balanced", "high_availability"))
        assert c["order"] <= b["order"] <= h["order"]  # computed from the forecast, not fixed quantities
        assert c["p_stockout"] >= b["p_stockout"] >= h["p_stockout"]
        assert c["expected_leftover"] <= b["expected_leftover"] <= h["expected_leftover"]
        assert c["investment"] <= b["investment"] <= h["investment"]
        for k in ("expected_leftover", "expected_shortage", "expected_excess_cost", "expected_stockout_cost", "expected_cost", "expected_profit", "fill_rate"):
            assert b[k] is not None
    assert {x["field"] for x in body["assumptions"]} >= {"lead_time_days", "price", "unit_cost", "service_level"}
    assert "not_guarantee" in body["notes"]


def test_stock_is_netted_and_flagged(analysed):
    base = {i["item"]: i for i in ask(analysed, **COSTS).json()["items"]}
    item = next(iter(base))
    r = ask(analysed, **COSTS, stock={item: {"on_hand": 30, "on_order": 10}}).json()
    row = next(i for i in r["items"] if i["item"] == item)
    assert row["inventory_position"] == 40 and row["flags"] == []
    gross = base[item]["by_strategy"]["balanced"]["order"]
    assert row["by_strategy"]["balanced"]["order"] == pytest.approx(gross - 40, abs=0.02)
    huge = ask(analysed, **COSTS, stock={item: {"on_hand": 1e6}}).json()
    assert next(i for i in huge["items"] if i["item"] == item)["by_strategy"]["balanced"]["order"] == 0
    assert next(i for i in ask(analysed, **COSTS, stock={item: {"on_hand": 5}}).json()["items"] if i["item"] == item)["flags"] == ["on_order_missing"]


def test_supplier_rules_apply_to_every_strategy(analysed):
    r = ask(analysed, **COSTS, min_order_qty=500, order_multiple=24).json()
    for item in r["items"]:
        for s in item["by_strategy"].values():
            assert s["order"] == 0 or (s["order"] >= 500 and s["order"] % 24 == 0)


def test_longer_lead_time_needs_more_stock(analysed):
    short = {i["item"]: i["by_strategy"]["balanced"]["order_up_to"] for i in ask(analysed, **{**COSTS, "lead_time_days": 0}).json()["items"]}
    long = {i["item"]: i["by_strategy"]["balanced"]["order_up_to"] for i in ask(analysed, **{**COSTS, "lead_time_days": 6}).json()["items"]}
    assert all(long[k] > short[k] for k in short)


def test_without_costs_there_is_no_money_and_the_levels_are_labelled_defaults(analysed):
    body = ask(analysed, lead_time_days=3).json()
    assert not body["cost_based"] and set(body["missing"]) == {"price", "unit_cost"} and "no_costs" in body["notes"]
    b = body["items"][0]["by_strategy"]["balanced"]
    assert b["investment"] is None and b["expected_cost"] is None and b["order"] > 0 and b["service_target"] == 0.9


def test_bad_requests_get_a_code(analysed):
    r = ask(analysed)
    assert r.status_code == 422 and r.json()["code"] == "lead_time_missing"
    r = ask(analysed, lead_time_days=10, review_days=7)  # 17 days against a 14-day forecast
    assert r.status_code == 422 and "14" in r.json()["detail"]
    assert ask(analysed, lead_time_days=3, price=-1).status_code == 422
    assert ask(analysed, lead_time_days=3, method="nope").status_code == 422


def test_a_service_level_held_on_the_replayed_past(analysed):
    """The distribution is an approximation, so check it: the share of past periods whose demand stayed within the order-up-to level
    should be near the target. This is the evidence behind the service levels shown, not a guarantee for the future."""
    cal = {c["strategy"]: c for c in ask(analysed, **COSTS).json()["calibration"]}
    for c in cal.values():
        assert c["n_cases"] > 100
        assert abs(c["realized"] - c["target"]) < 0.10, c


def test_the_forecast_is_not_changed_by_asking(analysed):
    client, ds = analysed
    before = client.get(f"/api/datasets/{ds}/dashboard").json()
    ask(analysed, **COSTS)
    ask(analysed, **{**COSTS, "lead_time_days": 6}, stock={"Milk": {"on_hand": 99}})
    assert client.get(f"/api/datasets/{ds}/dashboard").json() == before
