# Hindsight: project plan (draft for review)

**One line:** upload your sales history, press play, and watch what the forecast would have said at every point in the past, against what really happened, so you know how far to trust the next forecast.

## Why this exists
Forecasting tools say "AI-powered" and show one number. A shop owner cannot tell whether to trust it. Hindsight replays the past honestly: at each past day the model sees only what was known then, predicts the next days with a range, and the real sales are revealed afterwards. A track record replaces a promise.

## Scope (what it is and is not)
- **Is:** a local web app for one business. Upload Excel/CSV of daily (or weekly) sales per item or store; get a replay, a scorecard and the next forecast, each with an honest range.
- **Is not:** a magic accuracy claim, an inventory system, or a multi-user cloud service. Not tested on Egyptian data until a real shop shares a file.

## Three levels, same idea as before
| History available | What the app does |
|---|---|
| Plenty (about 2 years or more of daily data) | Compares a seasonal rule, a statistical method and a machine-learning model on the replay; picks the one that would have done best |
| Some (about 3 to 12 months) | Simple methods only (same-day-last-week, moving average), says why |
| Very little | Says "not enough history yet" and shows what it would need |

## Methods
1. **Baselines:** same day last week; average of recent same weekdays.
2. **Statistical:** an exponential-smoothing style model with weekly seasonality.
3. **Machine learning:** one gradient-boosted model per business, using lagged sales, weekday, month, holidays, price and promotions where available.
4. **Calendar:** Gregorian plus Islamic (Ramadan, Eids) and Coptic holidays. The Islamic dates move about 11 days earlier every year, which is why generic tools fumble them.
5. **Ranges:** conformal calibration from the replay's own errors (as in SENTINEL).
6. **Explanations:** which inputs pushed the forecast up or down (SHAP).
7. **Odd-day alerts:** flag days that do not fit the pattern.

## Evaluation (the part that makes it trustworthy)
- **Rolling-origin replay:** for each past date, train only on earlier data, forecast the next 7 and 28 days, then compare. No future information, tested by changing later data and checking earlier forecasts do not move.
- **Metrics:** error versus the simple baseline (so "better than the obvious rule?" is always answered), bias, and how often the stated range held.
- **Honest reporting:** report ties as ties, show where the method fails (new products, promotions, holidays), keep failed attempts.
- **Data for testing:** the public M5 Walmart data (CC BY 4.0). It proves the method, not the Egyptian calendar effect. That claim stays unproven until a real shop's data is tested; the app and docs say so.

## Milestones (approval at each gate, like SENTINEL)
1. Data and replay engine: load M5, rolling-origin backtest, baselines, tests.
2. Models and ranges: statistical and ML forecasts, conformal ranges, calendar features, scorecard metrics.
3. Explanations and odd-day alerts.
4. API and the interface: upload and column detection, replay stage, scorecard.
5. Polish, bilingual (English and Arabic, right-to-left) layout, accessibility and phone checks, performance.
6. Public recorded demo, screenshots, write-up, case study.

## Reuse from SENTINEL
Replay lab behaviour, interval calibration, explanation code, API shape, run-record registry, test habits, accessibility checks, snapshot demo exporter. SENTINEL itself is not modified.

## Risks
- Forecasting is crowded: the edge is honesty and the replay, not accuracy.
- Simple methods often win: the app must say so when they do.
- No Egyptian data yet: Ramadan and Eid benefits are unproven.
- Messy uploads (Arabic headers and digits, mixed dates, gaps): needs a forgiving, explained import.
- Scope creep: bilingual and multi-item views come after the core replay works.
