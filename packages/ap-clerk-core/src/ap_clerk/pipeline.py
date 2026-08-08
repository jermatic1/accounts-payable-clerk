from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ValidationError

from ap_clerk.documents import LoadedInvoice
from ap_clerk.extraction import InvoiceExtraction
from ap_clerk.extractors import InvoiceExtractor
from ap_clerk.matching import (
    DEFAULT_MATCH_MARGIN,
    DEFAULT_MATCH_THRESHOLD,
    PurchaseOrderMatch,
    VendorMatch,
    match_purchase_order,
    match_vendor,
)
from ap_clerk.purchase_orders import PurchaseOrder
from ap_clerk.vendors import Vendor

STATUS_AUTO_APPROVED: Final = "AUTO_APPROVED"
STATUS_HUMAN_REVIEW: Final = "HUMAN_REVIEW"
STATUS_REJECTED: Final = "REJECTED"

REASON_SCHEMA_INVALID = "SCHEMA_INVALID"
REASON_MATH_MISMATCH = "MATH_MISMATCH"
REASON_LINE_SUM_MISMATCH = "LINE_SUM_MISMATCH"
REASON_TOTALS_INCOMPLETE = "TOTALS_INCOMPLETE"
REASON_PO_MISSING = "PO_MISSING"
REASON_VENDOR_PO_MISMATCH = "VENDOR_PO_MISMATCH"
REASON_LOW_CONFIDENCE_VENDOR = "LOW_CONFIDENCE_VENDOR"
REASON_LOW_CONFIDENCE_PO = "LOW_CONFIDENCE_PO"
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_AUTO_APPROVED = "AUTO_APPROVED"

PipelineStatus = Literal["AUTO_APPROVED", "HUMAN_REVIEW", "REJECTED"]

MATH_TOLERANCE = 0.02


def check_math(extraction: InvoiceExtraction) -> tuple[bool, str | None]:
    if extraction.subtotal is None or extraction.total_amount is None:
        return False, REASON_TOTALS_INCOMPLETE

    tax = extraction.tax_total if extraction.tax_total is not None else 0.0
    calculated = round(extraction.subtotal + tax, 2)
    reported = round(extraction.total_amount, 2)
    if abs(calculated - reported) > MATH_TOLERANCE:
        return False, REASON_MATH_MISMATCH
    return True, None


def check_line_sum(extraction: InvoiceExtraction) -> tuple[bool, str | None]:
    amounts = [item.amount for item in extraction.line_items if item.amount is not None]
    if not amounts or extraction.subtotal is None:
        return True, None

    line_total = round(sum(amounts), 2)
    subtotal = round(extraction.subtotal, 2)
    if abs(line_total - subtotal) > MATH_TOLERANCE:
        return False, REASON_LINE_SUM_MISMATCH
    return True, None


class ResultPayload(BaseModel):
    extraction: InvoiceExtraction | dict[str, Any] | None = None
    math_ok: bool | None = None
    line_sum_ok: bool | None = None
    reason_code: str | None = None
    vendor_match: VendorMatch | None = None
    po_match: PurchaseOrderMatch | None = None
    page_count: int | None = None


class PipelineResult(BaseModel):
    status: PipelineStatus
    reason: str
    source_file: str | None = None
    payload: ResultPayload


def _result(
    status: PipelineStatus,
    reason: str,
    *,
    extraction: InvoiceExtraction | dict[str, Any],
    source_file: str | None,
    page_count: int | None,
    math_ok: bool | None = None,
    line_sum_ok: bool | None = None,
    vendor_match: VendorMatch | None = None,
    po_match: PurchaseOrderMatch | None = None,
) -> PipelineResult:
    return PipelineResult(
        status=status,
        reason=reason,
        source_file=source_file,
        payload=ResultPayload(
            extraction=extraction,
            math_ok=math_ok,
            line_sum_ok=line_sum_ok,
            reason_code=reason,
            vendor_match=vendor_match,
            po_match=po_match,
            page_count=page_count,
        ),
    )


def _has_po_text(extraction: InvoiceExtraction) -> bool:
    if extraction.purchase_order_raw and extraction.purchase_order_raw.strip():
        return True
    return any(v.strip() for v in extraction.purchase_order_variants if v)


def process_invoice(
    loaded: LoadedInvoice,
    *,
    extractor: InvoiceExtractor,
    vendors: Sequence[Vendor],
    purchase_orders: Sequence[PurchaseOrder],
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    match_margin: float = DEFAULT_MATCH_MARGIN,
    vendor_threshold: float | None = None,
    po_threshold: float | None = None,
) -> PipelineResult:
    raw = extractor.extract_invoice(loaded.image)
    return process_extraction(
        raw,
        vendors=vendors,
        purchase_orders=purchase_orders,
        source_file=str(loaded.source_path),
        match_threshold=match_threshold,
        match_margin=match_margin,
        vendor_threshold=vendor_threshold,
        po_threshold=po_threshold,
        page_count=loaded.page_count,
    )


def process_extraction(
    raw: dict[str, Any],
    *,
    vendors: Sequence[Vendor],
    purchase_orders: Sequence[PurchaseOrder],
    source_file: str | None = None,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    match_margin: float = DEFAULT_MATCH_MARGIN,
    vendor_threshold: float | None = None,
    po_threshold: float | None = None,
    page_count: int | None = None,
) -> PipelineResult:
    resolved_vendor_threshold = (
        vendor_threshold if vendor_threshold is not None else match_threshold
    )
    resolved_po_threshold = (
        po_threshold if po_threshold is not None else match_threshold
    )

    try:
        extraction = InvoiceExtraction.model_validate(raw)
    except ValidationError:
        return _result(
            STATUS_REJECTED,
            REASON_SCHEMA_INVALID,
            extraction=raw,
            source_file=source_file,
            page_count=page_count,
        )

    math_ok, math_reason = check_math(extraction)
    if not math_ok:
        assert math_reason is not None
        return _result(
            STATUS_HUMAN_REVIEW,
            math_reason,
            extraction=extraction,
            source_file=source_file,
            page_count=page_count,
            math_ok=False,
        )

    line_sum_ok, line_sum_reason = check_line_sum(extraction)
    if not line_sum_ok:
        assert line_sum_reason is not None
        return _result(
            STATUS_HUMAN_REVIEW,
            line_sum_reason,
            extraction=extraction,
            source_file=source_file,
            page_count=page_count,
            math_ok=True,
            line_sum_ok=False,
        )

    vendor_match = match_vendor(
        extraction,
        vendors,
        threshold=resolved_vendor_threshold,
        margin=match_margin,
    )

    scoped_vendor_id = vendor_match.vendor_id if vendor_match.confident else None
    po_match = match_purchase_order(
        extraction,
        purchase_orders,
        vendor_id=scoped_vendor_id,
        threshold=resolved_po_threshold,
        margin=match_margin,
    )

    return _route(
        extraction=extraction,
        math_ok=True,
        line_sum_ok=True,
        vendor_match=vendor_match,
        po_match=po_match,
        source_file=source_file,
        page_count=page_count,
    )


def _route(
    *,
    extraction: InvoiceExtraction,
    math_ok: bool,
    line_sum_ok: bool,
    vendor_match: VendorMatch,
    po_match: PurchaseOrderMatch,
    source_file: str | None,
    page_count: int | None = None,
) -> PipelineResult:
    def result(status: PipelineStatus, reason: str) -> PipelineResult:
        return _result(
            status,
            reason,
            extraction=extraction,
            source_file=source_file,
            page_count=page_count,
            math_ok=math_ok,
            line_sum_ok=line_sum_ok,
            vendor_match=vendor_match,
            po_match=po_match,
        )

    if not _has_po_text(extraction):
        return result(STATUS_HUMAN_REVIEW, REASON_PO_MISSING)

    both_ids = (
        vendor_match.vendor_id is not None
        and po_match.vendor_id is not None
        and po_match.purchase_order_id is not None
    )
    if both_ids and vendor_match.vendor_id != po_match.vendor_id:
        return result(STATUS_HUMAN_REVIEW, REASON_VENDOR_PO_MISMATCH)

    if not vendor_match.confident and not po_match.confident:
        return result(STATUS_HUMAN_REVIEW, REASON_LOW_CONFIDENCE)
    if not vendor_match.confident:
        return result(STATUS_HUMAN_REVIEW, REASON_LOW_CONFIDENCE_VENDOR)
    if not po_match.confident:
        return result(STATUS_HUMAN_REVIEW, REASON_LOW_CONFIDENCE_PO)

    return result(STATUS_AUTO_APPROVED, REASON_AUTO_APPROVED)
