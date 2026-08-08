from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ap_clerk.config import load_config
from ap_clerk.documents import load_invoice
from ap_clerk.errors import APClerkError
from ap_clerk.pipeline import STATUS_REJECTED, process_invoice
from ap_clerk.purchase_orders import load_purchase_orders
from ap_clerk.vendors import load_vendors
from ap_clerk.vlm import VisionInvoiceExtractor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ap-clerk",
        description="Extract and match invoice data from images or PDFs.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Path to config.toml (default: ./config.toml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    subparsers = parser.add_subparsers(dest="command")

    extract = subparsers.add_parser(
        "extract",
        help="Extract invoice fields and match against master data",
    )
    extract.add_argument(
        "invoice_path",
        type=Path,
        help="Path to invoice PDF",
    )
    extract.add_argument(
        "-o",
        "--output",
        default="-",
        help="Write result JSON to path, or - for stdout (default)",
    )
    return parser


def _configure_logging(*, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )


def _write_output(text: str, output: str) -> None:
    if output == "-":
        print(text)
        return
    path = Path(output)
    try:
        path.write_text(text + "\n", encoding="utf-8")
    except OSError as exc:
        raise APClerkError(f"could not write output: {exc}") from exc


def _cmd_extract(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    logging.getLogger(__name__).debug("loaded config from %s", config.config_path)

    vendors = load_vendors(config.vendors_path)
    purchase_orders = load_purchase_orders(config.purchase_orders_path)
    loaded = load_invoice(args.invoice_path)
    extractor = VisionInvoiceExtractor(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )
    result = process_invoice(
        loaded,
        extractor=extractor,
        vendors=vendors,
        purchase_orders=purchase_orders,
        match_threshold=config.match_threshold,
        match_margin=config.match_margin,
        vendor_threshold=config.vendor_threshold,
        po_threshold=config.po_threshold,
    )
    text = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=False)
    _write_output(text, args.output)
    if result.status == STATUS_REJECTED:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=bool(args.verbose))

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "extract":
        try:
            return _cmd_extract(args)
        except APClerkError as exc:
            print(f"extract: {exc}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0
