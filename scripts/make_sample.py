"""Write the small sample that ships with the app: daily unit sales for the 10 Walmart stores in the public M5 data (CC BY 4.0),
plus the event names M5 provides. Real data, US retail; it is there so the app can be tried without a file."""
from pathlib import Path

import pandas as pd

from hindsight.data.m5 import at_level, load_m5

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data = load_m5(ROOT / "data" / "raw" / "extracted")
    stores = at_level(data, "store")
    out = ROOT / "data" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    long = pd.DataFrame({"date": stores.dates.repeat(stores.n_series).strftime("%Y-%m-%d"),
                         "store": [i for _ in range(stores.n_days) for i in stores.ids],
                         "units_sold": stores.values.T.reshape(-1).astype(int)})
    long.to_csv(out / "m5_stores.csv", index=False)
    cal = data.calendar[["date", "event_name_1", "event_type_1", "event_name_2", "event_type_2"]]
    cal.to_csv(out / "m5_events.csv", index=False)
    print(f"{len(long):,} rows, {stores.n_series} stores, {stores.n_days} days -> {out}")


if __name__ == "__main__":
    main()
