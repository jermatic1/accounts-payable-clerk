from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

from ap_clerk.documents import load_invoice
from ap_clerk.pipeline import STATUS_AUTO_APPROVED, STATUS_HUMAN_REVIEW, process_invoice
from ap_clerk.purchase_orders import load_purchase_orders
from ap_clerk.vendors import load_vendors
from ap_clerk.vlm import VisionInvoiceExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
INVOICE_PDF = FIXTURES / "invoices" / "V001_P0001001.pdf"
VENDORS_PATH = FIXTURES / "vendors.json"
POS_PATH = FIXTURES / "purchase-orders.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config.toml"

pytestmark = pytest.mark.integration


def _live_vlm_settings() -> dict[str, Any] | None:
    if not CONFIG_PATH.is_file():
        return None
    try:
        data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    vlm = data.get("vlm")
    if not isinstance(vlm, dict):
        return None
    api_key = vlm.get("api_key")
    if (
        not isinstance(api_key, str)
        or not api_key.strip()
        or api_key.strip() == "replace-me"
    ):
        return None
    base_url = vlm.get("base_url")
    model = vlm.get("model")
    if not isinstance(base_url, str) or not isinstance(model, str):
        return None
    if not base_url.strip() or not model.strip():
        return None
    return vlm


@pytest.mark.integration
def test_live_vlm_extract_fixture_invoice() -> None:
    settings = _live_vlm_settings()
    if settings is None:
        pytest.skip("config.toml with real vlm.api_key not found")

    loaded = load_invoice(INVOICE_PDF)
    vendors = load_vendors(VENDORS_PATH)
    pos = load_purchase_orders(POS_PATH)
    timeout = settings.get("timeout_seconds", 120.0)
    extractor = VisionInvoiceExtractor(
        api_key=str(settings["api_key"]),
        base_url=str(settings["base_url"]),
        model=str(settings["model"]),
        timeout_seconds=float(timeout) if timeout is not None else 120.0,
    )

    result = process_invoice(
        loaded,
        extractor=extractor,
        vendors=vendors,
        purchase_orders=pos,
    )

    assert result.status in {STATUS_AUTO_APPROVED, STATUS_HUMAN_REVIEW}
    assert result.payload.extraction is not None
    dumped = result.model_dump(mode="json")
    assert "vendor_match" in dumped["payload"]
    assert "po_match" in dumped["payload"]
