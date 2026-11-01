from typing import Any, cast

from supabase import Client


class MeRepository:
    """Learner-scoped persistence operations for sessions and results."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def assign_session(
        self, learner_id: str, passage_grade_id: int, policy_version: str
    ) -> dict[str, Any] | None:
        response = self._client.rpc(
            "assign_learner_session",
            {
                "p_learner_id": learner_id,
                "p_passage_grade_id": passage_grade_id,
                "p_assignment_policy_version": policy_version,
            },
        ).execute()
        return _as_object(response.data)

    def get_learner(self, learner_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table("learners")
            .select("user_id,current_grade_id")
            .eq("user_id", learner_id)
            .maybe_single()
            .execute()
        )
        return _as_object(response.data)

    def count_passage_tokens(self, passage_id: str) -> int:
        response = (
            self._client.table("passage_tokens")
            .select("token_id", count="exact")
            .eq("passage_id", passage_id)
            .execute()
        )
        return (
            int(response.count)
            if response.count is not None
            else len(_as_rows(response.data))
        )

    def get_owned_session(
        self, learner_id: str, session_id: str
    ) -> dict[str, Any] | None:
        response = (
            self._client.table("sessions")
            .select("session_id,learner_id,passage_id,grade_at_assessment_id,status")
            .eq("session_id", session_id)
            .eq("learner_id", learner_id)
            .maybe_single()
            .execute()
        )
        return _as_object(response.data)

    def get_passage(self, passage_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table("passages")
            .select("passage_id,title,content,difficulty_grade_id")
            .eq("passage_id", passage_id)
            .maybe_single()
            .execute()
        )
        return _as_object(response.data)

    def list_questions(self, passage_id: str) -> list[dict[str, Any]]:
        response = (
            self._client.table("comprehension_questions")
            .select("question_id,question_order,prompt,points_possible")
            .eq("passage_id", passage_id)
            .order("question_order")
            .execute()
        )
        questions = _as_rows(response.data)
        if not questions:
            return []

        question_ids = [str(question["question_id"]) for question in questions]
        choice_response = (
            self._client.table("question_choices")
            .select("choice_id,question_id,choice_order,choice_text,is_correct")
            .in_("question_id", question_ids)
            .order("choice_order")
            .execute()
        )
        choices_by_question: dict[str, list[dict[str, Any]]] = {}
        for choice in _as_rows(choice_response.data):
            choices_by_question.setdefault(str(choice["question_id"]), []).append(choice)

        for question in questions:
            question["choices"] = choices_by_question.get(
                str(question["question_id"]), []
            )
        return questions

    def submit_comprehension(
        self, session_id: str, learner_id: str, answers: list[dict[str, Any]]
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "submit_learner_comprehension",
            {
                "p_session_id": session_id,
                "p_learner_id": learner_id,
                "p_answers": answers,
            },
        ).execute()
        result = _as_object(response.data)
        if result is None:
            raise RuntimeError("Comprehension submission returned no score")
        return result

    def get_latest_attempt(self, session_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table("comprehension_attempts")
            .select(
                "attempt_id,attempt_number,status,submitted_at,score_earned,score_possible"
            )
            .eq("session_id", session_id)
            .order("attempt_number", desc=True)
            .limit(1)
            .execute()
        )
        rows = _as_rows(response.data)
        return rows[0] if rows else None

    def get_latest_analysis(self, session_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table("reading_analyses")
            .select(
                "analysis_id,status,is_selected,wpm,word_recognition_pct,reading_level,created_at"
            )
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = _as_rows(response.data)
        return rows[0] if rows else None

    def get_selected_analysis(self, session_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table("reading_analyses")
            .select(
                "analysis_id,status,wpm,word_recognition_pct,reading_level"
            )
            .eq("session_id", session_id)
            .eq("is_selected", True)
            .maybe_single()
            .execute()
        )
        return _as_object(response.data)

    def list_reading_events(self, analysis_id: str) -> list[dict[str, Any]]:
        response = (
            self._client.table("reading_events")
            .select(
                "event_id,event_order,detected_type,reviewed_type,"
                "expected_start_token_id,expected_end_token_id,heard_text"
            )
            .eq("analysis_id", analysis_id)
            .order("event_order")
            .execute()
        )
        return _as_rows(response.data)

    def list_passage_tokens(self, passage_id: str) -> list[dict[str, Any]]:
        response = (
            self._client.table("passage_tokens")
            .select("token_id,position,token_text")
            .eq("passage_id", passage_id)
            .order("position")
            .execute()
        )
        return _as_rows(response.data)

    def list_behavior_observations(self, analysis_id: str) -> list[dict[str, Any]]:
        response = (
            self._client.table("behavior_observations")
            .select("type,outcome")
            .eq("analysis_id", analysis_id)
            .execute()
        )
        return _as_rows(response.data)

    def update_session(
        self, learner_id: str, session_id: str, fields: dict[str, Any]
    ) -> None:
        (
            self._client.table("sessions")
            .update(fields)
            .eq("session_id", session_id)
            .eq("learner_id", learner_id)
            .execute()
        )

    def expire_processing_sessions(self, cutoff_iso: str) -> list[dict[str, Any]]:
        response = self._client.rpc(
            "expire_stuck_reading_sessions", {"p_cutoff": cutoff_iso}
        ).execute()
        return _as_rows(response.data)


def _as_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return cast(dict[str, Any], value[0])
    return None


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = cast(list[object], value)
    return [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]
