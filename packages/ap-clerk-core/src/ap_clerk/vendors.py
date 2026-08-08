"""Vendor reference records and their JSON loader.

Shapes follow the fixture exports until real master data lands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ap_clerk.errors import APClerkError


class Vendor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor_id: str
    vendor_name: str
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    website: str | None = None


def _read_json_array(path: Path) -> list[Any]:
    if not path.is_file():
        raise APClerkError(f"vendors file not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise APClerkError(f"could not read vendors file: {path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APClerkError(f"invalid JSON in vendors file: {path}") from exc
    if not isinstance(data, list):
        raise APClerkError(f"vendors file must be a JSON array: {path}")
    return data


def load_vendors(path: Path) -> list[Vendor]:
    rows = _read_json_array(path)
    try:
        return [Vendor.model_validate(row) for row in rows]
    except ValidationError as exc:
        raise APClerkError(f"invalid vendor records in {path}: {exc}") from exc
