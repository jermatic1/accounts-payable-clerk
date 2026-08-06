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
