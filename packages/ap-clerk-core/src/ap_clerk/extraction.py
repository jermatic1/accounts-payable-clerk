from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MATH_TOLERANCE = 0.02

REASON_MATH_MISMATCH = "MATH_MISMATCH"
REASON_LINE_SUM_MISMATCH = "LINE_SUM_MISMATCH"
REASON_TOTALS_INCOMPLETE = "TOTALS_INCOMPLETE"


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class UnmappedField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    value: str | None = None


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor_name_raw: str | None = None
    vendor_name_variants: list[str] = Field(default_factory=list)
    vendor_address_raw: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    purchase_order_raw: str | None = None
    purchase_order_variants: list[str] = Field(default_factory=list)
    terms: str | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax_total: float | None = None
    total_amount: float | None = None
    unmapped_fields: list[UnmappedField] = Field(default_factory=list)


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
