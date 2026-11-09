# 6.3. API Documentation

| Endpoint | Method | Request | Response | Sample |
|---|---|---|---|---|
| App → Supabase Auth (`signInWithPassword`) | SDK call | Email, password | User and access session | `email: learner@example.test` |
| App → Supabase (`passages`, `sessions`) | `SELECT` / `INSERT` | Passage fields; completed session fields | Passage rows; insert success | `passages.select(id,text,word_count)` |
| App → Backend: `/analyze` **(legacy client)** | `POST` | Multipart `file`, `passage_id`; `X-API-Key` | Assessment result JSON | `file=reading.webm; passage_id=<uuid>` |
| Backend: `/health` | `GET` | None | Liveness status | `{"status":"ok"}` |
| Backend: `/v1/dashboard` | `GET` | Supabase `Bearer` token | Learner, summary, session history | `Authorization: Bearer <token>` |
| Backend: `/v1/me/sessions`<br>`/v1/me/sessions/{id}/upload-url`<br>`/v1/me/sessions/{id}/recording`<br>`/v1/me/sessions/{id}`<br>`/v1/me/sessions/{id}/result` | `POST` / `GET` | Bearer token; grade, content type, S3 key and recording metadata | Session/passage, signed upload fields, processing status, result | `passage_grade_id=4 → session_id → upload → result` |
| Backend → MAI: `/v1/mai/analyses`<br>`/v1/mai/analyses/{request_id}` → MAI `/analyses` | `POST` / `GET` | `X-Backend-Key`; `request_id`, `video_url`, passage title/content | MAI result or `202` with status URL | `{"request_id":"<uuid>","video_url":"<signed-url>"}` |
| `readright-ai` server API (README design only) | Not specified | `s3_file_id`, passage text | Merged audio/video findings | `{"s3_file_id":"<id>","passage":"..."}` |

**Compatibility note:** the app’s checked client still calls `/analyze`, while the backend’s current learner flow uses session creation and S3 upload routes. No app commit adopting that newer flow was found. The AI repo snapshot contains only `README.md`, which does not specify an HTTP path or method.

Trusted table CRUD routes are omitted here; they require `X-Backend-Key` and are documented in [the backend API contract](docs/api-contract.md) and [OpenAPI](openapi.json). The app-facing calls are in [`readright-app`](https://github.com/readright-se-sp/readright-app); AI architecture notes are in [`readright-ai`](https://github.com/readright-se-sp/readright-ai).
