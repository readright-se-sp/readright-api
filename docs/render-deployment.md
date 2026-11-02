# Deploying on Render

Create a Render **Web Service** from this repository and select the **Docker**
runtime. Leave **Root Directory** blank so Render finds the root `Dockerfile`
and `requirements.txt`. Set the health check path to `/health` if Render asks
for one. The container listens on Render's `PORT` value (default `10000`).

## Environment variables

Set these for the API and database-backed routes:

- `SUPABASE_URL`: the Supabase project URL.
- `SUPABASE_SERVICE_KEY`: the server-only service role key.
- `ALLOWED_ORIGINS`: JSON array of browser origins, for example
  `["https://readright.example.com"]`.

Set `BACKEND_API_KEY` to a long random secret for trusted backend callers of
the CRUD and MAI routes. Learner routes authenticate with Supabase Bearer tokens.

Set these to enable the learner reading flow and trusted MAI analysis route:

- `MAI_API_KEY`: MAI's `X-API-Key` credential. Store it as a Render secret.
- `MAI_BASE_URL`: optional; defaults to
  `https://readright-mai.reevsan.dev/v1`.
- `MAI_CONNECT_TIMEOUT_SECONDS`: optional; defaults to `5`.
- `MAI_READ_TIMEOUT_SECONDS`: optional; defaults to `125`.

The learner recording flow and trusted MAI route both call MAI through
`MAI_BASE_URL/analyses` and store results in Supabase. No separate
`AI_ANALYSIS_URL`, SQS, or Lambda is used. Render supports HTTP responses of up
to 100 minutes ([Render docs](https://render.com/docs/render-vs-vercel-comparison));
the request caller should allow enough time for MAI's response.

For learner recording uploads to S3, also set:

- `MEDIA_BUCKET_NAME`: the private S3 bucket name.
- `MEDIA_BUCKET_REGION`: the bucket's AWS Region, default `ap-southeast-1`.
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: credentials for an AWS
  identity scoped to the required bucket operations.

Render supplies `PORT` automatically. Do not add `PORT`, `MAI_QUEUE_URL`, or
SQS credentials for the direct MAI route.
