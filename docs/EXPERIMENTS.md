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

## First look at the data (`reports/eda_m5.md`)
Holiday effects on total sales are large for some US events (Labor Day 1.26 times a normal day, Thanksgiving 0.72, Christmas 0.00 because stores close) and nil for others, so a holiday-aware model has something to learn on this data. Overall volume grew about 60% from 2011 to 2016, so a model must handle changing level.
