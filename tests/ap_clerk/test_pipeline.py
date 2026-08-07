from __future__ import annotations

from pathlib import Path

from ap_clerk.extraction import (
    REASON_LINE_SUM_MISMATCH,
    REASON_MATH_MISMATCH,
    REASON_TOTALS_INCOMPLETE,
    InvoiceExtraction,
)
from ap_clerk.matching import PurchaseOrderMatch, VendorMatch
from ap_clerk.pipeline import (
    REASON_AUTO_APPROVED,
    REASON_LOW_CONFIDENCE,
    REASON_LOW_CONFIDENCE_PO,
    REASON_LOW_CONFIDENCE_VENDOR,
    REASON_PO_MISSING,
    REASON_SCHEMA_INVALID,
    REASON_VENDOR_PO_MISMATCH,
    STATUS_AUTO_APPROVED,
    STATUS_HUMAN_REVIEW,
    STATUS_REJECTED,
    _route,
    process_extraction,
)
from ap_clerk.purchase_orders import PurchaseOrder, load_purchase_orders
from ap_clerk.vendors import Vendor, load_vendors

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
VENDORS_PATH = FIXTURES / "vendors.json"
POS_PATH = FIXTURES / "purchase-orders.json"


def _fixture_masters() -> tuple[list[Vendor], list[PurchaseOrder]]:
    return load_vendors(VENDORS_PATH), load_purchase_orders(POS_PATH)


def _good_extraction(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "vendor_name_raw": "Summit Plumbing Supply",
        "purchase_order_raw": "P0001001",
        "subtotal": 1983.75,
        "tax_total": 0.0,
        "total_amount": 1983.75,
        "invoice_number": "INV-1",
    }
    base.update(overrides)
    return base


def test_process_exact_auto_approve() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(),
        vendors=vendors,
        purchase_orders=pos,
        source_file="sample.json",
    )
    assert result.status == STATUS_AUTO_APPROVED
    assert result.reason == REASON_AUTO_APPROVED
    assert result.source_file == "sample.json"
    assert result.payload.math_ok is True
    assert result.payload.vendor_match is not None
    assert result.payload.vendor_match.confident is True
    assert result.payload.vendor_match.vendor_id == "V001"
    assert result.payload.po_match is not None
    assert result.payload.po_match.confident is True
    assert result.payload.po_match.purchase_order_id == "P0001001"
    assert isinstance(result.payload.extraction, InvoiceExtraction)


def test_process_ocr_typo_auto_approve() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(
            vendor_name_raw="Summit Plumbng Supply",
            purchase_order_raw="POOO1OO1",
        ),
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_AUTO_APPROVED
    assert result.payload.vendor_match is not None
    assert result.payload.vendor_match.vendor_id == "V001"
    assert result.payload.po_match is not None
    assert result.payload.po_match.purchase_order_id == "P0001001"


def test_process_ambiguous_margin_review() -> None:
    vendors = [
        Vendor(vendor_id="A", vendor_name="Northwind Traders LLC"),
        Vendor(vendor_id="B", vendor_name="Northwind Traders Inc"),
    ]
    pos = [
        PurchaseOrder(purchase_order_id="PO-1", vendor_id="A", total_amount=100.0),
        PurchaseOrder(purchase_order_id="PO-2", vendor_id="B", total_amount=100.0),
    ]
    result = process_extraction(
        {
            "vendor_name_raw": "Northwind Traders",
            "purchase_order_raw": "PO-1",
            "subtotal": 100.0,
            "tax_total": 0.0,
            "total_amount": 100.0,
        },
        vendors=vendors,
        purchase_orders=pos,
        match_threshold=80.0,
        match_margin=10.0,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason in {
        REASON_LOW_CONFIDENCE,
        REASON_LOW_CONFIDENCE_VENDOR,
        REASON_LOW_CONFIDENCE_PO,
        REASON_VENDOR_PO_MISMATCH,
    }
    assert result.payload.vendor_match is not None
    assert len(result.payload.vendor_match.candidates) >= 2
    assert result.payload.vendor_match.confident is False or (
        result.payload.vendor_match.margin is not None
        and result.payload.vendor_match.margin < 10.0
    )


def test_process_vendor_po_mismatch() -> None:
    vendors = [
        Vendor(vendor_id="V-A", vendor_name="Alpha Manufacturing Group"),
        Vendor(vendor_id="V-B", vendor_name="Beta Manufacturing Group"),
    ]
    pos = [
        PurchaseOrder(
            purchase_order_id="ZZ-UNIQUE-PO", vendor_id="V-B", total_amount=50.0
        ),
    ]
    result = process_extraction(
        {
            "vendor_name_raw": "Alpha Manufacturing Group",
            "purchase_order_raw": "ZZ-UNIQUE-PO",
            "subtotal": 50.0,
            "total_amount": 50.0,
        },
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason == REASON_LOW_CONFIDENCE_PO

    result = process_extraction(
        {
            "vendor_name_raw": "Manufacturing Group",
            "purchase_order_raw": "ZZ-UNIQUE-PO",
            "subtotal": 50.0,
            "total_amount": 50.0,
        },
        vendors=vendors,
        purchase_orders=pos,
        match_threshold=70.0,
        match_margin=20.0,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    vm = result.payload.vendor_match
    pm = result.payload.po_match
    assert vm is not None and pm is not None
    assert pm.purchase_order_id == "ZZ-UNIQUE-PO"
    assert pm.vendor_id == "V-B"
    if vm.vendor_id is not None and vm.vendor_id != pm.vendor_id:
        assert result.reason == REASON_VENDOR_PO_MISMATCH
    else:
        assert result.reason in {
            REASON_LOW_CONFIDENCE,
            REASON_LOW_CONFIDENCE_VENDOR,
            REASON_VENDOR_PO_MISMATCH,
        }


def test_process_vendor_po_mismatch_via_pipeline_fields() -> None:
    extraction = InvoiceExtraction(
        vendor_name_raw="A",
        purchase_order_raw="P",
        subtotal=1.0,
        total_amount=1.0,
    )
    result = _route(
        extraction=extraction,
        math_ok=True,
        line_sum_ok=True,
        vendor_match=VendorMatch(
            vendor_id="V-A",
            vendor_name="A",
            score=100.0,
            margin=None,
            confident=True,
        ),
        po_match=PurchaseOrderMatch(
            purchase_order_id="P1",
            vendor_id="V-B",
            score=100.0,
            margin=None,
            confident=True,
        ),
        source_file=None,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason == REASON_VENDOR_PO_MISMATCH


def test_process_missing_po() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(purchase_order_raw=None, purchase_order_variants=[]),
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason == REASON_PO_MISSING
    assert result.payload.math_ok is True
    assert result.payload.vendor_match is not None
    assert result.payload.vendor_match.confident is True


def test_process_math_fail_despite_good_names() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(subtotal=1983.75, tax_total=0.0, total_amount=1900.0),
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason == REASON_MATH_MISMATCH
    assert result.payload.math_ok is False
    assert result.payload.line_sum_ok is None
    assert result.payload.vendor_match is None
    assert result.payload.po_match is None


def test_process_line_sum_mismatch_distinct_from_math() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(
            subtotal=1983.75,
            tax_total=0.0,
            total_amount=1983.75,
            line_items=[
                {"description": "a", "amount": 1000.0},
                {"description": "b", "amount": 900.0},
            ],
        ),
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason == REASON_LINE_SUM_MISMATCH
    assert result.payload.math_ok is True
    assert result.payload.line_sum_ok is False
    assert result.payload.vendor_match is None
    assert result.payload.po_match is None


def test_process_line_sum_ok_continues_to_match() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(
            line_items=[
                {"description": "a", "amount": 1000.0},
                {"description": "b", "amount": 983.75},
            ],
        ),
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_AUTO_APPROVED
    assert result.payload.math_ok is True
    assert result.payload.line_sum_ok is True


def test_process_no_line_amounts_skips_line_sum() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(line_items=[{"description": "x"}]),
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_AUTO_APPROVED
    assert result.payload.line_sum_ok is True


def test_process_separate_vendor_po_thresholds() -> None:
    vendors = [
        Vendor(vendor_id="A", vendor_name="Summit Plumbing Supply"),
        Vendor(vendor_id="B", vendor_name="Apex Electric Components"),
    ]
    pos = [
        PurchaseOrder(purchase_order_id="P0001001", vendor_id="A", total_amount=100.0),
    ]
    result = process_extraction(
        {
            "vendor_name_raw": "Summit Plumbng Supply",
            "purchase_order_raw": "P0001001",
            "subtotal": 100.0,
            "total_amount": 100.0,
        },
        vendors=vendors,
        purchase_orders=pos,
        match_threshold=99.0,
        vendor_threshold=80.0,
        po_threshold=99.0,
    )
    assert result.status == STATUS_AUTO_APPROVED
    assert result.payload.vendor_match is not None
    assert result.payload.vendor_match.vendor_id == "A"
    assert result.payload.po_match is not None
    assert result.payload.po_match.purchase_order_id == "P0001001"


def test_process_totals_incomplete() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        {"subtotal": 100.0, "vendor_name_raw": "Summit Plumbing Supply"},
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_HUMAN_REVIEW
    assert result.reason == REASON_TOTALS_INCOMPLETE
    assert result.payload.math_ok is False


def test_process_schema_invalid() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        {"subtotal": "not-a-number", "total_amount": 10.0},
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_REJECTED
    assert result.reason == REASON_SCHEMA_INVALID
    assert result.payload.math_ok is None
    assert result.payload.reason_code == REASON_SCHEMA_INVALID
    assert isinstance(result.payload.extraction, dict)


def test_process_result_json_stable() -> None:
    vendors, pos = _fixture_masters()
    result = process_extraction(
        _good_extraction(),
        vendors=vendors,
        purchase_orders=pos,
    )
    dumped = result.model_dump(mode="json")
    assert dumped["status"] == STATUS_AUTO_APPROVED
    assert dumped["payload"]["math_ok"] is True
    assert dumped["payload"]["extraction"]["total_amount"] == 1983.75
    assert dumped["payload"]["vendor_match"]["vendor_id"] == "V001"
    assert dumped["payload"]["po_match"]["purchase_order_id"] == "P0001001"
    assert "candidates" in dumped["payload"]["vendor_match"]
    assert "confident" in dumped["payload"]["vendor_match"]
