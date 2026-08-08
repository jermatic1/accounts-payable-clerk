from __future__ import annotations

from ap_clerk.extraction import InvoiceExtraction


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
    assert extraction.unmapped_fields == []


def test_invoice_extraction_unmapped_fields_roundtrip() -> None:
    extraction = InvoiceExtraction.model_validate(
        {
            "vendor_name_raw": "Acme",
            "unmapped_fields": [
                {"label": "FEIN#", "value": "01-111111"},
                {"label": "TAX EXEMPT", "value": "0.000%"},
            ],
        }
    )
    assert [(f.label, f.value) for f in extraction.unmapped_fields] == [
        ("FEIN#", "01-111111"),
        ("TAX EXEMPT", "0.000%"),
    ]
    dumped = extraction.model_dump(mode="json")
    assert dumped["unmapped_fields"][0] == {"label": "FEIN#", "value": "01-111111"}
