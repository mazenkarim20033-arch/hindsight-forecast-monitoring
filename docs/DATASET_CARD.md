# Dataset card: M5 (Walmart)

- **What it is:** daily unit sales for 30,490 item-and-store series (3,049 items in 10 stores across California, Texas and Wisconsin) from 2011-01-29 to 2016-05-22 (1,941 days), plus a calendar with events and SNAP flags, and weekly sell prices. Real retail data from Walmart, released for the M5 forecasting competition.
- **Source:** https://zenodo.org/records/12636070 (a copy of the Kaggle competition data), file `m5-forecasting-accuracy.zip`, 48,009,163 bytes, MD5 `86f57416a314197f40a17cc6fc60cbb4` (checked against the value on the page).
- **Licence:** Creative Commons Attribution 4.0 International. Credit: M5 Forecasting competition data, Walmart; Zenodo record DOI 10.5281/zenodo.12636070.
- **Not included in this repository.** It is downloaded into `data/raw/` (git-ignored, about 430 MB when extracted).
- **Files used:** `sales_train_evaluation.csv` (all 1,941 days), `calendar.csv`. `sell_prices.csv` is not used yet.
- **Properties that shape the work:** 68% of item-store days have zero sales (intermittent demand); weekends run about 20% above midweek; overall level grew about 60% over the period; stores are closed on Christmas (zero total sales).
- **Limits:** US supermarket data, not Egyptian shops or pharmacies. Islamic events in its calendar show no effect there, so it cannot validate calendar features for Egypt.
- **Use here:** proving and testing the replay method. Real validation for Egypt needs a real shop's sales file.
- **The bundled sample (since the item-level change):** `data/sample/m5_items.csv`, 100 products added up over the 10 stores, selected by the rule in `scripts/make_sample.py` (sold on at least 80% of days; slots per department in proportion to size; evenly spaced by total units). It has less zero-sales than a single item in a single store (68% zero days), so it is easier in that respect. Results on it are in `reports/item_sample_m5.md`; the store- and company-level research results above are unchanged.
