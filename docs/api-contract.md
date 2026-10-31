# API contracts

The backend exposes health and a learner dashboard. Assessment, media upload,
and comprehension routes below are the next frontend-facing contracts; they
are not implemented yet. ASR and vision are private services described in
[`ai-service-contracts.md`](ai-service-contracts.md).

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
