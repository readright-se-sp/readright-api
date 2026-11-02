# MAI 1.1.0 integration

The trusted ReadRight backend exposes `POST /v1/mai/analyses`. It accepts the
MAI 1.1.0 request body, creates or claims its `service_jobs` row, calls
`MAI_BASE_URL/analyses` with `X-API-Key`, validates the response, and saves the
result to Supabase before returning it. Processing is synchronous; no queue or
separate worker is involved.

The learner-facing recording route uses the same MAI client and persistence
workflow directly. It creates the video recording and unselected analysis row,
then submits that analysis ID as `request_id`; successful completion selects
the result for `/result` and the learner dashboard. No intermediate AI service
URL is configured.

## Request preconditions

- Send `X-Backend-Key` to authenticate the caller to ReadRight. The server-side
  `MAI_API_KEY` is sent from the Render API service to MAI.
- `request_id` must be the UUID of an existing `reading_analyses.analysis_id`.
- That analysis must use a video recording as its source, and its session's
  passage title and content must match the request.
- Use a fresh, unselected analysis with no pre-existing normalized events or
  separate ASR/vision jobs. MAI is the consolidated pipeline for that analysis.
- The `video_url` must be an HTTPS presigned S3 GET URL that MAI can use for at
  least 120 seconds after the request is submitted. MAI starts directly from
  the API call, so there is no queue delay.
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

The normal response is `200` with MAI's validated result. A successful response
contains `request_id`, `reading_score`, `wpm`, the six behavior flags, and
`miscues`. If the same request is already running, ReadRight returns `202` with
a `status_url`; poll that URL for `queued`, `running`, `completed` (with the MAI
response in `result`), or `failed`. Submitting an already completed request ID returns
its stored response without calling MAI again.

MAI or transport failures are persisted to the job and returned to the caller.
To retry a failed request, submit it again with the same `request_id` and a
fresh presigned URL. The existing service-job row advances its
`attempt_number`; successful results remain idempotently replayable.

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
written to database tables or application logs. The URL is sent directly to
MAI for the active request and is not queued or persisted.

MAI has no response fields for transcript, word-recognition percentage,
confidence, pipeline version, or scoring-policy version. Those existing
analysis fields are not fabricated. The MAI score range is also left
unconstrained until its scale is finalized.

## Request and timeout behavior

The API waits for MAI and persists the validated response before returning.
`MAI_READ_TIMEOUT_SECONDS` defaults to 125 seconds. The database claim prevents
two simultaneous requests with the same ID from processing the same analysis;
a duplicate receives `202` and can poll the status URL.

Both submission and status routes require `X-Backend-Key`.

## Configuration

Configure these values on the Render API service:

- `MAI_BASE_URL`: defaults to `https://readright-mai.reevsan.dev/v1`.
- `MAI_API_KEY`: the MAI service's `X-API-Key` credential. Keep it private and
  store it as a Render secret.
- `MAI_CONNECT_TIMEOUT_SECONDS`: defaults to `5`.
- `MAI_READ_TIMEOUT_SECONDS`: defaults to `125`.

The database migration must be applied to the intended Supabase project before
this route is used. Review `database-proposal.md` for the migration workflow.
