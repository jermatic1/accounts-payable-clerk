"""Models for the raw fields transcribed from an invoice page.

Everything is optional and as-printed; nothing here is validated or
trusted. Downstream checks and matching decide what to believe.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class UnmappedField(BaseModel):
    """Labeled value printed on the page that fits no schema field."""

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    value: str | None = None


class InvoiceExtraction(BaseModel):
    """A claim about an invoice — what the model read, before any check has vouched for it."""

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
