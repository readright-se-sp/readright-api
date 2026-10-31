---
name: design-docs
description: >
  Maintain concise ReadRight architecture, API contract, model, and database
  documentation. Use when the user asks for docs or when a code change affects
  one of those maintained contracts.
---

# ReadRight documentation conventions

Keep documentation short and update an existing page before adding another.
Maintain only:

- `ARCHITECTURE.md` for current and target boundaries.
- `docs/api-contract.md` for frontend requests and responses.
- `docs/ai-service-contracts.md` for external ASR/CV payloads, when those
  integrations are in scope.
- `docs/database-proposal.md` and `docs/schema-proposal.dbml` for data model
  decisions.
- `docs/lld/models/` and `docs/uml/class/models.md` for data shapes.

Label unimplemented designs as proposals. Keep the current implementation
distinct from target architecture. Do not add sequence diagrams, a journal,
per-class design files, or duplicate architecture pages unless the user asks.
