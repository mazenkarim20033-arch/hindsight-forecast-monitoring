# Data dictionary

Every data shape Hindsight reads, keeps or writes. Units: sales are in the units of the file (items sold or an amount, whatever column was chosen); money is in the currency of the prices the user enters; dates are calendar days; percentages in scenario inputs are written as percent (20 means +20%), shares elsewhere as fractions (0.2).

## 1. What a sales file may contain
Daily data only (weekly or monthly files must be converted first). CSV (comma, semicolon, tab or pipe; UTF-8 or Windows-1256) or Excel (first sheet with data). Up to 25 MB.

| Column role | Recognised by | Notes |
|---|---|---|
| **Date** (required) | Header words such as date, day, time, period, تاريخ, اليوم, or content that parses as dates | Day-first versus month-first is decided from the data; day-first when undecidable (a warning says so). Excel dates and serial numbers accepted. Arabic digits accepted. |
| **Sales** (required, long layout) | Header words such as sales, qty, quantity, units, amount, revenue, مبيعات, الكمية, or a mostly numeric column | Decimal commas, thousands separators and currency marks (EGP, ج.م, $) are read. Blank or negative values count as 0 and are reported. |
| **Item** (optional) | Header words such as item, product, sku, store, branch, صنف, منتج, فرع, or a text column with few distinct values | One or more columns. Several columns together form a composite item name `A / B`. No item column means one series, "All sales". |
| **Wide layout** | Two or more numeric columns and no text column | One column per item. Carries no price, cost or stock. |
| **Price** (optional) | Header words price, سعر, السعر | Latest value per item is read. |
| **Unit cost** (optional) | cost, purchase, تكلفة, سعر الشراء | Latest value per item. |
| **Stock on hand** (optional) | stock, on hand, inventory, balance, مخزون, رصيد | Latest value per item (the most recent row by date). |
| **Stock on order** (optional) | on order, ordered, pending, incoming, قيد الطلب | Latest value per item. |

Several rows for the same item and day are added together (receipts). Rows identical in every column are reported and, by default, also added; the user may remove them instead. Days with no rows between the first and last date count as 0 and are reported. A file needs at least 28 consecutive days; at most 100 items are kept (the 100 with the most sales).

## 2. The internal data contract (`SalesData`)
| Field | Meaning |
|---|---|
| `dates` | Every calendar day from the first to the last date, no gaps |
| `ids` | Unique item names, as text |
| `values` | Array of shape items x days, non-negative, no missing values |
| `meta` | One row per item (for example store, category) when the source has them |
| `calendar` | One row per date (events, SNAP flags) when the source has them |
| `source` | Where the data came from (file name or dataset note) |

## 3. Import report
`layout` (long or wide), `rows`, `n_series`, `first_date`, `last_date`, `n_days`, `mapping` (date, value, item, item_columns, item_cols, duplicates), `notes` (each with `level` info or warning, a plain-language `text`, a `code` and `params` so the screen can say it in the other language), and `business` (`columns` found and `values` per item).

## 4. Data-quality findings
Each: `code`, `level`, `n_items`, up to six item names, `params`, and for spikes up to five examples (item, date, value, usual level). Codes: `file_ends_early` (every item zero for the last 7 days), `stopped_selling` (28 or more trailing zero days after selling), `late_start` (first sale more than 90 days after the file begins), `mostly_zero` (60% or more zero days since first sale), `constant_values` (the same non-zero number on 28 or more days), `spikes` (a day more than 8 robust deviations above the item's usual non-zero level and at least 3 times it).

## 5. Adapter (YAML)
```yaml
name: my-weekly-export        # 1-40 characters: a-z, 0-9, dash, underscore; must equal the file name
description: Friday POS export
mapping:
  date: Date
  value: Qty
  item: Product               # or item_cols: [Region, Product]; or item_columns: [...] for wide files
  business: {price: Price, on_hand: Stock}
duplicates: sum               # or drop_exact
```
Stored in `adapters/` (shipped) or `artifacts/adapters/` (saved). Holds column names only, never data.

## 6. Inventory inputs (`InventorySettings`, `StockLevel`)
| Field | Meaning | Default when empty |
|---|---|---|
| `mode` | `periodic_review` (regular ordering) or `single_period` (perishables) | periodic_review |
| `lead_time_days` | Days from order to delivery, 0 to 28 | none: refused |
| `review_days` | Days between orders | 7, reported as a default |
| `period_days` | Selling period in single-period mode, 1 to 28 | none: refused |
| `price`, `unit_cost` | Per unit | unknown: no money figures |
| `holding_cost_per_day` | Per unit per day | unknown: no money figures in regular mode |
| `stockout_penalty` | Extra cost of a lost sale beyond lost margin | 0 when costs are given, reported |
| `salvage_value` | Value of an unsold unit (single period) | 0, reported |
| `service_level` | Target availability for High availability, between 0.5 and 1 | 0.95, reported |
| `min_order_qty`, `order_multiple` | Supplier rules | none |
| `conservative_factor` | Weight of a lost sale in Conservative, 0 to 1 | 0.5, reported |
| `on_hand`, `on_order` (per item) | Stock now and already ordered | unknown: the order is the full requirement, flagged |

Cover period = lead time + review days (or the selling period), at most 28 days. Anything left empty is unknown, never zero.

## 7. Scenario (`Scenario`)
`name`; `demand_change_pct`; `promo_uplift_pct` with `promo_days`; `seasonal_change_pct` with `seasonal_days`; `spike_pct` with `spike_days`; `supplier_delay_days`; `stock_reduction_pct`; `price_change_pct` with `price_elasticity` (negative, supplied by the user). Anything left out is not applied. Up to 8 per request.

## 8. Health response
`overall` and each item: `status` (healthy, watch, action, unknown) and five `signals` (accuracy, vs_simple, bias, coverage, drift), each with `value`, `status`, and the `watch` and `action` limits; `counts`; `timeline` (per replay date: pooled error of the method and the simple rule, plain and rolling over 8 dates, plotted at the day the results were known); `thresholds`; `windows`; `notes`. Challenger: `verdict` (promote_candidate, keep_current, inconclusive), `deployed` (always false), WAPE and bias of both, the gain with a 95% interval, number of dates.

## 9. Decision log records (`artifacts/audit/audit.sqlite`, table `events`)
Columns: `id` (never reused), `ts` (UTC), `kind` (`decision` or `outcome`), `ref` (the decision an outcome belongs to), `payload` (JSON), `prev_hash`, `hash` (SHA-256 chain). Updates and deletes are refused by the database.

**Decision payload:** dataset (file name, number of days, as-of date and index, fingerprint of the history), method, mode, cover days, whether costs were available and the underage and overage costs used, the chosen option, the inputs, assumptions (user or default), the scenario if any, the demand factor, forecast health at the time, one entry per item (forecast, on hand, on order, position, the three options' orders with their risk and cost estimates, the quantity actually ordered and whether it was changed), skipped items, total ordered, and the note (at most 500 characters).

**Outcome payload:** the decision id, the later file, the window (from, to, days), per item real sales, the forecast and its error, stock available, leftover, shortage, cost, and the same for each of the three options, totals, the cheapest option in hindsight, and the notes `one_window`, `sales_not_demand`, `not_a_verdict`.

## 10. The bundled sample (`data/sample/m5_items.csv`)
Columns `date`, `item`, `units_sold`: daily units for 100 real Walmart items (M5 product codes such as `FOODS_3_090`; M5 publishes no product names), each added up over the 10 stores that sell it, 2011-01-29 to 2016-05-22 (1,941 days), derived from the M5 Forecasting competition data, CC BY 4.0. Chosen by the fixed rule in `scripts/make_sample.py`: items that sold on at least 80% of days, each of the 7 departments getting slots in proportion to its size, taken at evenly spaced positions of the ranking by total units. `m5_events.csv` lists calendar events by date. The sample has no prices, costs or stock. See `DATASET_CARD.md`.
