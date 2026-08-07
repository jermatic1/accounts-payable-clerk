from __future__ import annotations

from pathlib import Path

import pytest

from ap_clerk.config import ConfigError, load_config
from ap_clerk.documents import load_invoice
from ap_clerk.pipeline import STATUS_AUTO_APPROVED, STATUS_HUMAN_REVIEW, process_invoice
from ap_clerk.purchase_orders import load_purchase_orders
from ap_clerk.vendors import load_vendors
from ap_clerk.vlm import VisionInvoiceExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
INVOICE_PDF = FIXTURES / "invoices" / "V001_P0001001.pdf"
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config.toml"

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_live_vlm_extract_fixture_invoice() -> None:
    if not CONFIG_PATH.is_file():
        pytest.skip("config.toml with real vlm.api_key not found")
    try:
        config = load_config(CONFIG_PATH)
    except ConfigError:
        pytest.skip("config.toml present but invalid")
    if config.api_key.strip() == "replace-me":
        pytest.skip("config.toml with real vlm.api_key not found")

    loaded = load_invoice(INVOICE_PDF)
    vendors = load_vendors(config.vendors_path)
    pos = load_purchase_orders(config.purchase_orders_path)
    extractor = VisionInvoiceExtractor(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )

    result = process_invoice(
        loaded,
        extractor=extractor,
        vendors=vendors,
        purchase_orders=pos,
        match_threshold=config.match_threshold,
        match_margin=config.match_margin,
        vendor_threshold=config.vendor_threshold,
        po_threshold=config.po_threshold,
    )

    assert result.status in {STATUS_AUTO_APPROVED, STATUS_HUMAN_REVIEW}
    assert result.payload.extraction is not None
    dumped = result.model_dump(mode="json")
    assert "vendor_match" in dumped["payload"]
    assert "po_match" in dumped["payload"]
