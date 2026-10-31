# API contracts

The backend exposes health, a learner dashboard, and CRUD routes for the
application tables. These routes use the Supabase service key and are protected
by a separate backend key; never call them from browser code.
AI inference remains outside this API. See [`ai-service-contracts.md`](ai-service-contracts.md)
for the private service boundaries.

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
the learner profile. The response contains aggregate reading progress and up
to ten latest sessions. It never accepts a learner ID from the browser.

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
  "recent_sessions": [
    {
      "session_id": "b4e706a3-f90c-4322-a67a-2d15e8547458",
      "status": "completed",
      "assigned_at": "2026-10-31T09:00:00Z",
      "completed_at": "2026-10-31T09:03:00Z",
      "passage": {
        "passage_id": "4ca3f2d0-7f6c-4caf-a45e-1c23a0e42656",
        "title": "A Day at the River",
        "language_code": "en"
      },
      "reading": {
        "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
        "status": "completed",
        "wpm": 85.5,
        "word_recognition_pct": 92.3,
        "reading_level": "Instructional"
      }
    }
  ]
}
```

`reading` is `null` until a selected analysis exists. Average scores include
completed selected analyses only. Errors: `401` for a missing/invalid token,
`404` when the authenticated user has no learner profile, and `503` when
Supabase is unavailable or not configured.

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
| `/v1/reading/sessions` | `learner_id`, `grade_at_assessment_id`, `passage_id`, `assignment_policy_version` (required), `status` | `status`, `reading_started_at`, `completed_at` |
| `/v1/reading/recordings` | `session_id`, `kind`, `storage_bucket`, `storage_path`, `content_type` (required), `derived_from_recording_id`, `size_bytes`, `sha256`, `duration_seconds` | `content_type`, `size_bytes`, `sha256`, `duration_seconds` |
| `/v1/reading/reading-analyses` | `session_id`, `source_recording_id`, `run_number`, `pipeline_version`, `scoring_policy_version` (required); `status`, `is_selected`, `transcript`, `reading_duration_seconds`, `wpm`, `word_recognition_pct`, `reading_level`, `failure_code`, `finished_at` | `status`, `is_selected`, transcript, duration, scores, level, failure and finish fields |
| `/v1/reading/reading-events` | `analysis_id`, `event_order`, `detected_type` (required); `source_service_job_id`, expected token IDs, `heard_text`, audio times, `confidence` | `reviewed_type`, `reviewer_id`, `reviewed_at`, `review_note` |
| `/v1/reading/behavior-observations` | `analysis_id`, `source_service_job_id`, `type`, `outcome` (required), `confidence`, `evidence_note` | `outcome`, `confidence`, `evidence_note` |
| `/v1/reading/phoneme-events` | `analysis_id`, `reading_event_id`, `source_service_job_id`, `alignment_position`, `notation`, `outcome` (required); expected/actual phoneme, audio times, `confidence` | expected/actual phoneme, notation, outcome, audio times and confidence |
| `/v1/services/jobs` | `session_id`, `analysis_id`, `input_recording_id`, `kind`, `service_name`, `attempt_number`, `required_for_completion`, `request_schema_version`, `request_sha256` (required); status, current flag, external ID, result/model versions, response, failure and timing fields | current flag, status, external ID, result/model versions, response, failure and timing fields |
| `/v1/comprehension/attempts` | `session_id`, `attempt_number` (required); `status`, `submitted_at`, scores | `status`, `submitted_at`, `score_earned`, `score_possible` |
| `/v1/comprehension/answers` | `attempt_id`, `question_id` (required), `selected_choice_id`, `answered_at` | `selected_choice_id`, `answered_at` |

The database enforces foreign keys, publication immutability, scoring ranges,
and attempt/answer state rules. These constraints can return `409` for related
record conflicts or `422` for invalid values; missing rows return `404`.
`auth.users` is managed through Supabase Auth, not table CRUD. The dashboard
summary view is read-only and remains available through `GET /v1/dashboard`.
Recording CRUD manages database metadata only; media bytes must be uploaded or
removed through Supabase Storage separately.

## Proposed learner flow

These routes are a starting contract and are not registered in FastAPI.

### Assign a passage

`GET /v1/passages?grade_id=4&language_code=en` returns published learner-safe
passage data. It must omit internal fields and answer keys.

`POST /v1/sessions` body:

```json
{ "passage_id": "4ca3f2d0-7f6c-4caf-a45e-1c23a0e42656" }
```

The backend derives the learner from the token and snapshots grade and policy.

### Request an upload target

`POST /v1/sessions/{session_id}/recordings` body:

```json
{
  "kind": "video",
  "file_name": "reading.webm",
  "content_type": "video/webm",
  "size_bytes": 18432000,
  "duration_seconds": 74.2,
  "sha256": "optional-lowercase-hex-digest"
}
```

Example response:

```json
{
  "recording_id": "065afbf2-a933-4f52-a5a5-e90f21e21a0a",
  "upload": {
    "method": "PUT",
    "url": "https://storage.example/upload/<short-lived-token>",
    "headers": { "Content-Type": "video/webm" },
    "expires_at": "2026-10-31T09:10:00Z"
  },
  "max_size_bytes": 157286400
}
```

Upload bytes directly to private object storage. The URL is temporary; store
only the bucket and object path. A video produces a video input for vision and
an audio derivative for ASR. The backend records the derivative's source link.

### Submit and poll

After upload, `POST /v1/sessions/{session_id}/submit` accepts:

```json
{ "recording_id": "065afbf2-a933-4f52-a5a5-e90f21e21a0a" }
```

It should enqueue analysis and return promptly:

```json
{
  "session_id": "b4e706a3-f90c-4322-a67a-2d15e8547458",
  "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
  "status": "processing",
  "status_url": "/v1/sessions/b4e706a3-f90c-4322-a67a-2d15e8547458"
}
```

`GET /v1/sessions/{session_id}` returns lifecycle state and service progress.
`GET /v1/sessions/{session_id}/results` returns selected scores, normalized
reading events, and behavior observations. The frontend must not call ASR or
vision services directly or infer completion from a fixed delay.

### Comprehension

`GET /v1/sessions/{session_id}/comprehension` returns questions and choices,
never `is_correct`. `PUT /v1/comprehension-attempts/{attempt_id}/answers` body:

```json
{
  "answers": [
    {
      "question_id": "39d62932-0418-4e33-a0dc-11ba6bcfc8a1",
      "selected_choice_id": "11111111-1111-4111-8111-111111111111"
    }
  ]
}
```

The backend validates attempt ownership and choice/question membership, grades
server-side, and freezes answers after submission.

## Client rules

- Never ship the Supabase service key or AI service credentials to a client.
- Treat session, analysis, recording, and job IDs as opaque identifiers.
- Render status from API responses; do not infer it from elapsed time.
- Keep service payloads and model-specific fields behind the backend boundary.
