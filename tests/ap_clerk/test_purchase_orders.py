from __future__ import annotations

import json
from pathlib import Path

import pytest

from ap_clerk.errors import APClerkError
from ap_clerk.purchase_orders import load_purchase_orders

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
POS_PATH = FIXTURES / "purchase-orders.json"


def test_load_purchase_orders_fixture() -> None:
    pos = load_purchase_orders(POS_PATH)
    assert len(pos) >= 1
    first = pos[0]
    assert first.purchase_order_id
    assert first.vendor_id
    assert isinstance(first.total_amount, float)
    assert first.lines


def test_load_purchase_orders_ignores_extra_fields(tmp_path: Path) -> None:
    pos_path = tmp_path / "pos.json"
    pos_path.write_text(
        json.dumps(
            [
                {
                    "purchase_order_id": "PO-A",
                    "vendor_id": "X1",
                    "total_amount": 12.5,
                    "extra_flag": "yes",
                    "lines": [{"description": "widget", "mystery": 1}],
                }
            ]
        ),
        encoding="utf-8",
    )
    pos = load_purchase_orders(pos_path)
    assert len(pos) == 1
    assert pos[0].purchase_order_id == "PO-A"
    assert pos[0].total_amount == 12.5


def test_load_purchase_orders_missing_file(tmp_path: Path) -> None:
    with pytest.raises(APClerkError, match="not found"):
        load_purchase_orders(tmp_path / "missing.json")


def test_load_purchase_orders_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(APClerkError, match="invalid JSON"):
        load_purchase_orders(path)


def test_load_purchase_orders_not_array(tmp_path: Path) -> None:
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"purchase_order_id": "P"}), encoding="utf-8")
    with pytest.raises(APClerkError, match="JSON array"):
        load_purchase_orders(path)


def test_load_purchase_orders_missing_required(tmp_path: Path) -> None:
    path = tmp_path / "pos.json"
    path.write_text(
        json.dumps([{"purchase_order_id": "P1", "vendor_id": "V1"}]),
        encoding="utf-8",
    )
    with pytest.raises(APClerkError, match="invalid purchase order"):
        load_purchase_orders(path)
