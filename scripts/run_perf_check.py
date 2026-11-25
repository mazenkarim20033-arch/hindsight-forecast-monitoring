"""How long do the decision features take? Writes reports/performance.md.

Two cases: the 100-item M5 sample (full analysis, loaded from the cache the app keeps) and a made-up file of 100 items over 500 days (the largest
the app accepts; a simple-tier analysis, since 500 days is under two years). Each call is timed three times and the median is reported. This
measures the computer it runs on: read the numbers as orders of magnitude."""
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from hindsight.app import audit_service, health_service, inventory_service, scenario_service, service  # noqa: E402
from hindsight.app.api import CACHE_DIR, load_sample  # noqa: E402
from hindsight.audit.store import AuditLog  # noqa: E402
from hindsight.data.sales import SalesData  # noqa: E402
from hindsight.inventory.inputs import InventorySettings  # noqa: E402
from hindsight.scenarios.apply import Scenario  # noqa: E402

SETTINGS = InventorySettings(lead_time_days=3, review_days=7, price=10, unit_cost=6, holding_cost_per_day=0.05)
SCEN = [Scenario(name="up", demand_change_pct=20), Scenario(name="late", supplier_delay_days=5), Scenario(name="promo", promo_uplift_pct=40, promo_days=3)]


def med(fn, n=3) -> float:
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return float(np.median(ts))


def measure(label: str, a: service.Analysis, with_challenger: bool) -> list[str]:
    log = AuditLog(Path(tempfile.mkdtemp()) / "a.sqlite")
    rows = {
        "Order recommendation (3 options, all items, with track-record table)": med(lambda: inventory_service.recommend(a, SETTINGS)),
        "Three what-if scenarios next to the baseline": med(lambda: scenario_service.run(a, SETTINGS, {}, service.AUTO, SCEN)),
        "Forecast health (all items, timeline, drift)": med(lambda: health_service.health(a)),
        "Record a decision in the log": med(lambda: audit_service.record_decision(log, a, "perf.csv", SETTINGS, {}, service.AUTO, "balanced", {}, "", None)),
    }
    if with_challenger:
        rows["Challenger test (retrain and replay 12 dates)"] = med(lambda: health_service.challenger(a), n=1)
    log.close()
    return [f"### {label}", "", f"{a.data.n_series} items, {a.data.n_days} days, tier '{a.plan.tier}'.", "", "| Call | Median seconds |", "|---|---|"] + [f"| {k} | {v:.2f} |" for k, v in rows.items()] + [""]


def main() -> None:
    out = ["# Performance of the decision features", "", "Measured on the computer that ran `scripts/run_perf_check.py`; orders of magnitude, not promises.", ""]
    data, _, _ = load_sample()
    a = service.run_analysis(data, service.Settings(horizon=28, calendar="events"), cache_dir=CACHE_DIR)
    out += measure("M5 sample", a, with_challenger=True)
    rng = np.random.default_rng(0)
    n, k = 500, 100
    shape = np.array([1.0, 0.8, 0.8, 0.9, 1.1, 1.8, 1.6])
    vals = np.maximum(0, np.rint(rng.uniform(5, 60, (k, 1)) * shape[np.arange(n) % 7] * (1 + 0.1 * rng.standard_normal((k, n)))))
    big = SalesData(pd.date_range("2022-01-01", periods=n), [f"item{j:03d}" for j in range(k)], vals)
    t = time.perf_counter()
    ab = service.run_analysis(big, service.Settings(horizon=28))
    out += [f"Analysis of the 100-item file took {time.perf_counter() - t:.1f} s (once per file).", ""]
    out += measure("100 items, 500 days (the largest file the app takes)", ab, with_challenger=False)
    Path(ROOT / "reports" / "performance.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
