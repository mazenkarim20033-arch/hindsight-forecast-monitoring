"""Decision Audit: the append-only log (protections and tamper detection), the outcome arithmetic, and the decision -> outcome flow through the API."""
import sqlite3
import threading

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hindsight.app.api import create_app
from hindsight.audit import outcome
from hindsight.audit.store import GENESIS, AuditError, AuditLog
from test_service_api import wait

# ---- the log -----------------------------------------------------------------------------------------------------------------------


@pytest.fixture()
def log(tmp_path):
    lg = AuditLog(tmp_path / "audit.sqlite")
    yield lg
    lg.close()


def test_the_file_is_created_only_when_first_used(tmp_path):
    lg = AuditLog(tmp_path / "sub" / "a.sqlite")
    assert not (tmp_path / "sub").exists()
    lg.append("decision", {"x": 1})
    assert (tmp_path / "sub" / "a.sqlite").exists()
    lg.close()


def test_events_chain_together_and_survive_a_restart(log, tmp_path):
    first = log.append("decision", {"note": "ملاحظة بالعربية", "n": 1})
    second = log.append("decision", {"n": 2})
    assert first["id"] == 1 and second["id"] == 2 and first["payload"]["note"] == "ملاحظة بالعربية"
    assert log.verify() == {"ok": True, "n": 2, "bad_id": None, "reason": None}
    raw = sqlite3.connect(log.path)
    assert raw.execute("SELECT prev_hash FROM events WHERE id = 1").fetchone()[0] == GENESIS
    assert raw.execute("SELECT prev_hash FROM events WHERE id = 2").fetchone()[0] == first["hash"]
    raw.close()
    again = AuditLog(log.path)
    assert [e["id"] for e in again.events()] == [2, 1] and again.verify()["ok"]  # newest first
    again.close()


def test_the_database_itself_refuses_updates_and_deletes(log):
    log.append("decision", {"n": 1})
    raw = sqlite3.connect(log.path)
    for sql in ("UPDATE events SET payload = '{}' WHERE id = 1", "DELETE FROM events WHERE id = 1"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute(sql)
    raw.close()
    assert log.get(1)["payload"] == {"n": 1}


def test_editing_a_record_after_removing_the_triggers_is_detected(log):
    for i in range(4):
        log.append("decision", {"n": i})
    raw = sqlite3.connect(log.path, isolation_level=None)
    raw.execute("DROP TRIGGER events_no_update")
    raw.execute("UPDATE events SET payload = '{\"n\":99}' WHERE id = 3")
    raw.close()
    v = log.verify()
    assert v["ok"] is False and v["bad_id"] == 3 and v["reason"] == "content"


def test_removing_a_record_is_detected(log):
    for i in range(4):
        log.append("decision", {"n": i})
    raw = sqlite3.connect(log.path, isolation_level=None)
    raw.execute("DROP TRIGGER events_no_delete")
    raw.execute("DELETE FROM events WHERE id = 2")
    raw.close()
    v = log.verify()
    assert v["ok"] is False and v["bad_id"] == 3 and v["reason"] == "link"


def test_one_outcome_per_decision_and_only_for_a_real_decision(log):
    d = log.append("decision", {"n": 1})
    o = log.append("outcome", {"result": 1}, ref=d["id"])
    assert log.outcome_of(d["id"])["id"] == o["id"]
    with pytest.raises(AuditError) as e:
        log.append("outcome", {"result": 2}, ref=d["id"])
    assert e.value.code == "outcome_exists"
    with pytest.raises(AuditError) as e:
        log.append("outcome", {"result": 2}, ref=999)
    assert e.value.code == "no_such_decision"
    with pytest.raises(AuditError) as e:
        log.append("outcome", {"result": 2}, ref=o["id"])  # an outcome is not a decision
    assert e.value.code == "no_such_decision"
    with pytest.raises(AuditError):
        log.append("note", {})
    assert log.verify()["ok"]


def test_many_writers_keep_the_chain_intact(log):
    def work(k):
        for i in range(15):
            log.append("decision", {"writer": k, "i": i})
    threads = [threading.Thread(target=work, args=(k,)) for k in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert log.verify() == {"ok": True, "n": 60, "bad_id": None, "reason": None}


# ---- outcome arithmetic ------------------------------------------------------------------------------------------------------------
def item(name="A", forecast=100.0, position=20.0, chosen=90.0, orders=(60.0, 90.0, 120.0)):
    return {"item": name, "forecast_demand": forecast, "position": position, "chosen_order": chosen,
            "by_strategy": {k: {"order": o} for k, o in zip(("conservative", "balanced", "high_availability"), orders)}}


def test_outcome_by_hand():
    ev = outcome.evaluate([item()], {"A": 130.0}, cu=4.0, co=1.0)
    c = ev["items"][0]["chosen"]  # stock 20 + 90 = 110 against demand 130
    assert c["level"] == 110 and c["shortage"] == 20 and c["leftover"] == 0 and c["stocked_out"] and c["cost"] == 80
    by = ev["items"][0]["by_strategy"]
    assert by["conservative"]["shortage"] == 50 and by["conservative"]["cost"] == 200  # level 80
    assert by["high_availability"]["leftover"] == 10 and by["high_availability"]["shortage"] == 0 and by["high_availability"]["cost"] == 10  # level 140
    assert ev["best_in_hindsight"] == "high_availability" and ev["cost_known"]
    assert ev["items"][0]["forecast_error"] == pytest.approx(-30 / 130, abs=1e-4) and ev["totals"]["cost"] == 80


def test_outcome_without_costs_gives_quantities_and_no_money():
    ev = outcome.evaluate([item()], {"A": 130.0}, cu=None, co=None)
    assert ev["cost_known"] is False and ev["best_in_hindsight"] is None and ev["totals"]["cost"] is None
    assert ev["items"][0]["chosen"]["cost"] is None and ev["items"][0]["chosen"]["shortage"] == 20


def test_outcome_totals_add_items_and_zero_sales_have_no_percentage_error():
    ev = outcome.evaluate([item("A"), item("B", forecast=50, position=0, chosen=60, orders=(40, 60, 80))], {"A": 100.0, "B": 0.0}, cu=3, co=1)
    assert ev["totals"]["actual"] == 100 and ev["totals"]["leftover"] == 10 + 60 and ev["items"][1]["forecast_error"] is None


# ---- through the API ---------------------------------------------------------------------------------------------------------------
SHAPE = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])
FULL = {name: np.maximum(0, np.rint(base * SHAPE[np.arange(340) % 7] * (1 + 0.08 * np.random.default_rng(j).standard_normal(340)))) for j, (name, base) in enumerate({"Milk": 40, "Bread": 80}.items())}


def csv_of(n: int, edit=None) -> bytes:
    rows = ["date,item,qty"]
    dates = pd.date_range("2022-01-01", periods=340)
    for name, v in FULL.items():
        vals = v.copy()
        if edit:
            vals = edit(name, vals)
        rows += [f"{d.date()},{name},{int(x)}" for d, x in zip(dates[:n], vals[:n])]
    return "\n".join(rows).encode()


COSTS = dict(lead_time_days=3, review_days=7, price=10, unit_cost=6, holding_cost_per_day=0.05)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    path = tmp_path_factory.mktemp("audit") / "audit.sqlite"
    client = TestClient(create_app(serve_web=False, audit_db=path))
    short = client.post("/api/datasets", files={"file": ("short.csv", csv_of(300), "text/csv")}).json()
    job = client.post(f"/api/datasets/{short['id']}/analysis", json={"horizon": 14}).json()
    assert wait(client, job["id"])["state"] == "done"
    return client, short["id"], path


def upload(client, raw, name):
    r = client.post("/api/datasets", files={"file": (name, raw, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_a_decision_is_recomputed_by_the_server_and_recorded_with_its_reasons(world):
    client, ds, _ = world
    plain = client.post(f"/api/datasets/{ds}/inventory", json=COSTS).json()
    r = client.post(f"/api/datasets/{ds}/audit/decisions", json={**COSTS, "strategy": "balanced", "orders": {"Milk": 123.0}, "note": "  Ordered more for the weekend  "})
    assert r.status_code == 200, r.text
    ev = r.json()
    p = ev["payload"]
    assert ev["kind"] == "decision" and len(ev["hash"]) == 64 and p["note"] == "Ordered more for the weekend"
    assert p["dataset"]["as_of"] == "2022-10-27" and p["dataset"]["as_of_index"] == 299 and p["window_days"] == 10 and p["cost_based"] and p["cu"] == 4
    by = {i["item"]: i for i in p["items"]}
    rec = {i["item"]: i["by_strategy"]["balanced"]["order"] for i in plain["items"]}
    assert by["Bread"]["chosen_order"] == rec["Bread"] and not by["Bread"]["overridden"]
    assert by["Milk"]["chosen_order"] == 123 and by["Milk"]["overridden"] and by["Milk"]["by_strategy"]["balanced"]["order"] == rec["Milk"]  # what was advised is kept beside what was done
    assert p["total_ordered"] == pytest.approx(123 + rec["Bread"], abs=0.02) and p["health"] in ("healthy", "watch", "action", "unknown") and p["scenario"] is None


def test_bad_decisions_are_refused_and_nothing_is_written(world):
    client, ds, _ = world
    before = len(client.get("/api/audit/events").json()["decisions"])
    assert client.post(f"/api/datasets/{ds}/audit/decisions", json={**COSTS, "strategy": "nonsense"}).status_code == 422
    r = client.post(f"/api/datasets/{ds}/audit/decisions", json={**COSTS, "orders": {"Nope": 5}})
    assert r.status_code == 422 and r.json()["code"] == "bad_override"
    assert client.post(f"/api/datasets/{ds}/audit/decisions", json={**COSTS, "orders": {"Milk": -1}}).json()["code"] == "bad_override"
    assert client.post(f"/api/datasets/{ds}/audit/decisions", json={"price": 10}).json()["code"] == "lead_time_missing"
    assert len(client.get("/api/audit/events").json()["decisions"]) == before


def test_a_decision_made_under_a_scenario_says_so(world):
    client, ds, _ = world
    r = client.post(f"/api/datasets/{ds}/audit/decisions", json={**COSTS, "scenario": {"name": "Promo", "demand_change_pct": 20}, "note": "planning for a promotion"})
    p = r.json()["payload"]
    assert p["scenario"] == {"name": "Promo", "demand_change_pct": 20} and p["demand_factor"] == 1.2
    plain = client.post(f"/api/datasets/{ds}/inventory", json=COSTS).json()
    base = {i["item"]: i["by_strategy"]["balanced"]["order"] for i in plain["items"]}
    assert all(i["by_strategy"]["balanced"]["order"] > base[i["item"]] for i in p["items"])


def test_the_decision_waits_for_its_window_then_the_outcome_follows_the_real_sales(world):
    client, ds, _ = world
    decisions = client.get("/api/audit/events").json()["decisions"]
    first = next(d for d in decisions if d["payload"]["scenario"] is None and d["payload"]["note"].startswith("Ordered"))
    same = client.post(f"/api/datasets/{ds}/audit/review").json()["decisions"]
    assert {d["status"] for d in same} == {"not_yet"} and same[0]["params"] == {"days": 10}  # the file ends on the day of the decision
    ref = client.post(f"/api/datasets/{ds}/audit/outcomes", json={"decision_id": first["id"]})
    assert ref.status_code == 422 and ref.json()["code"] == "not_yet"
    longer = upload(client, csv_of(340), "later.csv")
    rows = {d["decision_id"]: d for d in client.post(f"/api/datasets/{longer}/audit/review").json()["decisions"]}
    assert rows[first["id"]]["status"] == "ready"
    prev = rows[first["id"]]["preview"]
    assert prev["window"] == {"from": "2022-10-28", "to": "2022-11-06", "days": 10}
    milk = next(i for i in prev["items"] if i["item"] == "Milk")
    actual = float(FULL["Milk"][300:310].sum())
    assert milk["actual"] == actual
    level = first["payload"]["items"][0]["position"] + 123 if first["payload"]["items"][0]["item"] == "Milk" else None
    if level is not None:
        assert milk["chosen"]["shortage"] == pytest.approx(max(actual - level, 0), abs=0.01) and milk["chosen"]["leftover"] == pytest.approx(max(level - actual, 0), abs=0.01)
    saved = client.post(f"/api/datasets/{longer}/audit/outcomes", json={"decision_id": first["id"]})
    assert saved.status_code == 200, saved.text
    o = saved.json()
    assert o["kind"] == "outcome" and o["ref"] == first["id"] and o["payload"]["dataset"]["last_day"] == "2022-12-06" and "not_a_verdict" in o["payload"]["notes"]
    again = client.post(f"/api/datasets/{longer}/audit/outcomes", json={"decision_id": first["id"]})
    assert again.status_code == 422 and again.json()["code"] == "outcome_exists"
    assert next(d for d in client.post(f"/api/datasets/{longer}/audit/review").json()["decisions"] if d["decision_id"] == first["id"])["status"] == "recorded"
    listed = next(d for d in client.get("/api/audit/events").json()["decisions"] if d["id"] == first["id"])
    assert listed["outcome"]["id"] == o["id"]


def test_a_file_whose_history_differs_cannot_judge_the_decision(world):
    client, ds, _ = world
    decisions = client.get("/api/audit/events").json()["decisions"]
    target = next(d for d in decisions if d["payload"]["scenario"] is not None)
    restated = upload(client, csv_of(340, edit=lambda name, v: np.where(np.arange(340) == 10, v + 5, v)), "restated.csv")
    row = next(d for d in client.post(f"/api/datasets/{restated}/audit/review").json()["decisions"] if d["decision_id"] == target["id"])
    assert row["status"] == "different_data"
    n = len(client.get("/api/audit/events").json()["decisions"])
    r = client.post(f"/api/datasets/{restated}/audit/outcomes", json={"decision_id": target["id"]})
    assert r.status_code == 422 and r.json()["code"] == "different_data"
    missing = upload(client, "\n".join(["date,item,qty"] + [f"{d.date()},Milk,{int(x)}" for d, x in zip(pd.date_range('2022-01-01', periods=340), FULL['Milk'])]).encode(), "milk-only.csv")
    row = next(d for d in client.post(f"/api/datasets/{missing}/audit/review").json()["decisions"] if d["decision_id"] == target["id"])
    assert row["status"] == "items_missing"
    assert client.get("/api/audit/events").json()["verify"]["ok"] and len(client.get("/api/audit/events").json()["decisions"]) == n


def test_the_log_verifies_exports_and_detects_edits_made_outside_the_program(world):
    client, ds, path = world
    v = client.get("/api/audit/verify").json()
    assert v["ok"] and v["n"] == 3  # two decisions and one outcome; the refused requests wrote nothing
    export = client.get("/api/audit/export")
    assert "attachment" in export.headers["content-disposition"]
    body = export.json()
    assert body["verify"]["ok"] and [e["id"] for e in body["events"]] == sorted(e["id"] for e in body["events"])  # oldest first
    raw = sqlite3.connect(path, isolation_level=None)
    raw.execute("DROP TRIGGER events_no_update")
    raw.execute("UPDATE events SET payload = replace(payload, 'weekend', 'WEEKEND') WHERE id = 1")
    raw.close()
    bad = client.get("/api/audit/verify").json()
    assert bad["ok"] is False and bad["bad_id"] == 1


def test_the_log_is_owner_only(tmp_path):
    locked = TestClient(create_app(serve_web=False, owner_key="secret", audit_db=tmp_path / "a.sqlite"))
    for method, url in (("get", "/api/audit/events"), ("get", "/api/audit/verify"), ("get", "/api/audit/export"), ("post", "/api/datasets/x/audit/review"),
                        ("post", "/api/datasets/x/audit/decisions"), ("post", "/api/datasets/x/audit/outcomes")):
        r = getattr(locked, method)(url, **({"json": {"decision_id": 1}} if method == "post" else {}))
        assert r.status_code == 403, (url, r.status_code)
    assert locked.get("/api/audit/events", headers={"X-Owner-Key": "secret"}).status_code == 200
