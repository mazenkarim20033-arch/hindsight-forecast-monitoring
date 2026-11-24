# Evaluation plan

Two parts: what has been evaluated so far and what it supports, then the studies still needed, with the pass criteria written down **before** any real data is looked at.

## Part 1. What exists

| Claim | Evidence | Where | What it does not support |
|---|---|---|---|
| No forecast uses the future | Tests change later data and check earlier forecasts, ranges, alerts and health statuses do not move | `tests/test_replay.py`, `tests/test_health.py` | Leakage outside the replay engine, such as through how a file was prepared |
| The learning model beats the best simple rule on US retail | 141 replay dates, five levels, paired bootstrap intervals | `reports/models_m5.md`, `EXPERIMENTS.md` | Other industries, other countries, tuned or deep-learning competitors |
| Stated ranges are honest | Coverage 0.79 to 0.84 (80%) and 0.89 to 0.93 (90%) | `EXPERIMENTS.md` | Individual days; overlapping dates make intervals indicative |
| Odd-day alerts behave | Injected changes: 82% caught at 98% level, 2.0% false alarms; closures, halvings, doublings all caught | `reports/alerts_m5.md` | Subtle changes (+30% mostly missed), slow drifts |
| Order arithmetic is right | Hand-computed outcomes, brute-force check that the quantile minimises cost, closed-form check on a normal distribution | `tests/test_inventory.py` | That the inputs a user types are right |
| Stated service levels roughly hold | Six cover periods x four targets, 1,410 cases each; gap 0 to 6 points under target, growing with cover length | `reports/inventory_m5.md` | Item-level intermittent demand; a real business; why the gap exists (not investigated) |
| Scenarios are isolated and consistent | Isolation, factor and refusal tests | `tests/test_scenarios.py` | That a promotion or price change really has the effect typed in |
| Health reacts to change and is mostly quiet otherwise | Injected +50% and -30% changes (12 seeds each); unchanged synthetic series; fires on about a quarter of M5 store-days | `reports/health_m5.md` | Whether those M5 alarms were real; real shops |
| Onboarding reads messy files | 24 tests over composite keys, duplicates, price/cost/stock columns (English and Arabic headers), quality findings, adapters including hostile YAML | `tests/test_onboarding.py` | Real exports with headers and layouts not in the word lists |
| The log is append-only and tamper-evident | Triggers refuse edits; edits and deletions after removing triggers are detected; 4 threads, 60 records | `tests/test_audit.py` | Protection against someone who rebuilds the whole file |
| The features agree with each other | One path from upload to outcome comparing numbers across steps | `tests/test_integration.py` | Real-world data flow |
| Screens are accessible and work in demo mode | WCAG A/AA audit, light and dark, every page; recorded demo sweep | M6 notes in `FEATURE_DOCUMENTATION.md` | Phones, Safari, Firefox; screen reader use |

## Part 2. Studies still needed

Each study states its question, data, method, and the criterion that counts as passing, fixed now.

**S1. Forecast accuracy on a real business.** *Question:* does the learning model still beat the simple rule, and do the ranges hold, on a real shop's file? *Data:* one or more real daily sales files covering at least two years (a pharmacy, a grocery, a restaurant). *Method:* the same replay and scorecard, nothing tuned. *Pass:* the 95% interval of the gain over the reference rule is above zero at store level, and the 80% range covers between 0.75 and 0.85 of days. *If it fails:* the app already says "the simple rule was the most accurate"; record that result as it is.

**S2. Order service levels.** *Question:* is the calibration gap seen on M5 (0 to 6 points under target) also seen on the real file, and does it grow with the cover period? *Method:* `scripts/run_inventory_check.py` on the real file. *Pass:* realized service within 5 points of target for covers up to 14 days. *Also check:* item-level intermittent series separately, since M5 stores are not intermittent.

**S3. Do recommendations beat what the business did?** *Question:* compared with the business's own past orders, would the balanced option have cost less? *Data:* real order history with prices, costs and stock, and the sales that followed. *Method:* retrospective comparison using the same outcome arithmetic as the decision log, per cover period, over at least 12 periods. *Pass:* lower realised cost of being wrong in more than half of the periods **and** a paired interval that excludes zero. Not claimed until measured; sales are not demand, so shortage periods are flagged.

**S4. Health monitor labels.** *Question:* when the monitor says Action needed, was something actually wrong? *Method:* the owner marks known bad stretches (a supplier problem, a closure, a data error) on a real file; compare with statuses. *Pass:* at least 70% of marked stretches reach Watch or Action within 14 days, and no more than 15% of unmarked store-days are Action. The M5 figures (4.7% Action) are a starting point, not a result.

**S5. Onboarding on real exports.** *Question:* how often does detection pick the right columns on files the author has not seen? *Data:* at least 10 exports from different systems (Arabic and English headers). *Method:* record picks without correction, count files needing a manual change. *Pass:* correct date and sales columns in at least 8 of 10 without help; every miss produces a message that leads to a fix.

**S6. Language review.** A native Arabic speaker reads every screen; each change is applied and the translation-parity test must still pass. *Pass:* no sentence marked wrong or misleading about what a number means.

**S7. Usability.** Five people who run a business (not developers) complete: load a file, read the health status, get an order recommendation, record a decision. *Pass:* four of five finish unaided and can say in their own words what "Watch" and "service level" mean.

## Reporting rules
Results are reported whether or not they pass, with the sample size, the data's origin and what it cannot show. A failed criterion changes the documentation, not the criterion.
