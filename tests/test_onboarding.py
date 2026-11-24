"""Smart Data Onboarding: composite item keys, duplicate rules, price/cost/stock columns, quality findings, adapters, and the API around them."""
import numpy as np
import pandas as pd
import pytest
import yaml
from fastapi.testclient import TestClient

from hindsight.app import api as api_module
from hindsight.app.api import create_app
from hindsight.data import adapters, quality
from hindsight.data.importer import ImportProblem, read_sales_file
from hindsight.data.sales import SalesData


def csv(text: str) -> bytes:
    return text.strip().encode("utf-8")


def days(n=60, start="2024-01-01"):
    return pd.date_range(start, periods=n)


# ---- composite keys ----------------------------------------------------------------------------------------------------------------
def store_product_file(n=40) -> bytes:
    rows = ["date,region,product,qty"]
    for i, d in enumerate(days(n)):
        for region in ("North", "South"):
            for product in ("Milk", "Bread"):
                rows.append(f"{d.date()},{region},{product},{10 + i % 3 + (region == 'South') * 5 + (product == 'Bread')}")
    return csv("\n".join(rows))


def test_two_item_like_columns_are_flagged_instead_of_silently_added_together():
    data, rep, det = read_sales_file(store_product_file(), "x.csv")
    warn = next(n for n in rep.notes if n.code == "other_id_columns")
    assert warn.level == "warning" and det.id_col in ("region", "product") and data.n_series == 2
    assert "product" in warn.params["columns"] or "region" in warn.params["columns"]


def test_a_composite_key_keeps_every_combination_apart_and_loses_nothing():
    plain, _, _ = read_sales_file(store_product_file(), "x.csv")
    data, rep, det = read_sales_file(store_product_file(), "x.csv", {"date": "date", "value": "qty", "item_cols": ["region", "product"]})
    assert data.n_series == 4 and sorted(data.ids) == ["North / Bread", "North / Milk", "South / Bread", "South / Milk"]
    assert not any(n.code == "other_id_columns" for n in rep.notes)
    assert data.values.sum() == plain.values.sum()  # the same sales, split four ways instead of two
    assert rep.mapping["item_cols"] == ["region", "product"]
    with pytest.raises(ImportProblem, match="not in the file"):
        read_sales_file(store_product_file(), "x.csv", {"date": "date", "item_cols": ["region", "nope"]})


# ---- exact duplicates --------------------------------------------------------------------------------------------------------------
def dup_file() -> bytes:
    rows = ["date,item,qty"] + [f"{d.date()},Milk,10" for d in days(40)]
    rows += [f"{days(40)[5].date()},Milk,10", f"{days(40)[6].date()},Milk,10"]  # two rows copied
    return csv("\n".join(rows))


def test_exact_duplicates_are_reported_and_summed_by_default():
    data, rep, _ = read_sales_file(dup_file(), "d.csv")
    note = next(n for n in rep.notes if n.code == "exact_duplicates")
    assert note.level == "warning" and note.params == {"n": 2}
    assert data.values[0, 5] == 20 and data.values[0, 0] == 10


def test_the_caller_can_remove_exact_duplicates_instead():
    data, rep, _ = read_sales_file(dup_file(), "d.csv", {"date": "date", "value": "qty", "item": "item", "duplicates": "drop_exact"})
    assert data.values[0, 5] == 10 and data.values[0, 6] == 10
    assert any(n.code == "duplicates_dropped" and n.params == {"n": 2} for n in rep.notes) and not any(n.code == "exact_duplicates" for n in rep.notes)
    with pytest.raises(ImportProblem) as e:
        read_sales_file(dup_file(), "d.csv", {"date": "date", "value": "qty", "item": "item", "duplicates": "bogus"})
    assert e.value.code == "bad_duplicate_rule"


def test_receipts_that_differ_are_never_called_duplicates():
    rows = ["date,item,qty"]
    for d in days(40):
        rows += [f"{d.date()},Milk,2", f"{d.date()},Milk,3"]
    _, rep, _ = read_sales_file(csv("\n".join(rows)), "r.csv")
    assert not any(n.code == "exact_duplicates" for n in rep.notes)


# ---- price, cost and stock columns -------------------------------------------------------------------------------------------------
def priced_file(extra="", n=40) -> bytes:
    rows = [f"date,item,qty,price,unit cost,stock on hand,stock on order{extra}"]
    for i, d in enumerate(days(n)):
        for j, it in enumerate(("Milk", "Bread")):
            rows.append(f"{d.date()},{it},{8 + i % 4 + j},{10 + j + (i > 30)},{6 + j},{100 - i + j * 7},{20 if i == n - 1 else 0}")
    return csv("\n".join(rows))


def test_business_columns_are_found_and_are_not_mistaken_for_sales():
    data, rep, det = read_sales_file(priced_file(), "p.csv")
    assert det.value_col == "qty" and det.business == {"on_order": "stock on order", "unit_cost": "unit cost", "price": "price", "on_hand": "stock on hand"}
    assert rep.business["values"]["Milk"] == {"on_order": 20.0, "unit_cost": 6.0, "price": 11.0, "on_hand": 61.0}  # the latest row of each item
    assert rep.business["values"]["Bread"]["on_hand"] == 100 - 39 + 7
    assert data.values[0, 0] in (8, 9) and sorted(data.ids) == ["Bread", "Milk"]


def test_a_price_column_alone_is_not_treated_as_a_second_item():
    rows = ["date,qty,price"] + [f"{d.date()},{5 + i % 3},12.5" for i, d in enumerate(days(40))]
    data, rep, det = read_sales_file(csv("\n".join(rows)), "x.csv")
    assert det.layout == "long" and data.ids == ["All sales"] and rep.business["values"]["All sales"]["price"] == 12.5


def test_arabic_business_headers():
    rows = ["التاريخ,الصنف,الكمية,السعر,المخزون"] + [f"{d.date()},لبن,{5 + i % 3},١٢,{50 - i}" for i, d in enumerate(days(40))]
    _, rep, det = read_sales_file(csv("\n".join(rows)), "ar.csv")
    assert det.business == {"price": "السعر", "on_hand": "المخزون"} and rep.business["values"]["لبن"] == {"price": 12.0, "on_hand": 11.0}


def test_the_caller_can_say_the_file_has_no_such_columns():
    _, rep, det = read_sales_file(priced_file(), "p.csv", {"date": "date", "value": "qty", "item": "item", "business": {}})
    assert rep.business == {} and det.business == {}


def test_files_without_business_columns_are_unchanged():
    _, rep, det = read_sales_file(csv("date,item,qty\n" + "\n".join(f"{d.date()},Milk,5" for d in days(40))), "x.csv")
    assert rep.business == {} and det.business == {}


# ---- quality findings --------------------------------------------------------------------------------------------------------------
def sales(rows: dict[str, np.ndarray]) -> SalesData:
    n = len(next(iter(rows.values())))
    return SalesData(pd.date_range("2024-01-01", periods=n), list(rows), np.array(list(rows.values()), dtype=float))


def codes(findings):
    return {f["code"]: f for f in findings}


def test_a_healthy_file_has_no_findings():
    rng = np.random.default_rng(0)
    assert quality.assess(sales({"A": rng.integers(20, 40, 200), "B": rng.integers(5, 15, 200)})) == []


def test_items_that_stopped_or_started_late_are_named():
    rng = np.random.default_rng(1)
    a = rng.integers(20, 40, 300).astype(float)
    stopped = a.copy(); stopped[-40:] = 0
    late = a.copy(); late[:150] = 0
    f = codes(quality.assess(sales({"Live": a, "Stopped": stopped, "Late": late})))
    assert f["stopped_selling"]["items"] == ["Stopped"] and f["late_start"]["items"] == ["Late"]


def test_a_file_that_ends_early_is_one_warning_not_one_per_item():
    a = np.r_[np.full(100, 10.0), np.zeros(10)]
    f = codes(quality.assess(sales({"A": a, "B": a.copy()})))
    assert "file_ends_early" in f and "stopped_selling" not in f and f["file_ends_early"]["level"] == "warning"


def test_spikes_sparse_and_constant_items_are_found():
    rng = np.random.default_rng(2)
    spiky = rng.integers(20, 30, 200).astype(float); spiky[100] = 900
    sparse = np.zeros(200); sparse[::8] = 5
    const = np.full(200, 7.0)
    f = codes(quality.assess(sales({"Spiky": spiky, "Sparse": sparse, "Const": const})))
    assert f["spikes"]["items"] == ["Spiky"] and f["spikes"]["examples"][0]["value"] == 900 and f["spikes"]["examples"][0]["date"] == "2024-04-10"
    assert f["mostly_zero"]["items"] == ["Sparse"] and f["constant_values"]["items"] == ["Const"]


def test_quality_never_changes_the_data():
    rng = np.random.default_rng(3)
    d = sales({"A": rng.integers(0, 3, 200)})
    before = d.values.copy()
    quality.assess(d)
    assert np.array_equal(d.values, before)


# ---- adapters ----------------------------------------------------------------------------------------------------------------------
def make(name="shop", description="", **kw) -> adapters.Adapter:
    return adapters.Adapter(name=name, description=description, mapping=adapters.AdapterMapping(date="date", value="qty", item="item", **kw))


def test_an_adapter_round_trips_through_yaml_and_matches_by_columns(tmp_path):
    adapters.save(tmp_path, make(description="weekly POS export"))
    found, bad = adapters.list_adapters(tmp_path / "none", tmp_path)
    assert bad == [] and [a.name for a, _ in found] == ["shop"] and found[0][1] == "saved"
    assert adapters.match([found[0][0]], ["date", "item", "qty", "other"]).name == "shop"
    assert adapters.match([found[0][0]], ["date", "item"]) is None  # a column it names is missing
    best = adapters.match([make("small"), make("big", business={"price": "price"})], ["date", "item", "qty", "price"])
    assert best.name == "big"  # the one that explains more of the file


def test_applying_an_adapter_gives_the_same_result_as_choosing_by_hand():
    a = make(business={"price": "price"})
    raw = priced_file()
    by_adapter, rep_a, _ = read_sales_file(raw, "p.csv", adapters.to_mapping(a))
    by_hand, rep_h, _ = read_sales_file(raw, "p.csv", {"date": "date", "value": "qty", "item": "item", "business": {"price": "price"}})
    assert np.array_equal(by_adapter.values, by_hand.values) and rep_a.business == rep_h.business and set(rep_a.business["columns"]) == {"price"}


def test_adapter_names_cannot_escape_the_folder(tmp_path):
    for bad in ("../evil", "a/b", "A B", "", "x" * 41, ".hidden"):
        with pytest.raises(adapters.AdapterError) as e:
            adapters.save(tmp_path, adapters.Adapter(name=bad, mapping=adapters.AdapterMapping(date="d", value="v")))
        assert e.value.code == "bad_adapter_name"
    assert list(tmp_path.iterdir()) == []
    adapters.save(tmp_path, make())
    with pytest.raises(adapters.AdapterError) as e:
        adapters.save(tmp_path, make())
    assert e.value.code == "adapter_exists"
    adapters.save(tmp_path, make(description="changed"), overwrite=True)


def test_broken_adapter_files_are_reported_and_never_run_code(tmp_path):
    (tmp_path / "broken.yaml").write_text("name: [unclosed", encoding="utf-8")
    (tmp_path / "evil.yaml").write_text("name: evil\nmapping: !!python/object/apply:os.system ['echo hi']\n", encoding="utf-8")
    (tmp_path / "mismatch.yaml").write_text(yaml.safe_dump({"name": "other", "mapping": {"date": "d", "value": "v"}}), encoding="utf-8")
    adapters.save(tmp_path, make())
    found, bad = adapters.list_adapters(tmp_path / "none", tmp_path)
    assert [a.name for a, _ in found] == ["shop"] and len(bad) == 3


def test_a_saved_adapter_overrides_a_built_in_of_the_same_name(tmp_path):
    builtin, saved = tmp_path / "b", tmp_path / "s"
    adapters.save(builtin, make(description="shipped"))
    adapters.save(saved, make(description="mine"))
    found, _ = adapters.list_adapters(builtin, saved)
    assert found[0][0].description == "mine" and found[0][1] == "saved"


# ---- API ---------------------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api_module, "ADAPTERS_BUILTIN", tmp_path / "builtin")
    monkeypatch.setattr(api_module, "ADAPTERS_SAVED", tmp_path / "saved")
    return TestClient(create_app(serve_web=False))


def up(client, raw, name="f.csv"):
    r = client.post("/api/datasets", files={"file": (name, raw, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_reports_quality_business_columns_and_no_adapter_yet(client):
    s = up(client, priced_file())
    assert s["quality"] == [] or isinstance(s["quality"], list)
    assert s["report"]["business"]["columns"]["price"] == "price" and s["detection"]["business"]["on_hand"] == "stock on hand"
    assert s["adapter"] is None


def test_save_an_adapter_then_the_next_file_of_that_kind_is_recognised(client):
    s = up(client, priced_file())
    r = client.post(f"/api/datasets/{s['id']}/adapters", json={"name": "my-pos", "description": "Friday export"})
    assert r.status_code == 200, r.text
    assert r.json()["adapter"] == {"name": "my-pos", "description": "Friday export", "applied": True}
    assert [a["name"] for a in client.get("/api/adapters").json()["adapters"]] == ["my-pos"]
    again = up(client, priced_file())
    assert again["adapter"]["name"] == "my-pos" and again["adapter"]["applied"] is True
    dup = client.post(f"/api/datasets/{s['id']}/adapters", json={"name": "my-pos"})
    assert dup.status_code == 422 and dup.json()["code"] == "adapter_exists"
    bad = client.post(f"/api/datasets/{s['id']}/adapters", json={"name": "../x"})
    assert bad.status_code == 422 and bad.json()["code"] == "bad_adapter_name"


def test_applying_an_adapter_by_name_and_remapping_with_composite_keys_and_duplicate_rule(client):
    s = up(client, store_product_file())
    assert s["report"]["n_series"] == 2 and any(n["code"] == "other_id_columns" for n in s["report"]["notes"])
    r = client.post(f"/api/datasets/{s['id']}/mapping", json={"date": "date", "value": "qty", "item_cols": ["region", "product"]})
    assert r.status_code == 200 and r.json()["report"]["n_series"] == 4 and r.json()["detection"]["item_cols"] == ["region", "product"]
    client.post(f"/api/datasets/{s['id']}/adapters", json={"name": "split"})
    other = up(client, store_product_file())
    assert other["report"]["n_series"] == 2
    applied = client.post(f"/api/datasets/{other['id']}/mapping", json={"adapter": "split"}).json()
    assert applied["report"]["n_series"] == 4 and applied["adapter"]["applied"] is True
    assert client.post(f"/api/datasets/{other['id']}/mapping", json={"adapter": "nope"}).status_code == 404
    d = up(client, dup_file())
    fixed = client.post(f"/api/datasets/{d['id']}/mapping", json={"date": "date", "value": "qty", "item": "item", "duplicates": "drop_exact"}).json()
    assert any(n["code"] == "duplicates_dropped" for n in fixed["report"]["notes"])


def test_the_sample_cannot_save_an_adapter_and_uploads_stay_owner_only(client):
    sample = client.post("/api/datasets/sample").json()
    assert client.post(f"/api/datasets/{sample['id']}/adapters", json={"name": "x"}).status_code == 400
    locked = TestClient(create_app(serve_web=False, owner_key="secret"))
    s = locked.post("/api/datasets", files={"file": ("f.csv", priced_file(), "text/csv")}, headers={"X-Owner-Key": "secret"}).json()
    assert locked.post(f"/api/datasets/{s['id']}/adapters", json={"name": "x"}).status_code == 403
