# AI service contracts (proposal)

ASR and MediaPipe CV are separate private services. These versioned payloads
propose their integration contract; this backend has no clients or local
inference implementations. See
[architecture](../ARCHITECTURE.md).

## Boundary and ownership

| Component | Input | Output owned by component |
|---|---|---|
| ASR service | Audio, language hint, optional reference passage/tokens | Transcript and timed recognized words |
| CV service | Video, requested behavior checks | Behavior observations and assessability |
| ReadRight backend | Session, passage tokens, all service results | Miscue events, scores, analysis/session state, persistence, frontend response |

This keeps the model services replaceable and prevents frontend/database
contracts from depending on WhisperX or MediaPipe-specific response formats.
The backend validates service results and maps them into stable domain records.

## Dispatch envelope

The backend creates a `service_jobs` row and an outbox/queue message. A worker
may receive the message directly or through a private job endpoint; transport is
intentionally undecided. A newly scheduled attempt has a new job ID,
idempotency key, and incremented attempt number. Redelivery of the same attempt
reuses its job ID and idempotency key.

```json
{
  "request_schema_version": "1.0",
  "service_job_id": "2c44240b-4f16-4a94-b3bf-6e686150a13d",
  "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
  "kind": "asr",
  "attempt_number": 1,
  "idempotency_key": "0bf50cd4-4b7b-46d7-bae4-6a09a7120179",
  "deadline_at": "2026-10-31T09:20:00Z",
  "input": {
    "media": {
      "read_url": "https://storage.example/private/<short-lived-token>",
      "media_type": "audio/wav",
      "sha256": "64-lowercase-hex-characters",
      "duration_seconds": 74.2
    },
    "language_code": "en-PH",
    "reference": {
      "passage_id": "4ca3f2d0-7f6c-4caf-a45e-1c23a0e42656",
      "text": "Maya walked to the river.",
      "tokens": [
        { "token_id": "91bb2bdd-09c3-4e13-999c-4f6e60437001", "position": 1, "text": "Maya" },
        { "token_id": "91bb2bdd-09c3-4e13-999c-4f6e60437002", "position": 2, "text": "walked" }
      ]
    }
  }
}
```

For `vision`, `kind` is `vision`, `media_type` is a supported video type, and
`reference` is omitted. If passage tokens are needed for a future gaze/reading
alignment feature, add a field in a new request schema version. The CV service
does not need to receive learner names or auth tokens.

The backend creates the read URL just before dispatch. It is a capability, not
a durable recording identifier: never store it in `service_jobs`, logs,
diagnostic payloads, or frontend responses. The database stores the bucket/path
and digest instead. Workers authenticate with service identity (for example,
workload identity/mTLS), not a user-supplied API key.

## ASR request and result

ASR receives audio only. `reference` is optional when only unconstrained
transcription is requested; when present, it allows a word aligner to return
reference-linked timings. It must not cause the service to silently replace
recognized words with the expected passage.

The worker can report progress/acceptance immediately; final results follow the
shared result envelope. Example `result`:

```json
{
  "transcript": "Maya walked to the river.",
  "language_code": "en-PH",
  "words": [
    {
      "text": "Maya",
      "start_seconds": 0.42,
      "end_seconds": 0.91,
      "confidence": 0.94,
      "reference_token_position": 1
    },
    {
      "text": "walked",
      "start_seconds": 0.94,
      "end_seconds": 1.36,
      "confidence": 0.89,
      "reference_token_position": 2
    }
  ]
}
```

`reference_token_position` may be null or omitted when the word cannot be
aligned. Timestamps are seconds from the start of the submitted audio. A word
confidence is in `[0, 1]`; it is model confidence, not a reading score.

## MediaPipe CV request and result

The vision service receives video only and reports one observation for every
requested behavior. It returns `not_assessable` when video quality, framing, or
coverage is insufficient; it does not convert missing evidence into
`not_detected`.

Example `result`:

```json
{
  "observations": [
    {
      "type": "finger_pointing",
      "outcome": "detected",
      "confidence": 0.91,
      "evidence": {
        "start_seconds": 8.4,
        "end_seconds": 21.7,
        "note": "Hand remained near the reading line during sampled frames."
      }
    },
    {
      "type": "loss_of_place",
      "outcome": "not_assessable",
      "confidence": null,
      "evidence": {
        "start_seconds": null,
        "end_seconds": null,
        "note": "Page and eye region were outside the camera frame."
      }
    }
  ],
  "media_quality": {
    "assessable_duration_seconds": 39.5,
    "sampled_frame_count": 237
  }
}
```

`outcome` is one of `detected`, `not_detected`, or `not_assessable`.
`confidence` is nullable and bounded to `[0, 1]`. Evidence notes should be
short, non-identifying, and safe for authorized staff review.

## Shared completion envelope

```json
{
  "result_schema_version": "1.0",
  "service_job_id": "2c44240b-4f16-4a94-b3bf-6e686150a13d",
  "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
  "kind": "asr",
  "status": "succeeded",
  "service_name": "readright-asr",
  "model_version": "whisperx-<deployment-version>",
  "request_sha256": "64-lowercase-hex-characters",
  "started_at": "2026-10-31T09:01:02Z",
  "finished_at": "2026-10-31T09:01:18Z",
  "result": {
    "transcript": "Maya walked to the river.",
    "language_code": "en-PH",
    "words": []
  }
}
```

Failure example:

```json
{
  "result_schema_version": "1.0",
  "service_job_id": "2c44240b-4f16-4a94-b3bf-6e686150a13d",
  "analysis_id": "9d781d54-70bb-49c4-9cd0-11fd3e230c23",
  "kind": "asr",
  "status": "failed",
  "service_name": "readright-asr",
  "model_version": "whisperx-<deployment-version>",
  "failure": {
    "code": "UNSUPPORTED_LANGUAGE",
    "message": "The requested language is not enabled for this model."
  },
  "finished_at": "2026-10-31T09:01:18Z"
}
```

## Delivery, retries, and validation

- Use at-least-once delivery with idempotent processing. Enforce uniqueness for
  service job IDs and idempotency keys; duplicate completions must not create
  duplicate normalized events.
- Accept only results matching the expected job, analysis, kind, request hash,
  and schema version. Unknown schema versions fail closed and are retained as a
  service integration error.
- Compute `request_sha256` from a canonical logical request, including the media
  content digest and inference parameters but excluding the expiring read URL.
- Apply backend-owned deadlines and leases. A late result for a superseded
  attempt must not replace the current job's result.
- Keep raw response JSON for diagnostics subject to retention policy; use
  normalized `reading_events`, `behavior_observations`, and `phoneme_events` as
  the reporting source.
- Persist model version and immutable pipeline/scoring policy versions so a
  rerun can be compared with the selected analysis.
- Do not put credentials, signed URLs, or learner personally identifying
  information in result payloads.

## Open decisions before implementation

- Queue and callback mechanism versus private synchronous job endpoints.
- Supported audio/video codecs, max sizes/duration, and URL lifetime.
- Whether prosody is a third independent service or stays in backend processing.
- Whether ASR owns forced alignment or returns raw word timestamps for a
  backend alignment step.
- Retention period and permitted detail level for raw media and diagnostic
  service payloads.
