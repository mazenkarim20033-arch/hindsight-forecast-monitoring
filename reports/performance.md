# Performance of the decision features

Measured on the computer that ran `scripts/run_perf_check.py`; orders of magnitude, not promises.

### M5 sample

100 items, 1941 days, tier 'full'.

| Call | Median seconds |
|---|---|
| Order recommendation (3 options, all items, with track-record table) | 1.09 |
| Three what-if scenarios next to the baseline | 1.39 |
| Forecast health (all items, timeline, drift) | 0.14 |
| Record a decision in the log | 0.22 |
| Challenger test (retrain and replay 12 dates) | 7.08 |

Analysis of the 100-item file took 9.8 s (once per file).

### 100 items, 500 days (the largest file the app takes)

100 items, 500 days, tier 'simple'.

| Call | Median seconds |
|---|---|
| Order recommendation (3 options, all items, with track-record table) | 0.89 |
| Three what-if scenarios next to the baseline | 1.16 |
| Forecast health (all items, timeline, drift) | 0.12 |
| Record a decision in the log | 0.21 |
