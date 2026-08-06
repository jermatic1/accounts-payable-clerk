# Invoice generator

Generates sample vendor invoice PDFs for test fixtures.

## Usage

From the repo root:

```bash
uv run --package invoice-generator generate-invoices
```

## Paths

| Path | Role |
|------|------|
| `tests/fixtures/vendors.json` | Vendor master data |
| `tests/fixtures/purchase-orders.json` | Purchase order line items |
| `tests/fixtures/invoices/` | Generated invoice PDFs |
| `tests/fixtures/invoices/all-invoices.pdf` | All invoices in one printable PDF |
| `tools/invoice-generator/` | This tool |
