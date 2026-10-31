# ReadRight API

FastAPI service for ReadRight's reading assessment pipeline. The current
implementation accepts a recording at `POST /analyze`, runs WhisperX and
MediaPipe in the API process, and returns an aggregate assessment. The target
design moves ASR and MediaPipe vision into independently deployed services.
That separation is documented as a proposal; it is not yet reflected in the
runtime code.

## Documentation

- [Documentation guide](docs/README.md)
- [Architecture overview](ARCHITECTURE.md) — current implementation and target
  boundaries.
- [Frontend API and payload proposals](docs/api-contract.md) — existing
  `/analyze` contract and suggested session/upload/status flow.
- [AI service contracts](docs/ai-service-contracts.md) — versioned ASR and
  vision job/result examples.
- [Database proposal](docs/database-proposal.md) — review notes for the
  provisional model in `docs/schema-proposal.dbml`.

## Requirements

- Python 3.12
- FFmpeg
- Supabase project for the current passage/session repositories

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in the required API and Supabase settings in `.env`. Install FFmpeg using
your operating system's package manager.

## Run locally

```bash
uvicorn app.main:app --reload
```

The current endpoint is `POST /analyze` and requires `X-API-Key`. See the
[implemented API contract](docs/api-contract.md#implemented-endpoint). Do not
put a reusable backend API key or Supabase service key in frontend code.

## Deployment

`docker-compose.yml` describes the current single API container behind Caddy.
It does not deploy the proposed ASR or CV services. Deployment topology for
those services remains to be decided.
