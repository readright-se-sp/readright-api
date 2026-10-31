# Models — Class Diagram

## Current runtime models

```mermaid
classDiagram
    class AssessmentResult {
        <<Pydantic Model>>
        +wpm: float
        +word_recognition_pct: float
        +reading_level: ReadingLevel
        +correct: int
        +mispronunciation: int
        +substitution: int
        +omission: int
        +insertion: int
        +repetition: int
        +finger_pointing: bool
        +loss_of_place: bool
        +monotone_reading: bool
        +word_by_word_reading: bool
        +inaudible_reading: bool
        +db_save_failed: bool
    }
    class ReadingLevel {
        <<Literal>>
        Frustration
        Instructional
        Independent
    }
    AssessmentResult --> ReadingLevel
```

## ResultConsolidator

```mermaid
classDiagram
    class ResultConsolidator {
        +merge(go2_result: dict, go3_result: dict)$ AssessmentResult
    }
    ResultConsolidator --> AssessmentResult : produces
```

## WordSegment

```mermaid
classDiagram
    class WordSegment {
        <<TypedDict>>
        +word: str
        +start: float
        +end: float
        +score: float
    }
```

## MiscueCounts

```mermaid
classDiagram
    class MiscueCounts {
        <<TypedDict>>
        +correct: int
        +mispronunciation: int
        +substitution: int
        +omission: int
        +insertion: int
        +repetition: int
    }
    class MiscueClassifierProtocol {
        <<Protocol>>
        +classify(transcript_words: list, passage_text: str) MiscueCounts
    }
    MiscueClassifierProtocol --> MiscueCounts : returns
```

## ScoringResult

```mermaid
classDiagram
    class ScoringResult {
        <<TypedDict>>
        +wpm: float
        +word_recognition_pct: float
        +reading_level: ReadingLevel
    }
    class ScoringEngineProtocol {
        <<Protocol>>
        +score(transcript_words: list, miscue_counts: MiscueCounts, total_passage_words: int) ScoringResult
    }
    ScoringEngineProtocol --> ScoringResult : returns
```

## PassageRecord + PassageRepositoryProtocol

```mermaid
classDiagram
    class PassageRecord {
        <<TypedDict>>
        +text: str
        +word_count: int
        +proper_nouns: list~str~
    }
    class PassageRepositoryProtocol {
        <<Protocol>>
        +fetch(passage_id: str) PassageRecord
    }
    PassageRepositoryProtocol --> PassageRecord : returns
```

## SessionRecord + SessionRepositoryProtocol

```mermaid
classDiagram
    class SessionRecord {
        <<TypedDict>>
        +learner_id: str
        +passage_id: str
        +wpm: float
        +word_recognition_pct: float
        +reading_level: str
        +correct: int
        +mispronunciation: int
        +substitution: int
        +omission: int
        +insertion: int
        +repetition: int
        +finger_pointing: bool
        +loss_of_place: bool
        +monotone_reading: bool
        +word_by_word_reading: bool
        +inaudible_reading: bool
    }
    class SessionRepositoryProtocol {
        <<Protocol>>
        +insert(record: SessionRecord) None
    }
    SessionRepositoryProtocol --> SessionRecord : accepts
```

## ExtractionResult + MediaExtractorProtocol

```mermaid
classDiagram
    class ExtractionResult {
        <<TypedDict>>
        +wav_path: str
        +mp4_path: str
    }
    class MediaExtractorProtocol {
        <<Protocol>>
        +extract(source_path: str, out_dir: str) ExtractionResult
    }
    MediaExtractorProtocol --> ExtractionResult : returns
```

## GO2Result + GO3Result

```mermaid
classDiagram
    class GO2Result {
        <<TypedDict>>
        +wpm: float
        +word_recognition_pct: float
        +reading_level: str
        +correct: int
        +mispronunciation: int
        +substitution: int
        +omission: int
        +insertion: int
        +repetition: int
    }
    class GO3Result {
        <<TypedDict>>
        +finger_pointing: bool
        +loss_of_place: bool
        +monotone_reading: bool
        +word_by_word_reading: bool
        +inaudible_reading: bool
    }
```

## Referenced by

- LLD: `../../lld/models/assessment.md`
- LLD: `../../lld/models/transcription.md`
- LLD: `../../lld/models/miscue.md`
- LLD: `../../lld/models/scoring.md`
- LLD: `../../lld/models/passage.md`
- LLD: `../../lld/models/session.md`
- LLD: `../../lld/models/media-extractor-model.md`
- LLD: `../../lld/models/pipeline-results.md`
- LLD: `../../lld/models/cv-detector.md`
- LLD: `../../lld/models/prosody-detector.md`
- LLD: `../../lld/models/proper-noun.md`
