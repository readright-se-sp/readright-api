from dataclasses import dataclass
from typing import Any, Callable, cast

from supabase import Client


@dataclass
class DashboardSnapshot:
    summary: dict[str, Any]
    sessions: list[dict[str, Any]]
    passages: dict[str, dict[str, Any]]
    analyses: dict[str, dict[str, Any]]
    events: dict[str, list[dict[str, Any]]]
    observations: dict[str, list[dict[str, Any]]]


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

        sessions = _fetch_all(
            lambda: (
                self._client.table("sessions")
                .select("session_id,status,assigned_at,completed_at,passage_id")
                .eq("learner_id", learner_id)
                .order("assigned_at", desc=False)
                .order("session_id", desc=False)
            )
        )
        if not sessions:
            return DashboardSnapshot(summary_response.data, [], {}, {}, {}, {})

        session_ids = [str(row["session_id"]) for row in sessions]
        passage_ids = list({str(row["passage_id"]) for row in sessions})

        passages: dict[str, dict[str, Any]] = {}
        for passage_id_chunk in _chunks(passage_ids):
            rows = _fetch_all(
                lambda: (
                    self._client.table("passages")
                    .select("passage_id,title,language_code")
                    .in_("passage_id", passage_id_chunk)
                )
            )
            passages.update({str(row["passage_id"]): row for row in rows})

        analyses: list[dict[str, Any]] = []
        for session_id_chunk in _chunks(session_ids):
            analyses.extend(
                _fetch_all(
                    lambda: (
                        self._client.table("reading_analyses")
                        .select(
                            "analysis_id,session_id,status,wpm,word_recognition_pct,reading_level"
                        )
                        .in_("session_id", session_id_chunk)
                        .eq("is_selected", True)
                    )
                )
            )
        analyses_by_session = {str(row["session_id"]): row for row in analyses}
        analysis_ids = [str(row["analysis_id"]) for row in analyses]

        events_by_analysis: dict[str, list[dict[str, Any]]] = {}
        observations_by_analysis: dict[str, list[dict[str, Any]]] = {}
        for analysis_id_chunk in _chunks(analysis_ids):
            events = _fetch_all(
                lambda: (
                    self._client.table("reading_events")
                    .select("analysis_id,detected_type,reviewed_type")
                    .in_("analysis_id", analysis_id_chunk)
                    .order("analysis_id", desc=False)
                    .order("event_order", desc=False)
                )
            )
            for analysis_id, rows in _group_by_analysis(events).items():
                events_by_analysis.setdefault(analysis_id, []).extend(rows)

            observations = _fetch_all(
                lambda: (
                    self._client.table("behavior_observations")
                    .select("analysis_id,type,outcome")
                    .in_("analysis_id", analysis_id_chunk)
                )
            )
            for analysis_id, rows in _group_by_analysis(observations).items():
                observations_by_analysis.setdefault(analysis_id, []).extend(rows)

        return DashboardSnapshot(
            summary_response.data,
            sessions,
            passages,
            analyses_by_session,
            events_by_analysis,
            observations_by_analysis,
        )


_PAGE_SIZE = 1000
_IN_FILTER_SIZE = 200


def _fetch_all(query_factory: Callable[[], Any]) -> list[dict[str, Any]]:
    """Fetch every row in pages, avoiding PostgREST's default row cap."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = query_factory().range(offset, offset + _PAGE_SIZE - 1).execute()
        page = _rows(response.data)
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            return rows
        offset += _PAGE_SIZE


def _group_by_analysis(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["analysis_id"]), []).append(row)
    return grouped


def _chunks(values: list[str]) -> list[list[str]]:
    return [
        values[index : index + _IN_FILTER_SIZE]
        for index in range(0, len(values), _IN_FILTER_SIZE)
    ]


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = cast(list[object], value)
    return [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]
