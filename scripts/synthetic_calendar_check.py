"""SYNTHETIC check of the Egyptian calendar features. Not real sales.

Sales are generated with a known Ramadan lift and a known Eid al-Fitr lift, so we know the right answer. The question is only
whether the model can find a calendar effect *when one exists*. It says nothing about whether real shops have such an effect
(on M5, which is US data, Islamic events showed ratios around 1.0)."""
import numpy as np
import pandas as pd

from hindsight.calendar_features import egypt_calendar
from hindsight.data.sales import SalesData
from hindsight.replay.engine import run_replay
from hindsight.replay.metrics import wape
from hindsight.replay.ml import GlobalLightGBM
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N_DAYS, HORIZON = 1500, 14
PARAMS = dict(n_estimators=150, num_leaves=15, min_child_samples=20)


def main() -> None:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2019-01-01", periods=N_DAYS)
    cal = egypt_calendar(dates)
    t = np.arange(N_DAYS)
    weekly = np.array([1.0, 0.9, 0.9, 1.0, 1.2, 1.3, 1.1])[t % 7]
    effect = 1 + 0.5 * cal["ramadan"].to_numpy() + 0.6 * cal["eid_fitr"].to_numpy()
    base = np.array([40.0, 90.0, 150.0, 300.0, 600.0])[:, None]
    values = np.maximum(0, base * weekly * effect * (1 + 0.08 * rng.standard_normal((5, N_DAYS))))
    data = SalesData(dates, [f"shop{i}" for i in range(5)], values)
    origins = np.arange(900, N_DAYS - HORIZON, 5)
    rows = []
    for name, cals in (("with Egyptian calendar", [egypt_calendar]), ("without calendar", [])):
        r = run_replay(data, GlobalLightGBM(calendars=cals, params=PARAMS, refit_every=60, train_days=730), HORIZON, origins)
        ramadan_ahead = np.array([cal["ramadan"].to_numpy()[o + 1 : o + 1 + HORIZON].any() for o in origins])
        rows.append((name, wape(r), wape(r.where(ramadan_ahead)), wape(r.where(~ramadan_ahead))))
    lines = ["# Egyptian calendar check on SYNTHETIC data", "",
             "**This is made-up data.** Sales were generated with a known +50% lift in Ramadan and +60% on Eid al-Fitr, plus a weekly pattern and 8% noise. "
             "It only shows the model can learn a calendar effect that exists. It does not show that real shops have one.", "",
             f"{len(origins)} replay dates, {HORIZON}-day forecasts, WAPE (lower is better):", "",
             "| Model | All dates | Dates with Ramadan in the forecast window | Other dates |", "|---|---|---|---|"]
    lines += [f"| {n} | {a:.3f} | {b:.3f} | {c:.3f} |" for n, a, b, c in rows]
    (ROOT / "reports" / "synthetic_calendar_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
