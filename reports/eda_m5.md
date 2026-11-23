# M5 first look (generated)

Descriptive statistics of the public M5 Walmart data (US stores). Used to decide what the forecasting models need; not evidence about Egyptian shops.

## How sparse is each level?

| Level | Series | Days with zero sales | Median units per day |
|---|---|---|---|
| total | 1 | 0.0% | 34480.8 |
| state | 3 | 0.0% | 9906.4 |
| store | 10 | 0.1% | 3284.0 |
| store_category | 30 | 0.2% | 737.7 |
| store_department | 70 | 0.3% | 295.1 |
| item_store | 3000 | 68.1% | 0.4 |

## Weekly rhythm (total sales, ratio to the weekly average)

| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|
| 0.96 | 0.88 | 0.87 | 0.88 | 1.00 | 1.21 | 1.20 |

## Level over the years (average units per day, all stores)

| 2011 | 2012 | 2013 | 2014 | 2015 | 2016 |
|---|---|---|---|---|---|
| 26,281 | 32,956 | 35,988 | 35,862 | 37,810 | 41,835 |
(2011 and 2016 are partial years.)

## Holiday effect on total sales

Sales on the event day divided by the average of the same weekday in the four weeks before and after (1.00 = no effect). Small samples: the event happens once a year.

| Event | Times in data | Average ratio | Lowest | Highest |
|---|---|---|---|---|
| Christmas | 5 | 0.00 | 0.00 | 0.00 |
| Thanksgiving | 5 | 0.72 | 0.64 | 0.83 |
| LaborDay | 5 | 1.26 | 1.16 | 1.34 |
| Mother's day | 6 | 0.86 | 0.83 | 0.89 |
| Easter | 5 | 0.88 | 0.80 | 0.94 |
| Halloween | 5 | 0.90 | 0.85 | 0.97 |
| ColumbusDay | 5 | 1.09 | 0.98 | 1.15 |
| Father's day | 4 | 0.92 | 0.90 | 0.95 |
| NewYear | 5 | 0.92 | 0.72 | 1.03 |
| PresidentsDay | 6 | 1.07 | 1.02 | 1.20 |
| VeteransDay | 5 | 1.07 | 0.99 | 1.11 |
| LentStart | 6 | 1.05 | 0.90 | 1.33 |
| Cinco De Mayo | 5 | 1.04 | 0.99 | 1.10 |
| ValentinesDay | 6 | 0.96 | 0.91 | 1.03 |
| Chanukah End | 5 | 1.04 | 0.94 | 1.17 |
| Eid al-Fitr | 5 | 0.97 | 0.88 | 1.02 |
| NBAFinalsStart | 5 | 1.03 | 0.89 | 1.10 |
| StPatricksDay | 6 | 0.97 | 0.93 | 1.01 |
| OrthodoxChristmas | 5 | 1.02 | 0.95 | 1.08 |
| IndependenceDay | 5 | 0.98 | 0.82 | 1.09 |
| Pesach End | 6 | 0.98 | 0.85 | 1.14 |
| SuperBowl | 6 | 0.99 | 0.92 | 1.09 |
| EidAlAdha | 5 | 1.01 | 0.92 | 1.08 |
| NBAFinalsEnd | 5 | 0.99 | 0.92 | 1.10 |
| Ramadan starts | 5 | 1.01 | 0.92 | 1.12 |
| LentWeek2 | 6 | 1.01 | 0.91 | 1.12 |
| OrthodoxEaster | 5 | 0.99 | 0.82 | 1.07 |
| MemorialDay | 5 | 0.99 | 0.95 | 1.05 |
| Purim End | 6 | 1.00 | 0.92 | 1.07 |
| MartinLutherKingDay | 5 | 1.00 | 0.95 | 1.07 |

The three Islamic events (Ramadan starts, Eid al-Fitr, Eid al-Adha) are listed in the data, but US shoppers are not the population of interest; any benefit of Islamic-calendar features for Egyptian shops must be tested on Egyptian data.
