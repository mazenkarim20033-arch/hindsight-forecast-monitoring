# Odd-day alerts on M5 (generated)

Store level (10 stores), boosted forecaster, 28-day replay every 5 days. A day is flagged when sales fall outside the range of the latest forecast made before it. 60 one-day changes were injected into the real sales in the last 730 days (the injected days are synthetic; the rest is real US data). False alarms are flagged days among days not touched, so some 'false alarms' may be genuinely unusual real days.

| Range level | Share of injected days caught | Flagged normal days | Flagged by chance if ranges were exact |
|---|---|---|---|
| 95% | 93% (60 days) | 4.3% (on injected run), 4.8% (on untouched data) | 5% |
| 98% | 82% (60 days) | 1.5% (on injected run), 2.0% (on untouched data) | 2% |

## Share caught by size of change (injected days)

| Change | 95% range | 98% range |
|---|---|---|
| closed (zero sales) | 10/10 | 10/10 |
| sales -50% | 10/10 | 10/10 |
| sales -25% | 10/10 | 6/10 |
| sales +30% | 6/10 | 3/10 |
| sales +60% | 10/10 | 10/10 |
| sales x2.2 | 10/10 | 10/10 |

## The biggest surprises in the untouched real data, last 730 days (98% range)

| Store | Date | Actual | Expected | Direction | Known event that day |
|---|---|---|---|---|---|
| CA_2 | 2016-03-20 | 2300 | 5739 | lower | - |
| TX_2 | 2015-03-25 | 5928 | 2777 | higher | - |
| CA_2 | 2016-03-19 | 2779 | 5697 | lower | - |
| TX_2 | 2015-03-24 | 131 | 2862 | lower | - |
| TX_2 | 2015-06-15 | 6793 | 4063 | higher | - |
| TX_3 | 2015-06-15 | 6750 | 4142 | higher | - |
| WI_1 | 2015-02-01 | 1847 | 4197 | lower | SuperBowl |
| WI_1 | 2015-01-31 | 6902 | 4742 | higher | - |
| TX_1 | 2015-11-26 | 2688 | 848 | higher | Thanksgiving |
| WI_1 | 2015-12-28 | 1521 | 3262 | lower | - |
| CA_2 | 2016-03-27 | 6296 | 4187 | higher | Easter |
| TX_1 | 2015-06-15 | 5190 | 3388 | higher | - |

## Sample explanation: whole company, forecast made on 2015-11-20 for 2015-11-26 (Thanksgiving)

Forecast 26,548; what actually happened: 23,631. Reasons, in units sold:

| Reason | Units |
|---|---|
| a typical day at the recent level | +38,319 |
| usual weekly pattern | -4,654 |
| time of year | -3,966 |
| holidays and events | -3,672 |
| recent change in sales | +304 |
| how far ahead and how big | +216 |
