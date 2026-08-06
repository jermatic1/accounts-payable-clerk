# Agent guidelines

## Code style

- Prefer clear code over comments. Do not add comments that restate what the code does.
- Comments are only for non-obvious intent, tradeoffs, or constraints.
- Keep changes small and consistent with existing style.

## Git

- Prefer simple commit messages (short subject; body only when needed).
- Do not commit unless asked.
- Do not amend, force-push, or rewrite history unless asked.

## Checks

- Before commit: `task lint` and `task test`.
- End of a change-set: `task check` (full gate).

## Notes

- Do not invent URLs or expand scope beyond the request.
