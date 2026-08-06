"""Build invoice dicts and write PDF fixtures."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from pypdf import PdfWriter

from invoice_generator.pdf import render_invoice

DEFAULT_TERMS = "Net 30"
DEFAULT_TERMS_DAYS = 30

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
DEFAULT_VENDORS = FIXTURES / "vendors.json"
DEFAULT_PURCHASE_ORDERS = FIXTURES / "purchase-orders.json"
DEFAULT_OUTPUT = FIXTURES / "invoices"
COMBINED_NAME = "all-invoices.pdf"


def load_json(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def city_state_zip(vendor: dict) -> str:
    return f"{vendor['city']}, {vendor['state']} {vendor['zip']}"


def vendor_fein(vendor_id: str) -> str:
    digits = "".join(ch for ch in vendor_id if ch.isdigit()) or "0"
    body = f"{(int(digits) * 1111111) % 100000000:08d}"
    return f"{body[:2]}-{body[2:]}"


def format_display_date(value: str | date) -> str:
    if isinstance(value, date):
        return f"{value.month}/{value.day}/{value.year}"
    year, month, day = value.split("-")
    return f"{int(month)}/{int(day)}/{year}"


def parse_iso_date(value: str) -> date:
    year, month, day = value.split("-")
    return date(int(year), int(month), int(day))


def build_invoice(vendor: dict, purchase_order: dict | None = None) -> dict:
    invoice = {
        "vendor_name": vendor["vendor_name"],
        "street": vendor["street"],
        "city_state_zip": city_state_zip(vendor),
        "phone": vendor["phone"],
        "fein": vendor_fein(vendor["vendor_id"]),
        "website": vendor["website"],
        "invoice_date": "",
        "invoice_number": "",
        "purchase_order": "",
        "due_date": "",
        "terms": "",
        "lines": [],
        "subtotal": None,
        "total": None,
    }
    if purchase_order is None:
        return invoice

    total = float(purchase_order["total_amount"])
    po_id = purchase_order["purchase_order_id"]
    invoice_date = parse_iso_date(purchase_order["order_date"])
    due_date = invoice_date + timedelta(days=DEFAULT_TERMS_DAYS)
    invoice.update(
        {
            "invoice_date": format_display_date(invoice_date),
            "invoice_number": f"INV-{po_id}",
            "purchase_order": po_id,
            "due_date": format_display_date(due_date),
            "terms": DEFAULT_TERMS,
            "lines": [
                {
                    "description": line["description"],
                    "amount": float(line["amount"]),
                }
                for line in purchase_order["lines"]
            ],
            "subtotal": total,
            "total": total,
        }
    )
    return invoice


def merge_pdfs(paths: list[Path], output: Path) -> Path:
    writer = PdfWriter()
    for path in paths:
        writer.append(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)
    return output


def generate_invoices(
    vendors_path: Path = DEFAULT_VENDORS,
    purchase_orders_path: Path = DEFAULT_PURCHASE_ORDERS,
    output_dir: Path = DEFAULT_OUTPUT,
) -> list[Path]:
    vendors = {vendor["vendor_id"]: vendor for vendor in load_json(vendors_path)}
    purchase_orders = load_json(purchase_orders_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for vendor_id, vendor in vendors.items():
        path = output_dir / f"{vendor_id}.pdf"
        render_invoice(path, build_invoice(vendor))
        written.append(path)

    for purchase_order in purchase_orders:
        vendor_id = purchase_order["vendor_id"]
        po_id = purchase_order["purchase_order_id"]
        path = output_dir / f"{vendor_id}_{po_id}.pdf"
        render_invoice(path, build_invoice(vendors[vendor_id], purchase_order))
        written.append(path)

    combined = merge_pdfs(written, output_dir / COMBINED_NAME)
    written.append(combined)
    return written
