# Hindsight: project overview

**One line.** A local web app that forecasts daily sales, shows a measured track record for every forecast, and turns the forecast into order decisions that can be checked later.

## The problem
Small and mid-sized businesses are offered forecasts as a single number with an "AI" label. Two things are missing. First, any way to know whether that number deserves trust. Second, a link from the number to a decision (how much to order) and from the decision back to what actually happened. Hindsight is built around closing both gaps honestly: every claim it makes carries a measurement, and what it cannot know is said on the screen.

## Who it is for
An owner or planner of a business that sells in units every day (a shop, pharmacy, restaurant, warehouse) and can export daily sales to CSV or Excel. It is a single-business, single-computer tool, not a multi-user cloud service.

## What it does
| Area | What you get | Where it is described |
|---|---|---|
| **Forecast with a track record** | Next-days forecast per item with a range whose coverage is measured on the past; plain-language reasons; odd-day alerts; replay lab; scorecard against a simple rule | `CASE_STUDY.md`, `EXPERIMENTS.md` |
| **Decision Optimizer** | How much to order under three options (conservative, balanced, high availability) from your costs, lead time and stock; every assumption labelled; a measured check of how often the stated service level held | `FEATURE_DOCUMENTATION.md` |
| **What-if Scenarios** | Demand change, promotion, supplier delay, lower stock, price change (with your own elasticity) shown next to the baseline, labelled hypothetical | `FEATURE_DOCUMENTATION.md` |
| **Forecast Health Monitor** | Healthy, Watch or Action needed from recent error, simple-rule comparison, bias and range coverage; demand drift shown as information; an optional retrained-model test that is never deployed | `FEATURE_DOCUMENTATION.md`, `reports/health_m5.md` |
| **Smart Data Onboarding** | Columns found in English and Arabic, item names from several columns, duplicate handling, price/cost/stock columns, data-quality findings, saved adapters | `FEATURE_DOCUMENTATION.md`, `DATA_DICTIONARY.md` |
| **Decision Audit** | A tamper-evident, append-only record of each decision and, later, what happened | `FEATURE_DOCUMENTATION.md` |

The interface is in English and right-to-left Arabic. The app opens on a bundled sample (100 real Walmart items from the public M5 data), never on an upload screen.

## How it was built
The first version (replay, forecasters, ranges, reasons, alerts, dashboard) was built in earlier milestones and published. The decision-intelligence upgrade was added in seven milestones, each ending in tests, documentation and an approval before the next began:

| Milestone | Delivered | Tests after it (Python / web) |
|---|---|---|
| 0 | Audit of the existing app and plan | - |
| 1 | Decision Optimizer | 125 / 31 |
| 2 | What-if Scenario Simulator | 151 / 33 |
| 3 | Forecast Health Monitor | 165 / 35 |
| 4 | Smart Data Onboarding | 189 / 37 |
| 5 | Decision Audit | 206 / 40 |
| 6 | Integration across features, performance, demo mode | 207 / 43 |
| 7 | Final documentation and review | see `README.md` |

Rules held throughout: nothing rewritten or removed, no random train/test splits and no future leakage, no invented financial assumptions (missing costs are never silently zero), scenario results never presented as validated, no automatic deployment of any model, no M5-specific assumptions in the general platform.

## What is evidenced, and what is not
**Evidenced (public M5 Walmart data, US retail; the bundled sample is 100 items, each added up over the chain's 10 stores):** on those items the learning model beats the best simple rule by about 1 WAPE point (32.9% against 33.9%, interval +0.2 to +1.6), ahead on 88% of replay dates, while at store and company level the edge is 2 to 3 points; stated 80% and 90% ranges held on 79.9% and 89.7% of days; order service levels land 0.7 to 2.6 points under their targets (a gap that grows with the cover period); the health monitor reacts within days to an injected level change on synthetic data and, judged against each item's own earlier noise, calls 80% of item-days healthy on the sample (the fixed limits alone called 48% healthy).

**Not evidenced:** anything about Egyptian shops, pharmacies, restaurants or warehouses; the money figures of the optimizer on a real business (the sample has no prices, costs or stock); price elasticity or promotion effects; health thresholds on real shops; the Arabic wording (written by Claude, not read by a native speaker); item-level intermittent demand for ordering. See `LIMITATIONS.md`, and `EVALUATION_PLAN.md` for how each gap would be closed.

## Repository map
```
src/hindsight/   data/ replay/ inventory/ scenarios/ monitoring/ audit/ app/      (Python: engine, features, API)
web/src/         pages, components, i18n (EN/AR), recorded-playback client       (React + TypeScript + Vite)
tests/           Python tests, including end-to-end integration
scripts/         evaluation and export scripts; reports/ holds their output
adapters/        shipped example column mappings
docs/            this documentation
```

## Status
Seven of seven milestones are built locally. Publishing the new work (committing, pushing, redeploying the public demo), the LinkedIn entry and the Arabic review all wait for the owner's go-ahead.
