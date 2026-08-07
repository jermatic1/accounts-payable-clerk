from __future__ import annotations

import json
from pathlib import Path

import pytest

from ap_clerk.errors import APClerkError
from ap_clerk.vendors import load_vendors

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
VENDORS_PATH = FIXTURES / "vendors.json"


def test_load_vendors_fixture() -> None:
    vendors = load_vendors(VENDORS_PATH)
    assert len(vendors) >= 1
    first = vendors[0]
    assert first.vendor_id
    assert first.vendor_name
    ids = {v.vendor_id for v in vendors}
    assert len(ids) == len(vendors)


def test_load_vendors_ignores_extra_fields(tmp_path: Path) -> None:
    vendors_path = tmp_path / "vendors.json"
    vendors_path.write_text(
        json.dumps(
            [
                {
                    "vendor_id": "X1",
                    "vendor_name": "Extra Corp",
                    "unexpected_field": True,
                    "nested": {"a": 1},
                }
            ]
        ),
        encoding="utf-8",
    )
    vendors = load_vendors(vendors_path)
    assert len(vendors) == 1
    assert vendors[0].vendor_id == "X1"
    assert vendors[0].vendor_name == "Extra Corp"


def test_load_vendors_missing_file(tmp_path: Path) -> None:
    with pytest.raises(APClerkError, match="not found"):
        load_vendors(tmp_path / "missing.json")


def test_load_vendors_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(APClerkError, match="invalid JSON"):
        load_vendors(path)


def test_load_vendors_not_array(tmp_path: Path) -> None:
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"vendor_id": "X"}), encoding="utf-8")
    with pytest.raises(APClerkError, match="JSON array"):
        load_vendors(path)


def test_load_vendors_missing_required(tmp_path: Path) -> None:
    path = tmp_path / "vendors.json"
    path.write_text(json.dumps([{"vendor_name": "No Id"}]), encoding="utf-8")
    with pytest.raises(APClerkError, match="invalid vendor"):
        load_vendors(path)
