"""Calendar knowledge a forecaster may use for any date, including future ones (holidays are known in advance).

`egypt_calendar` adds the Islamic calendar (Ramadan, Eids), Coptic and national holidays. Islamic dates come from the
Umm al-Qura tables (hijridate) and can differ by a day from the dates announced locally after moon sighting.
`m5_calendar` exposes the event columns that ship with the M5 data. Both return a frame indexed by date."""
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
from hijridate import Gregorian, Hijri

EGYPT_COLUMNS = ["ramadan", "ramadan_last10", "eid_fitr", "eid_adha", "days_to_ramadan", "days_to_eid_fitr", "days_to_eid_adha",
                 "coptic_christmas", "sham_el_nessim", "national_holiday", "hijri_month"]
FIXED_NATIONAL = {(1, 25), (4, 25), (5, 1), (7, 23), (10, 6)}  # revolution, Sinai, labour, revolution, armed forces


@lru_cache(maxsize=None)
def _hijri(ordinal: int) -> tuple[int, int, int]:
    h = Gregorian.fromdate(date.fromordinal(ordinal)).to_hijri()
    return h.year, h.month, h.day


def orthodox_easter(year: int) -> date:
    """Coptic and Orthodox Easter (Meeus Julian algorithm, shifted to the Gregorian calendar; valid 1900-2099)."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return date(year, month, day + 1) + timedelta(days=13)


def _event_dates(first: date, last: date, month: int, day: int) -> list[date]:
    h0, h1 = Gregorian.fromdate(first).to_hijri().year, Gregorian.fromdate(last).to_hijri().year
    return [date.fromordinal(Hijri(y, month, day).to_gregorian().toordinal()) for y in range(h0 - 1, h1 + 2)]


def _days_to_nearest(dates: pd.DatetimeIndex, events: list[date], lo: int, hi: int) -> np.ndarray:
    ev = np.array([e.toordinal() for e in events])
    ords = np.array([d.toordinal() for d in dates])
    diff = ev[None, :] - ords[:, None]  # positive: event is ahead
    pick = np.abs(diff).argmin(axis=1)
    return np.clip(diff[np.arange(len(ords)), pick], lo, hi)


def egypt_calendar(dates: pd.DatetimeIndex) -> pd.DataFrame:
    dates = pd.DatetimeIndex(dates)
    ords = [d.toordinal() for d in dates]
    hy, hm, hd = zip(*(_hijri(o) for o in ords))
    hm, hd = np.array(hm), np.array(hd)
    first, last = dates.min().date(), dates.max().date()
    easter = {y: orthodox_easter(y) for y in range(first.year - 1, last.year + 2)}
    sham = {e + timedelta(days=1) for e in easter.values()}
    out = pd.DataFrame(index=dates)
    out["ramadan"] = (hm == 9).astype(int)
    out["ramadan_last10"] = ((hm == 9) & (hd >= 21)).astype(int)
    out["eid_fitr"] = ((hm == 10) & (hd <= 3)).astype(int)
    out["eid_adha"] = ((hm == 12) & (hd >= 10) & (hd <= 13)).astype(int)
    out["days_to_ramadan"] = _days_to_nearest(dates, _event_dates(first, last, 9, 1), -30, 45)
    out["days_to_eid_fitr"] = _days_to_nearest(dates, _event_dates(first, last, 10, 1), -10, 21)
    out["days_to_eid_adha"] = _days_to_nearest(dates, _event_dates(first, last, 12, 10), -10, 21)
    out["coptic_christmas"] = [int(d.month == 1 and d.day == 7) for d in dates]
    out["sham_el_nessim"] = [int(d.date() in sham) for d in dates]
    out["national_holiday"] = [int((d.month, d.day) in FIXED_NATIONAL) for d in dates]
    out["hijri_month"] = hm
    return out[EGYPT_COLUMNS]


def basic_calendar(dates: pd.DatetimeIndex) -> pd.DataFrame:
    dates = pd.DatetimeIndex(dates)
    doy = dates.dayofyear.to_numpy()
    return pd.DataFrame({"dow": dates.dayofweek, "month": dates.month, "dom": dates.day, "doy_sin": np.sin(2 * np.pi * doy / 365.25),
                         "doy_cos": np.cos(2 * np.pi * doy / 365.25)}, index=dates)


class M5Events:
    """The event columns shipped with M5, keyed by date. Dates outside the calendar get no event."""

    def __init__(self, calendar: pd.DataFrame):
        cal = calendar.copy()
        cal["date"] = pd.to_datetime(cal["date"])
        names = sorted(set(cal["event_name_1"].dropna()) | set(cal["event_name_2"].dropna()))
        self._codes = {n: i + 1 for i, n in enumerate(names)}
        types = sorted(set(cal["event_type_1"].dropna()) | set(cal["event_type_2"].dropna()))
        self._tcodes = {t: i + 1 for i, t in enumerate(types)}
        self._table = pd.DataFrame({
            "event": cal["event_name_1"].map(self._codes).fillna(0).astype(int).to_numpy(),
            "event_type": cal["event_type_1"].map(self._tcodes).fillna(0).astype(int).to_numpy(),
            "has_event": (cal["event_name_1"].notna() | cal["event_name_2"].notna()).astype(int).to_numpy(),
        }, index=pd.DatetimeIndex(cal["date"]))

    def __call__(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        return self._table.reindex(pd.DatetimeIndex(dates)).fillna(0).astype(int)
