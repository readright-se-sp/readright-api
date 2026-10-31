---
name: generate-and-verify
description: >
  Implement or change Python code in the ReadRight backend. Keep code typed and
  small, inspect the result, and update only the concise maintained docs when
  their contracts change.
---

# Python changes

- Use Python 3.12 syntax and precise parameter/return types.
- Keep API, persistence, and domain logic in separate modules when separation
  improves ownership; avoid adding layers without a concrete need.
- Use Pydantic or `TypedDict` for structured data. Use protocols at real
  replacement boundaries.
- Put environment settings in `app/config.py`.
- Run `pyright app/` for changes that affect typing when the user has not asked
  to skip verification. Do not run tests unless the user asks.
- Update `docs/api-contract.md`, `docs/models.md`, the database docs, or
  `docs/ai-service-contracts.md` only when the change affects those contracts.
- Keep unimplemented endpoints and integrations labeled as proposals.
- Do not add sequence diagrams, a change journal, or per-class docs unless the
  user asks.
