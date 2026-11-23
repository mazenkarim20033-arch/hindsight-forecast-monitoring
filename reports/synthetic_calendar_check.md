# Egyptian calendar check on SYNTHETIC data

**This is made-up data.** Sales were generated with a known +50% lift in Ramadan and +60% on Eid al-Fitr, plus a weekly pattern and 8% noise. It only shows the model can learn a calendar effect that exists. It does not show that real shops have one.

118 replay dates, 14-day forecasts, WAPE (lower is better):

| Model | All dates | Dates with Ramadan in the forecast window | Other dates |
|---|---|---|---|
| with Egyptian calendar | 0.065 | 0.067 | 0.065 |
| without calendar | 0.088 | 0.176 | 0.078 |
