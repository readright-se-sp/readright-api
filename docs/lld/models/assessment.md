# `AssessmentResult` — current response model

`AssessmentResult` is the Pydantic response model returned by the current
synchronous `/analyze` endpoint. It contains 15 fields: 9 GO2 aggregate fields,
5 GO3 behavior flags, and `db_save_failed` metadata.

| Field | Type | Source |
|---|---|---|
| `wpm` | `float` | GO2 scoring |
| `word_recognition_pct` | `float`, 0–100 | GO2 scoring |
| `reading_level` | `Frustration`, `Instructional`, or `Independent` | GO2 scoring |
| `correct` | `int` | GO2 miscue count |
| `mispronunciation` | `int` | GO2 miscue count |
| `substitution` | `int` | GO2 miscue count |
| `omission` | `int` | GO2 miscue count |
| `insertion` | `int` | GO2 miscue count |
| `repetition` | `int` | GO2 miscue count |
| `finger_pointing` | `bool` | GO3 CV detector |
| `loss_of_place` | `bool` | GO3 CV detector |
| `monotone_reading` | `bool` | GO3 prosody detector |
| `word_by_word_reading` | `bool` | GO3 prosody detector |
| `inaudible_reading` | `bool` | GO3 prosody detector |
| `db_save_failed` | `bool` | API persistence metadata |

This model does not yet expose per-word events, phoneme evidence, analysis
status, or comprehension results. Those belong to the proposed session-oriented
API and database model, not this response type.

## Related

- Source: [`app/models/assessment.py`](../../../app/models/assessment.py)
- API contract: [`api-contract.md`](../../api-contract.md)
- Target data model: [`database-proposal.md`](../../database-proposal.md)
