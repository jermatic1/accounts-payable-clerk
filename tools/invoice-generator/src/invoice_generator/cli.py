"""CLI entry point for invoice fixture generation."""

from __future__ import annotations

from invoice_generator.generate import DEFAULT_OUTPUT, generate_invoices


def main() -> None:
    written = generate_invoices()
    print(f"Wrote {len(written)} invoices to {DEFAULT_OUTPUT}")
    for path in written:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
