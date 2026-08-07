from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ap-clerk")
    subparsers = parser.add_subparsers(dest="command")

    extract = subparsers.add_parser("extract", help="Extract invoice data")
    extract.add_argument("invoice", help="Path to invoice image or PDF")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "extract":
        print("extract is not implemented yet", file=sys.stderr)
        return 0

    parser.print_help()
    return 0
