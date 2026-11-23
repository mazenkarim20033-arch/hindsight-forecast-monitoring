"""First look at M5: how sparse is it at each level, how strong is the weekly rhythm, and do holidays visibly move total sales?
Descriptive only. These effects are for US Walmart stores and say nothing about Egyptian shops."""
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight.data.m5 import at_level, load_m5

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "extracted"


def main() -> None:
    data = load_m5(RAW)
    lines = ["# M5 first look (generated)", "", "Descriptive statistics of the public M5 Walmart data (US stores). Used to decide what the forecasting models need; not evidence about Egyptian shops.", "",
             "## How sparse is each level?", "", "| Level | Series | Days with zero sales | Median units per day |", "|---|---|---|---|"]
    for level, sample in [("total", None), ("state", None), ("store", None), ("store_category", None), ("store_department", None), ("item_store", 3000)]:
        d = at_level(data, level, sample=sample, seed=0)
        lines.append(f"| {level} | {d.n_series} | {(d.values == 0).mean():.1%} | {np.median(d.values.mean(axis=1)):.1f} |")
    total = at_level(data, "total").values[0]
    dates = data.dates
    s = pd.Series(total, index=dates)

    wd = s.groupby(s.index.dayofweek).mean()
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    lines += ["", "## Weekly rhythm (total sales, ratio to the weekly average)", "", "| " + " | ".join(names) + " |", "|" + "---|" * 7,
              "| " + " | ".join(f"{wd[i] / wd.mean():.2f}" for i in range(7)) + " |"]
    yr = s.groupby(s.index.year).mean()
    lines += ["", "## Level over the years (average units per day, all stores)", "", "| " + " | ".join(str(y) for y in yr.index) + " |", "|" + "---|" * len(yr),
              "| " + " | ".join(f"{v:,.0f}" for v in yr.values) + " |", "(2011 and 2016 are partial years.)"]

    cal = data.calendar.reset_index(drop=True)
    rows = []
    for name in sorted(cal["event_name_1"].dropna().unique()):
        lifts = []
        for i in cal.index[cal["event_name_1"] == name]:
            ref = [total[i + k] for k in (-28, -21, -14, -7, 7, 14, 21, 28) if 0 <= i + k < len(total)]
            if len(ref) >= 4 and np.mean(ref) > 0:
                lifts.append(total[i] / np.mean(ref))
        if lifts:
            rows.append((name, len(lifts), float(np.mean(lifts)), float(np.min(lifts)), float(np.max(lifts))))
    lines += ["", "## Holiday effect on total sales", "",
              "Sales on the event day divided by the average of the same weekday in the four weeks before and after (1.00 = no effect). Small samples: the event happens once a year.", "",
              "| Event | Times in data | Average ratio | Lowest | Highest |", "|---|---|---|---|---|"]
    for name, n, avg, lo, hi in sorted(rows, key=lambda r: -abs(r[2] - 1)):
        lines.append(f"| {name} | {n} | {avg:.2f} | {lo:.2f} | {hi:.2f} |")
    lines += ["", "The three Islamic events (Ramadan starts, Eid al-Fitr, Eid al-Adha) are listed in the data, but US shoppers are not the population of interest; any benefit of Islamic-calendar features for Egyptian shops must be tested on Egyptian data."]
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "eda_m5.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
