"""Forecast health: drift measures, status rules, leakage-freedom, detection of an injected change, and the API."""
import copy

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hindsight.app import health_service, service
from hindsight.app.api import create_app
from hindsight.data.sales import SalesData
from hindsight.monitoring import drift
from hindsight.monitoring.rules import Thresholds, grade_high, grade_low, worst
from test_service_api import upload, wait, weekly_csv

SHAPE = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])


def synth(n: int, shift_at: int | None = None, factor: float = 1.5, seed: int = 0, items=("Milk", "Bread")) -> SalesData:
    """Weekly-pattern sales with noise. If `shift_at` is given, the FIRST item changes level from that day on; the others are untouched."""
    rng = np.random.default_rng(seed)
    rows = []
    for j in range(len(items)):
        base = 40 * (j + 1) * SHAPE[np.arange(n) % 7] * (1 + 0.08 * rng.standard_normal(n))
        if j == 0 and shift_at is not None:
            base[shift_at:] *= factor
        rows.append(np.maximum(0, np.rint(base)))
    return SalesData(pd.date_range("2022-01-01", periods=n), list(items), np.array(rows))


def analyse(data: SalesData, horizon: int = 14) -> service.Analysis:
    return service.run_analysis(data, service.Settings(horizon=horizon))


# ---- drift measures ----------------------------------------------------------------------------------------------------------------
def test_psi_is_near_zero_for_the_same_distribution_and_large_for_a_shift():
    rng = np.random.default_rng(0)
    ref, same, moved = rng.normal(100, 10, 2000), rng.normal(100, 10, 500), rng.normal(130, 10, 500)
    assert drift.psi(ref, same) < 0.05
    assert drift.psi(ref, moved) > 1.0
    assert drift.psi(ref, moved) > drift.psi(ref, rng.normal(105, 10, 500))  # a bigger shift scores higher


def test_psi_and_ks_need_enough_values_and_survive_ties():
    assert drift.psi(np.arange(10.0), np.arange(100.0)) is None and drift.ks(np.arange(100.0), np.arange(10.0)) is None
    zeros = np.zeros(300)
    assert drift.psi(zeros, zeros) == pytest.approx(0.0, abs=1e-9)  # a constant series: no usable quantiles, no crash
    assert drift.psi(zeros, np.ones(100)) > 1.0
    mostly_zero = np.r_[np.zeros(200), np.arange(1, 101.0)]
    assert drift.psi(mostly_zero, mostly_zero) == pytest.approx(0.0, abs=1e-9)


def test_ks_detects_a_shift_with_a_p_value():
    rng = np.random.default_rng(1)
    stat, p = drift.ks(rng.normal(0, 1, 500), rng.normal(1, 1, 500))
    assert stat > 0.3 and p < 1e-6
    assert drift.ks(rng.normal(0, 1, 500), rng.normal(0, 1, 500))[1] > 0.01


# ---- rules -------------------------------------------------------------------------------------------------------------------------
def test_grading_rules():
    assert [grade_high(v, 1.25, 1.5) for v in (1.0, 1.3, 1.6)] == ["healthy", "watch", "action"]
    assert [grade_low(v, 0.7, 0.55) for v in (0.8, 0.6, 0.5)] == ["healthy", "watch", "action"]
    assert grade_high(None, 1, 2) == "unknown" and grade_high(float("nan"), 1, 2) == "unknown" and grade_low(None, 1, 2) == "unknown"
    assert worst(["healthy", "unknown", "watch"]) == "watch" and worst(["unknown"]) == "unknown" and worst(["healthy", "action", "watch"]) == "action"


# ---- on a real replay --------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def stable():
    return analyse(synth(640))


def test_a_stable_series_is_mostly_healthy_and_every_signal_is_reported(stable):
    h = health_service.health(stable)
    assert h["overall"]["status"] in ("healthy", "watch") and h["counts"]["action"] == 0
    for item in h["items"]:
        assert {s["key"] for s in item["signals"]} == {"accuracy", "vs_simple", "bias", "coverage", "drift"}
    assert h["windows"]["n_recent"] == 8 and h["windows"]["n_earlier"] >= 20 and h["timeline"]
    assert set(h["thresholds"]) == set(Thresholds.__dataclass_fields__)


def test_drift_is_shown_but_never_changes_the_status(stable):
    h = health_service.health(stable, T=Thresholds(psi_watch=-1.0))  # every item now counts as "shifted"
    assert all(next(s for s in i["signals"] if s["key"] == "drift")["status"] == "watch" for i in h["items"])
    base = health_service.health(stable)
    assert [i["status"] for i in h["items"]] == [i["status"] for i in base["items"]]


def test_the_reference_method_is_not_compared_with_itself(stable):
    h = health_service.health(stable, method=service.REFERENCE)
    assert all("vs_simple" not in {s["key"] for s in i["signals"]} for i in h["items"])


def test_nothing_after_the_chosen_day_is_used(stable):
    """The status as of day D must not move if everything that happened after D is rewritten."""
    day = stable.data.n_days - 120
    expected = health_service.health(stable, day=day)
    h = stable.settings.horizon
    other = copy.deepcopy(stable)
    for r in list(other.replays.values()) + [ir.replay for ir in other.ranges.values()]:
        late = r.origins + h > day
        r.actuals[late] = 1e9
    other.data.values[:, day + 1:] = 1e9
    assert health_service.health(other, day=day) == expected
    assert expected["as_of"] == str(stable.data.dates[day].date())
    assert all(t["known"] <= expected["as_of"] for t in expected["timeline"])
    assert expected["windows"]["recent_to"] <= expected["as_of"]


def test_too_little_history_gives_unknown_rather_than_a_guess(stable):
    h = health_service.health(stable, day=stable.data.n_days - 1 - 400)
    assert h["overall"]["status"] in ("unknown", "healthy", "watch", "action")
    early = health_service.health(stable, day=140)  # fewer than 20 earlier replay dates exist
    assert early["overall"]["status"] == "unknown" and all(i["status"] == "unknown" for i in early["items"])


def test_an_injected_level_change_is_caught_and_the_untouched_item_stays_quiet():
    """Detection check: one item's sales rise by 50% on a known day. The monitor must leave 'healthy' for that item soon after, and must not
    raise 'action' for the item that did not change *under a fixed method*. (Several seeds, so one lucky draw cannot pass this.) Under "best method
    so far" the choice of method is shared by all items, so one item's change can make the others look worse too: that is documented, not tested away."""
    delays, quiet = [], []
    for seed in range(5):
        data = synth(640, shift_at=480, factor=1.5, seed=seed)
        a = analyse(data)
        first = None
        for day in range(480, 600):
            h = health_service.health(a, day=day)
            if first is None and h["items"][0]["status"] != "healthy":
                first = day - 480
        delays.append(first)
        quiet.append(all(health_service.health(a, service.REFERENCE, day=day)["items"][1]["status"] != "action" for day in range(480, 600, 5)))
    assert all(d is not None for d in delays), delays
    assert max(delays) <= 45, delays  # within about six weeks of the change, every time
    assert all(quiet)


def test_a_stable_series_rarely_raises_action():
    """False alarms: over every fifth day of stable synthetic data, 'action' should be rare."""
    a = analyse(synth(700, seed=11))
    statuses = [i["status"] for day in range(300, 690, 5) for i in health_service.health(a, day=day)["items"]]
    counts = {k: statuses.count(k) for k in set(statuses)}
    assert statuses.count("action") / len(statuses) < 0.10 and statuses.count("watch") / len(statuses) < 0.35, counts


# ---- API ---------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def served():
    client = TestClient(create_app(serve_web=False))
    s = upload(client, weekly_csv(400))
    job = client.post(f"/api/datasets/{s['id']}/analysis", json={"horizon": 14}).json()
    assert wait(client, job["id"])["state"] == "done"
    return client, s["id"]


def test_health_endpoint_and_threshold_overrides(served):
    client, ds = served
    r = client.post(f"/api/datasets/{ds}/health", json={})
    assert r.status_code == 200, r.text
    base = r.json()
    assert base["overall"]["status"] in ("healthy", "watch", "action", "unknown") and "not_prediction" in base["notes"]
    strict = client.post(f"/api/datasets/{ds}/health", json={"thresholds": {"wape_ratio_watch": 0.01, "wape_ratio_action": 0.02}}).json()
    assert strict["overall"]["status"] == "action" and strict["thresholds"]["wape_ratio_watch"] == 0.01
    assert client.post(f"/api/datasets/{ds}/health", json={"thresholds": {"nonsense": 1}}).status_code == 422
    assert client.post(f"/api/datasets/{ds}/health", json={"method": "no such method"}).status_code == 422


def test_challenger_needs_two_years_and_says_why(served):
    client, ds = served
    r = client.post(f"/api/datasets/{ds}/health/challenger", json={})
    assert r.status_code == 422 and r.json()["code"] == "needs_full_tier"


def test_challenger_is_evaluated_on_the_past_and_never_deployed():
    a = analyse(synth(800, seed=3), horizon=14)
    assert a.plan.tier == "full"
    before = (list(a.replays), a.replays[service.AUTO].forecasts.copy())
    c = health_service.challenger(a, k=6)
    assert c["deployed"] is False and c["verdict"] in ("promote_candidate", "keep_current", "inconclusive") and c["n_dates"] == 6
    assert c["gain_ci95"][0] <= c["gain"] <= c["gain_ci95"][1] and c["challenger"]["wape"] > 0 and c["from"] < c["to"] <= str(a.data.dates[-1].date())
    assert {"challenger_never_deployed", "challenger_small_sample"} <= set(c["notes"])
    assert list(a.replays) == before[0] and np.array_equal(a.replays[service.AUTO].forecasts, before[1])  # asking changed nothing about what the app forecasts
