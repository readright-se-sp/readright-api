import logging

from app.features.dashboard.models import (
    DashboardLearner,
    DashboardPassage,
    DashboardReading,
    DashboardSession,
    DashboardSummary,
    LearnerDashboard,
)
from app.features.dashboard.repository import DashboardRepository

logger = logging.getLogger(__name__)


class LearnerProfileNotFound(Exception):
    """The authenticated user does not have a learner profile."""


class DashboardDataUnavailable(Exception):
    """The dashboard could not be loaded from persistence."""


class DashboardService:
    """Builds the learner-facing dashboard from persisted assessment data."""

    def __init__(self, repository: DashboardRepository) -> None:
        self._repository = repository

    def get_dashboard(self, learner_id: str) -> LearnerDashboard:
        try:
            snapshot = self._repository.fetch(learner_id)
        except Exception as exc:
            logger.exception("Could not load learner dashboard")
            raise DashboardDataUnavailable from exc

        if snapshot is None:
            raise LearnerProfileNotFound

        recent_sessions: list[DashboardSession] = []
        for session in snapshot.sessions:
            passage = snapshot.passages.get(str(session["passage_id"]))
            if passage is None:
                continue

            analysis = snapshot.analyses.get(str(session["session_id"]))
            reading = (
                DashboardReading(
                    analysis_id=analysis["analysis_id"],
                    status=analysis["status"],
                    wpm=analysis["wpm"],
                    word_recognition_pct=analysis["word_recognition_pct"],
                    reading_level=analysis["reading_level"],
                )
                if analysis is not None
                else None
            )

            recent_sessions.append(
                DashboardSession(
                    session_id=session["session_id"],
                    status=session["status"],
                    assigned_at=session["assigned_at"],
                    completed_at=session["completed_at"],
                    passage=DashboardPassage(
                        passage_id=passage["passage_id"],
                        title=passage["title"],
                        language_code=passage["language_code"],
                    ),
                    reading=reading,
                )
            )

        summary = snapshot.summary
        return LearnerDashboard(
            learner=DashboardLearner(
                user_id=summary["learner_id"],
                display_name=summary["display_name"],
                grade_id=summary["grade_id"],
                grade_label=summary["grade_label"],
            ),
            summary=DashboardSummary(
                sessions_total=summary["sessions_total"],
                sessions_completed=summary["sessions_completed"],
                sessions_in_progress=summary["sessions_in_progress"],
                average_wpm=summary["average_wpm"],
                average_word_recognition_pct=summary[
                    "average_word_recognition_pct"
                ],
            ),
            recent_sessions=recent_sessions,
        )
