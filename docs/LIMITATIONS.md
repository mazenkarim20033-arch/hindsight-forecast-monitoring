# Limitations

What Hindsight does not do, as of Milestone 6. This file grows with each milestone.

- **Evidence is US retail only.** Results come from 10 Walmart stores (M5). Nothing is claimed for Egyptian shops, pharmacies, restaurants, warehouses or manufacturers. The Egyptian calendar is shown to work only on labelled synthetic data.
- **The sample has only daily sales.** No prices, costs, stock levels or lead times. Every money figure in the optimizer comes from numbers typed in by the user, or from the labelled illustrative example.
- **Sales are not demand.** A stock-out lowers recorded sales, so forecasts learned from sales understate demand where shortages happened.
- **Demand spread is an approximation.** It is built from the forecast's own earlier ratios of actual to forecast. On M5 stores a stated 95% availability held 91.5 to 94.5% of the time (details in FEATURE_DOCUMENTATION.md).
- **Forecasts reach at most 28 days ahead**, so lead time plus review period above 28 days is refused.
- **Item-level intermittent demand** (most days zero) has not been evaluated for ordering.
- **Daily data only**; weekly or monthly files must be converted first.
- **The public demo is recorded playback**: it cannot load files or recompute the optimizer.
- **Arabic text was written by Claude, not reviewed by a native speaker**, including the new inventory screen.
- **Nothing is stored on the server between restarts** (files). Saved scenarios live in the browser only. Only the decision log is stored on the server computer.
- Not yet tested on phones, Safari or Firefox.
- **Scenario results are not forecasts.** They apply assumptions the user states (demand change, promotion, delay, price elasticity). Hindsight has not tested any of them against what really happened, and does not estimate price elasticity. Scenario spread is the baseline spread scaled; one factor applies to all items; pull-forward after a promotion and cannibalisation are not modelled.
- **Forecast health is a set of conventions, not a validated detector.** Limits are round numbers; one was revised after a first look. Detection was shown on synthetic changes, and about a quarter of M5 store-days were not healthy with no ground truth for which were real. Demand drift (PSI, KS) is shown but never sets the status. The challenger test uses about 12 overlapping dates, so its verdict is weak evidence, and Hindsight never switches methods by itself.
- **Onboarding is heuristic.** Column detection and the data-quality checks use word lists and round-number limits; unusual headers need a manual pick or a saved adapter. Stock, price and cost are read as the latest value in the file and are not reconciled with sales. Wide files carry no price, cost or stock. Nothing about detection accuracy is claimed beyond the tested cases.
- **The decision log is tamper-evident, not tamper-proof, and permanent.** Records cannot be edited or deleted, a person with the file can rebuild the chain, and the log stays on one computer. Outcomes judge one cover period from recorded sales (not demand) and need a newer version of the same file with unchanged history.
- **Integration is tested on synthetic and sample data only.** Speed was measured on one development computer; no real business file has been run end to end.
