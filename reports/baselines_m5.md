# Baseline replay on M5 (generated)

Every 5th day over the last 730 days is a replay date (141 dates, 2014-05-25 to 2016-04-24, 20 to 21 dates per weekday, so no weekday is favoured); at each, a forecaster sees only earlier days and predicts the next 28. Nothing is tuned. M5 is US Walmart data. WAPE = total absolute error / total sales (lower is better); bias > 0 means over-forecasting; MASE < 1 beats the in-sample weekly rule.

## total (1 series; 0% of days have zero sales)

| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |
|---|---|---|---|---|---|---|
| average of the same weekday, last 4 weeks | 0.075 | 0.072-0.079 | 0.074 | 0.076 | -0.008 | 0.92 |
| same day last week | 0.096 | 0.090-0.102 | 0.090 | 0.098 | -0.006 | 1.18 |
| average of the last 28 days | 0.134 | 0.131-0.136 | 0.133 | 0.134 | -0.008 | 1.64 |
| last day | 0.174 | 0.166-0.183 | 0.169 | 0.176 | -0.001 | 2.14 |

Best: average of the same weekday, last 4 weeks. Against 'same day last week' it removes 0.021 of total sales in error (95% interval 0.015 to 0.026).

## state (3 series; 0% of days have zero sales)

| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |
|---|---|---|---|---|---|---|
| average of the same weekday, last 4 weeks | 0.087 | 0.083-0.091 | 0.085 | 0.088 | -0.008 | 0.93 |
| same day last week | 0.111 | 0.105-0.116 | 0.106 | 0.112 | -0.006 | 1.14 |
| average of the last 28 days | 0.142 | 0.139-0.145 | 0.142 | 0.142 | -0.008 | 1.33 |
| last day | 0.186 | 0.179-0.195 | 0.181 | 0.188 | -0.001 | 1.71 |

Best: average of the same weekday, last 4 weeks. Against 'same day last week' it removes 0.024 of total sales in error (95% interval 0.019 to 0.029).

## store (10 series; 0% of days have zero sales)

| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |
|---|---|---|---|---|---|---|
| average of the same weekday, last 4 weeks | 0.098 | 0.095-0.102 | 0.096 | 0.099 | -0.008 | 0.91 |
| same day last week | 0.123 | 0.117-0.129 | 0.118 | 0.125 | -0.006 | 1.10 |
| average of the last 28 days | 0.152 | 0.150-0.155 | 0.152 | 0.152 | -0.008 | 1.28 |
| last day | 0.199 | 0.192-0.207 | 0.191 | 0.201 | -0.001 | 1.66 |

Best: average of the same weekday, last 4 weeks. Against 'same day last week' it removes 0.025 of total sales in error (95% interval 0.020 to 0.030).

## store_category (30 series; 0% of days have zero sales)

| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |
|---|---|---|---|---|---|---|
| average of the same weekday, last 4 weeks | 0.117 | 0.114-0.121 | 0.114 | 0.118 | -0.008 | 0.90 |
| same day last week | 0.146 | 0.140-0.153 | 0.142 | 0.148 | -0.006 | 1.10 |
| average of the last 28 days | 0.165 | 0.163-0.168 | 0.164 | 0.166 | -0.008 | 1.15 |
| last day | 0.217 | 0.210-0.225 | 0.207 | 0.221 | -0.001 | 1.53 |

Best: average of the same weekday, last 4 weeks. Against 'same day last week' it removes 0.029 of total sales in error (95% interval 0.024 to 0.034).

## store_department (70 series; 0% of days have zero sales)

| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |
|---|---|---|---|---|---|---|
| average of the same weekday, last 4 weeks | 0.136 | 0.132-0.140 | 0.131 | 0.137 | -0.008 | 1.01 |
| same day last week | 0.168 | 0.161-0.174 | 0.161 | 0.170 | -0.006 | 1.20 |
| average of the last 28 days | 0.180 | 0.177-0.183 | 0.178 | 0.181 | -0.008 | 1.21 |
| last day | 0.235 | 0.228-0.243 | 0.223 | 0.239 | -0.001 | 1.53 |

Best: average of the same weekday, last 4 weeks. Against 'same day last week' it removes 0.032 of total sales in error (95% interval 0.027 to 0.037).

## item_store (1000 series, random sample; 68% of days have zero sales)

| Method | WAPE | 95% interval | WAPE days 1-7 | WAPE days 8-28 | Bias | MASE (median) |
|---|---|---|---|---|---|---|
| average of the last 28 days | 0.821 | 0.815-0.827 | 0.788 | 0.832 | -0.003 | 1.02 |
| average of the same weekday, last 4 weeks | 0.849 | 0.843-0.855 | 0.815 | 0.860 | -0.003 | 1.06 |
| same day last week | 0.956 | 0.949-0.963 | 0.915 | 0.970 | -0.002 | 1.17 |
| last day | 0.972 | 0.960-0.982 | 0.923 | 0.988 | -0.000 | 1.17 |

Best: average of the last 28 days. Against 'same day last week' it removes 0.135 of total sales in error (95% interval 0.132 to 0.139).

