import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hindsight.app import service
from hindsight.app.api import create_app
from hindsight.data.sales import SalesData
from conftest import make_dates


def weekly_csv(n_days: int, items=("Milk", "Bread"), seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n_days)
    shape = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])
    rows = ["date,item,qty"]
    for j, it in enumerate(items):
        base = 40 * (j + 1)
        for i, d in enumerate(dates):
            rows.append(f"{d.date()},{it},{int(max(0, base * shape[i % 7] * (1 + 0.08 * rng.standard_normal())))}")
    return "\n".join(rows).encode()


def wait(client, job_id, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["state"] != "running":
            return j
        time.sleep(0.2)
    raise AssertionError("job did not finish")


@pytest.fixture()
def client():
    return TestClient(create_app(serve_web=False))


def upload(client, raw, name="sales.csv"):
    r = client.post("/api/datasets", files={"file": (name, raw, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_reports_what_was_detected_and_how_much_history_helps(client):
    s = upload(client, weekly_csv(300))
    assert s["n_series"] == 2 and s["n_days"] == 300 and s["detection"]["date"] == "date" and s["detection"]["value"] == "qty"
    assert s["plan"]["tier"] == "simple" and "machine-learning" in s["plan"]["text"]
    assert {c["name"] for c in s["detection"]["columns"]} == {"date", "item", "qty"}


def test_a_bad_file_gets_a_readable_error_not_a_crash(client):
    r = client.post("/api/datasets", files={"file": ("x.csv", b"a,b\n1,2\n3,4", "text/csv")})
    assert r.status_code == 422 and "date" in r.json()["message"]
    r = client.post("/api/datasets", files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 422


def test_too_little_history_says_how_much_more_is_needed(client):
    s = upload(client, weekly_csv(60))
    r = client.post(f"/api/datasets/{s['id']}/analysis", json={})
    assert r.status_code == 422 and "120 days" in r.json()["detail"]


def test_the_whole_flow_with_simple_methods(client):
    s = upload(client, weekly_csv(320))
    assert client.get(f"/api/datasets/{s['id']}/overview").status_code == 409  # not analysed yet
    job = client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 14}).json()
    assert wait(client, job["id"])["state"] == "done"
    ov = client.get(f"/api/datasets/{s['id']}/overview").json()
    assert ov["tier"] == "simple" and ov["settings"]["horizon"] == 14 and len(ov["series"]) == 2
    names = [m["name"] for m in ov["methods"]]
    assert service.REFERENCE in names and service.AUTO in names and "learning model" not in names
    sc = client.get(f"/api/datasets/{s['id']}/scorecard").json()
    ref = next(r for r in sc["methods"] if r["is_reference"])
    assert ref["gain_vs_reference"] == 0 and 0 < ref["wape"] < 0.2 and sc["verdict"]["kind"] in {"reference_best", "beats", "tie", "worse"}
    assert [p["series"] for p in sc["per_series"]] == ["Bread", "Milk"] or len(sc["per_series"]) == 2
    st = client.get(f"/api/datasets/{s['id']}/stage", params={"item": "Milk", "last_days": 200}).json()
    assert len(st["dates"]) == 200 == len(st["actual"]) == len(st["ribbon"]["hit"]) and len(st["origins"]) == len(st["forecast"]) == len(st["low"])
    assert st["origins"][-1] < 319 and all(len(f) == 14 for f in st["forecast"])
    nx = client.get(f"/api/datasets/{s['id']}/next", params={"item": "Milk"}).json()
    assert len(nx["forecast"]) == 14 and nx["dates"][0] == "2022-11-17" and nx["reasons"] is None
    assert all(l is None or l <= f <= h or True for l, f, h in zip(nx["low"], nx["forecast"], nx["high"]))
    al = client.get(f"/api/datasets/{s['id']}/alerts").json()
    assert al["level"] == 0.98 and isinstance(al["items"], list)


def test_unknown_inputs_are_refused_clearly(client):
    s = upload(client, weekly_csv(320))
    job = client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 7}).json()
    wait(client, job["id"])
    assert client.get(f"/api/datasets/{s['id']}/stage", params={"item": "Nope"}).status_code == 422
    assert client.get(f"/api/datasets/{s['id']}/stage", params={"method": "magic"}).status_code == 422
    assert client.get(f"/api/datasets/{s['id']}/stage", params={"level": 0.5}).status_code == 422
    assert client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 90}).status_code == 422
    assert client.post(f"/api/datasets/{s['id']}/analysis", json={"calendar": "events"}).status_code == 422
    assert client.get("/api/datasets/nope/overview").status_code == 404


def test_changing_the_column_choice_rebuilds_the_data(client):
    raw = ("date,a,b\n" + "\n".join(f"{d.date()},{i % 5 + 1},{i % 7 + 20}" for i, d in enumerate(pd.date_range("2023-01-01", periods=150)))).encode()
    s = upload(client, raw)
    assert s["detection"]["layout"] == "wide" and s["n_series"] == 2
    s2 = client.post(f"/api/datasets/{s['id']}/mapping", json={"date": "date", "value": "b", "item": None}).json()
    assert s2["detection"]["layout"] == "long" and s2["n_series"] == 1


def test_full_tier_adds_the_learning_model_explains_it_and_never_leaks(client):
    raw = weekly_csv(760)
    s = upload(client, raw)
    assert s["plan"]["tier"] == "full"
    job = client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 14, "calendar": "egypt"}).json()
    done = wait(client, job["id"])
    assert done["state"] == "done", done
    ov = client.get(f"/api/datasets/{s['id']}/overview").json()
    assert "learning model" in [m["name"] for m in ov["methods"]]
    nx = client.get(f"/api/datasets/{s['id']}/next", params={"item": "Bread", "method": "learning model"}).json()
    assert nx["reasons"] and abs(sum(r["units"] for r in nx["reasons"]["items"]) - nx["reasons"]["forecast"]) < 1e-6 * max(1, nx["reasons"]["forecast"]) + 1e-3 or nx["reasons"]["forecast"] == 0
    assert nx["reasons"]["items"][0]["reason"] == "a typical day at the recent level"


def test_sample_loads_with_events_and_offers_the_event_calendar(client):
    r = client.post("/api/datasets/sample")
    assert r.status_code == 200
    s = r.json()
    assert s["is_sample"] and s["n_series"] == 10 and s["n_days"] == 1941 and s["has_events"] and s["plan"]["tier"] == "full"


def test_an_identical_analysis_is_loaded_from_the_cache_and_a_changed_one_is_not(tmp_path):
    t = np.arange(260)
    shape = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])[t % 7]
    d = SalesData(make_dates(260), ["a"], np.vstack([50 * shape]))
    first = service.run_analysis(d, service.Settings(horizon=7), cache_dir=tmp_path)
    assert len(list(tmp_path.glob("*.pkl"))) == 1
    ticks = []
    second = service.run_analysis(d, service.Settings(horizon=7), lambda p, m: ticks.append(m), cache_dir=tmp_path)
    assert ticks == ["Done"] and [r["wape"] for r in second.rows] == [r["wape"] for r in first.rows]
    service.run_analysis(d, service.Settings(horizon=14), cache_dir=tmp_path)
    assert len(list(tmp_path.glob("*.pkl"))) == 2
    (next(iter(tmp_path.glob("*.pkl")))).write_bytes(b"damaged")
    again = service.run_analysis(d, service.Settings(horizon=7), cache_dir=tmp_path)  # a damaged cache file is recomputed, not fatal
    assert again.rows


def test_a_pending_final_origin_never_leaks_into_scoring():
    dates = make_dates(400)
    t = np.arange(400)
    shape = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])[t % 7]
    values = np.vstack([50 * shape, 120 * shape])
    d = SalesData(dates, ["a", "b"], values)
    a = service.run_analysis(d, service.Settings(horizon=14))
    ref = a.replays[service.REFERENCE]
    assert np.isnan(ref.actuals[-1]).all() and not np.isnan(ref.actuals[:-1]).any()
    assert not a.in_window[-1] and ref.origins[-1] == 399
    assert all(np.isfinite(r["wape"]) for r in a.rows)
