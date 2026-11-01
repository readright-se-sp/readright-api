# ReadRight backend

FastAPI backend for ReadRight. AI inference runs in external services. The
backend queues MAI 1.1.0 analyses, exposes a status route, and persists each
result to Supabase after a worker calls MAI. It also provides health, learner
dashboard, and trusted-backend CRUD routes.

## Docs

- [API contracts](docs/api-contract.md)
- [Models](docs/models.md)
- [Database design and migrations](docs/database-proposal.md)
- [AI service payloads](docs/ai-service-contracts.md)
- [MAI queued integration](docs/mai-integration.md)
- [Learner recording storage](docs/media-storage.md)
- [AWS Lambda deployment with SAM](docs/lambda-deployment.md)

## Run locally

Requires Python 3.12. Configure Supabase and `BACKEND_API_KEY` for CRUD routes.
Set `MAI_BASE_URL`, `MAI_API_KEY`, and `MAI_QUEUE_URL` to enable MAI background
processing. Never expose service keys or backend keys to browser code.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

`GET /health` is public. `GET /v1/dashboard` requires a Supabase user access
token and a matching `learners` row. Full-table CRUD routes require
`X-Backend-Key` and are for trusted server-side callers. See
[API contracts](docs/api-contract.md).

Database migrations live under `supabase/migrations/`. Local Supabase
development is described in [database design](docs/database-proposal.md).
