# Models on M5 (generated)

Replay dates every 5 days from day 365 to the end (310 dates); scored on the last 730 days (141 dates), each forecasting the next 28 days. Nothing is tuned. Gain is measured against 'average of the same weekday, last 4 weeks' (the best simple rule): WAPE points saved, with a 95% bootstrap interval over replay dates. Win rate is the share of replay dates on which the method had less total error than that rule. Coverage is the share of days whose actual sales fell inside the range (the target is 0.80 and 0.90); width is the average range width divided by average sales. US retail data only.

## total (1 series)

| Method | WAPE | Gain vs rule (95% interval) | Win rate | Bias | 80% range: coverage / width | 90% range: coverage / width |
|---|---|---|---|---|---|---|
| gradient boosting | 0.045 | +0.030 (+0.028 to +0.032) | 99% | -0.012 | 0.82 / 0.15 | 0.91 / 0.20 |
| best method so far | 0.045 | +0.030 (+0.028 to +0.032) | 99% | -0.012 | 0.83 / 0.15 | 0.92 / 0.21 |
| average of the same weekday, last 4 weeks | 0.075 | +0.000 (+0.000 to +0.000) | 0% | -0.008 | 0.82 / 0.23 | 0.91 / 0.31 |
| exponential smoothing | 0.083 | -0.008 (-0.012 to -0.004) | 33% | -0.004 | 0.84 / 0.27 | 0.92 / 0.35 |
| same day last week | 0.096 | -0.021 (-0.026 to -0.015) | 17% | -0.006 | 0.82 / 0.29 | 0.91 / 0.39 |
| average of the last 28 days | 0.134 | -0.059 (-0.062 to -0.055) | 0% | -0.008 | 0.83 / 0.44 | 0.93 / 0.52 |
| last day | 0.174 | -0.099 (-0.108 to -0.091) | 0% | -0.001 | 0.82 / 0.61 | 0.91 / 0.77 |

Which method 'best so far' chose over the scored dates: gradient boosting 100%.

## state (3 series)

| Method | WAPE | Gain vs rule (95% interval) | Win rate | Bias | 80% range: coverage / width | 90% range: coverage / width |
|---|---|---|---|---|---|---|
| gradient boosting | 0.059 | +0.028 (+0.025 to +0.030) | 99% | -0.011 | 0.83 / 0.21 | 0.91 / 0.28 |
| best method so far | 0.059 | +0.028 (+0.025 to +0.030) | 99% | -0.011 | 0.83 / 0.21 | 0.91 / 0.28 |
| average of the same weekday, last 4 weeks | 0.087 | +0.000 (+0.000 to +0.000) | 0% | -0.008 | 0.82 / 0.29 | 0.91 / 0.39 |
| exponential smoothing | 0.092 | -0.006 (-0.009 to -0.002) | 30% | -0.004 | 0.82 / 0.32 | 0.92 / 0.44 |
| same day last week | 0.111 | -0.024 (-0.029 to -0.019) | 11% | -0.006 | 0.81 / 0.37 | 0.91 / 0.50 |
| average of the last 28 days | 0.142 | -0.055 (-0.059 to -0.052) | 0% | -0.008 | 0.82 / 0.46 | 0.92 / 0.56 |
| last day | 0.186 | -0.099 (-0.107 to -0.091) | 0% | -0.001 | 0.81 / 0.64 | 0.91 / 0.81 |

Which method 'best so far' chose over the scored dates: gradient boosting 100%.

## store (10 series)

| Method | WAPE | Gain vs rule (95% interval) | Win rate | Bias | 80% range: coverage / width | 90% range: coverage / width |
|---|---|---|---|---|---|---|
| gradient boosting | 0.075 | +0.023 (+0.020 to +0.025) | 96% | -0.005 | 0.81 / 0.24 | 0.90 / 0.33 |
| best method so far | 0.075 | +0.023 (+0.020 to +0.025) | 96% | -0.005 | 0.81 / 0.24 | 0.90 / 0.33 |
| average of the same weekday, last 4 weeks | 0.098 | +0.000 (+0.000 to +0.000) | 0% | -0.008 | 0.80 / 0.31 | 0.90 / 0.43 |
| exponential smoothing | 0.103 | -0.005 (-0.007 to -0.002) | 31% | -0.006 | 0.80 / 0.32 | 0.90 / 0.46 |
| same day last week | 0.123 | -0.025 (-0.030 to -0.020) | 9% | -0.006 | 0.80 / 0.38 | 0.90 / 0.54 |
| average of the last 28 days | 0.152 | -0.054 (-0.057 to -0.051) | 0% | -0.008 | 0.80 / 0.48 | 0.90 / 0.60 |
| last day | 0.199 | -0.100 (-0.108 to -0.092) | 0% | -0.001 | 0.80 / 0.66 | 0.90 / 0.87 |

Which method 'best so far' chose over the scored dates: gradient boosting 100%.

## store_category (30 series)

| Method | WAPE | Gain vs rule (95% interval) | Win rate | Bias | 80% range: coverage / width | 90% range: coverage / width |
|---|---|---|---|---|---|---|
| gradient boosting | 0.094 | +0.023 (+0.021 to +0.026) | 99% | -0.005 | 0.80 / 0.33 | 0.90 / 0.45 |
| best method so far | 0.094 | +0.023 (+0.021 to +0.026) | 99% | -0.005 | 0.80 / 0.33 | 0.90 / 0.45 |
| average of the same weekday, last 4 weeks | 0.117 | +0.000 (+0.000 to +0.000) | 0% | -0.008 | 0.79 / 0.39 | 0.89 / 0.54 |
| same day last week | 0.146 | -0.029 (-0.034 to -0.024) | 7% | -0.006 | 0.80 / 0.48 | 0.90 / 0.67 |
| average of the last 28 days | 0.165 | -0.048 (-0.051 to -0.045) | 0% | -0.008 | 0.79 / 0.53 | 0.89 / 0.67 |
| last day | 0.217 | -0.100 (-0.107 to -0.092) | 0% | -0.001 | 0.79 / 0.72 | 0.89 / 0.96 |

Which method 'best so far' chose over the scored dates: gradient boosting 100%.

## store_department (70 series)

| Method | WAPE | Gain vs rule (95% interval) | Win rate | Bias | 80% range: coverage / width | 90% range: coverage / width |
|---|---|---|---|---|---|---|
| gradient boosting | 0.115 | +0.021 (+0.019 to +0.023) | 99% | -0.006 | 0.80 / 0.46 | 0.90 / 0.66 |
| best method so far | 0.115 | +0.021 (+0.019 to +0.023) | 99% | -0.006 | 0.80 / 0.46 | 0.90 / 0.66 |
| average of the same weekday, last 4 weeks | 0.136 | +0.000 (+0.000 to +0.000) | 0% | -0.008 | 0.80 / 0.53 | 0.89 / 0.77 |
| same day last week | 0.168 | -0.032 (-0.037 to -0.027) | 6% | -0.006 | 0.80 / 0.65 | 0.90 / 0.95 |
| average of the last 28 days | 0.180 | -0.044 (-0.047 to -0.042) | 0% | -0.008 | 0.79 / 0.63 | 0.89 / 0.84 |
| last day | 0.235 | -0.099 (-0.107 to -0.092) | 0% | -0.001 | 0.79 / 0.84 | 0.89 / 1.13 |

Which method 'best so far' chose over the scored dates: gradient boosting 100%.

