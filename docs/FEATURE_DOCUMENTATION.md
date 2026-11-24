# Feature documentation

Status key: **implemented** means built, tested and measured as described; **planned** means not built. Milestones 1 to 6 are implemented so far.

## Decision Optimizer (implemented, Milestone 1)

Screen: **Inventory & decisions**. API: `POST /api/datasets/{id}/inventory`. Code: `src/hindsight/inventory/` (arithmetic and input rules), `src/hindsight/app/inventory_service.py` (joins it to the forecast), `src/hindsight/app/inventory_routes.py`.

### What it does
For every item (or store), recommends how much to order over a cover period under three options, and shows what each option costs and risks:

| Option | Rule |
|---|---|
| Balanced | The demand quantile at the critical ratio `Cu / (Cu + Co)`: the order that minimises expected cost. |
| Conservative | The same rule, counting a lost sale as `conservative_factor` (default 0.5) times as costly. |
| High availability | At least the target availability (default 95%), or the balanced level if that is higher. |

The quantities are computed from the forecast and the costs; none is a fixed number.

### Inputs
Lead time, days between orders (or the selling period), price, unit cost, holding cost per unit per day, extra cost of a lost sale, salvage value, target availability, minimum order, order multiple, and on-hand and on-order stock per item. Anything left empty is treated as **unknown, never zero**. The response lists every assumption used, marked `user` or `default`.

Defaults that exist (all reported when used): 7 days between orders; target availability 95%; conservative weight 0.5; stock-out penalty 0 (when costs are given); salvage 0 (single period). Without prices and costs the three options use fixed cover levels (80%, 90%, target) and **no money figures are produced**. If holding cost is missing in regular-ordering mode, costs are also withheld, because leftovers cannot be weighed.

### Mathematics
Let `D` be demand over the cover period, `Cu` the cost of ordering one unit too few and `Co` the cost of one unit too many. The stock level minimising `E[Cu·(D−Q)+ + Co·(Q−D)+]` is the quantile `F⁻¹(Cu/(Cu+Co))` (the newsvendor result; checked by brute force in `tests/test_inventory.py`).

- **Regular ordering (base stock).** Cover period `T = lead time + days between orders`. Order-up-to level `S` is the demand quantile over `T`; order = `S − (on hand + on order)`, then raised to the minimum order and rounded **up** to the order multiple (so rounding can only raise availability). `Cu = price − unit cost + stock-out penalty`. `Co = holding cost × days between orders`: leftover units are carried for one more cycle. This is a single-cycle approximation of the multi-period optimum, not the exact solution for lost sales.
- **One selling period (perishables).** Cover period is the selling period; `Co = unit cost − salvage + holding × period`. Stock on hand is netted off.
- **Outcomes** for a stock level `Q` are averages over the demand outcomes: expected leftover `E[(Q−D)+]`, expected shortage `E[(D−Q)+]`, chance of running short `P(D>Q)`, fill rate `E[min(D,Q)]/E[D]`. Money: excess cost `Co·leftover`, lost-sales cost `Cu·shortage`, investment `unit cost × order`. Expected profit is for this order only (stock already held is treated as sunk).

### Where the demand distribution comes from
Hindsight's forecaster gives a point forecast, not a full distribution. The demand outcomes are the live forecast of the cover period multiplied by earlier ratios of actual sales to forecast for periods of the same length (the newest 120, at least 20 needed, only periods that had already finished). This is an **empirical approximation of the spread**, not a fitted model. The screen therefore shows a calibration table: on the replayed past, how often did demand stay within each order-up-to level?

### Evaluation (actual results)
`scripts/run_inventory_check.py` on the 10-store M5 sample (141 scored dates × 10 stores = 1,410 cases per row; `reports/inventory_m5.md`):

| Cover | Target 80% | 90% | 95% | 98% |
|---|---|---|---|---|
| 3 days | 77.6% | 88.9% | 94.5% | 98.3% |
| 10 days | 76.5% | 87.6% | 93.4% | 97.8% |
| 28 days | 74.3% | 85.6% | 91.5% | 96.0% |

The target is slightly **missed**: the real service level is 0 to 6 points below it, and the gap widens with the cover period. The cause is not investigated here (sales growth over the period is one candidate). Read a displayed 95% as "about 92 to 95% on this data". Cases overlap in time, so small gaps are within noise. Store-level data only; not checked on item-level data with many zero days.

Tests (`tests/test_inventory.py`, 26): quantile result against hand-computed values and brute force; a normal distribution against its closed form; higher underage cost gives more stock; inventory position netting; minimum order and multiples; zero and constant demand; missing and unusable inputs refused with a code; strategy ordering on a real replay; lead time monotonicity; no change to forecasts by asking.

### Limits
- The sample has **no prices, costs, stock or lead times**. The demo uses clearly labelled illustrative numbers; none of its money figures describe a real business.
- Sales are not demand: stock-outs hide demand, so the forecast and order are biased low where shortages happened.
- Cover periods above 28 days cannot be planned (the forecaster looks 28 days ahead); the request is refused with an explanation.
- No claim for intermittent item-level demand (most days zero) until it is evaluated. Single-period mode and the money figures are tested for arithmetic, not validated against a real business.
- No carry-over policy simulation yet (planned). The older **ordering-rule backtest** remains on the same screen.
- The public demo shows one recorded example and cannot recompute.

### Adding a business or dataset
The optimizer needs only a forecast per item and the settings above. Prices, costs and stock are never read from the data file yet; per-item costs and stock upload arrive with Smart Data Onboarding (planned).

## What-if Scenario Simulator (implemented, Milestone 2)

Screen: **Inventory & decisions → What-if scenarios**. API: `POST /api/datasets/{id}/scenarios`. Code: `src/hindsight/scenarios/apply.py` (pure functions), `src/hindsight/app/scenario_service.py`, route in `inventory_routes.py`.

### What it does
Takes the baseline from the Order decisions tab (same costs, lead time, stock) and up to 8 user-defined scenarios, and shows baseline and scenarios side by side for the chosen option (conservative, balanced or high availability): total order, money tied up, expected leftover, expected shortage, expected cost of being wrong. It also answers the sharper question for each scenario: **what would the baseline order mean if the scenario happened?** (`if_baseline_order`: shortage, leftover, cost and the chance of running short, per item and in total.)

| Scenario input | How it is applied |
|---|---|
| Demand change (%) | Every demand outcome is multiplied by 1 + pct/100. |
| Promotion, seasonal change, demand spike (% and days) | Factor = 1 + pct/100 × days/cover days (days beyond the cover period are cut and the screen says so). Daily demand is taken as flat across the period. |
| Supplier delay (days) | Lead time + delay, so the cover period is longer and the forecast of that longer period is used. Stock already on order is not delayed. Regular-ordering mode only. |
| Stock reduction (%) | Stock on hand × (1 − pct/100) for items with a stock figure; stock on order unchanged. Needs stock for at least one item. |
| Price change (%) | Price used for margins × (1 + pct/100) and demand × (1 + pct/100)^elasticity (constant elasticity). **The user must supply the elasticity** (negative); Hindsight does not estimate it. |

Several effects in one scenario are combined by multiplying demand factors (+10% and +10% make +21%).

### Design decisions (for interviews)
- **Pure functions on copies.** `apply(scenario, settings, stock)` deep-copies its inputs and returns new ones; the baseline objects are never touched. The endpoint is stateless: baseline and scenarios arrive together and nothing is stored on the server, so scenarios cannot leak into the baseline or each other. Tests check that results do not change with the other scenarios in the request and that later plain requests are unaffected.
- **Scenarios reuse the optimizer.** Each is one call of the same `recommend` function with changed inputs and a demand factor, so the maths is not duplicated.
- **Nothing is invented.** Elasticity is required and refused if missing or positive; a price change without a price, a delay in single-period mode, a stock cut with no stock, a window beyond the forecast, a price drop that removes the margin: each is refused with a plain-language reason and a code. A refused scenario does not stop the others.
- **Not presented as validated.** Every scenario is labelled hypothetical, its effects are listed as assumptions, results carry no calibration (the track record in M1 describes the baseline only), and the notes say the effects were never checked against what really happened.
- **Saving, renaming, removing, resetting** live in the browser (`localStorage`), because a server store was not needed for a stateless calculation. Export gives JSON (everything) or CSV (totals for the chosen option).

### Evaluation (actual results)
These are correctness tests, not accuracy claims: `tests/test_scenarios.py` (26 tests). Demand factors and the elasticity formula against hand computation; effects multiply; baseline objects unchanged after `apply`; more demand gives larger orders (scaled by the factor within 1%); a stock reduction of x units adds x units to the order; a supplier delay lengthens the cover and raises the order; the baseline order runs short more often when demand rises and leaves more unsold when it falls; scenario results are identical alone or among others; refusals and bad ranges.

### Limits
- Scenario results are arithmetic on stated assumptions, **not forecasts**. Whether a +30% promotion really lifts sales 30% is the user's assumption.
- The spread around a scenario is the baseline spread scaled by the factor. Promotions can change how uncertain demand is; that is not modelled.
- Promotion pull-forward (sales dipping afterwards), cannibalisation and a delay in stock already on order are not modelled.
- Price elasticity is constant by assumption.
- One factor applies to all items. Per-item scenarios are not supported yet.
- The public demo shows five recorded scenarios (example sizes chosen by the author, elasticity -1.5 typed in as an example) and cannot recompute.

## Forecast Health Monitor (implemented, Milestone 3)

Screen: **Forecast health**. API: `POST /api/datasets/{id}/health` and `POST /api/datasets/{id}/health/challenger`. Code: `src/hindsight/monitoring/` (`drift.py`, `rules.py`: pure), `src/hindsight/app/health_service.py`, `src/hindsight/app/monitoring_routes.py`. Read-only: nothing here changes what the app forecasts.

### What it does
Answers "is the forecast still doing as well as it did?" with one status per item and overall: **Healthy, Watch, Action needed, or Not enough history**, with the reasons in plain words, a chart of recent error over time, and the thresholds used.

| Check | Measure | Watch / Action |
|---|---|---|
| Error against earlier | WAPE over the last 8 replay dates divided by WAPE over up to 150 earlier ones | > 1.25 / > 1.5 |
| Against the simple rule | recent WAPE divided by the same-weekday rule's WAPE on the same dates | > 1.10 / > 1.30 |
| Leaning high or low | recent (forecast - actual) divided by actual, absolute | > 10% / > 20% |
| Range held | share of real sales inside the 80% range | < 70% / < 55% |
| Demand shift (information only) | PSI of the last 56 days against the 364 before, plus KS statistic and p-value | shown above 0.10; never sets the status |

The status is the worst of the four error-based checks. All limits are in `monitoring/rules.py`, returned with every response, and can be overridden per request.

### Design decisions (for interviews)
- **As of a day, leak-free by construction.** `health(..., day=D)` uses only replay dates whose whole forecast horizon had been observed by day D. A test rewrites everything after D and checks the answer does not move. The same function can therefore be run on every past day to measure how often it would have fired.
- **Drift does not set the status.** The data changing is not a failure; the forecast failing is. PSI limits (0.10 / 0.25) are conventions from credit scoring. On M5 they fire on 70% of store-days because sales grow, and on 76% of those the error-based status was healthy. So PSI and KS are measured and shown but informational. This was decided from that evidence (`reports/health_m5.md`).
- **One threshold was revised after a first look, and it is said so.** "Worse than the simple rule" flagged at 1.00 on stable synthetic data, which is noise when the method and the rule are near-identical; it now flags at 1.10 and 1.30. No other limit was changed.
- **Challenger, never deployed.** The test retrains the same learning model on only the latest 365 days (refit every 14 days), replays the last 12 dates against the current method through the same replay engine (so it sees only what was known then), and reports the paired WAPE difference with a bootstrap interval. The verdict is `promote_candidate` only if the whole interval favours the challenger; otherwise `keep_current` or `inconclusive`. `deployed` is always false: Hindsight has no mechanism to switch methods by itself.

### Evaluation (actual results, `scripts/run_health_check.py`, written to `reports/health_m5.md`)
- **M5 sample**, 1,460 store-days (every 5th day of the last 730): 76.3% healthy, 19.0% watch, 4.7% action. M5 has no known broken period, so these are shares of alarms, not proven false alarms.
- **Injected change** (synthetic weekly data, one item, change on day 480, 12 seeds each). Sales +50%: caught in all 12, median 3 days (worst 6) to leave "healthy"; "action" in all 12 (median 6 days). Sales -30%: caught in all 12, median 4 days (worst 9); "action" in all 12 (median 9 days).
- **Unchanged synthetic series** (12 seeds, 1,872 item-days): 89.9% healthy, 9.6% watch, 0.5% action.
- **Tests** (`tests/test_health.py`, 14): PSI and KS on known distributions, ties and tiny samples; grading rules; drift never changes the status; nothing after the chosen day is used; unknown (not a guess) when history is short; an injected change caught within 45 days in 5 seeds while an unchanged item under a fixed method never reaches "action"; low rate of "action" on stable data; API and threshold overrides; challenger refused without two years of data; challenger evaluated on the past, never deployed, and leaving the analysis untouched.
- **Challenger on M5** (12 dates): no clear difference (retrained 7.37% against current 7.41% error, interval -0.33 to +0.35 points): `inconclusive`.

### Limits
- Synthetic data is easier than real sales; the detection numbers show the rules can notice a clear change, not that they will on a real shop.
- About a quarter of M5 store-days are not healthy; some are probably real bad stretches (holidays), some noise. This was not separated.
- Replay dates overlap, so the recent window holds fewer independent results than eight. The challenger uses 12 dates: its interval is wide and a single test is weak evidence.
- With "best method so far", one method is chosen for all items together, so a change in one item can make the others look worse (seen in testing).
- Health is measured against recorded sales, not demand.
- Thresholds are conventions, not fitted. Per-item thresholds and alert delivery (email, messages) are not built.
- The public demo shows the recorded status and one recorded challenger test for the default method; it cannot recompute.

## Smart Data Onboarding (implemented, Milestone 4)

Screen: the **Data** page, after a file is chosen. API: `POST /api/datasets` (upload), `POST /api/datasets/{id}/mapping` (choices), `GET /api/adapters`, `POST /api/datasets/{id}/adapters` (save). Code: `src/hindsight/data/importer.py` (extended), `data/quality.py`, `data/adapters.py`, `adapters/` (shipped examples). Existing import behaviour is unchanged unless a new option is used.

### What it adds
| Feature | What happens |
|---|---|
| **Item names from several columns** | A file with region and product columns used to name items by one of them and silently add the other away. Now a warning says so (`other_id_columns`), and ticking both columns names each item `North / Milk` (a composite key). Totals are preserved: the same sales, split further. |
| **Exact duplicate rows** | Rows identical to another row in every column are counted and reported (`exact_duplicates`). Default is to add them together, as before (receipts do repeat); the user can choose to remove the extra copies (`duplicates_dropped`). Rows that differ in any column are never called duplicates. |
| **Price, unit cost, stock on hand, stock on order columns** | Found by header (English and Arabic) and by being mostly numbers, kept out of the sales column and out of item detection, and read as the **latest value per item**. The Inventory screen's button "Use stock and prices from the file" fills stock per item; a price or cost is filled only when every item has the same one (the optimizer takes a single value), otherwise it is left empty and the screen says so. Holding cost is never in a sales file and is never guessed. |
| **Data-quality findings** | Reports only, never changes data: no sales in the last 7 days for every item (export cut off), items that stopped selling, items that started late, mostly-zero items, always-identical values, and days far above an item's usual level (robust: median plus 8 scaled MADs and at least 3 times the median). Each names the items and gives examples. |
| **Adapters (YAML)** | A saved description of how one kind of file maps onto the data: date, sales, item (or several), price/cost/stock columns, duplicate rule. A file matches when every column the adapter names is present; the best match (most columns) is suggested, and "Use it" sets the same choices the screen offers. `adapters/m5_stores.yaml` ships as an example; saved ones go to `artifacts/adapters/`. |

### Design decisions (for interviews)
- **Extend, do not rewrite.** The importer keeps its signature and all 31 earlier tests pass unchanged; new behaviour is reached only through new mapping keys (`item_cols`, `business`, `duplicates`).
- **Report first, act on request.** Quality findings and duplicate warnings never alter data on their own. The one automatic behaviour (adding duplicates together) is the old behaviour, now visible.
- **Business values are opt-in and never invented.** They are offered, not applied; unknown stays unknown (the M1 rule). A price that differs by item is not averaged.
- **Adapters cannot do more than a person could.** They only set the same column choices. YAML is read with `safe_load` and validated by Pydantic; names are plain slugs equal to the file name (no path traversal); files are read and written only in two fixed folders; broken files are reported, not fatal. A test confirms a YAML file with a Python-object tag runs no code.
- **Saving an adapter is owner-only**, like loading data, and stores column names only, never data.

### Evaluation (actual results)
`tests/test_onboarding.py` (24 tests), run with the 31 earlier importer and data tests (all pass):
- composite key: 2 columns flagged, 4 items after choosing both, total sales unchanged; unknown column refused;
- duplicates: counted, summed by default, removed on request, unknown rule refused, differing receipts never flagged;
- business columns: found by English and Arabic headers, `stock on order` not confused with stock on hand, `unit cost` not confused with price, a lone price column not treated as an item or as sales, latest value per item, can be switched off, absent when the file has none;
- quality: a healthy file has no findings; stopped, late, cut-off, spike, sparse and constant cases each found; data left unchanged;
- adapters: YAML round trip, best match by columns, applying one equals choosing by hand, path-like and invalid names refused, overwrite refused unless asked, broken or hostile YAML reported and not executed, saved overrides built-in;
- API: quality, business columns and adapter hint in the upload summary; save, recognise a second file, apply by name, remap with composite key and duplicate rule; the sample cannot save an adapter; saving is owner-only.
No claim is made about how well detection works on files the tests do not cover; real shop exports vary.

### Limits
- Header detection is a list of English and Arabic words. A file whose columns use other words needs the column picked by hand (or an adapter saved once).
- Wide files (one column per item) do not carry price, cost or stock columns.
- Only daily data. Weekly or monthly files must be converted first.
- Stock is read as the latest row's value, not reconciled against sales. A stock column that is a snapshot at a different date from the last sales day will be off by that gap.
- Quality limits (28 days, 90 days, 60% zero days, 8 deviations) are round numbers, not fitted.
- One price and one unit cost for the whole optimizer; per-item prices are not supported yet.
- Adapters are stored on the computer running Hindsight and are not shared between computers.
- The public demo cannot load files, so none of this is exercised there.

## Decision Audit (implemented, Milestone 5)

Screen: **Decision log**, plus a "Record this decision" panel under the order table (Order decisions tab) and under a chosen scenario (What-if tab). API: `POST /api/datasets/{id}/audit/decisions`, `GET /api/audit/events`, `GET /api/audit/verify`, `GET /api/audit/export`, `POST /api/datasets/{id}/audit/review`, `POST /api/datasets/{id}/audit/outcomes`. Code: `src/hindsight/audit/` (`store.py`, `outcome.py`), `src/hindsight/app/audit_service.py`, `src/hindsight/app/audit_routes.py`. Everything is owner-only, like loading data.

### What it does
Keeps a written record in one SQLite file on this computer (`artifacts/audit/audit.sqlite`, or the path in `HINDSIGHT_AUDIT_DB`):
- **A decision record**: the recommendation for all three options and every item, the quantity actually ordered (and which items were changed from the advice), the free-text reason, the stock and cost inputs and which of them were defaults, the forecast method, forecast health at the time, the cover period, and a fingerprint of the sales history up to that day. Optionally the decision is recorded as planned for a what-if scenario, marked hypothetical.
- **An outcome record** (added later, once the cover period is over): the real sales over the window against what was available (stock plus order), the leftover and shortage, the cost with the recorded costs, the forecast error, and the same worked out for the quantity each of the three options would have ordered, with the cheapest in hindsight named.

### Design decisions (for interviews)
- **Append-only, in two layers.** SQLite triggers abort every UPDATE and DELETE and ids never repeat. On top of that each row stores a SHA-256 hash over the previous hash, the time, kind, reference and the exact payload text, so `verify()` finds an edit, a removal or a reordering even if the triggers were dropped. It is tamper-*evident*, not tamper-proof: someone with the file can rebuild the whole chain, and the log cannot say who wrote it. The screen says so.
- **The server recomputes the recommendation.** A decision is recorded from the loaded analysis and the inputs, not from numbers the browser sends, so the log holds what Hindsight actually said. Only the overrides and the note come from the person.
- **An outcome must come from the same history.** It is accepted only from a file whose values up to the decision day hash to the recorded fingerprint (same items, same numbers, later days added) and only once the whole cover window is observed. A restated history, missing items or an unfinished window give a coded refusal and write nothing. One outcome per decision (a unique index), so a result cannot be re-rolled until it looks good.
- **Preview is separate from saving.** "Check outcomes" computes and shows but writes nothing; saving is an explicit click.
- **Outcome arithmetic is the same as the optimizer's:** stock available over the window is position plus order; leftover and shortage are measured against real sales; cost uses the recorded underage and overage costs. Missing costs give quantities and no money, never a guess.
- **Lazy file.** Importing the program or starting the server creates no file; it appears on the first record.

### Evaluation (actual results)
`tests/test_audit.py` (17 tests): the file is created only on first use; chain links and survives a restart (Arabic text round-trips); the database refuses UPDATE and DELETE; editing a record after dropping the triggers is detected at that record; deleting one is detected; one outcome per decision and only for a real decision; four threads writing 60 records keep the chain intact; outcome arithmetic against hand computation (including no-cost and zero-sales cases); through the API on a real replay: the recorded recommendation equals the optimizer's, overrides are flagged and the advice is kept beside what was done, refused requests write nothing, a scenario decision is marked, a decision waits for its window, the outcome matches real sales (actual demand equals the sum of the following days), a second outcome is refused, a file with restated history or missing items cannot judge a decision, export and verification work and an edit made outside the program is detected, and every route is owner-only.

### Limits
- One cover period per decision, judged on recorded sales, and sales are not demand: a stock-out hides demand. An outcome is one data point, not a verdict on the method or the decision.
- Outcomes need a newer version of the same file with unchanged history. If the shop corrects old numbers, the decision can no longer be judged against that file (by design).
- The log is tamper-evident, not tamper-proof, and is not shared between computers. Backing it up is the user's job (the export button helps).
- Records cannot be edited or deleted, including mistakes and sensitive notes. There is no redaction feature.
- Stock and costs written to the log are whatever was typed or filled from the file; nothing checks them against reality.
- The public demo has no log (it runs without a server).

## Integration (implemented, Milestone 6)

No new engine. This milestone connects the five features so they behave as one product, and checks that they agree with each other.

### How the features connect
```
file -> Onboarding (columns, keys, duplicates, price/cost/stock, quality, adapter)
          |                                   \
          v                                    v  (latest stock and prices, offered not forced)
   replay + forecast  ------------------>  Decision Optimizer  <---- What-if Scenarios (same function, changed copies)
          |                                   |
          v                                   v
   Forecast Health  (caution shown on the     Decision log: record (server recomputes), later outcome from the same history
   dashboard and above the order advice)
```
- **Health reaches the pages that rely on the forecast.** The dashboard has a "Is the forecast still reliable?" section; the order screen shows a caution when health is Watch or Action needed; the health page leads back to the orders.
- **Onboarding feeds the optimizer.** "Use stock and prices from the file" fills per-item stock and, only if every item has the same one, price and cost.
- **Scenarios reuse the optimizer, and the log reuses both.** A scenario's baseline is the plain recommendation; a decision can be recorded under a scenario; the log stores the health status of the moment and a fingerprint of the data.
- **The menu follows the work:** Forecast (dashboard, stores, holiday effects, replay lab, scorecard), Decide (inventory & decisions), Monitor (forecast health, decision log), Files (data). The old Stock planner is still reachable as the "Ordering-rule backtest" tab, and `/planner` still works.

### Evaluation (actual results)
- **One path through everything** (`tests/test_integration.py`): upload a priced file, save an adapter, run the forecast, plan orders with the file's stock (the inventory position equals the file's on-hand plus on-order exactly), run a scenario whose baseline equals the plain recommendation, read health as of the last day, hit the six older endpoints, record a decision (it repeats the optimizer's orders and carries the health status), load the same report with 40 more days (recognised by the adapter), save the outcome (real sales equal the sums from the file; stock available equals position plus order), and verify the log. It compares each step's numbers with another step's.
- **Language parity** (`web/src/test/i18n.test.tsx`, existing): every English string has an Arabic one with the same blanks; it kept passing through all five features.
- **Every screen in a real browser**, light and dark, automated accessibility audit (WCAG A/AA, contrast included): 10 pages plus the scenario and backtest tabs, no violations apart from two pre-existing header items (the brand link and the language button).
- **Public demo mode** (recorded playback): all pages load; the recorded optimizer example, five recorded scenarios, recorded health and one recorded challenger test show; the decision log explains that it lives on the user's own computer instead of showing an error. Found and fixed while checking: the log page used to show a failure box in the demo.
- **Speed** (`scripts/run_perf_check.py` -> `reports/performance.md`, median of three on the development computer): on the 10-store M5 sample an order recommendation takes 0.12 s, three scenarios 0.14 s, health 0.02 s, recording a decision 0.04 s, the challenger test 2.6 s. On a 100-item, 500-day file (the largest the app accepts): 0.95 s, 1.2 s, 0.12 s and 0.21 s; the analysis of that file takes about 11 s once. No optimisation was needed.

### Limits
- The integration test uses synthetic data; the browser sweeps use the M5 sample and made-up files. No real shop has used it yet.
- Health appears on the dashboard and the order screen only; it does not yet block anything. It is advice, by design.
- Moving the older routes out of `api.py` into per-feature routers is still deferred.
- The Arabic text for all five features has not been read by a native speaker.
