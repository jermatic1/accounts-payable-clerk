from __future__ import annotations

from pathlib import Path

import pytest

from ap_clerk.documents import load_invoice
from ap_clerk.errors import APClerkError
from ap_clerk.extraction import InvoiceExtraction
from ap_clerk.pipeline import STATUS_AUTO_APPROVED, STATUS_HUMAN_REVIEW, process_invoice
from ap_clerk.purchase_orders import load_purchase_orders
from ap_clerk.vendors import load_vendors
from ap_clerk.vlm import FakeInvoiceExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
INVOICE_PDF = FIXTURES / "invoices" / "V001_P0001001.pdf"
VENDORS_PATH = FIXTURES / "vendors.json"
POS_PATH = FIXTURES / "purchase-orders.json"

_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_load_invoice_pdf_fixture() -> None:
    loaded = load_invoice(INVOICE_PDF)
    assert loaded.page_count >= 1
    assert loaded.image[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(loaded.image) > 100
    assert loaded.mime == "image/png"
    assert loaded.source_path == INVOICE_PDF


def test_load_invoice_png(tmp_path: Path) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(_MIN_PNG)
    loaded = load_invoice(path)
    assert loaded.page_count == 1
    assert loaded.image == _MIN_PNG
    assert loaded.mime == "image/png"
    assert loaded.source_path == path


def test_load_invoice_jpeg_mime(tmp_path: Path) -> None:
    path = tmp_path / "scan.jpg"
    path.write_bytes(b"\xff\xd8\xfffake-jpeg")
    loaded = load_invoice(path)
    assert loaded.page_count == 1
    assert len(loaded.image) == len(b"\xff\xd8\xfffake-jpeg")
    assert loaded.mime == "image/jpeg"


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(APClerkError, match="file not found"):
        load_invoice(tmp_path / "nope.pdf")


def test_load_unsupported_format(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(APClerkError, match="unsupported"):
        load_invoice(path)


def test_fake_extractor_with_real_pdf_render_json_shape() -> None:
    loaded = load_invoice(INVOICE_PDF)
    assert loaded.page_count >= 1
    assert loaded.image[:8] == b"\x89PNG\r\n\x1a\n"

    vendors = load_vendors(VENDORS_PATH)
    pos = load_purchase_orders(POS_PATH)
    extractor = FakeInvoiceExtractor(
        {
            "vendor_name_raw": "Summit Plumbing Supply",
            "purchase_order_raw": "P0001001",
            "subtotal": 1983.75,
            "tax_total": 0.0,
            "total_amount": 1983.75,
            "invoice_number": "INV-1",
        }
    )

    result = process_invoice(
        loaded,
        extractor=extractor,
        vendors=vendors,
        purchase_orders=pos,
    )

    assert result.status == STATUS_AUTO_APPROVED
    assert result.source_file == str(INVOICE_PDF)
    assert result.payload.page_count == loaded.page_count
    assert result.payload.math_ok is True
    assert isinstance(result.payload.extraction, InvoiceExtraction)
    assert result.payload.vendor_match is not None
    assert result.payload.vendor_match.vendor_id == "V001"
    assert result.payload.po_match is not None
    assert result.payload.po_match.purchase_order_id == "P0001001"

    dumped = result.model_dump(mode="json")
    assert dumped["status"] in {STATUS_AUTO_APPROVED, STATUS_HUMAN_REVIEW}
    assert dumped["payload"]["page_count"] == loaded.page_count
    assert "extraction" in dumped["payload"]
    assert "vendor_match" in dumped["payload"]
    assert "po_match" in dumped["payload"]

    assert len(extractor.calls) == 1
    assert extractor.calls[0][0] == loaded.image
    assert extractor.calls[0][1] == "image/png"
