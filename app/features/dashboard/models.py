from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DashboardLearner(BaseModel):
    user_id: UUID
    display_name: str | None
    grade_id: int
    grade_label: str


class DashboardSummary(BaseModel):
    sessions_total: int
    sessions_completed: int
    sessions_in_progress: int
    average_wpm: float | None
    average_word_recognition_pct: float | None


class DashboardSession(BaseModel):
    session_id: UUID
    status: str
    assigned_at: datetime
    completed_at: datetime | None
    passage_id: UUID
    passage_title: str
    language_code: str
    wpm: float | None
    word_recognition_pct: float | None
    reading_level: str | None
    correct: int | None
    mispronunciation: int | None
    substitution: int | None
    omission: int | None
    insertion: int | None
    repetition: int | None
    refusal_to_pronounce: int | None
    finger_pointing: bool | None
    loss_of_place: bool | None
    monotone_reading: bool | None
    word_by_word_reading: bool | None
    inaudible_reading: bool | None


class LearnerDashboard(BaseModel):
    learner: DashboardLearner
    summary: DashboardSummary
    sessions: list[DashboardSession]
