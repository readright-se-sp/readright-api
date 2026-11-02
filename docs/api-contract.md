# API contracts

The backend exposes health, a learner dashboard, learner-facing reading and
comprehension routes, and CRUD routes for the application tables. CRUD routes
use the Supabase service key and are protected by a separate backend key; never
call them from browser code.
AI inference remains in external services. ReadRight queues MAI requests and
polls for results; the worker calls the MAI service synchronously. This flow is
documented in [`mai-integration.md`](mai-integration.md); the proposed ASR/CV
boundaries are in [`ai-service-contracts.md`](ai-service-contracts.md).

## Implemented routes

### `GET /health`

Unauthenticated liveness check:

```json
{ "status": "ok" }
```

### `GET /v1/dashboard`

Send the signed-in user's Supabase access token:

```http
Authorization: Bearer <access-token>
```

The backend verifies the token with Supabase Auth and uses its user ID to find
the learner profile. The response contains aggregate reading progress and the
learner's full session history in chronological order. It never accepts a
learner ID from the browser.

```json
{
  "learner": {
    "user_id": "4b255bc3-46da-4f8f-9a7d-1ef91cc5532d",
    "display_name": "Maya",
    "grade_id": 4,
    "grade_label": "Grade 4"
  },
  "summary": {
    "sessions_total": 8,
    "sessions_completed": 6,
    "sessions_in_progress": 2,
    "average_wpm": 85.5,
    "average_word_recognition_pct": 92.3
  },
  "sessions": [
    {
      "session_id": "b4e706a3-f90c-4322-a67a-2d15e8547458",
      "status": "completed",
      "assigned_at": "2026-10-31T09:00:00Z",
      "completed_at": "2026-10-31T09:03:00Z",
      "passage_id": "4ca3f2d0-7f6c-4caf-a45e-1c23a0e42656",
      "passage_title": "A Day at the River",
      "language_code": "en",
      "wpm": 85.5,
      "word_recognition_pct": 92.3,
      "reading_level": "Instructional",
      "correct": 42,
      "mispronunciation": 1,
      "substitution": 2,
      "omission": 0,
      "insertion": 0,
      "repetition": 1,
      "refusal_to_pronounce": 0,
      "finger_pointing": false,
      "loss_of_place": false,
      "monotone_reading": false,
      "word_by_word_reading": true,
      "inaudible_reading": false
    }
  ]
}
```

Each `sessions` item is flat and includes passage details, reading scores,
miscue counts, and behavioral flags. The list includes all sessions, ordered
oldest first by `assigned_at`. Scores are `null` when unavailable; miscue
counts are `null` until a selected analysis is completed or partial, and
behavior flags are `null` when unavailable or not assessable. Average scores
include completed selected analyses only. The first valid Bearer request
creates a missing learner row from `grade_level` and `display_name` in Supabase
user metadata. Errors: `401` for a missing/invalid token, `422` when
new-account metadata has no configured grade, and `503` when Supabase is
unavailable.

### `POST /v1/mai/analyses`

This trusted-backend route accepts the MAI 1.1.0 `AnalysisRequest`, places it
on the SQS work queue, and returns `202` with a `status_url`. The worker calls
MAI synchronously, saves the response and normalized fields, and the caller
polls `GET /v1/mai/analyses/{request_id}`. It requires `X-Backend-Key`. The
request ID must identify an existing video-backed reading analysis, and the
passage must match that analysis's session. See the
[MAI integration guide](mai-integration.md) for idempotency, field mapping,
errors, and configuration.

### Full-table backend CRUD

Configure a strong `BACKEND_API_KEY` in the backend environment and send it as
`X-Backend-Key`. This credential is for trusted server-side callers and must
never be shipped to the frontend. These routes are unavailable with `503` until
the key is configured. The database connection is privileged; there is no
staff-role model, so these routes are for trusted backend callers, not learners.

Each collection supports `GET` (paginated list), `POST` (create),
`GET /{record_id}`, `PATCH /{record_id}`, and `DELETE /{record_id}`. List
requests accept `limit` (1–500, default 100) and `offset` (default 0), and
return `{ "items": [], "limit": 100, "offset": 0, "total": 0 }`. Create and
update bodies are typed in OpenAPI and reject unknown fields. Database defaults
are used for generated IDs and timestamps.

| Collection | Create fields | Update fields |
| --- | --- | --- |
| `/v1/identity/grade-levels` | `grade_id`, `label`, `sequence` (all required) | `label`, `sequence` |
| `/v1/identity/learners` | `user_id`, `current_grade_id` (required), `display_name` | `current_grade_id`, `display_name` |
| `/v1/content/passages` | `title`, `difficulty_grade_id`, `language_code`, `content` (required), `status`, `published_at` | `title`, `difficulty_grade_id`, `language_code`, `content`, `status`, `published_at` |
| `/v1/content/passage-tokens` | `passage_id`, `position`, `token_text` (required), `is_proper_noun` | `position`, `token_text`, `is_proper_noun` |
| `/v1/content/comprehension-questions` | `passage_id`, `question_order`, `prompt` (required), `points_possible` | `question_order`, `prompt`, `points_possible` |
| `/v1/content/question-choices` | `question_id`, `choice_order`, `choice_text` (required), `is_correct` | `choice_order`, `choice_text`, `is_correct` |
| `/v1/reading/sessions` | `learner_id`, `grade_at_assessment_id`, `passage_id`, `assignment_policy_version` (required), `status` | `status`, `session_timestamp`, `completed_at` |
| `/v1/reading/recordings` | `session_id`, `kind`, `storage_bucket`, `storage_path`, `content_type` (required), `derived_from_recording_id`, `size_bytes`, `sha256`, `duration_seconds` | `content_type`, `size_bytes`, `sha256`, `duration_seconds` |
| `/v1/reading/reading-analyses` | `session_id`, `source_recording_id`, `run_number`, `pipeline_version`, `scoring_policy_version` (required); `status`, `is_selected`, `transcript`, `reading_duration_seconds`, `wpm`, `reading_score`, `word_recognition_pct`, `reading_level`, `failure_code`, `finished_at` | `status`, `is_selected`, transcript, duration, scores, level, failure and finish fields |
| `/v1/reading/reading-events` | `analysis_id`, `event_order`, `detected_type` (required); `source_service_job_id`, expected token IDs, `heard_text`, MAI phrases/phoneme arrays/millisecond offsets/object key, audio times, `confidence` | `reviewed_type`, `reviewer_id`, `reviewed_at`, `review_note` |
| `/v1/reading/behavior-observations` | `analysis_id`, `source_service_job_id`, `type`, `outcome` (required), `confidence`, `evidence_note` | `outcome`, `confidence`, `evidence_note` |
| `/v1/reading/phoneme-events` | `analysis_id`, `reading_event_id`, `source_service_job_id`, `alignment_position`, `notation`, `outcome` (required); expected/actual phoneme, audio times, `confidence` | expected/actual phoneme, notation, outcome, audio times and confidence |
| `/v1/services/jobs` | `session_id`, `analysis_id`, `input_recording_id`, `kind` (`asr`, `vision`, `prosody`, `pronunciation`, `mai`), `service_name`, `attempt_number`, `required_for_completion`, `request_schema_version`, `request_sha256` (required); status, current flag, external ID, result/model versions, response, failure and timing fields | current flag, status, external ID, result/model versions, response, failure and timing fields |
| `/v1/comprehension/attempts` | `session_id`, `attempt_number` (required); `status`, `submitted_at`, scores | `status`, `submitted_at`, `score_earned`, `score_possible` |
| `/v1/comprehension/answers` | `attempt_id`, `question_id` (required), `selected_choice_id`, `answered_at` | `selected_choice_id`, `answered_at` |

The database enforces foreign keys, publication immutability, scoring ranges,
and attempt/answer state rules. These constraints can return `409` for related
record conflicts or `422` for invalid values; missing rows return `404`.
`auth.users` is managed through Supabase Auth, not table CRUD. The dashboard
summary view is read-only and remains available through `GET /v1/dashboard`.
Recording CRUD manages database metadata only; media bytes must be uploaded or
removed through Supabase Storage separately.

## Learner-facing reading and comprehension routes

These routes use `Authorization: Bearer <Supabase access token>`. The backend
verifies the token, ensures the learner profile exists, and scopes every query
to that user ID. The browser never calls the `X-Backend-Key` CRUD routes.

### Assign and upload a passage

`POST /v1/me/sessions` accepts `{ "passage_grade_id": 4 }`; the field may be
omitted to use the learner's current grade. An existing assigned session for
that passage grade is returned idempotently. Otherwise the backend assigns a
published passage the learner has not read when one is available. The response
uses frontend names: `session_id`, then `passage.id`, `passage.title`,
`passage.text`, and `passage.wordCount`.

`POST /v1/me/sessions/{session_id}/upload-url` accepts the browser's exact
`content_type`, including codec parameters, and returns `storage_key`, an S3
presigned POST (`upload.url` and `upload.fields`), and `expires_at`. The signed
policy allows 1 byte through 150 MiB by default. Upload the `file` field last;
do not send the Bearer token to S3.

`POST /v1/me/sessions/{session_id}/recording` accepts `storage_key`,
`content_type`, `size_bytes`, and whole `duration_seconds`. The backend checks
that the object exists and its metadata matches, moves the session to
`processing`, backdates `session_timestamp` by the reading duration, and sends
the analysis request with a one-hour presigned GET URL. It returns `202` and
does not create recording or analysis rows itself.

### Poll and read results

`GET /v1/me/sessions/{session_id}` returns `status`, `analysis_status`, and
`comprehension_status`. A processing session with no analysis row reports
`analysis_status: "running"`. The scheduled timeout sweep marks processing
work older than ten minutes failed only if no completed or partial analysis
exists.

`GET /v1/me/sessions/{session_id}/result` returns a flat result with capitalized
`reading_level`, comprehension level `1`–`3` or `null`, top-level miscue
counts, `miscue_details` grouped by type, and nullable reading habits. It only
returns a selected analysis whose status is `completed` or `partial`.
Each `miscue_details` item's `said` value is nullable when no heard text is
stored. The current MAI contract requires `spoken_phrase` to be a string, so
valid MAI responses may use an empty string for an omission but cannot send
`null`; other stored events can still have `said: null`. Clients should use a
fallback for both `null` and blank strings.

### Comprehension

`GET /v1/me/sessions/{session_id}/questions` returns questions and ordered
options, never `is_correct`. `POST /v1/me/sessions/{session_id}/comprehension`
accepts one answer per question. `choice` is a zero-based option position,
`"idk"`, or `null`. The backend stores `"idk"` and blank choices as
`selected_choice_id: null`; both earn zero but remain in `score_possible`.

The score bands are 80% and above → level 3; 59% to below 80% → level 2; below
59% → level 1. `SCORING_POLICY_VERSION` defaults to `phil-iri-v1` in runtime
configuration and SAM parameters and is sent to the analysis service.

The root [`openapi.json`](../openapi.json) is the generated OpenAPI catalogue
for the registered routes and frontend response models.

## Client rules

- Never ship the Supabase service key or AI service credentials to a client.
- Treat session, analysis, recording, and job IDs as opaque identifiers.
- Render status from API responses; do not infer it from elapsed time.
- Keep service payloads and model-specific fields behind the backend boundary.
