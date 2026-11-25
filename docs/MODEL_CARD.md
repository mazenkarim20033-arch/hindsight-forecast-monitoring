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
Rules, not a model. Each signal must be past a fixed limit and also unusual for that item (more than 2 / 3 robust deviations worse than the item's own earlier windows of the same length). Signals: recent WAPE against earlier WAPE (watch above x1.25, action above x1.5), against the simple rule (x1.10 / x1.30), bias (10% / 20%), and share of real sales inside the 80% range (below 70% / 55%). The status is the worst of these four; demand drift (PSI, KS) is shown but never changes it. A retrained challenger (same model, latest 365 days, refit every 14 days) can be tested on the last 12 dates; it is never deployed.

## Evaluation on public data (M5, last 730 days, 28-day horizon, nothing tuned)
**The bundled 100-item sample** (`reports/item_sample_m5.md`; products added up over 10 stores, chosen by a fixed rule written before any forecast was run):

| Method | WAPE | Gain over the reference (95% interval) | Ahead on |
|---|---|---|---|
| Reference rule (same weekday, 4 weeks) | 33.9% | | |
| Learning model | 32.9% | +1.0 pts (+0.2 to +1.6) | 88% of dates |
| Best method so far | 33.2% | +0.7 pts (-0.1 to +1.3) | 75% |
| Average of the last 28 days | 34.2% | -0.3 pts (-0.4 to -0.2) | 31% |

The learning model had the lower error on 87 of the 100 items. On a 10-item sample chosen the same way (a different, earlier rule) it tied the reference rule; the edge needs enough items for a global model to learn from.

**Store and company level** (research, `reports/models_m5.md`; the learning model's edge is larger where series are smoother):

| Level | Reference rule WAPE | Learning model WAPE | Gain (95% interval) |
|---|---|---|---|
| Whole company | 0.075 | 0.045 | +0.030 (+0.028 to +0.032) |
| Store | 0.098 | 0.075 | +0.023 (+0.020 to +0.025) |
| Store x department | 0.136 | 0.115 | +0.021 (+0.019 to +0.023) |

- Ranges: on the item sample the 80% range held on 79.9% of days and the 90% range on 89.7%; at store and company level 79 to 84% and 89 to 93%.
- Alerts at the 98% level (store level, research): 82% of injected one-day changes caught at a 2.0% false-alarm rate; closures, halvings and doublings all caught; a +30% day caught 3 times in 10.
- Order service levels on the item sample (14,100 cases per row): a stated 95% held 94.1% (3-day cover), 93.6% (10-day) and 92.4% (28-day); a stated 80% held 78.9%, 78.5% and 77.8%. The target is slightly missed (0.7 to 2.6 points) and the gap grows with the cover period (`reports/inventory_m5.md`).
- Health (`reports/health_m5.md`): on 14,600 item-days, 80.3% healthy, 9.6% watch, 10.1% action with the current rule; the fixed limits alone gave 48.2%, 31.1% and 20.7%. On synthetic data a +50% change left "healthy" after a median of 3 days (worst 6), a -30% change after 6 (worst 9); an unchanged synthetic series was 93.3% healthy, 6.2% watch, 0.5% action.

## Limits and risks
- **US retail data only.** Islamic and Egyptian events show ratios near 1.0 on M5. The Egyptian calendar is verified on labelled synthetic data only.
- **Sales are not demand.** A stock-out hides demand, so forecasts and orders are biased low where shortages happened.
- **Default settings.** The learning model was not tuned, so its gain is not an upper bound, and it was not compared with deep-learning forecasters.
- **Intermittent demand.** The sample items sold on at least 80% of days (as products added up over ten stores). A single item in a single store (68% zero days in M5) was not evaluated for ordering or forecasting beyond the research baselines.
- **Calibration gap.** Order service levels are slightly lower than stated.
- **Conventions, not fitted detectors.** Health limits are round numbers; one was revised after a first look at synthetic data.
- **Human in the loop.** Nothing is deployed, switched or ordered automatically. Recommendations are advice, with assumptions visible.

## Who to contact / how to challenge it
Every number above can be regenerated with the scripts in `scripts/`; the tests in `tests/` guard the main promises (no future leakage, order arithmetic against hand calculation, append-only log, scenario isolation).
