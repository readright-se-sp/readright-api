# `GO2Result` + `GO3Result` — current internal shapes

These `TypedDict` objects are internal to the current in-process pipelines and
are merged into `AssessmentResult` before the API response.

## `GO2Result`

| Field | Type |
|---|---|
| `wpm` | `float` |
| `word_recognition_pct` | `float` |
| `reading_level` | `str` |
| `correct` | `int` |
| `mispronunciation` | `int` |
| `substitution` | `int` |
| `omission` | `int` |
| `insertion` | `int` |
| `repetition` | `int` |

## `GO3Result`

Five `bool` fields: `finger_pointing`, `loss_of_place`, `monotone_reading`,
`word_by_word_reading`, and `inaudible_reading`.

## Related

- Source: [`app/models/pipeline_results.py`](../../../app/models/pipeline_results.py)
- API model: [`assessment.md`](assessment.md)
- Target service payloads: [`ai-service-contracts.md`](../../ai-service-contracts.md)
