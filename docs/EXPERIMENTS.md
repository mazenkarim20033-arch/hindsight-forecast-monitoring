# Experiments

Source of truth: `reports/*.md` (generated) and `experiments/runs/*.json`. Numbers below are copied from the generated reports.

## M1: data, replay engine and baselines (M5, US Walmart)

**Replay setup.** A replay date is the last day a forecaster may see. Dates are every 5th day over the last 730 days (141 dates, 2014-05-25 to 2016-04-24, 20 to 21 per weekday); at each, the forecaster sees only earlier days and predicts the next 28. Nothing is tuned. All baselines are simple on purpose: they are the yardstick any cleverer method must beat.

**Headline numbers** (WAPE = total absolute error divided by total sales, lower is better; over the 28-day horizon):

| Level | Series | Zero-sales days | Best baseline | WAPE | Same day last week | Last day |
|---|---|---|---|---|---|---|
| Whole company | 1 | 0% | average of the same weekday, last 4 weeks | 0.075 | 0.095 | 0.174 |
| State | 3 | 0% | same | 0.087 | 0.110 | 0.186 |
| Store | 10 | 0.1% | same | 0.098 | 0.122 | 0.199 |
| Store and category | 30 | 0.2% | same | 0.117 | 0.146 | 0.217 |
| Store and department | 70 | 0.3% | same | 0.136 | 0.167 | 0.235 |
| Single item in a store (1,000 sampled) | 1,000 | 68% | average of the last 28 days | 0.82 | 0.955 | 0.97 |

### What this supports
- At every aggregated level the same winner appears: **the average of the same weekday over the last four weeks** beats the other three baselines, and the gain over "same day last week" is clearly above zero (store level: about 2.4 points of total sales, interval 1.8 to 2.9).
- Weekly rhythm matters: weekends run about 20% above midweek (Sat 1.21, Sun 1.20, Wed 0.87 of the weekly average), which is why the "last day" rule is worst.
- Forecast error grows as series get smaller: about 7.5% for the whole company, 9.8% for a store, 13.6% for a department.
- Forecast quality barely drops from days 1 to 7 to days 8 to 28 for these baselines (store level: 0.096 against 0.099), because they assume a stable weekly pattern.
- **Single items are very hard.** 68% of item-store days have zero sales, the best baseline's error is 82% of total sales, and its MASE is about 1.03: no better than the plain weekly rule. A clever model must be judged here against this, and ranges for such series need care (see the plan).

### What it does not support
- Anything about Egyptian shops. This is US retail data. The calendar lists Ramadan start, Eid al-Fitr and Eid al-Adha, but in US stores they show **no visible effect** (ratios 1.01, 0.97, 1.01 against the surrounding weeks). So the data cannot test whether Islamic-calendar features help Egyptian businesses; that claim stays unproven until a real shop's data is tested.
- A ranking of forecasting methods in general: only four trivial baselines were run, nothing tuned.
- Tight intervals: the percentile intervals come from resampling replay dates, which overlap in what they forecast, so they are indicative.

### Things that went wrong
- **A weekday trap.** My first replay used every 7th day, so every replay date was a Sunday. That made the "last day" rule look much worse than it is (bias +20%) and could have quietly favoured or hurt the weekly rules. Switching to a step of 5 fixed it (bias -0.1%) and a test now guards it; rankings did not change.
- **A real bug.** The "same weekday average" baseline sliced its history wrongly when fewer than seven days existed. A test with short histories caught it, and it is fixed.
- One of my own date tests used a setup that failed for a different reason than intended; corrected.

## M2: models, ranges and selection (M5, US Walmart)
Full tables: `reports/models_m5.md`; raw numbers: `experiments/runs/models-m5-*.json`; script: `scripts/run_models.py`. Replay dates every 5 days (310), scored on the last 730 days (141 dates), 28-day horizon, nothing tuned. Reference rule: average of the same weekday over the last 4 weeks.

| Level | Reference rule WAPE | Gradient boosting WAPE | Gain (95% interval) | Win rate |
|---|---|---|---|---|
| total | 0.075 | 0.045 | +0.030 (+0.028 to +0.032) | 99% |
| state | 0.087 | 0.059 | +0.028 (+0.025 to +0.030) | 99% |
| store | 0.098 | 0.075 | +0.023 (+0.020 to +0.025) | 96% |
| store x category | 0.117 | 0.094 | +0.023 (+0.021 to +0.026) | 99% |
| store x department | 0.136 | 0.115 | +0.021 (+0.019 to +0.023) | 99% |

### What this supports
- On this US data, a global gradient-boosting model beats the best simple rule at every level, on nearly every replay date. The gain shrinks (in points) as series get smaller, but it holds.
- Exponential smoothing is **worse** than the simple weekday rule at every level where it was run (about 0.5 points of WAPE), and it is by far the slowest (413 s at store level). It is kept as an honest comparison, not as a recommendation.
- The ranges are honest: the 80% range covered 0.79 to 0.84 of days and the 90% range 0.89 to 0.93, across all methods and levels. A better forecaster gets narrower ranges at the same coverage (total: 0.15 wide with boosting versus 0.23 with the rule).
- "Best method so far" chose gradient boosting on 100% of scored dates, so it matched boosting. With one clearly dominant method the selector adds nothing here; it is there for data where no single method dominates.

### What it does not support
- Nothing about Egyptian shops: this is US data with US events. The calendar for Egypt (Ramadan, Eids, Coptic Christmas, Sham el-Nessim, national days) is built and tested, but its benefit is **unproven on real data**. On M5, Islamic events showed ratios near 1.0.
- `reports/synthetic_calendar_check.md` is SYNTHETIC data with a built-in Ramadan and Eid lift. The model with the calendar scored WAPE 0.067 on windows containing Ramadan versus 0.176 without. That shows the mechanism works when an effect exists, nothing more.
- Gradient boosting was run with default settings and no tuning, so the gain is not an upper bound. No claim is made against methods not tested (for example deep-learning forecasters).
- Item-level (single product at a store) series were not run in M2.

### Things that went wrong
- `hijri-converter` is deprecated; switched to `hijridate`. Hijri dates follow Umm al-Qura and can differ by a day from local moon sighting.
- A test assumed one Ramadan per Gregorian year; 2030 has two. The test now checks the first run's length.

## First look at the data (`reports/eda_m5.md`)
Holiday effects on total sales are large for some US events (Labor Day 1.26 times a normal day, Thanksgiving 0.72, Christmas 0.00 because stores close) and nil for others, so a holiday-aware model has something to learn on this data. Overall volume grew about 60% from 2011 to 2016, so a model must handle changing level.
