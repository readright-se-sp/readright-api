# MAI 1.1.0 integration

The trusted ReadRight backend exposes `POST /v1/mai/analyses`. It accepts the
MAI 1.1.0 request body, calls `MAI_BASE_URL/analyses` with `X-API-Key`, waits for
the synchronous response, validates it, and stores the result before returning
the same result to the caller.

## Request preconditions

- Send `X-Backend-Key` to authenticate the caller to ReadRight. The MAI key is
  separate and is sent only from Lambda to the MAI service.
- `request_id` must be the UUID of an existing `reading_analyses.analysis_id`.
- That analysis must use a video recording as its source, and its session's
  passage title and content must match the request.
- Use a fresh, unselected analysis with no pre-existing normalized events or
  separate ASR/vision jobs. MAI is the consolidated pipeline for that analysis.
- The `video_url` must be an HTTPS presigned S3 GET URL that MAI can use for at
  least 120 seconds. The caller must refresh an expired URL before retrying.
- Create a fresh analysis row for each distinct run. Reusing a completed
  `request_id` returns the stored response without calling MAI again.

The request follows the supplied MAI contract:

```json
{
  "request_id": "3f6c1c7e-9a0d-4a53-8f55-5d2d4f0c8a11",
  "video_url": "https://bucket.s3.ap-southeast-1.amazonaws.com/recordings/abc.webm?X-Amz-Signature=...",
  "passage_title": "Pam's Cat",
  "passage_content": "Pam has a cat. It is on the bed.",
  "output_key_prefix": "analyses/3f6c1c7e-9a0d-4a53-8f55-5d2d4f0c8a11/"
}
```

## Persistence mapping

| MAI field | Supabase storage |
| --- | --- |
| `request_id` | `service_jobs.idempotency_key`; it also identifies `reading_analyses.analysis_id` |
| Full success response | `service_jobs.response_payload` (used for exact idempotent replay) |
| `reading_score`, `wpm` | `reading_analyses.reading_score`, `reading_analyses.wpm` |
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
written to tables or application logs.

MAI has no response fields for transcript, word-recognition percentage,
confidence, pipeline version, or scoring-policy version. Those existing
analysis fields are not fabricated. The MAI score range is also left
unconstrained until its scale is finalized.

## Timeouts and AWS endpoint

The MAI read timeout is 125 seconds, matching the contract's suggested client
timeout. Lambda is configured for 150 seconds. API Gateway HTTP APIs have a
non-increasable 30-second integration timeout, so a request through `ApiUrl`
will not reliably receive the complete MAI response. Call this route through
the SAM output named `SynchronousApiUrl`, appending `/v1/mai/analyses` instead.
That is the Lambda Function URL; this route still requires `X-Backend-Key`.

If MAI returns an error, ReadRight forwards its status and error body and marks
the job failed or timed out. A repeated request while a job is active returns
409 `REQUEST_IN_PROGRESS`. If a prior call timed out, retry with the same
`request_id`; MAI's idempotency behavior can return its completed result.

## Configuration

Set these Lambda values through the SAM deployment parameters:

- `MaiBaseUrl`: defaults to `https://readright-mai.reevsan.dev/v1`.
- `MaiApiKey`: the MAI service's `X-API-Key` credential. The SAM parameter is
  marked `NoEcho`; do not place the value in chat, source control, or a saved
  `samconfig.toml`.

The database migration must be applied to the intended Supabase project before
this route is used. Review `database-proposal.md` for the migration workflow.
