import io

import numpy as np
import pandas as pd
import pytest

from hindsight.data.importer import ImportProblem, MAX_SERIES, read_sales_file


def csv(text: str) -> bytes:
    return text.strip().encode("utf-8")


def days(n=60, start="2024-01-01"):
    return pd.date_range(start, periods=n)


def long_csv(n=60, fmt="%Y-%m-%d", items=("Milk", "Bread"), date_name="date", item_name="item", value_name="qty", sep=","):
    rows = [sep.join([date_name, item_name, value_name])]
    for i, d in enumerate(days(n)):
        for j, it in enumerate(items):
            rows.append(sep.join([d.strftime(fmt), it, str(10 + (i + j) % 7)]))
    return csv("\n".join(rows))


def test_a_plain_english_long_file_is_read_without_changes():
    data, rep, det = read_sales_file(long_csv(), "sales.csv")
    assert det.layout == "long" and (det.date_col, det.value_col, det.id_col) == ("date", "qty", "item")
    assert data.ids == ["Bread", "Milk"] or sorted(data.ids) == ["Bread", "Milk"]
    assert data.n_days == 60 and rep.first_date == "2024-01-01" and rep.last_date == "2024-02-29"
    assert not [n for n in rep.notes if n.level == "warning"]


def test_arabic_headers_and_arabic_digits_are_understood():
    lines = ["التاريخ,الصنف,الكمية"]
    for i, d in enumerate(days(40)):
        digits = str(10 + i % 5).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        lines.append(f"{d.strftime('%Y-%m-%d')},لبن,{digits}")
    data, rep, det = read_sales_file(csv("\n".join(lines)), "مبيعات.csv")
    assert (det.date_col, det.value_col, det.id_col) == ("التاريخ", "الكمية", "الصنف")
    assert data.ids == ["لبن"] and data.values[0, 0] == 10 and data.values[0, 3] == 13


def test_semicolons_and_decimal_commas_work():
    lines = ["date;amount"] + [f"{d.strftime('%d/%m/%Y')};{1234 + i},5" for i, d in enumerate(days(40))]
    data, _, det = read_sales_file(csv("\n".join(lines)), "x.csv")
    assert det.layout == "long" and data.values[0, 0] == pytest.approx(1234.5)


def test_day_first_and_month_first_dates_are_told_apart_by_the_data():
    data, _, _ = read_sales_file(long_csv(fmt="%d/%m/%Y", n=60), "x.csv")
    assert data.dates[0] == pd.Timestamp("2024-01-01") and data.dates[-1] == pd.Timestamp("2024-02-29")
    us, _, _ = read_sales_file(long_csv(fmt="%m/%d/%Y", n=60), "x.csv")
    assert us.dates[0] == pd.Timestamp("2024-01-01") and us.dates[-1] == pd.Timestamp("2024-02-29")


def test_one_row_per_receipt_is_added_into_days():
    rows = ["date,item,qty"]
    for d in days(40):
        rows += [f"{d.date()},Milk,2", f"{d.date()},Milk,3"]
    data, rep, _ = read_sales_file(csv("\n".join(rows)), "r.csv")
    assert (data.values == 5).all() and any("added together" in n.text for n in rep.notes)


def test_wide_files_with_one_column_per_item_are_detected():
    rows = ["date,Milk,Bread,Eggs"] + [f"{d.date()},{5 + i % 3},{7},{i % 4}" for i, d in enumerate(days(40))]
    data, rep, det = read_sales_file(csv("\n".join(rows)), "w.csv")
    assert det.layout == "wide" and sorted(data.ids) == ["Bread", "Eggs", "Milk"] and data.n_days == 40


def test_missing_days_are_filled_with_zero_and_reported():
    rows = ["date,qty"] + [f"{d.date()},9" for i, d in enumerate(days(60)) if not 20 <= i < 26]
    data, rep, _ = read_sales_file(csv("\n".join(rows)), "g.csv")
    assert data.n_days == 60 and data.values[0, 20:26].sum() == 0
    assert any("6 days" in n.text and "longest run: 6" in n.text for n in rep.notes)


def test_negative_and_blank_numbers_are_handled_and_reported():
    rows = ["date,qty"] + [f"{d.date()},{'' if i == 3 else ('-4' if i == 5 else '8')}" for i, d in enumerate(days(40))]
    data, rep, _ = read_sales_file(csv("\n".join(rows)), "n.csv")
    assert data.values[0, 3] == 0 and data.values[0, 5] == 0 and (data.values >= 0).all()
    texts = " ".join(n.text for n in rep.notes)
    assert "negative" in texts and "no readable sales number" in texts


def test_excel_files_with_real_dates_work_and_extra_sheets_are_flagged():
    df = pd.DataFrame({"Date": days(50), "Product": "Tea", "Units": np.arange(50) % 6 + 5})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Sales", index=False)
        df.to_excel(w, sheet_name="Copy", index=False)
    data, rep, det = read_sales_file(buf.getvalue(), "sales.xlsx")
    assert data.ids == ["Tea"] and data.n_days == 50 and any("2 sheets" in n.text for n in rep.notes)


def test_the_caller_can_override_the_guess():
    raw = csv("day,a,b,c\n" + "\n".join(f"{d.date()},{i},{i + 1},{i + 2}" for i, d in enumerate(days(40))))
    _, _, det = read_sales_file(raw, "x.csv")
    assert det.layout == "wide"
    data, _, det2 = read_sales_file(raw, "x.csv", {"date": "day", "value": "b", "item": None, "item_columns": []})
    assert det2.layout == "long" and data.ids == ["All sales"] and data.values[0, 2] == 3
    with pytest.raises(ImportProblem, match="not in the file"):
        read_sales_file(raw, "x.csv", {"date": "nope"})


@pytest.mark.parametrize("raw,name,message", [
    (csv("a,b\n1,2\n3,4"), "x.csv", "No column looks like a date"),
    (csv("date,note\n" + "\n".join(f"{d.date()},hello" for d in days(40))), "x.csv", "No column holds sales numbers"),
    (csv("date,qty\n2024-01-01,5\n2024-01-02,6"), "x.csv", "28 consecutive days"),
    (b"whatever", "x.pdf", "Upload a .csv or .xlsx"),
    (csv("only\n1\n2"), "x.csv", "at least a date column"),
])
def test_unusable_files_get_an_explanation(raw, name, message):
    with pytest.raises(ImportProblem, match=message):
        read_sales_file(raw, name)


def test_a_file_with_too_many_items_keeps_the_biggest():
    n = MAX_SERIES + 20
    rows = ["date,item,qty"] + [f"{d.date()},item{k},{k + 1}" for d in days(30) for k in range(n)]
    data, rep, _ = read_sales_file(csv("\n".join(rows)), "big.csv")
    assert data.n_series == MAX_SERIES and "item119" in data.ids and "item0" not in data.ids
    assert any(f"{n} items" in x.text for x in rep.notes)


def test_item_names_that_contain_digits_are_text_and_currency_marks_are_ignored():
    rows = ["date,store,units_sold"] + [f"{d.date()},CA_{k},{k}" for d in days(40) for k in (1, 2)]
    data, _, det = read_sales_file(csv("\n".join(rows)), "s.csv")
    assert det.id_col == "store" and sorted(data.ids) == ["CA_1", "CA_2"]
    priced = ["date,amount"] + [f"{d.date()},{1000 + i} EGP" if i % 2 else f"{d.date()},١٬٢٣٤ ج.م" for i, d in enumerate(days(40))]
    data2, _, _ = read_sales_file(csv("\n".join(priced)), "p.csv")
    assert data2.values[0, 1] == 1001 and data2.values[0, 0] == 1234


def test_a_date_column_is_not_confused_with_numbers_that_look_like_years():
    rows = ["date,qty"] + [f"{d.date()},{2020 + i % 5}" for i, d in enumerate(days(40))]
    _, _, det = read_sales_file(csv("\n".join(rows)), "y.csv")
    assert det.date_col == "date" and det.value_col == "qty"
