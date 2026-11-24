# Forecast health: how the rules behave

## A. M5 sample (10 stores, every 5th day of the last 730 days, method: best method so far)

Store-days checked: 1460. Shares: {'healthy': 0.763, 'watch': 0.19, 'action': 0.047, 'unknown': 0.0}

## C. Demand drift on the same store-days

PSI above the conventional 0.25 limit on 1016 of 1460 store-days (70%); on 769 of those (76%) the status from error-based signals was healthy. That is why drift is shown but does not set the status.

## B. Injected change: sales rise 50% on day 480 of 640

Seeds: 12. Missed entirely: 0. Days until the item left 'healthy': median 3, worst 6. 'Action' reached in 12 of 12 seeds (median 6 days).

## B. Injected change: sales fall 30% on day 480 of 640

Seeds: 12. Missed entirely: 0. Days until the item left 'healthy': median 4, worst 9. 'Action' reached in 12 of 12 seeds (median 9 days).

## B. Unchanged synthetic series (12 seeds, every 5th day from day 300)

Item-days: 1872. Shares: {'healthy': 0.899, 'watch': 0.096, 'action': 0.005, 'unknown': 0.0}

Caveat: synthetic data is easier than real sales. These numbers say the rules can notice a clear change and stay mostly quiet otherwise; they do not promise the same on a real shop.
