import logging

from app.features.dashboard.models import (
    DashboardLearner,
    DashboardSession,
    DashboardSummary,
    LearnerDashboard,
)
from app.features.dashboard.repository import DashboardRepository

logger = logging.getLogger(__name__)

DASHBOARD_MISCUE_TYPES = (
    "correct",
    "mispronunciation",
    "substitution",
    "omission",
    "insertion",
    "repetition",
    "refusal_to_pronounce",
)
DASHBOARD_BEHAVIOR_TYPES = (
    "finger_pointing",
    "loss_of_place",
    "monotone_reading",
    "word_by_word_reading",
    "inaudible_reading",
)


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

        sessions: list[DashboardSession] = []
        for session in snapshot.sessions:
            passage = snapshot.passages.get(str(session["passage_id"]))
            if passage is None:
                continue

            analysis = snapshot.analyses.get(str(session["session_id"]))
            scores: dict[str, Any] = {
                "wpm": None,
                "word_recognition_pct": None,
                "reading_level": None,
            }
            miscues: dict[str, int | None] = dict.fromkeys(
                DASHBOARD_MISCUE_TYPES, None
            )
            behaviors: dict[str, bool | None] = dict.fromkeys(
                DASHBOARD_BEHAVIOR_TYPES, None
            )

            if analysis is not None:
                scores.update(
                    wpm=analysis["wpm"],
                    word_recognition_pct=analysis["word_recognition_pct"],
                    reading_level=analysis["reading_level"],
                )
                analysis_id = str(analysis["analysis_id"])
                for observation in snapshot.observations.get(analysis_id, []):
                    behavior_type = observation.get("type")
                    if behavior_type not in behaviors:
                        continue
                    outcome = observation.get("outcome")
                    behaviors[behavior_type] = (
                        True
                        if outcome == "detected"
                        else False
                        if outcome == "not_detected"
                        else None
                    )

                if analysis["status"] in {"completed", "partial"}:
                    counts = dict.fromkeys(DASHBOARD_MISCUE_TYPES, 0)
                    for event in snapshot.events.get(analysis_id, []):
                        event_type = event.get("reviewed_type") or event.get(
                            "detected_type"
                        )
                        if event_type in counts:
                            counts[event_type] += 1
                    miscues = counts

            sessions.append(
                DashboardSession(
                    session_id=session["session_id"],
                    status=session["status"],
                    assigned_at=session["assigned_at"],
                    completed_at=session["completed_at"],
                    passage_id=passage["passage_id"],
                    passage_title=passage["title"],
                    language_code=passage["language_code"],
                    **scores,
                    **miscues,
                    **behaviors,
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
            sessions=sessions,
        )
