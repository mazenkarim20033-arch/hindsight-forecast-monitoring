# Forecast health: how the rules behave

## A. M5 sample (100 items, every 5th day of the last 730 days, method: best method so far)

Item-days checked: 14600.

- Current rule (past the fixed limit AND unusual for that item): {'healthy': 0.803, 'watch': 0.096, 'action': 0.101, 'unknown': 0.0}
- Fixed limits alone (how the monitor first worked): {'healthy': 0.482, 'watch': 0.311, 'action': 0.207, 'unknown': 0.0}

On single items the fixed limits fired on about half of all item-days, because item-level sales are noisy; judging each signal against that item's own earlier ups and downs is the change made after seeing that. M5 has no known broken period, so these are shares of alarms, not proven false alarms.

## C. Demand drift on the same item-days

PSI above the conventional 0.25 limit on 9344 of 14600 item-days (64%); on 7116 of those (76%) the status from error-based signals was healthy. Drift is shown but does not set the status.

## B. Injected change: sales rise 50% on day 480 of 640

Seeds: 12. Missed entirely: 0. Days until the item left 'healthy': median 3, worst 6. 'Action' reached in 12 of 12 seeds (median 6 days).

## B. Injected change: sales fall 30% on day 480 of 640

Seeds: 12. Missed entirely: 0. Days until the item left 'healthy': median 6, worst 9. 'Action' reached in 12 of 12 seeds (median 9 days).

## B. Unchanged synthetic series (12 seeds, every 5th day from day 300)

Item-days: 1872. Shares: {'healthy': 0.933, 'watch': 0.062, 'action': 0.005, 'unknown': 0.0}

Caveat: synthetic data is easier than real sales. These numbers say the rules can notice a clear change and stay mostly quiet otherwise; they do not promise the same on a real shop.
