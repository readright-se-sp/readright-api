from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MiscueType = Literal[
    "mispronunciation",
    "omission",
    "substitution",
    "insertion",
    "repetition",
    "transposition",
    "reversal",
    "self-correction",
]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: UUID
    video_url: str = Field(json_schema_extra={"format": "uri"})
    passage_title: str = Field(min_length=1)
    passage_content: str = Field(min_length=1)
    output_key_prefix: str | None = None

    @field_validator("video_url")
    @classmethod
    def require_https_video_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("video_url must use HTTPS")
        return value


class Miscue(BaseModel):
    model_config = ConfigDict(extra="allow")

    actual_phrase: str
    spoken_phrase: str
    actual_phoneme: list[str]
    spoken_phoneme: list[str]
    read_start: int = Field(ge=0)
    read_end: int = Field(ge=0)
    audio_object_key: str
    miscue_type: MiscueType

    @model_validator(mode="after")
    def validate_offset_order(self) -> "Miscue":
        if self.read_end < self.read_start:
            raise ValueError("read_end must be at or after read_start")
        return self


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: UUID
    reading_score: Decimal = Field(allow_inf_nan=False)
    wpm: Decimal = Field(ge=0, allow_inf_nan=False)
    is_word_by_word: bool
    is_disregard_punctuation: bool
    is_monotonous: bool
    is_lack_expression: bool
    is_hardly_audible: bool
    is_finger_pointing: bool
    miscues: list[Miscue]


ErrorCode = Literal[
    "INVALID_REQUEST",
    "VIDEO_DOWNLOAD_FAILED",
    "VIDEO_URL_EXPIRED",
    "UNSUPPORTED_MEDIA",
    "NO_SPEECH_DETECTED",
    "REQUEST_IN_PROGRESS",
    "RATE_LIMITED",
    "TIMEOUT",
    "PROCESSING_FAILED",
    "UPLOAD_FAILED",
    "SERVICE_UNAVAILABLE",
    "INTERNAL_ERROR",
]


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: ErrorCode
    message: str
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: ErrorBody


class AnalysisSubmission(BaseModel):
    request_id: UUID
    status: Literal["accepted"]
    status_url: str


class AnalysisStatus(BaseModel):
    request_id: UUID
    status: Literal["queued", "running", "completed", "failed"]
    result: AnalysisResponse | None = None
    error: ErrorBody | None = None
