from dataclasses import dataclass
from typing import Any, cast

from supabase import Client


@dataclass
class DashboardSnapshot:
    summary: dict[str, Any]
    sessions: list[dict[str, Any]]
    passages: dict[str, dict[str, Any]]
    analyses: dict[str, dict[str, Any]]


class DashboardRepository:
    """Loads the records used to assemble a learner dashboard."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def fetch(self, learner_id: str) -> DashboardSnapshot | None:
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
        if summary_response is None or not isinstance(summary_response.data, dict):
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
            return DashboardSnapshot(summary_response.data, [], {}, {})

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

        return DashboardSnapshot(summary_response.data, sessions, passages, analyses)


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = cast(list[object], value)
    return [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]
