# Repository guidance

This repository is the ReadRight backend shell. Local ASR, MediaPipe CV,
prosody, and `/analyze` processing have been removed. The runtime currently
serves `GET /health`; frontend and AI service contracts remain proposals.

## Layout

```text
app/
  main.py                 # FastAPI app and startup
  config.py               # Environment settings
  routers/health.py       # Liveness endpoint
  models/                 # Typed domain and service boundary shapes
  services/db/            # Supabase client and repositories
docs/
  api-contract.md         # Current and proposed frontend API
  models.md               # Consolidated model reference
  database-proposal.md    # Notes and open database decisions
  schema-proposal.dbml    # Provisional PostgreSQL schema
  ai-service-contracts.md # Proposed external ASR/CV payloads
```

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The only current route is `GET /health`. Supabase settings are optional until
database-backed routes are added. Do not put service-role credentials in a
frontend.

## Documentation

Keep docs concise. Update `docs/api-contract.md`, `docs/models.md`,
`docs/database-proposal.md`, or `docs/ai-service-contracts.md` when their
contracts change. Do not add sequence diagrams or a change journal unless the
user asks. Clearly label unimplemented designs as proposals.
