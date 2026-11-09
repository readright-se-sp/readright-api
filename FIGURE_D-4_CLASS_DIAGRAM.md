# Figure D-4: ReadRight domain class diagram

```mermaid
classDiagram
    direction TB

    class Learner {
        +UUID userId
        +int currentGradeId
        +string displayName
    }
    class GradeLevel {
        +int gradeId
        +string label
        +int sequence
    }
    class Passage {
        +UUID passageId
        +string title
        +string languageCode
        +string content
        +string status
    }
    class PassageToken {
        +UUID tokenId
        +int position
        +string tokenText
        +bool isProperNoun
    }
    class ReadingSession {
        +UUID sessionId
        +string status
        +datetime assignedAt
        +datetime completedAt
    }
    class Recording {
        +UUID recordingId
        +string kind
        +string storagePath
        +string contentType
        +decimal durationSeconds
    }
    class ReadingAnalysis {
        +UUID analysisId
        +string status
        +bool isSelected
        +decimal wpm
        +decimal wordRecognitionPct
        +string readingLevel
    }
    class ReadingEvent {
        +UUID eventId
        +string detectedType
        +string reviewedType
        +string heardText
        +decimal confidence
    }
    class BehaviorObservation {
        +UUID observationId
        +string type
        +string outcome
        +decimal confidence
    }
    class ComprehensionQuestion {
        +UUID questionId
        +int questionOrder
        +string prompt
        +decimal pointsPossible
    }
    class QuestionChoice {
        +UUID choiceId
        +int choiceOrder
        +string choiceText
        +bool isCorrect
    }
    class ComprehensionAttempt {
        +UUID attemptId
        +int attemptNumber
        +string status
        +decimal scoreEarned
        +decimal scorePossible
    }
    class ComprehensionAnswer {
        +UUID answerId
        +datetime answeredAt
    }

    class SessionResultResponse {
        <<API DTO>>
        +UUID sessionId
        +decimal wpm
        +decimal wordRecognitionPct
        +string readingLevel
        +int comprehensionLevel
    }
    class AnalysisRequest {
        <<MAI API DTO>>
        +UUID requestId
        +string videoUrl
        +string passageTitle
        +string passageContent
    }
    class AnalysisResponse {
        <<MAI API DTO>>
        +UUID requestId
        +decimal readingScore
        +decimal wpm
        +list miscues
    }
    class Miscue {
        <<MAI API DTO>>
        +string actualPhrase
        +string spokenPhrase
        +string miscueType
        +int readStart
        +int readEnd
    }

    GradeLevel "1" --> "0..*" Learner : current grade
    GradeLevel "1" --> "0..*" Passage : difficulty grade
    GradeLevel "1" --> "0..*" ReadingSession : grade at assessment
    Learner "1" --> "0..*" ReadingSession : completes
    Passage "1" *-- "1..*" PassageToken : tokenizes
    Passage "1" --> "0..*" ReadingSession : assigned to
    Passage "1" *-- "0..*" ComprehensionQuestion : has
    ReadingSession "1" *-- "0..*" Recording : stores
    ReadingSession "1" *-- "0..*" ReadingAnalysis : produces
    Recording "1" --> "0..*" ReadingAnalysis : source recording
    ReadingAnalysis "1" *-- "0..*" ReadingEvent : detects
    ReadingAnalysis "1" *-- "0..*" BehaviorObservation : observes
    ReadingEvent "0..*" --> "0..2" PassageToken : expected token range
    ComprehensionQuestion "1" *-- "1..*" QuestionChoice : offers
    ReadingSession "1" *-- "0..*" ComprehensionAttempt : records
    ComprehensionAttempt "1" *-- "0..*" ComprehensionAnswer : contains
    ComprehensionQuestion "1" --> "0..*" ComprehensionAnswer : answered by
    QuestionChoice "0..1" --> "0..*" ComprehensionAnswer : selected choice
    SessionResultResponse ..> ReadingSession : summarizes
    AnalysisRequest ..> AnalysisResponse : sent to MAI
    AnalysisResponse *-- "0..*" Miscue : returns
    AnalysisResponse ..> ReadingAnalysis : supplies analysis data
```

This is a domain and data-contract class diagram for the learner workflow shown in the frontend repository: sign in, complete a reading session and comprehension quiz, view results, and review progress. The frontend uses React function components and hooks, so its pages are not represented as classes. The diagram focuses on the classes and relationships shared through the app API, backend data model, and MAI analysis contract. I could not find a separate Figure D-1 file in the linked repositories; the use-case flow is documented in `readright-app` `dev` branch `src/App.jsx`.

Sources: `readright-app` `dev` branch (`src/App.jsx`, `src/lib/api.js`); `readright-api` (`app/features/me/models.py`, `app/features/mai/models.py`, and Supabase schema migrations); `readright-ai` `dev` branch (`server/app/models.py`).
