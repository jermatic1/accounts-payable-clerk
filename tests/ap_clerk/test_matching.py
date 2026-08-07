from __future__ import annotations

from ap_clerk.extraction import InvoiceExtraction
from ap_clerk.matching import match_purchase_order, match_vendor, normalize
from ap_clerk.purchase_orders import PurchaseOrder
from ap_clerk.vendors import Vendor


def test_normalize_trim_case_separators() -> None:
    assert normalize("  Summit-Plumbing_Supply  ") == "summit plumbing supply"


def test_normalize_ocr_confusables() -> None:
    # 0→o and 1→i so OCR digit/letter swaps share a key; words stay intact
    assert normalize("P0001001") == normalize("POOOIOOI")
    assert normalize("P0001001") == normalize("POOO1OO1")
    assert normalize("Summ1t") == normalize("Summit")
    assert normalize("Summit") == "summit"


def test_match_vendor_exact() -> None:
    vendors = [
        Vendor(vendor_id="A", vendor_name="Summit Plumbing Supply"),
        Vendor(vendor_id="B", vendor_name="Apex Electric Components"),
    ]
    extraction = InvoiceExtraction(vendor_name_raw="Summit Plumbing Supply")
    result = match_vendor(extraction, vendors, threshold=85.0, margin=5.0)
    assert result.confident is True
    assert result.vendor_id == "A"
    assert result.score == 100.0
    assert result.candidates
    assert result.candidates[0].id == "A"


def test_match_vendor_typo() -> None:
    vendors = [
        Vendor(vendor_id="A", vendor_name="Summit Plumbing Supply"),
        Vendor(vendor_id="B", vendor_name="Apex Electric Components"),
    ]
    extraction = InvoiceExtraction(vendor_name_raw="Summit Plumbng Supply")
    result = match_vendor(extraction, vendors, threshold=85.0, margin=5.0)
    assert result.confident is True
    assert result.vendor_id == "A"
    assert result.score is not None and result.score >= 85.0


def test_match_vendor_ambiguous_margin() -> None:
    vendors = [
        Vendor(vendor_id="A", vendor_name="Acme Industrial Supply"),
        Vendor(vendor_id="B", vendor_name="Acme Industrial Supplies"),
    ]
    extraction = InvoiceExtraction(vendor_name_raw="Acme Industrial Supply")
    result = match_vendor(extraction, vendors, threshold=85.0, margin=5.0)
    assert len(result.candidates) >= 2
    assert result.margin is not None
    if result.margin < 5.0:
        assert result.confident is False
    else:
        assert result.vendor_id == "A"
        assert result.confident is True


def test_match_vendor_ambiguous_forced() -> None:
    vendors = [
        Vendor(vendor_id="A", vendor_name="Northwind Traders LLC"),
        Vendor(vendor_id="B", vendor_name="Northwind Traders Inc"),
    ]
    extraction = InvoiceExtraction(vendor_name_raw="Northwind Traders")
    result = match_vendor(extraction, vendors, threshold=80.0, margin=10.0)
    assert result.score is not None and result.score >= 80.0
    assert result.margin is not None
    assert result.margin < 10.0
    assert result.confident is False
    assert {c.id for c in result.candidates} >= {"A", "B"}


def test_match_po_exact_and_vendor_scoped() -> None:
    pos = [
        PurchaseOrder(purchase_order_id="PO-ALPHA", vendor_id="V1", total_amount=100.0),
        PurchaseOrder(purchase_order_id="PO-BETA", vendor_id="V2", total_amount=200.0),
    ]
    extraction = InvoiceExtraction(purchase_order_raw="PO-ALPHA")
    result = match_purchase_order(
        extraction,
        pos,
        vendor_id="V1",
        threshold=85.0,
        margin=5.0,
    )
    assert result.confident is True
    assert result.purchase_order_id == "PO-ALPHA"
    assert result.vendor_id == "V1"
    assert result.score == 100.0


def test_match_po_ocr_confusable() -> None:
    pos = [
        PurchaseOrder(purchase_order_id="P0001001", vendor_id="V1", total_amount=10.0),
        PurchaseOrder(purchase_order_id="P0002002", vendor_id="V1", total_amount=20.0),
    ]
    extraction = InvoiceExtraction(purchase_order_raw="POOO1OO1")
    result = match_purchase_order(
        extraction,
        pos,
        vendor_id="V1",
        threshold=85.0,
        margin=5.0,
    )
    assert result.confident is True
    assert result.purchase_order_id == "P0001001"
