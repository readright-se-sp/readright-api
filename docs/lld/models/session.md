# `SessionRecord` + `SessionRepositoryProtocol` — current implementation

## Responsibility

Defines the flat record currently written to Supabase after a successful
assessment and the persistence interface used by the orchestrator.

## `SessionRecord` fields

| Field | Type | Notes |
|---|---|---|
| `learner_id` | `str` | UUID string; blank skips insert |
| `passage_id` | `str` | Passage identifier |
| `wpm` | `float` | |
| `word_recognition_pct` | `float` | |
| `reading_level` | `str` | |
| `correct` | `int` | Correct event count |
| `mispronunciation` | `int` | Miscue count |
| `substitution` | `int` | Miscue count |
| `omission` | `int` | Miscue count |
| `insertion` | `int` | Miscue count |
| `repetition` | `int` | Miscue count |
| `finger_pointing` … `inaudible_reading` | `bool` | Five aggregate behavior flags |

## Persistence behavior

`SessionRepositoryProtocol.insert(record)` writes to the current `sessions`
table. The orchestrator treats a write failure as non-fatal and returns
`db_save_failed=true`. This flat shape is separate from the normalized,
provisional model in [`database-proposal.md`](../../database-proposal.md).

## Related

- Source: [`app/models/session.py`](../../../app/models/session.py)
- Class diagram: [`models.md`](../../uml/class/models.md)
