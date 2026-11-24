"""Turn a messy sales file (CSV or Excel) into validated daily sales, and say exactly what was guessed and what was changed.

Real shop files are untidy: Arabic or English headers, Arabic-Indic digits, comma or semicolon separators, day-first dates, a row per
receipt instead of a row per day, blank cells. The importer looks at headers and content, picks the date, value and item columns, lets
the caller override any pick, and reports every change it made (summed receipts, filled empty days, zeroed negatives)."""
import io
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from hindsight.data.sales import DataValidationError, SalesData

MAX_SERIES = 100
MIN_DAYS = 28

DATE_WORDS = ["date", "day", "time", "period", "تاريخ", "التاريخ", "اليوم", "يوم", "بتاريخ", "الفترة"]
VALUE_WORDS = ["sales", "sale", "qty", "quantity", "units", "unit", "amount", "revenue", "total", "sold", "volume", "orders",
               "مبيعات", "المبيعات", "كمية", "الكمية", "الكميه", "عدد", "العدد", "مبيع", "المباع", "إجمالي", "اجمالي", "الإجمالي", "قيمة", "القيمة", "ايراد", "إيراد"]
ID_WORDS = ["item", "product", "sku", "store", "shop", "branch", "category", "name", "id", "code", "location", "outlet",
            "صنف", "الصنف", "منتج", "المنتج", "فرع", "الفرع", "محل", "المحل", "اسم", "الاسم", "كود", "الكود", "قسم", "القسم", "فئة", "الفئة", "بند", "البند", "سلعة", "السلعة"]
# Optional business columns. When a file carries them, Hindsight reads the latest value per item and offers it to the inventory screen.
# Checked in this order, so "stock on order" is not mistaken for stock on hand and "unit cost" is not mistaken for a price.
BUSINESS_WORDS = {
    "on_order": ["on order", "on_order", "onorder", "ordered", "pending", "incoming", "قيد الطلب", "تحت الطلب", "مطلوب"],
    "unit_cost": ["cost", "purchase", "تكلفة", "التكلفة", "تكلفه", "سعر الشراء", "سعر الجملة"],
    "price": ["price", "سعر", "السعر"],
    "on_hand": ["stock", "on hand", "on_hand", "onhand", "inventory", "balance", "مخزون", "المخزون", "رصيد", "الرصيد"],
}
DUPLICATE_POLICIES = ("sum", "drop_exact")
ID_SEPARATOR = " / "
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


class ImportProblem(Exception):
    """A file that cannot be used. The message says what is wrong and how to fix it; `code` and `params` let a client say it in another language."""

    def __init__(self, message: str, code: str = "", **params):
        super().__init__(message)
        self.code, self.params = code, params


@dataclass
class Note:
    level: str  # "info" or "warning"
    text: str
    code: str = ""
    params: dict = field(default_factory=dict)


def _note(level: str, text: str, code: str = "", **params) -> Note:
    return Note(level, text, code, params)


@dataclass
class Detection:
    layout: str  # "long": one row per (date, item); "wide": one column per item
    date_col: str
    value_col: str | None
    id_col: str | None
    series_cols: list[str]
    columns: list[dict]  # every column with a few sample values, for the confirm screen
    notes: list[Note] = field(default_factory=list)
    id_cols: list[str] = field(default_factory=list)  # two or more columns that together name an item (store + product); empty when one column does
    business: dict = field(default_factory=dict)  # kind -> column, for price, unit_cost, on_hand, on_order columns found in the file
    duplicates: str = "sum"  # what to do with rows that are exact copies of another row: "sum" them in, or "drop_exact"


@dataclass
class ImportReport:
    layout: str
    rows: int
    n_series: int
    first_date: str
    last_date: str
    n_days: int
    mapping: dict
    notes: list[Note]
    business: dict = field(default_factory=dict)  # {"columns": {kind: column}, "values": {item: {kind: latest value}}}; empty when the file has none


def _fix_text(s: str) -> str:
    return s.translate(AR_DIGITS).replace("٫", ".").replace("٬", ",").replace(" ", " ").strip()


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1256", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ImportProblem("The file's text encoding could not be read. Save it as CSV (UTF-8) or Excel and upload again.", "encoding")


def _read_table(raw: bytes, filename: str, notes: list[Note]) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=object)
        except Exception as e:  # noqa: BLE001 - any reader failure is a bad file for the user
            raise ImportProblem(f"The Excel file could not be opened ({type(e).__name__}). Save it again as .xlsx or CSV and upload again.", "excel_unreadable") from e
        sheets = {k: v for k, v in sheets.items() if len(v) and v.shape[1] >= 2}
        if not sheets:
            raise ImportProblem("No sheet in the workbook has a table with at least two columns.", "no_sheet")
        first = next(iter(sheets))
        if len(sheets) > 1:
            notes.append(_note("warning", f"The workbook has {len(sheets)} sheets with data. Only the first one, '{first}', was read.", "sheets", n=len(sheets), first=str(first)))
        df = sheets[first]
    elif name.endswith((".csv", ".txt", ".tsv")):
        text = _decode(raw)
        first_lines = "\n".join(text.splitlines()[:5])
        sep = max([",", ";", "\t", "|"], key=first_lines.count)
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=object, skip_blank_lines=True)
        except Exception as e:  # noqa: BLE001
            raise ImportProblem("The file could not be read as a table. Check that it has one header row and one row per record.", "unreadable_table") from e
    else:
        raise ImportProblem("Upload a .csv or .xlsx file.", "bad_type")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if not c.startswith("Unnamed:")]].dropna(how="all")
    if df.shape[1] < 2 or len(df) < 2:
        raise ImportProblem("The file needs at least a date column and a sales column, with a header row.", "too_small")
    return df.reset_index(drop=True)


def _to_number(col: pd.Series) -> pd.Series:
    def one(x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return np.nan
        if isinstance(x, (int, float, np.integer, np.floating)):
            return float(x)
        s = _fix_text(str(x))
        if re.search(r"\d\s*[/\-.]\s*\d+\s*[/\-.]\s*\d", s):  # 15/03/2024 is a date, not a number
            return np.nan
        s = re.sub(r"(?i)\b(?:egp|l\.?e\.?|usd)\b|ج\.م|جنيه|[$£€]", "", s).replace(" ", "")  # currency marks are not part of the number
        if not re.fullmatch(r"[+-]?[\d.,]+(?:[eE][+-]?\d+)?", s):  # anything else, such as "CA_1", is text
            return np.nan
        if s.count(",") and s.count("."):
            s = s.replace(",", "")
        elif s.count(",") == 1 and re.fullmatch(r"-?\d+,\d{1,2}", s):
            s = s.replace(",", ".")  # decimal comma
        else:
            s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            return np.nan
    return col.map(one).astype(float)


def _number_share(col: pd.Series) -> float:
    return float(_to_number(col).notna().mean()) if len(col) else 0.0


def _parse_dates(col: pd.Series, notes: list[Note]) -> pd.Series:
    """Parse dates, deciding day-first versus month-first from the data; day-first when a file cannot tell."""
    if pd.api.types.is_datetime64_any_dtype(col):
        return pd.to_datetime(col).dt.normalize()
    if col.map(lambda x: hasattr(x, "year")).mean() > 0.9:  # real dates from Excel
        return pd.to_datetime(col, errors="coerce").dt.normalize()
    s = col.map(lambda x: _fix_text(str(x)) if x is not None and not (isinstance(x, float) and np.isnan(x)) else "")
    nums = pd.to_numeric(s, errors="coerce")
    if nums.notna().mean() > 0.9 and nums.between(20000, 80000).all():  # Excel serial days
        return (pd.Timestamp("1899-12-30") + pd.to_timedelta(nums, unit="D")).dt.normalize()
    iso = pd.to_datetime(s, format="ISO8601", errors="coerce")
    if iso.notna().mean() > 0.9:
        return iso.dt.normalize()
    parts = s.str.extract(r"^(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})")
    p1, p2 = pd.to_numeric(parts[0], errors="coerce"), pd.to_numeric(parts[1], errors="coerce")
    if (p1 > 12).any() and not (p2 > 12).any():
        dayfirst = True
    elif (p2 > 12).any() and not (p1 > 12).any():
        dayfirst = False
    else:
        dayfirst = True
        if ((p1 <= 12) & (p2 <= 12) & (p1 != p2)).any():
            notes.append(_note("warning", "Some dates could be read as day/month or month/day, and nothing in the file settles it. They were read as day/month, as is usual in Egypt. If that is wrong, change the date format in the file.", "ambiguous_dates"))
    out = pd.to_datetime(s, dayfirst=dayfirst, errors="coerce", format="mixed")
    return out.dt.normalize()


def _header_hit(name: str, words: list[str]) -> bool:
    n = _fix_text(name).lower()
    return any(w in n for w in words)


def _business_columns(df: pd.DataFrame, skip: list[str]) -> dict[str, str]:
    """Columns that hold a price, a unit cost or stock figures, found by header and by being mostly numbers."""
    found: dict[str, str] = {}
    for c in df.columns:
        if c in skip or c in found.values() or _number_share(df[c].head(500)) < 0.8:
            continue
        for kind, words in BUSINESS_WORDS.items():
            if kind not in found and _header_hit(c, words):
                found[kind] = c
                break
    return found


def detect(df: pd.DataFrame) -> Detection:
    notes: list[Note] = []
    cols = list(df.columns)
    sample = df.head(500)
    info = []
    for c in cols:
        info.append({"name": c, "examples": [str(x) for x in df[c].dropna().head(3)], "numeric_share": round(_number_share(sample[c]), 2)})
    probe_notes: list[Note] = []

    def date_share(c):
        d = _parse_dates(sample[c], probe_notes)
        return float(d.notna().mean())

    shares = {c: date_share(c) for c in cols}
    def plausible(c):  # a column of plain numbers is a date only if the header says so
        real_dates = sample[c].map(lambda x: hasattr(x, "year")).mean() > 0.9
        return shares[c] > 0.8 and (real_dates or _number_share(sample[c]) < 0.95 or _header_hit(c, DATE_WORDS))

    cands = [c for c in cols if plausible(c)]
    named = [c for c in cands if _header_hit(c, DATE_WORDS)]
    if not (named or cands):
        raise ImportProblem("No column looks like a date. Add a column with the day of each sale (for example 2024-03-15 or 15/03/2024) and upload again.", "no_date_column")
    date_col = (named or cands)[0]
    business = _business_columns(df, [date_col])
    rest = [c for c in cols if c != date_col and c not in business.values()]  # a price column is not a sales column, and not an item
    numeric = [c for c in rest if _number_share(sample[c]) > 0.9]
    texty = [c for c in rest if c not in numeric]
    id_named = [c for c in texty if _header_hit(c, ID_WORDS)]
    value_named = [c for c in numeric if _header_hit(c, VALUE_WORDS)]
    if len(numeric) >= 2 and not texty and not value_named:
        layout, id_col, value_col, series_cols = "wide", None, None, numeric
    else:
        layout = "long"
        id_col = (id_named or [c for c in texty if 1 < df[c].nunique() <= max(200, len(df) // 3)] or [None])[0]
        pool = value_named or numeric
        if not pool:
            raise ImportProblem("No column holds sales numbers. Add a column with the quantity or amount sold per row and upload again.", "no_value_column")
        value_col = pool[0]
        series_cols = []
        if len(pool) > 1 and not value_named:
            notes.append(_note("warning", f"Several columns look like numbers. '{value_col}' was used as the sales column; change it if that is wrong.", "several_numeric", column=str(value_col)))
    return Detection(layout, date_col, value_col, id_col, series_cols, info, notes, business=business if layout == "long" else {})


def _latest_business(long: pd.DataFrame, det: Detection, ids: list[str]) -> dict:
    """The most recent non-empty price, cost and stock figure for each item. Nothing is filled in for items that have none."""
    ordered = long.sort_values("date", kind="stable")
    values: dict[str, dict] = {i: {} for i in ids}
    for kind in det.business:
        last = ordered.groupby("series")[f"@{kind}"].last()
        for item, v in last.items():
            if item in values and pd.notna(v):
                values[item][kind] = float(v)
    return {"columns": dict(det.business), "values": {k: v for k, v in values.items() if v}}


def build(df: pd.DataFrame, det: Detection, source: str = "upload") -> tuple[SalesData, ImportReport]:
    notes = list(det.notes)
    if det.duplicates not in DUPLICATE_POLICIES:
        raise ImportProblem(f"Unknown duplicate rule {det.duplicates!r}.", "bad_duplicate_rule", rule=str(det.duplicates))
    exact = df.duplicated().to_numpy()  # rows identical to an earlier row in every column
    if exact.any():
        n_exact = int(exact.sum())
        if det.duplicates == "drop_exact":
            df = df.loc[~exact].reset_index(drop=True)
            notes.append(_note("info", f"{n_exact} rows were exact copies of another row and were removed.", "duplicates_dropped", n=n_exact))
        else:
            notes.append(_note("warning", f"{n_exact} rows are exact copies of another row. They were added together like separate receipts. If they are double entries, choose to remove exact duplicates.", "exact_duplicates", n=n_exact))
    work = pd.DataFrame({"date": _parse_dates(df[det.date_col], notes)})
    bad_dates = int(work["date"].isna().sum())
    if det.layout == "wide":
        for c in det.series_cols:
            work[c] = _to_number(df[c])
        long = work.melt(id_vars="date", var_name="series", value_name="value")
    else:
        if det.id_cols:
            work["series"] = df[det.id_cols].astype(str).apply(lambda r: ID_SEPARATOR.join(_fix_text(x) for x in r), axis=1)
        else:
            work["series"] = df[det.id_col].astype(str).map(_fix_text) if det.id_col else "All sales"
        work["value"] = _to_number(df[det.value_col])
        for kind, col in det.business.items():
            work[f"@{kind}"] = _to_number(df[col])
        long = work
    if det.layout == "long" and not det.id_cols and det.id_col:
        others = [c for c in df.columns if c not in (det.date_col, det.value_col, det.id_col, *det.business.values()) and _number_share(df[c].head(500)) < 0.5
                  and 1 < df[c].nunique() <= max(200, len(df) // 3)]
        if others:
            notes.append(_note("warning", f"The file also has these item-like columns: {', '.join(others)}. Only '{det.id_col}' names the items, so rows that differ only in those columns were added together. To keep them apart, name items by more than one column.", "other_id_columns", columns=", ".join(others), used=str(det.id_col)))
    if bad_dates:
        notes.append(_note("warning", f"{bad_dates} rows had no readable date and were left out.", "bad_dates", n=bad_dates))
        long = long.dropna(subset=["date"])
    blank = int(long["value"].isna().sum())
    if blank:
        notes.append(_note("warning", f"{blank} rows had no readable sales number and were counted as 0.", "blank_values", n=blank))
        long = long.assign(value=long["value"].fillna(0.0))
    neg = int((long["value"] < 0).sum())
    if neg:
        notes.append(_note("warning", f"{neg} rows had negative numbers (returns?). They were counted as 0.", "negatives", n=neg))
        long = long.assign(value=long["value"].clip(lower=0))
    if long.empty:
        raise ImportProblem("No usable rows were left after reading dates and numbers.", "no_rows")
    per_day = long.groupby(["series", "date"], sort=False)["value"].sum().reset_index()
    if len(per_day) < len(long):
        notes.append(_note("info", f"Several rows shared the same item and day ({len(long):,} rows became {len(per_day):,} daily totals). They were added together.", "aggregated", rows=len(long), days=len(per_day)))
    first, last = per_day["date"].min(), per_day["date"].max()
    days = pd.date_range(first, last, freq="D")
    if len(days) < MIN_DAYS:
        raise ImportProblem(f"The file covers only {len(days)} days. At least {MIN_DAYS} consecutive days are needed, and several months for a useful replay.", "too_short", days=len(days), min_days=MIN_DAYS)
    wide = per_day.pivot(index="date", columns="series", values="value").reindex(days)
    gaps = int(wide.isna().all(axis=1).sum())
    if gaps:
        run = int((wide.isna().all(axis=1).astype(int).groupby((~wide.isna().all(axis=1)).cumsum()).cumsum()).max())
        notes.append(_note("warning", f"{gaps} days between the first and last date had no rows at all (longest run: {run} days). They were counted as 0 sales. If the shop was open and records are missing, the forecast will be misled.", "gaps", n=gaps, longest=run))
    partial = int(wide.isna().sum().sum()) - gaps * wide.shape[1]
    if partial > 0:
        notes.append(_note("info", f"{partial:,} item-days had no row (the item did not sell or was not recorded). They were counted as 0.", "partial_days", n=partial))
    wide = wide.fillna(0.0)
    if wide.shape[1] > MAX_SERIES:
        keep = wide.sum().nlargest(MAX_SERIES).index
        notes.append(_note("warning", f"The file has {wide.shape[1]} items. The {MAX_SERIES} with the most sales were kept.", "too_many_items", n=int(wide.shape[1]), kept=MAX_SERIES))
        wide = wide[keep]
    wide = wide.loc[:, wide.sum() > 0]
    business = _latest_business(long, det, [str(c) for c in wide.columns]) if det.layout == "long" and det.business else {}
    if wide.shape[1] == 0:
        raise ImportProblem("Every item has zero sales in this file.", "all_zero")
    ids = [str(c) for c in wide.columns]
    if len(set(ids)) != len(ids):
        raise ImportProblem("Two items have the same name after cleaning. Rename one of them in the file.", "duplicate_items")
    data = SalesData(pd.DatetimeIndex(days), ids, wide.to_numpy().T.copy(), source=source)
    try:
        data.validate()
    except DataValidationError as e:
        raise ImportProblem(str(e), "invalid_data") from e
    mapping = {"date": det.date_col, "value": det.value_col, "item": det.id_col, "item_columns": det.series_cols}
    mapping["item_cols"] = det.id_cols
    mapping["duplicates"] = det.duplicates
    report = ImportReport(det.layout, len(df), len(ids), str(first.date()), str(last.date()), len(days), mapping, notes, business)
    return data, report


def read_sales_file(raw: bytes, filename: str, mapping: dict | None = None) -> tuple[SalesData, ImportReport, Detection]:
    """Read, detect and build in one step. `mapping` may override the detected columns: keys date, value, item, item_columns."""
    notes: list[Note] = []
    df = _read_table(raw, filename, notes)
    det = detect(df)
    det.notes = notes + det.notes
    if mapping:
        asked = [mapping.get("date"), mapping.get("value"), mapping.get("item"), *(mapping.get("item_columns") or []), *(mapping.get("item_cols") or [])]
        missing = [c for c in asked if c and c not in df.columns]
        if missing:
            raise ImportProblem(f"These columns are not in the file: {', '.join(missing)}.", "missing_columns", columns=", ".join(missing))
        det.date_col = mapping.get("date") or det.date_col
        if mapping.get("item_columns"):
            det.layout, det.series_cols, det.value_col, det.id_col = "wide", list(mapping["item_columns"]), None, None
        else:
            det.layout, det.series_cols = "long", []
            det.value_col = mapping.get("value") or det.value_col
            det.id_col = mapping.get("item") if "item" in mapping else det.id_col
            if mapping.get("item_cols"):
                det.id_cols, det.id_col = list(mapping["item_cols"]), None
        if "business" in mapping:  # the caller names the price/cost/stock columns (possibly none)
            det.business = {k: v for k, v in (mapping["business"] or {}).items() if v}
        elif det.layout == "long":
            det.business = {k: v for k, v in det.business.items() if v not in (det.value_col, det.id_col, *det.id_cols, det.date_col)}
        if mapping.get("duplicates"):
            det.duplicates = mapping["duplicates"]
    data, report = build(df, det, source=filename)
    return data, report, det
