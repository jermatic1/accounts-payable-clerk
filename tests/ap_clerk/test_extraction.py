from __future__ import annotations

from ap_clerk.extraction import (
    REASON_LINE_SUM_MISMATCH,
    REASON_MATH_MISMATCH,
    REASON_TOTALS_INCOMPLETE,
    InvoiceExtraction,
    LineItem,
    check_line_sum,
    check_math,
)


def test_math_pass_with_tax() -> None:
    extraction = InvoiceExtraction(
        subtotal=1250.0,
        tax_total=100.0,
        total_amount=1350.0,
    )
    ok, reason = check_math(extraction)
    assert ok is True
    assert reason is None


def test_math_pass_without_tax() -> None:
    extraction = InvoiceExtraction(
        subtotal=100.0,
        tax_total=None,
        total_amount=100.0,
    )
    ok, reason = check_math(extraction)
    assert ok is True
    assert reason is None


def test_math_pass_within_tolerance() -> None:
    extraction = InvoiceExtraction(
        subtotal=10.0,
        tax_total=0.01,
        total_amount=10.02,
    )
    ok, reason = check_math(extraction)
    assert ok is True
    assert reason is None


def test_math_fail_mismatch() -> None:
    extraction = InvoiceExtraction(
        subtotal=500.0,
        tax_total=45.0,
        total_amount=540.0,
    )
    ok, reason = check_math(extraction)
    assert ok is False
    assert reason == REASON_MATH_MISMATCH


def test_math_missing_subtotal() -> None:
    extraction = InvoiceExtraction(
        subtotal=None,
        tax_total=10.0,
        total_amount=100.0,
    )
    ok, reason = check_math(extraction)
    assert ok is False
    assert reason == REASON_TOTALS_INCOMPLETE


def test_math_missing_total() -> None:
    extraction = InvoiceExtraction(
        subtotal=100.0,
        tax_total=10.0,
        total_amount=None,
    )
    ok, reason = check_math(extraction)
    assert ok is False
    assert reason == REASON_TOTALS_INCOMPLETE


def test_line_sum_pass() -> None:
    extraction = InvoiceExtraction(
        subtotal=100.0,
        total_amount=100.0,
        line_items=[
            LineItem(description="a", amount=40.0),
            LineItem(description="b", amount=60.0),
        ],
    )
    ok, reason = check_line_sum(extraction)
    assert ok is True
    assert reason is None


def test_line_sum_pass_within_tolerance() -> None:
    extraction = InvoiceExtraction(
        subtotal=10.02,
        total_amount=10.02,
        line_items=[
            LineItem(amount=5.0),
            LineItem(amount=5.0),
        ],
    )
    ok, reason = check_line_sum(extraction)
    assert ok is True
    assert reason is None


def test_line_sum_mismatch() -> None:
    extraction = InvoiceExtraction(
        subtotal=100.0,
        total_amount=100.0,
        line_items=[
            LineItem(amount=40.0),
            LineItem(amount=50.0),
        ],
    )
    ok, reason = check_line_sum(extraction)
    assert ok is False
    assert reason == REASON_LINE_SUM_MISMATCH


def test_line_sum_skipped_when_no_line_amounts() -> None:
    extraction = InvoiceExtraction(
        subtotal=100.0,
        total_amount=100.0,
        line_items=[
            LineItem(description="no amount"),
            LineItem(description="also none", amount=None),
        ],
    )
    ok, reason = check_line_sum(extraction)
    assert ok is True
    assert reason is None


def test_line_sum_skipped_when_no_lines() -> None:
    extraction = InvoiceExtraction(subtotal=100.0, total_amount=100.0)
    ok, reason = check_line_sum(extraction)
    assert ok is True
    assert reason is None


def test_line_sum_skipped_when_subtotal_missing() -> None:
    extraction = InvoiceExtraction(
        subtotal=None,
        total_amount=100.0,
        line_items=[LineItem(amount=50.0)],
    )
    ok, reason = check_line_sum(extraction)
    assert ok is True
    assert reason is None


def test_invoice_extraction_ignores_extra_fields() -> None:
    extraction = InvoiceExtraction.model_validate(
        {
            "vendor_name_raw": "Acme",
            "subtotal": 10.0,
            "total_amount": 10.0,
            "unexpected": True,
        }
    )
    assert extraction.vendor_name_raw == "Acme"
    assert extraction.subtotal == 10.0
