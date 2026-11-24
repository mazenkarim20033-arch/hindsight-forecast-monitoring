"""One path through every feature, checking that they agree with each other: onboarding -> forecast -> orders -> scenarios -> health -> decision log -> outcome,
plus the older screens still answering on the same data. Each step's numbers are compared with another step's, not just checked for shape."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hindsight.app import api as api_module
from hindsight.app.api import create_app
from test_service_api import wait

SHAPE = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])
ITEMS = {"Milk": 40, "Bread": 80}
QTY = {k: np.maximum(0, np.rint(b * SHAPE[np.arange(340) % 7] * (1 + 0.07 * np.random.default_rng(i).standard_normal(340)))) for i, (k, b) in enumerate(ITEMS.items())}
COSTS = dict(lead_time_days=3, review_days=7, price=10, unit_cost=6, holding_cost_per_day=0.05)


def shop_csv(n: int) -> bytes:
    dates = pd.date_range("2022-01-01", periods=n)
    rows = ["date,item,qty,price,unit cost,stock on hand,stock on order"]
    for k in ITEMS:
        for i, d in enumerate(dates):
            rows.append(f"{d.date()},{k},{int(QTY[k][i])},10,6,{50 + (i % 40) + 20 * (k == 'Bread')},{25 if i == n - 1 else 0}")
    return "\n".join(rows).encode()


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("integration")
    mp = pytest.MonkeyPatch()
    mp.setattr(api_module, "ADAPTERS_BUILTIN", root / "builtin")
    mp.setattr(api_module, "ADAPTERS_SAVED", root / "saved")
    client = TestClient(create_app(serve_web=False, audit_db=root / "audit.sqlite"))
    yield client
    mp.undo()


def test_the_whole_path_agrees_with_itself(world):
    c = world
    # 1. Onboarding: the file's price, cost and stock columns are found and kept apart from sales.
    first = c.post("/api/datasets", files={"file": ("shop.csv", shop_csv(300), "text/csv")}).json()
    ds = first["id"]
    biz = first["report"]["business"]
    assert set(biz["columns"]) == {"price", "unit_cost", "on_hand", "on_order"} and first["detection"]["value"] == "qty"
    assert {i: v["price"] for i, v in biz["values"].items()} == {"Milk": 10.0, "Bread": 10.0}
    assert first["n_series"] == 2 and c.post(f"/api/datasets/{ds}/adapters", json={"name": "shop-export"}).status_code == 200

    # 2. Forecast on the cleaned data.
    job = c.post(f"/api/datasets/{ds}/analysis", json={"horizon": 14}).json()
    assert wait(c, job["id"])["state"] == "done"

    # 3. Orders, using the stock the file carried.
    stock = {i: {"on_hand": v["on_hand"], "on_order": v["on_order"]} for i, v in biz["values"].items()}
    inv = c.post(f"/api/datasets/{ds}/inventory", json={**COSTS, "stock": stock}).json()
    for it in inv["items"]:
        assert it["inventory_position"] == stock[it["item"]]["on_hand"] + stock[it["item"]]["on_order"]  # netted off exactly what the file said

    # 4. Scenarios share the optimizer: their baseline is the plain recommendation, and a rise in demand raises the order.
    sc = c.post(f"/api/datasets/{ds}/scenarios", json={**COSTS, "stock": stock, "scenarios": [{"name": "up", "demand_change_pct": 30}]}).json()
    assert sc["baseline"] == inv
    assert sc["scenarios"][0]["result"]["totals"]["balanced"]["order"] > inv["totals"]["balanced"]["order"]

    # 5. Health as of the last day of this file.
    health = c.post(f"/api/datasets/{ds}/health", json={}).json()
    assert health["as_of"] == "2022-10-27" and sum(health["counts"].values()) == 2

    # 6. The old screens still answer on the same data.
    for path in ("overview", "dashboard", "scorecard", "planner", "effects", "total"):
        assert c.get(f"/api/datasets/{ds}/{path}").status_code == 200, path

    # 7. A decision recorded from these inputs repeats the optimizer's numbers and carries the health status.
    rec = c.post(f"/api/datasets/{ds}/audit/decisions", json={**COSTS, "stock": stock, "strategy": "balanced", "note": "weekly order"}).json()
    p = rec["payload"]
    assert p["health"] == health["overall"]["status"] and p["dataset"]["as_of"] == health["as_of"]
    assert {i["item"]: i["chosen_order"] for i in p["items"]} == {i["item"]: i["by_strategy"]["balanced"]["order"] for i in inv["items"]}
    assert p["total_ordered"] == pytest.approx(inv["totals"]["balanced"]["order"], abs=0.02)

    # 8. Later the shop sends the same report with 40 more days: it is recognised, and the outcome matches the real sales.
    later = c.post("/api/datasets", files={"file": ("shop_later.csv", shop_csv(340), "text/csv")}).json()
    assert later["adapter"] == {"name": "shop-export", "description": "", "applied": True}
    review = c.post(f"/api/datasets/{later['id']}/audit/review").json()["decisions"]
    assert [r["status"] for r in review] == ["ready"]
    out = c.post(f"/api/datasets/{later['id']}/audit/outcomes", json={"decision_id": rec["id"]}).json()
    window = p["window_days"]
    for row in out["payload"]["items"]:
        assert row["actual"] == QTY[row["item"]][300:300 + window].sum()
        rec_item = next(i for i in p["items"] if i["item"] == row["item"])
        assert row["chosen"]["level"] == pytest.approx(rec_item["position"] + rec_item["chosen_order"], abs=0.02)
        assert row["chosen"]["shortage"] == pytest.approx(max(row["actual"] - row["chosen"]["level"], 0), abs=0.02)

    # 9. The log is intact and holds exactly what was written.
    assert c.get("/api/audit/verify").json() == {"ok": True, "n": 2, "bad_id": None, "reason": None}
    assert [e["kind"] for e in c.get("/api/audit/export").json()["events"]] == ["decision", "outcome"]
