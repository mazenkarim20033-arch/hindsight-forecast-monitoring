# Limitations

What Hindsight does not do, as of Milestone 6. This file grows with each milestone.

- **Evidence is US retail only.** Results come from public Walmart data (M5): 100 real items added up over 10 stores, plus store- and company-level research. Nothing is claimed for Egyptian shops, pharmacies, restaurants, warehouses or manufacturers. The Egyptian calendar is shown to work only on labelled synthetic data.
- **The sample has only daily sales.** No prices, costs, stock levels or lead times. Every money figure in the optimizer comes from numbers typed in by the user, or from the labelled illustrative example.
- **Sales are not demand.** A stock-out lowers recorded sales, so forecasts learned from sales understate demand where shortages happened.
- **Demand spread is an approximation.** It is built from the forecast's own earlier ratios of actual to forecast. On the M5 item sample a stated 95% availability held 92.4 to 94.1% of the time (details in FEATURE_DOCUMENTATION.md).
- **Forecasts reach at most 28 days ahead**, so lead time plus review period above 28 days is refused.
- **Item-level intermittent demand** (most days zero) has not been evaluated for ordering.
- **Daily data only**; weekly or monthly files must be converted first.
- **The public demo is recorded playback**: it cannot load files or recompute the optimizer.
- **Arabic text was written by Claude, not reviewed by a native speaker**, including the new inventory screen.
- **Nothing is stored on the server between restarts** (files). Saved scenarios live in the browser only. Only the decision log is stored on the server computer.
- Not yet tested on phones, Safari or Firefox.
- **Scenario results are not forecasts.** They apply assumptions the user states (demand change, promotion, delay, price elasticity). Hindsight has not tested any of them against what really happened, and does not estimate price elasticity. Scenario spread is the baseline spread scaled; one factor applies to all items; pull-forward after a promotion and cannibalisation are not modelled.
- **Forecast health is a set of conventions, not a validated detector.** Limits are round numbers; one was revised after a first look. Detection was shown on synthetic changes; on the M5 items 20% of item-days were not healthy with no ground truth for which were real, and the rule was changed once after the fixed limits fired on half of them. Demand drift (PSI, KS) is shown but never sets the status. The challenger test uses about 12 overlapping dates, so its verdict is weak evidence, and Hindsight never switches methods by itself.
- **Onboarding is heuristic.** Column detection and the data-quality checks use word lists and round-number limits; unusual headers need a manual pick or a saved adapter. Stock, price and cost are read as the latest value in the file and are not reconciled with sales. Wide files carry no price, cost or stock. Nothing about detection accuracy is claimed beyond the tested cases.
- **The decision log is tamper-evident, not tamper-proof, and permanent.** Records cannot be edited or deleted, a person with the file can rebuild the chain, and the log stays on one computer. Outcomes judge one cover period from recorded sales (not demand) and need a newer version of the same file with unchanged history.
- **Integration is tested on synthetic and sample data only.** Speed was measured on one development computer; no real business file has been run end to end.
- **The learning model's edge on single items is small.** About 1 WAPE point on 100 items (interval +0.2 to +1.6), against 2 to 3 points at store and company level; on 10 items it tied. Errors on single items are about a third of sales. Items that sell on fewer than 80% of days (and single items in single stores) were not part of the sample.
