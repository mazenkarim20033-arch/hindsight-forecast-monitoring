# The 100-item sample: forecaster comparison

100 items, 1941 days, 141 scored replay dates (every 5 days over the last 730 days), 28-day horizon. Reference rule: 'average of the same weekday, last 4 weeks'. WAPE = total absolute error divided by total sales (lower is better).

| Method | WAPE | Gain over the reference (95% interval) | Ahead on | 80% range held | 90% range held |
|---|---|---|---|---|---|
| last day | 42.2% | -8.3 pts (-8.9 to -7.5) | 1% | 79.9% | 89.8% |
| average of the last 28 days | 34.2% | -0.3 pts (-0.4 to -0.2) | 31% | 79.9% | 92.6% |
| same day last week | 39.3% | -5.4 pts (-5.9 to -4.9) | 1% | 80.0% | 89.8% |
| average of the same weekday, last 4 weeks | 33.9% | reference |  | 79.9% | 89.7% |
| learning model | 32.9% | +1.0 pts (+0.2 to +1.6) | 88% | 79.9% | 89.7% |
| best method so far | 33.2% | +0.7 pts (-0.1 to +1.3) | 75% | 79.9% | 89.8% |

App verdict: 'learning model' beat the simple weekday rule: off by 32.9% of sales against 33.9%, and ahead on 88% of replay dates.

## Spread across the items

- Share of days with no sales per item: median 6.2%, highest 19.8%.
- Item-level WAPE of the reference rule: median 43.6% (lowest 14.1%, highest 72.0%).
- The learning model had the lower WAPE on 87 of 100 items and the higher on 13.

Read this as: on single products (added up over ten stores) errors are several times larger than at store or company level (reports/models_m5.md), and the learning model's edge over the simple rule is real but small. The sample holds 100 items chosen by a fixed rule; other items or other businesses may differ.