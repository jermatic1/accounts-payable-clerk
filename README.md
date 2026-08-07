# Accounts Payable Clerk

Responsibilities:
 * Receives electronic invoices; parses invoices into a format consumable by ERP systems.
 * Reviews invoices for exceptions such as missing Purchase Orders; exports invoices on for approval.

## Development

[uv](https://docs.astral.sh/uv/) manages dependencies; [Task](https://taskfile.dev) is the interface.

```bash
# install deps + dev tools
task init:dev

# available tasks
task --list

# ruff lint/format check + basedpyright
task lint

# pytest
task test

# lint + tests (run before merging a change-set)
task check
```

## Packages

| Package | Import | Role |
|---------|--------|------|
| `packages/ap-clerk-core` | `ap_clerk` | Domain library |
| `packages/ap-clerk-cli` | `ap_clerk_cli` | Thin CLI frontend |

```bash
cp config.example.toml config.toml
# edit api_key, base_url, model, masters paths

task extract-invoice -- extract path/to/invoice.pdf
# or: uv run --package ap-clerk-cli ap-clerk extract path/to/invoice.pdf
```
