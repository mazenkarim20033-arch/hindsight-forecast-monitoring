# Model card

Hindsight uses several small models and rules rather than one large model. This card describes each, what it is for, how it was evaluated and where it should not be used. Numbers come from `reports/` and `EXPERIMENTS.md`; none was written without a source.

## 1. Forecasters (daily sales, 7 to 28 days ahead)
| Name in the app | What it is |
|---|---|
| last day | Tomorrow looks like today |
| same day last week | Each day looks like the same weekday last week |
| average of the same weekday, last 4 weeks | **The reference rule.** Each day looks like the mean of that weekday over four weeks |
| average of the last 28 days | A flat moving average |
| learning model | One global LightGBM model across all items (see below). Runs only when the file covers at least two years |
| best method so far | At each date, the method with the lowest error over its last 8 completed replay dates; before that, the reference rule |

**Learning model.** Gradient-boosted trees, one model for all items, predicting the target as a ratio of the item's recent 28-day level so large and small items share it. Inputs: weekday-cycle ratio, last-week-same-day ratio, last-7-day ratio, last-day ratio, trend ratio, log level, days ahead, plus calendar features of the day being predicted (weekday, month, and optionally the Egyptian calendar or the events listed with the file). Settings (not tuned): 250 trees, learning rate 0.05, 31 leaves, minimum 40 samples per leaf, subsample 0.8, column sample 0.8, L2 1.0, seed 0. It is retrained every 28 days using only rows whose outcome was already known, on the most recent 730 days. Exponential smoothing was tested in research and is not offered.

**Intended use.** Daily unit sales of a business with a weekly rhythm and at least two years of history.
**Not for.** Intermittent item-level demand (68% zero days on M5 single items: the best baseline error was 82% of sales); hourly or weekly data (convert to daily first); new items with no history; any claim about Egypt (see Limits).

## 2. Ranges
Rolling conformal ranges: at each replay date the range is built from the same method's earlier errors that were already known at that date, scaled to the item's recent level. Levels 80% and 90% for display, 98% for odd-day alerts. Coverage is measured, not assumed.

## 3. Reasons and alerts
Reasons are exact tree contributions (TreeSHAP built into LightGBM) grouped into a few readable reasons; they sum to the forecast and describe what the model leaned on, not causes. An odd day is a day where real sales fall outside the 98% range of the latest forecast made before it.

## 4. Order recommendation (the Decision Optimizer)
Not a learned model: arithmetic on the forecast. Demand over the cover period is approximated by the live forecast multiplied by the newest up to 120 earlier ratios of actual to forecast sales for periods of the same length (at least 20 needed, only finished periods). The cost-optimal stock level is the demand quantile at `Cu / (Cu + Co)` (the newsvendor result, checked by brute force in the tests); Conservative counts a lost sale as half as costly; High availability is at least the target service level (default 95%). Regular-ordering mode uses a single-cycle base-stock approximation. Without prices and costs, fixed levels (80%, 90%, target) are used and no money is shown.

## 5. Scenarios
Pure functions on copies of the inputs: demand multipliers (promotion, seasonal change, spike: `1 + pct x days / cover days`), a longer lead time, lower stock, and a price change with a constant-elasticity demand effect using an elasticity the user must supply. Effects multiply. Results are arithmetic on assumptions, never forecasts.

## 6. Health status
Rules, not a model: recent WAPE against earlier WAPE (watch above x1.25, action above x1.5), against the simple rule (x1.10 / x1.30), bias (10% / 20%), and share of real sales inside the 80% range (below 70% / 55%). The status is the worst of these four; demand drift (PSI, KS) is shown but never changes it. A retrained challenger (same model, latest 365 days, refit every 14 days) can be tested on the last 12 dates; it is never deployed.

## Evaluation on public data (M5, 10 Walmart stores, last 730 days, 28-day horizon, nothing tuned)
| Level | Reference rule WAPE | Learning model WAPE | Gain (95% interval) |
|---|---|---|---|
| Whole company | 0.075 | 0.045 | +0.030 (+0.028 to +0.032) |
| Store | 0.098 | 0.075 | +0.023 (+0.020 to +0.025) |
| Store x department | 0.136 | 0.115 | +0.021 (+0.019 to +0.023) |

- Ranges: the 80% range held on 79 to 84% of days, the 90% range on 89 to 93%.
- Alerts at the 98% level: 82% of injected one-day changes caught at a 2.0% false-alarm rate; closures, halvings and doublings all caught; a +30% day caught 3 times in 10.
- Order service levels (1,410 cases per row): a stated 95% held 94.5% (3-day cover), 93.4% (10-day) and 91.5% (28-day); a stated 80% held 77.6%, 76.5% and 74.3%. The target is slightly missed and the gap grows with the cover period (`reports/inventory_m5.md`).
- Health (`reports/health_m5.md`): 76.3% healthy, 19.0% watch, 4.7% action on 1,460 store-days; on synthetic data a +50% change was left "healthy" after a median of 3 days (worst 6), a -30% change after 4 (worst 9); an unchanged synthetic series was 89.9% healthy, 9.6% watch, 0.5% action.

## Limits and risks
- **US retail data only.** Islamic and Egyptian events show ratios near 1.0 on M5. The Egyptian calendar is verified on labelled synthetic data only.
- **Sales are not demand.** A stock-out hides demand, so forecasts and orders are biased low where shortages happened.
- **Default settings.** The learning model was not tuned, so its gain is not an upper bound, and it was not compared with deep-learning forecasters.
- **Intermittent demand.** Single items with mostly zero days were not evaluated for ordering.
- **Calibration gap.** Order service levels are slightly lower than stated.
- **Conventions, not fitted detectors.** Health limits are round numbers; one was revised after a first look at synthetic data.
- **Human in the loop.** Nothing is deployed, switched or ordered automatically. Recommendations are advice, with assumptions visible.

## Who to contact / how to challenge it
Every number above can be regenerated with the scripts in `scripts/`; the tests in `tests/` guard the main promises (no future leakage, order arithmetic against hand calculation, append-only log, scenario isolation).
