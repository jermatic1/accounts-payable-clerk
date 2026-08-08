"""Purchase order reference records and their JSON loader.

Shapes follow the fixture exports until real master data lands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ap_clerk.errors import APClerkError


class PurchaseOrderLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    line_number: int | None = None
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class PurchaseOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")

    purchase_order_id: str
    vendor_id: str
    total_amount: float
    order_date: str | None = None
    lines: list[PurchaseOrderLine] = Field(default_factory=list)


def _read_json_array(path: Path) -> list[Any]:
    if not path.is_file():
        raise APClerkError(f"purchase orders file not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise APClerkError(f"could not read purchase orders file: {path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APClerkError(f"invalid JSON in purchase orders file: {path}") from exc
    if not isinstance(data, list):
        raise APClerkError(f"purchase orders file must be a JSON array: {path}")
    return data


def load_purchase_orders(path: Path) -> list[PurchaseOrder]:
    rows = _read_json_array(path)
    try:
        return [PurchaseOrder.model_validate(row) for row in rows]
    except ValidationError as exc:
        raise APClerkError(f"invalid purchase order records in {path}: {exc}") from exc
