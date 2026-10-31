# Frontend API and payload proposals

This document separates the endpoint implemented by this repository from a
possible frontend contract for the service-oriented design. Proposed `/v1`
routes below are examples for discussion; they are not currently registered by
the FastAPI application.

## Implemented endpoint

### `POST /analyze`

Synchronous multipart upload. The API key is intended for trusted callers; a
static `X-API-Key` must not be embedded in a browser or mobile application.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `file` | binary | yes | Audio or video recording supported by FFmpeg |
| `passage_id` | string | yes | Existing passage identifier |
| `learner_id` | string | no | Blank skips the current session insert |
| `X-API-Key` | header | yes | Matches backend `API_KEY` setting |

The current multipart fields are `file`, `passage_id`, and optional
`learner_id`. A trusted server-side caller may send them with the required
`X-API-Key`. This endpoint is not a safe direct browser integration because it
uses a reusable static key. The proposed browser flow is documented below.

Implemented `200` response (`AssessmentResult`):

```json
{
  "wpm": 85.5,
  "word_recognition_pct": 92.3,
  "reading_level": "Instructional",
  "correct": 48,
  "mispronunciation": 2,
  "substitution": 1,
  "omission": 1,
  "insertion": 0,
  "repetition": 1,
  "finger_pointing": false,
  "loss_of_place": false,
  "monotone_reading": false,
  "word_by_word_reading": false,
  "inaudible_reading": false,
  "db_save_failed": false
}
```

The current response contains aggregate counts and behavior flags. It does not
include per-word `reading_events`, phoneme alignments, comprehension data, or
session/analysis IDs.

Error responses from `POST /analyze`:

| Status | Current body |
|---|---|
| `401` | `{"detail":"Invalid API key"}` |
| `413` | `{"error":"...","code":"FILE_TOO_LARGE"}` |
| `503` | `{"error":"...","code":"BUSY"}` |
| `500` | `{"error":"...","code":"EXTRACTION_FAILED"}` or `ANALYSIS_FAILED` or `CONSOLIDATION_FAILED` |

### `GET /health`

Unauthenticated liveness endpoint. The current response is `{"status":"ok"}`.

## Proposed frontend flow

Use the backend as the single public API. The frontend authenticates with the
application's user token; the backend derives `learner_id` from that identity.
The browser gets a temporary object-storage upload URL from the backend, sends
the recording directly to private storage, then asks the backend to start
analysis. The ASR and CV services remain private and are never called from the
frontend.

The route names and bodies below are illustrative. Choose and version them
before implementation.

### 1. List passages and start an assigned session

`GET /v1/passages?grade_id=4&language_code=en`

Return only learner-safe content. Do not include internal publication fields or
answer keys.

`POST /v1/sessions`

```json
{
  "passage_id": "4ca3f2d0-7f6c-4caf-a45e-1c23a0e42656"
}
```

The authenticated user determines the learner. The server captures the
learner's grade and assignment-policy version at assignment time.

```json
{
  "session_id": "b4e706a3-f90c-4322-a67a-2d15e8547458",
  "status": "assigned",
  "passage": {
    "passage_id": "4ca3f2d0-7f6c-4caf-a45e-1c23a0e42656",
    "title": "A Day at the River",
    "language_code": "en",
    "content": "...",
    "tokens": [
      { "position": 1, "text": "Maya", "is_proper_noun": true },
      { "position": 2, "text": "walked", "is_proper_noun": false }
    ]
  },
  "created_at": "2026-10-31T09:00:00Z"
}
```

### 2. Request a recording upload target

`POST /v1/sessions/{session_id}/recordings`

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

The URL is temporary and must not be saved in the database or logs. The backend
stores only the private bucket/path and metadata.

### 3. Upload, then submit for analysis

The frontend `PUT`s the bytes to the returned URL. After storage confirms the
upload, it calls `POST /v1/sessions/{session_id}/submit`:

```json
{
  "recording_id": "065afbf2-a933-4f52-a5a5-e90f21e21a0a"
}
```

The backend verifies ownership and object existence, creates an analysis and
service jobs, then returns promptly:

```json
{
  "session_id": "b4e706a3-f90c-4322-a67a-2d15e8547458",
  "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
  "status": "processing",
  "status_url": "/v1/sessions/b4e706a3-f90c-4322-a67a-2d15e8547458"
}
```

For a video upload, the backend must make both inputs available: the original
video for CV and extracted audio for ASR. The proposal assumes the extracted
audio is stored as a private audio object; the database model still needs a
clear link from that derivative back to its source video.

### 4. Poll session and read the result

`GET /v1/sessions/{session_id}` returns one of the session lifecycle states
(`assigned`, `reading`, `processing`, `comprehension`, `completed`, `failed`)
and the selected analysis when available. A processing response can include
service status without exposing internal signed URLs:

```json
{
  "session_id": "b4e706a3-f90c-4322-a67a-2d15e8547458",
  "status": "processing",
  "analysis": {
    "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
    "status": "partial",
    "services": {
      "asr": "completed",
      "vision": "running"
    }
  }
}
```

On completion, `GET /v1/sessions/{session_id}/results` returns normalized
reporting data. Example (field names are proposed):

```json
{
  "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
  "status": "completed",
  "transcript": "Maya walked the river.",
  "scores": {
    "wpm": 85.5,
    "word_recognition_pct": 92.3,
    "reading_level": "Instructional"
  },
  "miscue_counts": {
    "correct": 4,
    "mispronunciation": 0,
    "substitution": 0,
    "omission": 1,
    "insertion": 0,
    "repetition": 0
  },
  "behaviors": [
    { "type": "finger_pointing", "outcome": "detected", "confidence": 0.91 },
    { "type": "loss_of_place", "outcome": "not_detected", "confidence": 0.86 }
  ],
  "events": [
    {
      "event_order": 1,
      "detected_type": "omission",
      "expected_start_position": 3,
      "expected_end_position": 3,
      "heard_text": null,
      "audio_start_seconds": null,
      "audio_end_seconds": null,
      "confidence": 0.78
    }
  ]
}
```

`not_assessable` must remain distinct from `not_detected`. Do not turn missing or
low-quality evidence into a negative behavior result.

### 5. Comprehension, when enabled

`GET /v1/sessions/{session_id}/comprehension` returns prompts and choices. The
learner payload must never include `is_correct`:

```json
{
  "attempt_id": "21d37e7c-882f-41e6-b514-8eb818840d7f",
  "status": "in_progress",
  "questions": [
    {
      "question_id": "39d62932-0418-4e33-a0dc-11ba6bcfc8a1",
      "question_order": 1,
      "prompt": "Where did Maya go?",
      "points_possible": 1,
      "choices": [
        { "choice_id": "11111111-1111-4111-8111-111111111111", "choice_order": 1, "text": "To the river" },
        { "choice_id": "22222222-2222-4222-8222-222222222222", "choice_order": 2, "text": "To the market" }
      ]
    }
  ]
}
```

Submit answers with `PUT /v1/comprehension-attempts/{attempt_id}/answers`:

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

The server validates that each choice belongs to its question and that the
attempt belongs to the authenticated learner. Freeze answers after submission.

## Frontend integration rules

- Send a user access token to the backend; never ship the Supabase service key,
  AI service credentials, or a reusable backend API key to clients.
- Treat `session_id` and `analysis_id` as opaque identifiers.
- Upload media to private storage using the one-use/short-lived target; do not
  proxy large video bodies through the frontend application server unless that
  is an intentional deployment choice.
- Render service/analysis status from backend responses. Do not infer completion
  from a fixed delay.
- The current endpoint is synchronous; the proposed session flow is
  asynchronous. They should not be presented as the same API version.
