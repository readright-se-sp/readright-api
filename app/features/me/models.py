from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passage_grade_id: int | None = Field(default=None, ge=1, le=7)


class SessionPassage(BaseModel):
    id: UUID
    title: str
    text: str
    wordCount: int


class StartSessionResponse(BaseModel):
    session_id: UUID
    status: Literal["assigned"]
    passage: SessionPassage


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: str = Field(
        min_length=1,
        max_length=255,
        description="Use the exact file.type value, including any codec parameters.",
    )


class UploadTarget(BaseModel):
    url: str
    fields: dict[str, str]


class UploadUrlResponse(BaseModel):
    storage_key: str
    upload: UploadTarget
    expires_at: datetime


class RecordingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_key: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0, description="The uploaded file's byte size.")
    duration_seconds: int = Field(
        gt=0, description="Whole seconds of recorded reading audio/video."
    )


class RecordingResponse(BaseModel):
    session_id: UUID
    status: Literal["processing"]


class SessionStatusResponse(BaseModel):
    session_id: UUID
    status: Literal[
        "assigned", "reading", "processing", "comprehension", "completed", "failed"
    ]
    analysis_status: Literal["running", "partial", "completed", "failed"] | None
    comprehension_status: Literal["in_progress", "submitted", "abandoned"] | None


class QuestionResponse(BaseModel):
    id: UUID
    question: str
    options: list[str]


class ComprehensionAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    choice: StrictInt | Literal["idk"] | None = Field(
        description="Zero-based option position, 'idk', or null for no answer."
    )


class ComprehensionSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[ComprehensionAnswerRequest] = Field(min_length=1)


class ComprehensionSubmissionResponse(BaseModel):
    score_earned: float
    score_possible: float
    comprehension_level: Literal[1, 2, 3]


class ResultPassage(BaseModel):
    id: UUID
    title: str


class MiscueDetail(BaseModel):
    said: str | None
    expected: str
    sentence: str | None = None


class SessionResultResponse(BaseModel):
    session_id: UUID
    passage: ResultPassage
    wpm: float | None
    word_recognition_pct: float | None
    reading_level: str | None
    comprehension_level: Literal[1, 2, 3] | None
    correct: int
    mispronunciation: int
    substitution: int
    omission: int
    insertion: int
    repetition: int
    refusal_to_pronounce: int
    miscue_details: dict[str, list[MiscueDetail]]
    finger_pointing: bool | None
    loss_of_place: bool | None
    monotone_reading: bool | None
    word_by_word_reading: bool | None
    inaudible_reading: bool | None
