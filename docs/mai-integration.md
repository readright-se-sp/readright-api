# MAI 1.1.0 integration

The trusted ReadRight backend exposes `POST /v1/mai/analyses`. It accepts the
MAI 1.1.0 request body, records the job, places it on an encrypted SQS queue,
and returns `202 Accepted` with a status URL. A worker calls
`MAI_BASE_URL/analyses` with `X-API-Key`, waits for MAI's synchronous response,
validates it, and stores the result. The caller polls ReadRight for completion.

## Request preconditions

- Send `X-Backend-Key` to authenticate the caller to ReadRight. The MAI key is
  separate and is sent only from Lambda to the MAI service.
- `request_id` must be the UUID of an existing `reading_analyses.analysis_id`.
- That analysis must use a video recording as its source, and its session's
  passage title and content must match the request.
- Use a fresh, unselected analysis with no pre-existing normalized events or
  separate ASR/vision jobs. MAI is the consolidated pipeline for that analysis.
- The `video_url` must be an HTTPS presigned S3 GET URL that MAI can use for at
  least 120 seconds after MAI begins processing. Queue delay comes before that
  window, so use a longer presign lifetime to allow for queueing and retries.
- Create a fresh analysis row for each distinct run. Reusing a completed
  `request_id` returns the stored response without calling MAI again.

The submitted body follows the supplied MAI contract:

```json
{
  "request_id": "3f6c1c7e-9a0d-4a53-8f55-5d2d4f0c8a11",
  "video_url": "https://bucket.s3.ap-southeast-1.amazonaws.com/recordings/abc.webm?X-Amz-Signature=...",
  "passage_title": "Pam's Cat",
  "passage_content": "Pam has a cat. It is on the bed.",
  "output_key_prefix": "analyses/3f6c1c7e-9a0d-4a53-8f55-5d2d4f0c8a11/"
}
```

Accepted response:

```json
{
  "request_id": "3f6c1c7e-9a0d-4a53-8f55-5d2d4f0c8a11",
  "status": "accepted",
  "status_url": "/v1/mai/analyses/3f6c1c7e-9a0d-4a53-8f55-5d2d4f0c8a11"
}
```

Poll the returned URL. It reports `queued`, `running`, `completed` (with the
MAI response in `result`), or `failed` (with an error). If the request was
already completed, submitting the same request ID returns its stored response
directly with status 200.

The worker retries transient MAI errors and transport failures up to three
queue receives. It uses integer `Retry-After` values when available, capped to
the message's remaining one-hour queue retention. After the retry budget is
exhausted, poll reports `failed`; submit the same logical request again with
the same `request_id` and a fresh presigned URL to start a new service-job
attempt.

## Persistence mapping

| MAI field | Supabase storage |
| --- | --- |
| `request_id` | `service_jobs.idempotency_key`; it also identifies `reading_analyses.analysis_id` |
| Full success response | `service_jobs.response_payload` (used for exact idempotent replay) |
| `reading_score`, `wpm` | `reading_analyses.reading_score`, `reading_analyses.wpm`; WPM uses the existing two-decimal database precision, while the complete MAI response is retained in `service_jobs.response_payload` |
| Six behavior booleans | One `behavior_observations` row per behavior, with `detected` or `not_detected` |
| `actual_phrase`, `spoken_phrase` | `reading_events.actual_phrase`, `reading_events.spoken_phrase`; `spoken_phrase` is also copied to the legacy `heard_text` field |
| `actual_phoneme`, `spoken_phoneme` | Exact ordered arrays in `reading_events.actual_phonemes`, `reading_events.spoken_phonemes` |
| `read_start`, `read_end` | Exact millisecond values in `read_start_ms`/`read_end_ms`, plus normalized seconds in `audio_start_seconds`/`audio_end_seconds` |
| `audio_object_key` | `reading_events.audio_object_key`; ReadRight stores the key and does not fetch the object |
| `miscue_type` | `reading_events.detected_type`; `self-correction` becomes enum value `self_correction` |

Expected passage token IDs and phoneme alignment rows are not invented because
the MAI response does not include token IDs or phoneme alignment positions. The
exact phoneme arrays and complete response remain available for later alignment
work. Presigned video URLs are excluded from request hashes and are never
written to database tables or application logs. A URL is present in the SQS
message body while the job waits or runs; SQS server-side encryption is enabled
and message retention is one hour. Queue access is limited to the API and worker
Lambda roles. Use a URL lifetime that covers possible queue delay plus MAI's
120-second processing window.

MAI has no response fields for transcript, word-recognition percentage,
confidence, pipeline version, or scoring-policy version. Those existing
analysis fields are not fabricated. The MAI score range is also left
unconstrained until its scale is finalized.

## Background processing and timeouts

The API Gateway request only validates, records, and queues the request, so it
returns before the API Gateway timeout. The SQS worker has a 150-second Lambda
timeout and a 125-second MAI read timeout. SQS visibility is 900 seconds, six
times the worker timeout, and a dead-letter queue captures repeated
infrastructure or message-processing failures. Worker concurrency is capped at
five. Queue messages are processed at least once; database claims and MAI
idempotency prevent duplicate results.

Use the SAM `ApiUrl` for submission and polling. Both routes require
`X-Backend-Key`.

## Configuration

Set these Lambda values through the SAM deployment parameters:

- `MaiBaseUrl`: defaults to `https://readright-mai.reevsan.dev/v1`.
- `MaiApiKey`: the MAI service's `X-API-Key` credential. The SAM parameter is
  marked `NoEcho`; do not place the value in chat, source control, or a saved
  `samconfig.toml`. It is configured only on the worker Lambda.

The database migration must be applied to the intended Supabase project before
this route is used. Review `database-proposal.md` for the migration workflow.
