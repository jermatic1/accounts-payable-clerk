# ap-clerk-cli

Thin CLI frontend for accounts payable invoice processing.

## Setup

From the repo root:

```bash
uv sync --all-packages
cp config.example.toml config.toml
# edit api_key, base_url, model, masters paths
```

`config.toml` is gitignored and may contain secrets. Never commit it.

## Usage

```bash
ap-clerk extract path/to/invoice.pdf
ap-clerk extract invoice.pdf -o result.json
ap-clerk extract invoice.pdf -c /path/to/other-config.toml
ap-clerk -v extract invoice.pdf
```

Via Task:

```bash
task extract-invoice -- extract path/to/invoice.pdf
```

Or:

```bash
uv run --package ap-clerk-cli ap-clerk extract path/to/invoice.pdf
```

## CLI shape

```text
ap-clerk [--config PATH] [-v] extract INVOICE_PATH [-o PATH]
```

Per-run only: invoice path, optional config path, output path, verbose. Masters, VLM, and match thresholds come from `config.toml`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | `AUTO_APPROVED` or `HUMAN_REVIEW` |
| 1 | `REJECTED`, or operator error (`APClerkError`) |
| 2 | argparse / usage error |

Result JSON is written to stdout (or `-o`).
