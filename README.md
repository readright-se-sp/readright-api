# ReadRight backend

FastAPI backend for ReadRight. Local ASR, MediaPipe CV, prosody analysis, and
the synchronous `/analyze` pipeline have been removed. ASR and vision are
separate service boundaries; the backend currently provides health and a
learner dashboard API.

## Docs

- [Architecture](ARCHITECTURE.md)
- [API contracts](docs/api-contract.md)
- [Models](docs/models.md)
- [Database design and migrations](docs/database-proposal.md)
- [AI service payloads](docs/ai-service-contracts.md)

## Run locally

Requires Python 3.12. Configure Supabase Auth and database access for the
dashboard endpoint.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

`GET /health` is public. `GET /v1/dashboard` requires a Supabase user access
token and a matching `learners` row. See [API contracts](docs/api-contract.md).

Database migrations live under `supabase/migrations/`. Local Supabase
development is described in [database design](docs/database-proposal.md).
