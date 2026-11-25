# Interview guide

For explaining and defending Hindsight to a hiring manager or technical interviewer. Everything here is something the project actually does and can show; the "do not claim" list matters as much as the pitch.

## The 30-second version
"Hindsight forecasts daily sales and, unlike most forecasting demos, shows how that forecast would have performed over the last two years using only what was known at each past date. I extended it into a decision tool: it turns the forecast into order recommendations from the business's own costs and stock, lets you try what-if scenarios, monitors whether the forecast is still healthy, and keeps a tamper-evident record of decisions so they can be compared with what happened. The main thing I'd point to is that every claim carries a measurement, and the app says what it does not know."

## The two-minute version
1. **Problem.** Forecast tools give one number; owners can't tell if it deserves trust, and nothing connects the number to a decision or the decision to its result.
2. **Evidence first.** Rolling-origin replay with no future leakage (tested by changing the future and checking the past doesn't move). On public Walmart data the learning model beats the best simple rule: by 2 to 3 WAPE points at store and company level, and by about 1 point (32.9% against 33.9%, interval above zero, ahead on 88% of dates) on 100 single items, where everything is noisier. The stated 80% range held on 79.9% of days.
3. **Decisions.** Ordering uses the newsvendor result: the cost-optimal stock is the demand quantile at `Cu/(Cu+Co)`. I measured it: a stated 95% service level held 92.4 to 94.1% depending on cover period, and I show that table in the app instead of hiding it.
4. **Honesty rules.** Missing costs are never silently zero; scenarios are labelled hypothetical; a retrained model is tested but never switched on by the app.
5. **Engineering.** 211 Python and 43 web tests, an end-to-end test that compares numbers across features, English and Arabic with right-to-left layout, and an accessibility audit of every screen.

## Decisions you should be able to defend
| Decision | The reasoning in a sentence | Likely follow-up | Honest answer |
|---|---|---|---|
| **Rolling-origin replay, never a random split** | A random split lets a model see the future of the series; replay gives each forecast only the earlier days | "Why not cross-validation?" | Time-series CV is the same idea; I built the replay myself so the no-leakage guarantee could be tested directly |
| **A simple rule is always in the race** | If a clever model can't beat "same weekday, last four weeks" it hasn't earned its place | "Did yours?" | On M5, yes at every level, with intervals above zero, but the edge shrinks from 2 to 3 points at store level to about 1 point on single items; on a 10-item sample it tied. Exponential smoothing did not win and was dropped |
| **Conformal-style ranges from the method's own earlier errors** | Coverage is measured on the past, not assumed from a distribution | "Is it guaranteed?" | No: calibrated on average, overlapping dates make intervals indicative |
| **Newsvendor quantile for orders** | It's the cost-minimising stock level for a given cost of too little versus too much, and I checked it by brute force | "Your demand distribution isn't fitted" | Correct: it's an empirical approximation (forecast times earlier actual/forecast ratios), which is why the app shows a calibration table; real service levels were 0.7 to 2.6 points under target on the item sample |
| **Defaults reported, costs never invented** | A hidden zero cost gives a confident wrong answer | "What if the user has no costs?" | Fixed service levels (80/90/target) and no money figures, with a banner saying why |
| **Scenarios as pure functions on copies** | Isolation can be tested; the baseline can't change by accident | "Is +20% demand realistic?" | The app doesn't know. The user states it and the results are labelled hypothetical; price elasticity must be supplied, not inferred |
| **Health: error-based status, drift informational** | The data changing isn't a failure; the forecast failing is | "Why not use PSI?" | I tried the standard limits: they fired on 64% of M5 item-days because sales move around, and 76% of those days were healthy by error. So PSI is shown, not used |
| **Admitting revisions** | Honest process builds trust | "Did you tune thresholds?" | Twice, and both are disclosed: "worse than the simple rule" went from 1.00 to 1.10 after it flagged noise on stable synthetic data; and when I moved the demo from 10 stores to 100 single items the fixed limits fired on half of all item-days, so each signal must now also be unusual for that item's own noise (2 and 3 robust deviations, chosen as conventions before measuring). The fixed-only result is kept in the report |
| **Challenger never deployed** | Auto-switching models on 12 overlapping dates would be reckless | "How strong is the test?" | Weak; the interval is wide and the verdict says so |
| **Append-only log with a hash chain** | Triggers stop the app rewriting history; hashes reveal edits by anyone who bypasses them | "Is it tamper-proof?" | No, tamper-evident: someone with the file could rebuild the chain; it also can't say who wrote a record |
| **Server recomputes decisions** | The log must hold what the system actually said, not what a browser sent | "Why can't the user edit it?" | They can change the quantity ordered and add a note; the recommendation itself is the server's |
| **Outcome only from the same history** | Judging a decision against a file whose past was restated would be meaningless | "What if the shop corrects numbers?" | Then that file can't judge the decision, by design |

## Numbers worth knowing (all from `reports/`)
- Learning model WAPE against the reference rule: 32.9% against 33.9% on 100 items (+1.0 point, interval +0.2 to +1.6); 4.5% against 7.5% (all stores), 7.5% against 9.8% (one store), 11.5% against 13.6% (store by department).
- Range coverage: on the item sample the 80% range held 79.9% and the 90% range 89.7%; at store and company level 79 to 84% and 89 to 93%.
- Alerts (98% level): 82% of injected one-day changes caught, 2.0% false alarms; +30% days mostly missed.
- Order service levels (100 items): stated 95% held 94.1% (3-day cover), 93.6% (10-day), 92.4% (28-day).
- Health on the 100 M5 items: 80.3% healthy, 9.6% watch, 10.1% action of 14,600 item-days (fixed limits alone: 48.2%, 31.1%, 20.7%). On synthetic data a +50% change left "healthy" after a median of 3 days (worst 6), a -30% change after 6 (worst 9).
- Speed (100 items): order recommendation 1.1 s, three scenarios 1.4 s, health 0.14 s, recording a decision 0.22 s, the retrained-model test 7 s; the first analysis of the sample takes about four minutes, once.
- Tests: 211 Python, 43 web.

## Things that went wrong (tell these; they show judgement)
- A replay on every 7th day made every origin a Sunday and one baseline look far worse than it is; a step of 5 days fixed it and a test guards it.
- The importer read store names such as `CA_1` as numbers; found by loading the sample, fixed with a regression test.
- The first interface was upload-first with a dark blue stage and looked like a template; rebuilt as a dashboard.
- My own calibration test needed a lower threshold than I first set because the synthetic data gives fewer cases; I changed the test, not the claim, and noted it.
- The first health threshold fired on noise (above).
- The decision-log page showed a failure box in the public demo; found in the integration sweep and fixed.
- The first demo sample was 10 stores, which made everything look easy. Switching to real items showed errors of about a third of sales, a learning-model edge of about one point instead of two to three, and a health monitor that cried wolf on half of all days; I reported all three and fixed the monitor instead of picking friendlier data.

## Do not claim
- Anything about Egyptian shops. The Egyptian calendar works on labelled synthetic data only; M5 shows no Islamic-event effect.
- That it "improves profit" or "reduces stock-outs" in a business. It hasn't been tried on one. What is shown: calibrated ranges, order arithmetic that matches hand calculation, and a measured service-level gap.
- That the Arabic is reviewed. It is not.
- That price or promotion scenarios predict anything. They are arithmetic on typed assumptions.
- That the log is tamper-proof, or that the health thresholds are validated on real shops.

## Questions to ask them back
Where do forecasts get used for ordering today, and how do they know when to stop trusting them? How are outcomes recorded? Those are exactly the two gaps this project is built around.
