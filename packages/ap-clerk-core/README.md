# ap-clerk-core

Domain library for accounts payable invoice processing. Shared by CLI, web, and desktop frontends.

Import name: `ap_clerk`.

## Install

From the repo root:

```bash
uv sync --all-packages
```

## Modules

| Module | Role |
|--------|------|
| `config` | `Config`, `load_config` from `config.toml` |
| `documents` | `LoadedInvoice`, `load_invoice` (first PDF page rendered to PNG) |
| `errors` | `APClerkError`, `ExtractionError` |
| `extraction` | `InvoiceExtraction`, `LineItem`, `UnmappedField` (pure data models) |
| `matching` | Vendor and purchase-order fuzzy match |
| `pipeline` | `PipelineResult`, `process_invoice`, `process_extraction`, math / line-sum checks, statuses and reason codes |
| `purchase_orders` | `PurchaseOrder`, `load_purchase_orders` |
| `vendors` | `Vendor`, `load_vendors` |
| `extractors` | `InvoiceExtractor`, `FakeInvoiceExtractor`, `VisionInvoiceExtractor` |

## Façade

```python
from pathlib import Path

from ap_clerk.config import load_config
from ap_clerk.documents import load_invoice
from ap_clerk.pipeline import process_invoice
from ap_clerk.purchase_orders import load_purchase_orders
from ap_clerk.vendors import load_vendors
from ap_clerk.extractors import VisionInvoiceExtractor

config = load_config(Path("config.toml"))
result = process_invoice(
    load_invoice(Path("invoice.pdf")),
    extractor=VisionInvoiceExtractor(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    ),
    vendors=load_vendors(config.vendors_path),
    purchase_orders=load_purchase_orders(config.purchase_orders_path),
    match_threshold=config.match_threshold,
    match_margin=config.match_margin,
    vendor_threshold=config.vendor_threshold,
    po_threshold=config.po_threshold,
)
```

`process_extraction(dict, …)` is the dict-only test seam (no vision).

## Config

See `config.example.toml` at the repo root. Secrets go in gitignored `config.toml`.
