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


class DashboardPassage(BaseModel):
    passage_id: UUID
    title: str
    language_code: str


class DashboardReading(BaseModel):
    analysis_id: UUID
    status: str
    wpm: float | None
    word_recognition_pct: float | None
    reading_level: str | None


class DashboardSession(BaseModel):
    session_id: UUID
    status: str
    assigned_at: datetime
    completed_at: datetime | None
    passage: DashboardPassage
    reading: DashboardReading | None


class LearnerDashboard(BaseModel):
    learner: DashboardLearner
    summary: DashboardSummary
    recent_sessions: list[DashboardSession]
