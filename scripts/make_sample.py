"""Write the sample that ships with the app: daily unit sales for 100 actual items in the public M5 data (Walmart, CC BY 4.0), plus the event names M5
provides. Real data, US retail; it is there so the app can be tried without a file.

Each item's sales are added up over the 10 Walmart stores that sell it, so one series is one product across the chain (M5 publishes product codes
such as FOODS_3_090, not names). 100 is the most items the app accepts, and a global forecasting model has more to learn from with more series.

The items are chosen by a fixed rule written down before any forecast was run on them, which never looks at how forecastable anything is:
  * eligible: the item sold on at least 80% of days (so no item launched late or already discontinued; real files have those, and the app's
    data-quality checks cover them);
  * each of the 7 departments gets a share of the 100 slots in proportion to its number of eligible items;
  * inside a department the items are taken at evenly spaced positions of the ranking by total units, so the sample spans slow and fast sellers."""
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight.data.m5 import load_m5

ROOT = Path(__file__).resolve().parents[1]
MIN_SELLING_SHARE = 0.80
N_ITEMS = 100


def choose_items(items: pd.DataFrame, n: int = N_ITEMS) -> list[str]:
    """`items` has one row per item (code as index) with columns total, selling_share and dept_id."""
    eligible = items[items["selling_share"] >= MIN_SELLING_SHARE]
    slots = (eligible.groupby("dept_id").size() / len(eligible) * n).round().astype(int)
    slots.iloc[int(np.argmax(slots.to_numpy()))] += n - int(slots.sum())  # rounding leftovers go to the largest department
    chosen: list[str] = []
    for dept, group in eligible.groupby("dept_id"):
        ranked = group.sort_values("total", kind="stable")
        k = int(slots[dept])
        chosen += [ranked.index[min(int((j + 0.5) / k * len(ranked)), len(ranked) - 1)] for j in range(k)]
    return sorted(set(chosen))


def main() -> None:
    data = load_m5(ROOT / "data" / "raw" / "extracted")
    per_item = data.aggregate(["item_id"], name="item")
    meta = data.meta.drop_duplicates("item_id").set_index("item_id")
    values = np.asarray(per_item.values, dtype=float)
    info = pd.DataFrame({"total": values.sum(axis=1), "selling_share": (values > 0).mean(axis=1)}, index=per_item.ids)
    info["dept_id"] = meta.loc[info.index, "dept_id"].to_numpy()
    chosen = choose_items(info)
    keep = [per_item.ids.index(i) for i in chosen]
    out = ROOT / "data" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    long = pd.DataFrame({"date": per_item.dates.repeat(len(chosen)).strftime("%Y-%m-%d"),
                         "item": [i for _ in range(per_item.n_days) for i in chosen],
                         "units_sold": values[keep].T.reshape(-1).astype(int)})
    long.to_csv(out / "m5_items.csv", index=False)
    cal = data.calendar[["date", "event_name_1", "event_type_1", "event_name_2", "event_type_2"]]
    cal.to_csv(out / "m5_events.csv", index=False)
    print(f"{len(long):,} rows, {len(chosen)} items, {per_item.n_days} days -> {out}")
    print(info.loc[chosen].groupby("dept_id").agg(items=("total", "size"), median_units=("total", "median"), min_selling_share=("selling_share", "min")).to_string())


if __name__ == "__main__":
    main()
