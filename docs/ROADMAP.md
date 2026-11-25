# Roadmap

Ordered by how much each item would raise trust in the product, not by how interesting it is. Every item points at a limit already stated in `LIMITATIONS.md`.

## Next (needs a real business, not more code)
1. **Run on one real shop's file** and report the results, good or bad (`EVALUATION_PLAN.md`, S1 to S3). Everything else rests on this.
2. **Native Arabic review** of every screen (S6). The wording was written by Claude and has not been read by a native speaker.
3. **Publish the new work.** Commit, push, redeploy the public demo, update the portfolio and CV text, add the project to LinkedIn. Each is an outward action that waits for the owner.

## Soon (small, well-defined)
4. **Per-item price and unit cost.** The optimizer takes one price and one cost. Onboarding already reads per-item values from a file; the arithmetic needs to use them.
5. **Carry-over policy simulation.** Orders are judged one cover period at a time. A multi-period simulation would show the effect of stock carried between orders.
6. **Intermittent single items.** The bundled sample is 100 products that each sold on at least 80% of days. Evaluate forecasting and ordering for single items in single stores (68% zero days in M5) and, if needed, a different demand model for them.
7. **Investigate the calibration gap.** Order service levels land 0.7 to 2.6 points under target on the item sample and the gap grows with the cover period. Candidates include growth over the period; it was not examined.
8. **Per-item scenarios.** One factor applies to all items today.
9. **Move the older routes out of `api.py`** into per-feature routers like the newer ones (deferred as a risky rewrite with no user-visible benefit).

## Later (larger)
10. **Demand rather than sales.** Correct recorded sales for stock-outs when stock history is available.
11. **Promotion and price data as model inputs,** so that scenario effects can be estimated from the business's own history instead of typed in. Not before enough history exists to check the estimate.
12. **Alert delivery** (email or messaging) for Watch and Action needed, and per-item thresholds.
13. **Sharing adapters** between computers, and a way to back up the decision log.
14. **Other time grains** (weekly, monthly) and other horizons.
15. **Wider browser and device testing** (phones, Safari, Firefox) and a screen-reader pass.

## Deliberately not planned
- Automatic deployment of a retrained model, automatic ordering, or any action without a person's decision.
- Claims about Egyptian businesses before an Egyptian business's data has been tested.
- A multi-user cloud service. The tool is for one business on one computer; the owner-only rule and in-memory uploads follow from that.
