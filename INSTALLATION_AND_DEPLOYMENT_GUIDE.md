# 6.5. Installation and Deployment Guide

This guide covers the three `dev` branches as one system:

| Repository | Role |
|---|---|
| [readright-app](https://github.com/readright-se-sp/readright-app/tree/dev) | React learner-facing web app |
| [readright-api](https://github.com/readright-se-sp/readright-api/tree/dev) | FastAPI application backend and Supabase access |
| [readright-ai](https://github.com/readright-se-sp/readright-ai/tree/dev) | Media analysis API and audio/video workers |

The commands below use Bash, macOS/Linux, or WSL syntax unless noted. Keep real keys in local environment files or the hosting provider's secret manager; never commit them.

## Local setup

### Prerequisites

- Git
- Node.js 20+ and npm
- Python 3.12 for the application API; Python 3.11+ and `uv` if running MAI outside Docker
- Docker Desktop or Docker Engine with Compose
- Supabase CLI for the local database and Auth stack
- An AWS S3 development bucket and credentials for the full recording flow. The backend signs browser uploads directly to S3.

### 1. Clone the repositories

```bash
mkdir readright-workspace
cd readright-workspace
git clone --branch dev https://github.com/readright-se-sp/readright-app.git
git clone --branch dev https://github.com/readright-se-sp/readright-api.git
git clone --branch dev https://github.com/readright-se-sp/readright-ai.git
```

### 2. Start Supabase and apply the schema

From `readright-api/`, start Docker and run:

```bash
supabase start
supabase db reset
supabase status
```

Use the local API URL, anon key, and service-role key printed by `supabase status` in the app and backend configuration below. The migrations create the schema, but this repository does not include seed passages or comprehension questions; load approved development content before trying to start a learner session.

### 3. Configure and start the AI service

From `readright-ai/`:

```bash
cp .env.example .env
```

Set a local `MAI_API_KEY` in `.env` and leave `MAI_SITE_ADDRESS=localhost`. Start the Compose stack:

```bash
docker compose up --build -d
curl -k https://localhost/health/ready
```

The local Compose stack starts Caddy, the MAI API, Redis, a local S3-compatible Moto service, a real video worker, and a **fake audio worker**. It is suitable for integration work, but does not provide real audio scoring. The Caddy certificate is local-development TLS; trust its local CA on the backend host rather than disabling certificate verification.

To let the local backend trust the Compose endpoint, export Caddy's local root certificate and set `SSL_CERT_FILE` in the shell used to run the backend:

```bash
docker compose exec -T caddy cat /data/caddy/pki/authorities/local/root.crt > /tmp/readright-mai-root.crt
export SSL_CERT_FILE=/tmp/readright-mai-root.crt
```

### 4. Configure and start the application API

From `readright-api/`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set these values in `.env`:

| Variable | Local value / purpose |
|---|---|
| `SUPABASE_URL` | Local Supabase URL, normally `http://127.0.0.1:54321` |
| `SUPABASE_SERVICE_KEY` | Local service-role key from `supabase status` |
| `BACKEND_API_KEY` | A random local-only key for trusted backend routes |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` |
| `MAI_BASE_URL` | `https://localhost/v1` for the local Compose AI service |
| `MAI_API_KEY` | Same local key configured in the AI repository |
| `MEDIA_BUCKET_NAME` | Private development S3 bucket used for browser recording uploads |
| `MEDIA_BUCKET_REGION` | Region of that S3 bucket |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Restricted development credentials with the required bucket access |

The backend S3 client currently uses AWS S3 directly; the Moto instance in the AI Compose stack is for MAI's local output clips and does not replace the browser upload bucket. Configure that private development bucket's browser CORS for `http://localhost:5173` as well.

Run the API from the repository root:

```bash
uvicorn app.main:app --reload
```

Check `http://localhost:8000/health` and `http://localhost:8000/docs`. If you do not want to run MAI locally, use the development MAI URL and key supplied by the project maintainers for `MAI_BASE_URL` and `MAI_API_KEY` instead.

### 5. Configure and start the frontend

From `readright-app/`:

```bash
npm ci
cp .env.example .env.local
```

Set `.env.local`:

```dotenv
VITE_SUPABASE_URL=http://127.0.0.1:54321
VITE_SUPABASE_ANON_KEY=<local-anon-key-from-supabase-status>
VITE_FASTAPI_URL=http://localhost:8000
VITE_USE_V1_API=true
```

`VITE_FASTAPI_URL` is the API origin; the client adds `/v1` to its requests. Start the frontend:

```bash
npm run dev
```

Open `http://localhost:5173`, register a development learner, and allow camera and microphone access. A complete recording requires the development passage/question data and S3 configuration from the previous steps.

## Deployment

The repositories document the following target setup. Their docs do not identify which static frontend host currently serves the live build, so Vercel and Cloudflare Pages are listed as frontend options rather than a verified live-provider choice.

### 1. Supabase

Use a managed Supabase project for Auth and PostgreSQL. Before applying schema changes to the target project, review them:

```bash
supabase link --project-ref <project-ref>
supabase db push --dry-run
supabase db push
```

Configure the learner authentication settings and approved passage/question data in that project. Keep the service-role key on the backend only; the frontend receives only the Supabase anon/publishable key.

### 2. AI service — AWS EC2

The AI repository's deployment guide specifies an AWS EC2 `g5.2xlarge` instance in `ap-southeast-2` (Sydney), running Docker Compose behind Caddy for HTTPS. The API, Redis, and audio/video workers run as separate containers. DNS for `readright-mai.reevsan.dev` points to the instance, with ports 80/443 open for Caddy TLS.

The instance-side startup script reads `MAI_API_KEY` from AWS Systems Manager Parameter Store (default parameter `/readright/mai/api-key`) and starts the production Compose file. The instance role needs permission to read that parameter and access the configured S3 bucket. The documented idle-check script runs every five minutes and stops the instance after 30 minutes without a request; configure EC2 stop behavior accordingly.

Configure the root `.env` with the MAI site address, API key source, `MAI_S3_BUCKET`, and `AWS_REGION`. Set `AWS_REGION` to the actual bucket region. The AI deployment architecture describes a real CrisperWhisper audio worker, but the repository's current Compose stack still uses a fake audio worker; confirm the real audio lane is installed and enabled before treating this as production speech scoring.

### 3. Backend — Render Web Service

The active backend deployment guide targets a Render Web Service using the repository's Dockerfile. Use the repository root as the service root, set `/health` as the health check, and let Render provide `PORT`. The current backend calls MAI directly over HTTPS; the archived Lambda/SQS guide is not the active deployment path.

Set these Render environment variables or secrets:

- `SUPABASE_URL` and server-only `SUPABASE_SERVICE_KEY`
- `BACKEND_API_KEY` for trusted backend-only routes
- `ALLOWED_ORIGINS` as a JSON list containing the deployed frontend origin
- `MAI_BASE_URL=https://readright-mai.reevsan.dev/v1` and the matching server-only `MAI_API_KEY`
- `MEDIA_BUCKET_NAME` and `MEDIA_BUCKET_REGION`
- AWS credentials or an equivalent AWS identity with only the required S3 permissions
- Pipeline/scoring/assignment version settings if they differ from the documented defaults

The backend timeout must allow for MAI's synchronous response window. Keep `MAI_API_KEY`, the Supabase service key, `BACKEND_API_KEY`, and AWS credentials out of browser configuration and source control.

### 4. Frontend — Vercel or Cloudflare Pages

Deploy the Vite app as a static SPA. The repository includes a Vercel rewrite so client-side routes resolve to `index.html`.

| Setting | Value |
|---|---|
| Build command | `npm run build` |
| Output directory | `dist` |
| Node.js | 20+ |

Set the following build-time variables in the hosting dashboard:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_FASTAPI_URL` — HTTPS API origin, without `/v1`
- `VITE_USE_V1_API=true`

After setting the frontend domain, add that exact origin to the backend's `ALLOWED_ORIGINS`. Rebuild the frontend after changing any `VITE_` setting because Vite embeds these values in the static bundle. The frontend's legacy `VITE_API_KEY` setting is not a secret and should not be used as authentication for the v1 learner API; v1 requests use the signed-in learner's Supabase access token.

### 5. Verify the deployed integration

1. Confirm the frontend loads over HTTPS and can sign in through Supabase Auth.
2. Confirm the backend `GET /health` returns healthy and the browser can reach it without a CORS error.
3. Confirm the MAI `GET /health/ready` reports its dependencies ready.
4. Start a test session and verify that S3 accepts the signed browser upload, MAI returns an analysis, and the backend stores the result in Supabase.
5. Check that the dashboard and history pages load the learner's saved sessions.

## Repository deployment references

- [Frontend README and deployment notes](https://github.com/readright-se-sp/readright-app/blob/dev/README.md)
- [AI deployment architecture](https://github.com/readright-se-sp/readright-ai/blob/dev/docs/deployment-architecture.md)
- [AI Compose and instance setup](https://github.com/readright-se-sp/readright-ai/blob/dev/server/README.md)
- [Backend Render deployment](docs/render-deployment.md)
- [Backend database migrations](docs/database-proposal.md)
- [Backend media storage design](docs/media-storage.md)
- [Archived backend Lambda deployment](docs/lambda-deployment.md)
