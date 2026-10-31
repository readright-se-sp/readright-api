from typing import Any, cast

from supabase import Client

from app.models import (
    DashboardLearner,
    DashboardPassage,
    DashboardReading,
    DashboardSession,
    DashboardSummary,
    LearnerDashboard,
)


class DashboardRepository:
    """Reads a learner-scoped dashboard snapshot from Supabase."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def fetch(self, learner_id: str) -> LearnerDashboard | None:
        summary_response = (
            self._client.table("learner_dashboard_summary")
            .select(
                "learner_id,display_name,grade_id,grade_label,sessions_total,"
                "sessions_completed,sessions_in_progress,average_wpm,"
                "average_word_recognition_pct"
            )
            .eq("learner_id", learner_id)
            .maybe_single()
            .execute()
        )
        if summary_response is None:
            return None
        summary = summary_response.data
        if not isinstance(summary, dict):
            return None

        session_response = (
            self._client.table("sessions")
            .select("session_id,status,assigned_at,completed_at,passage_id")
            .eq("learner_id", learner_id)
            .order("assigned_at", desc=True)
            .limit(10)
            .execute()
        )
        sessions = _rows(session_response.data)
        if not sessions:
            return _build_dashboard(summary, [], {}, {})

        session_ids = [str(row["session_id"]) for row in sessions]
        passage_ids = list({str(row["passage_id"]) for row in sessions})

        passage_response = (
            self._client.table("passages")
            .select("passage_id,title,language_code")
            .in_("passage_id", passage_ids)
            .execute()
        )
        passages = {
            str(row["passage_id"]): row for row in _rows(passage_response.data)
        }

        analysis_response = (
            self._client.table("reading_analyses")
            .select(
                "analysis_id,session_id,status,wpm,word_recognition_pct,reading_level"
            )
            .in_("session_id", session_ids)
            .eq("is_selected", True)
            .execute()
        )
        analyses = {
            str(row["session_id"]): row for row in _rows(analysis_response.data)
        }

        return _build_dashboard(summary, sessions, passages, analyses)


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = cast(list[object], value)
    return [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]


def _build_dashboard(
    summary: dict[str, Any],
    sessions: list[dict[str, Any]],
    passages: dict[str, dict[str, Any]],
    analyses: dict[str, dict[str, Any]],
) -> LearnerDashboard:
    recent_sessions: list[DashboardSession] = []
    for session in sessions:
        passage = passages.get(str(session["passage_id"]))
        if passage is None:
            continue

        analysis = analyses.get(str(session["session_id"]))
        reading: DashboardReading | None = None
        if analysis is not None:
            reading = DashboardReading(
                analysis_id=analysis["analysis_id"],
                status=analysis["status"],
                wpm=analysis["wpm"],
                word_recognition_pct=analysis["word_recognition_pct"],
                reading_level=analysis["reading_level"],
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
