"""Adapters: a saved description of how one kind of file maps onto Hindsight's data (which column is the date, the sales, the item...).

A shop that exports the same report every week should not have to confirm the columns every time. An adapter is a small YAML file. It
matches a file when every column it names is present, and applying it only sets the same column choices the confirm screen offers, so an
adapter cannot do anything a person could not do by hand. YAML is read with `safe_load` and validated, names are restricted to plain
slugs, and files are only ever read from or written to the two adapter folders."""
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
KINDS = ("price", "unit_cost", "on_hand", "on_order")


class AdapterError(ValueError):
    def __init__(self, message: str, code: str, **params):
        super().__init__(message)
        self.code, self.params = code, params


class AdapterMapping(BaseModel):
    date: str
    value: str | None = None
    item: str | None = None
    item_cols: list[str] = Field(default_factory=list)  # two or more columns that together name an item
    item_columns: list[str] = Field(default_factory=list)  # wide files: one column per item
    business: dict[str, str] = Field(default_factory=dict)  # price, unit_cost, on_hand, on_order -> column


class Adapter(BaseModel):
    name: str
    description: str = Field("", max_length=200)
    mapping: AdapterMapping
    duplicates: Literal["sum", "drop_exact"] = "sum"

    @property
    def columns(self) -> list[str]:
        m = self.mapping
        return [c for c in [m.date, m.value, m.item, *m.item_cols, *m.item_columns, *m.business.values()] if c]


def to_mapping(a: Adapter) -> dict:
    """The mapping `read_sales_file` takes."""
    m = a.mapping
    out: dict = {"date": m.date, "duplicates": a.duplicates, "business": dict(m.business)}
    if m.item_columns:
        out["item_columns"] = list(m.item_columns)
    else:
        out |= {"value": m.value, "item": m.item, "item_cols": list(m.item_cols)}
    return out


def _load_dir(folder: Path, source: str) -> tuple[list[tuple[Adapter, str]], list[str]]:
    found, bad = [], []
    if not folder.is_dir():
        return found, bad
    for f in sorted(folder.glob("*.yaml")):
        try:
            a = Adapter(**yaml.safe_load(f.read_text(encoding="utf-8")))
            if not NAME.match(a.name) or a.name != f.stem:
                raise ValueError("the name must be a plain slug equal to the file name")
            found.append((a, source))
        except (ValueError, ValidationError, yaml.YAMLError, TypeError) as err:
            bad.append(f"{f.name}: {err}")
    return found, bad


def list_adapters(builtin: Path, saved: Path) -> tuple[list[tuple[Adapter, str]], list[str]]:
    """Every valid adapter with where it came from ("built-in" or "saved"); a saved one overrides a built-in of the same name. Broken files are reported, not fatal."""
    a, bad_a = _load_dir(builtin, "built-in")
    b, bad_b = _load_dir(saved, "saved")
    merged = {x.name: (x, s) for x, s in a} | {x.name: (x, s) for x, s in b}
    return list(merged.values()), bad_a + bad_b


def match(adapters: list[Adapter], file_columns: list[str]) -> Adapter | None:
    """The adapter that names the most columns, among those whose columns are all in the file."""
    have = set(file_columns)
    fits = [a for a in adapters if set(a.columns) <= have]
    return max(fits, key=lambda a: len(a.columns), default=None)


def from_import(name: str, description: str, mapping: dict, detection: dict, duplicates: str) -> Adapter:
    """Build an adapter from what the confirm screen currently shows."""
    if not NAME.match(name or ""):
        raise AdapterError("Use 1 to 40 lowercase letters, digits, dashes or underscores, starting with a letter or digit.", "bad_adapter_name")
    wide = detection.get("layout") == "wide"
    return Adapter(name=name, description=description or "",
                   mapping=AdapterMapping(date=mapping["date"], value=None if wide else mapping.get("value"), item=None if wide else mapping.get("item"),
                                          item_cols=[] if wide else list(mapping.get("item_cols") or []), item_columns=list(mapping.get("item_columns") or []) if wide else [],
                                          business=dict(detection.get("business") or {})),
                   duplicates=duplicates)


def save(folder: Path, a: Adapter, overwrite: bool = False) -> Path:
    if not NAME.match(a.name):
        raise AdapterError("Use 1 to 40 lowercase letters, digits, dashes or underscores, starting with a letter or digit.", "bad_adapter_name")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{a.name}.yaml"
    if path.exists() and not overwrite:
        raise AdapterError(f"An adapter named '{a.name}' already exists.", "adapter_exists", name=a.name)
    path.write_text(yaml.safe_dump(a.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
