import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings
from app.features.me.models import (
    ComprehensionSubmissionResponse,
    MiscueDetail,
    QuestionResponse,
    RecordingResponse,
    SessionResultResponse,
    SessionStatusResponse,
    StartSessionResponse,
    UploadUrlResponse,
)
from app.features.me.repository import MeRepository
from app.features.me.storage import (
    head_recording,
    make_download_url,
    make_upload_post,
)

logger = logging.getLogger(__name__)

VIDEO_TYPE_PATTERN = re.compile(
    r"^video/(?:webm|mp4)(?:;codecs=[A-Za-z0-9.,_ -]+)?$", re.IGNORECASE
)
MISCUE_TYPES = (
    "mispronunciation",
    "substitution",
    "omission",
    "insertion",
    "repetition",
    "refusal_to_pronounce",
)
BEHAVIOR_TYPES = (
    "finger_pointing",
    "loss_of_place",
    "monotone_reading",
    "word_by_word_reading",
    "inaudible_reading",
)


class SessionNotFound(Exception):
    """The session does not belong to this authenticated learner."""


class SessionConflict(Exception):
    """The session is not in a state that accepts this action."""


class PassageNotFound(Exception):
    """No published passage is available for the selected grade."""


class InvalidRecording(Exception):
    """The recording metadata or storage key is invalid."""


class RecordingTooLarge(Exception):
    """The uploaded recording exceeds the configured size limit."""


class UnsupportedRecording(Exception):
    """The uploaded recording has an unsupported media type."""


class AnalysisServiceUnavailable(Exception):
    """The configured analysis service did not accept the recording."""


class MediaStorageUnavailable(Exception):
    """Media bucket configuration is missing or unavailable."""


class InvalidAnswers(Exception):
    """Submitted answers do not match the passage questions."""


class AttemptAlreadySubmitted(Exception):
    """The learner already submitted this comprehension attempt."""


class ResultNotReady(Exception):
    """The selected reading analysis is not ready to return."""


class MeService:
    """Implements Bearer-authenticated learner session workflows."""

    def __init__(self, repository: MeRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def start_session(
        self, learner_id: str, requested_grade_id: int | None
    ) -> StartSessionResponse:
        learner = self._repository.get_learner(learner_id)
        if learner is None:
            raise SessionNotFound
        passage_grade_id = requested_grade_id or int(learner["current_grade_id"])
        session = self._repository.assign_session(
            learner_id,
            passage_grade_id,
            self._settings.ASSIGNMENT_POLICY_VERSION,
        )
        if session is None:
            raise PassageNotFound
        passage_id = str(session["passage_id"])
        return StartSessionResponse(
            session_id=session["session_id"],
            status="assigned",
            passage={
                "id": passage_id,
                "title": session["title"],
                "text": session["content"],
                "wordCount": self._repository.count_passage_tokens(passage_id),
            },
        )

    def create_upload_url(
        self, learner_id: str, session_id: str, content_type: str
    ) -> UploadUrlResponse:
        session = self._get_owned_session(learner_id, session_id)
        if session["status"] not in {"assigned", "reading"}:
            raise SessionConflict
        if VIDEO_TYPE_PATTERN.fullmatch(content_type) is None:
            raise UnsupportedRecording
        if not self._settings.MEDIA_BUCKET_NAME:
            raise MediaStorageUnavailable

        media_subtype = content_type.split(";", 1)[0].lower().split("/", 1)[1]
        key = (
            f"recordings/{learner_id}/{session_id}/"
            f"{uuid.uuid4()}.{media_subtype}"
        )
        upload = make_upload_post(key, content_type)
        return UploadUrlResponse(
            storage_key=key,
            upload=upload,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )

    async def submit_recording(
        self,
        learner_id: str,
        session_id: str,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        duration_seconds: int,
    ) -> RecordingResponse:
        session = self._get_owned_session(learner_id, session_id)
        if session["status"] not in {"assigned", "reading"}:
            raise SessionConflict
        if not self._settings.MEDIA_BUCKET_NAME:
            raise MediaStorageUnavailable
        if not storage_key.startswith(f"recordings/{learner_id}/{session_id}/"):
            raise InvalidRecording
        if VIDEO_TYPE_PATTERN.fullmatch(content_type) is None:
            raise UnsupportedRecording
        extension = content_type.split(";", 1)[0].lower().split("/", 1)[1]
        if not storage_key.endswith(f".{extension}"):
            raise InvalidRecording
        if size_bytes > self._settings.MAX_UPLOAD_BYTES:
            raise RecordingTooLarge

        object_metadata = head_recording(storage_key)
        if object_metadata["size_bytes"] != size_bytes:
            raise RecordingTooLarge
        if object_metadata["content_type"] != content_type:
            raise UnsupportedRecording

        passage = self._repository.get_passage(str(session["passage_id"]))
        if passage is None:
            raise PassageNotFound
        if not self._settings.AI_ANALYSIS_URL or not self._settings.BACKEND_API_KEY:
            raise AnalysisServiceUnavailable

        media_url = make_download_url(storage_key)
        now = datetime.now(UTC)
        self._repository.update_session(
            learner_id,
            session_id,
            {
                "status": "processing",
                "session_timestamp": now - timedelta(seconds=duration_seconds),
                "processing_started_at": now,
            },
        )
        payload = {
            "session_id": session_id,
            "passage_id": str(session["passage_id"]),
            "storage_bucket": self._settings.MEDIA_BUCKET_NAME,
            "storage_key": storage_key,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "duration_seconds": duration_seconds,
            "media_url": media_url,
            "pipeline_version": self._settings.PIPELINE_VERSION,
            "scoring_policy_version": self._settings.SCORING_POLICY_VERSION,
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.AI_ANALYSIS_TIMEOUT_SECONDS),
                follow_redirects=False,
            ) as http:
                response = await http.post(
                    _analysis_endpoint(self._settings.AI_ANALYSIS_URL),
                    json=payload,
                    headers={"X-Backend-Key": self._settings.BACKEND_API_KEY},
                )
        except httpx.RequestError as exc:
            self._reset_session_for_retry(learner_id, session_id)
            logger.warning("Analysis service was unreachable for session %s", session_id)
            raise AnalysisServiceUnavailable from exc

        if response.status_code != 202:
            self._reset_session_for_retry(learner_id, session_id)
            logger.warning(
                "Analysis service rejected session %s with status %s",
                session_id,
                response.status_code,
            )
            raise AnalysisServiceUnavailable

        return RecordingResponse(session_id=session_id, status="processing")

    def get_session_status(
        self, learner_id: str, session_id: str
    ) -> SessionStatusResponse:
        session = self._get_owned_session(learner_id, session_id)
        analysis = self._repository.get_latest_analysis(session_id)
        attempt = self._repository.get_latest_attempt(session_id)

        analysis_status: str | None
        if session["status"] == "failed":
            analysis_status = "failed"
        elif analysis is None:
            analysis_status = (
                "running"
                if session["status"] in {"processing", "comprehension"}
                else None
            )
        elif analysis["status"] in {"completed", "partial", "failed"}:
            analysis_status = str(analysis["status"])
        else:
            analysis_status = "running"

        if analysis_status == "failed" and session["status"] != "failed":
            self._repository.update_session(
                learner_id, session_id, {"status": "failed"}
            )
            session["status"] = "failed"
        elif (
            analysis_status in {"completed", "partial"}
            and attempt is not None
            and attempt["status"] == "submitted"
            and session["status"] != "completed"
        ):
            self._repository.update_session(
                learner_id,
                session_id,
                {"status": "completed", "completed_at": datetime.now(UTC)},
            )
            session["status"] = "completed"

        return SessionStatusResponse(
            session_id=session_id,
            status=session["status"],
            analysis_status=analysis_status,
            comprehension_status=attempt["status"] if attempt is not None else None,
        )

    def get_questions(
        self, learner_id: str, session_id: str
    ) -> list[QuestionResponse]:
        session = self._get_owned_session(learner_id, session_id)
        questions = self._repository.list_questions(str(session["passage_id"]))
        return [
            QuestionResponse(
                id=question["question_id"],
                question=question["prompt"],
                options=[choice["choice_text"] for choice in question["choices"]],
            )
            for question in questions
        ]

    def submit_comprehension(
        self,
        learner_id: str,
        session_id: str,
        submitted_answers: list[dict[str, Any]],
    ) -> ComprehensionSubmissionResponse:
        session = self._get_owned_session(learner_id, session_id)
        if session["status"] in {"assigned", "reading", "failed", "completed"}:
            raise SessionConflict

        questions = self._repository.list_questions(str(session["passage_id"]))
        question_ids = {str(question["question_id"]) for question in questions}
        if not questions or len(submitted_answers) != len(questions):
            raise InvalidAnswers

        answer_ids = [str(answer["question_id"]) for answer in submitted_answers]
        if len(set(answer_ids)) != len(answer_ids) or set(answer_ids) != question_ids:
            raise InvalidAnswers

        question_by_id = {
            str(question["question_id"]): question for question in questions
        }
        rpc_answers: list[dict[str, Any]] = []
        for answer in submitted_answers:
            question_id = str(answer["question_id"])
            selected_choice_id: str | None = None
            choice = answer["choice"]
            if isinstance(choice, int):
                options = question_by_id[question_id]["choices"]
                if choice < 0 or choice >= len(options):
                    raise InvalidAnswers
                selected_choice_id = str(options[choice]["choice_id"])
            elif choice not in {None, "idk"}:
                raise InvalidAnswers
            rpc_answers.append(
                {
                    "question_id": question_id,
                    "selected_choice_id": selected_choice_id,
                }
            )

        try:
            score = self._repository.submit_comprehension(
                session_id, learner_id, rpc_answers
            )
        except Exception as exc:
            if "attempt already submitted" in str(exc).lower():
                raise AttemptAlreadySubmitted from exc
            raise

        analysis = self._repository.get_latest_analysis(session_id)
        analysis_status = analysis.get("status") if analysis is not None else None
        if analysis_status in {"completed", "partial"}:
            self._repository.update_session(
                learner_id,
                session_id,
                {"status": "completed", "completed_at": datetime.now(UTC)},
            )
        else:
            self._repository.update_session(
                learner_id, session_id, {"status": "comprehension"}
            )

        earned = Decimal(str(score["score_earned"]))
        possible = Decimal(str(score["score_possible"]))
        level = _comprehension_level(earned, possible)
        return ComprehensionSubmissionResponse(
            score_earned=float(earned),
            score_possible=float(possible),
            comprehension_level=level,
        )

    def get_result(self, learner_id: str, session_id: str) -> SessionResultResponse:
        session = self._get_owned_session(learner_id, session_id)
        passage = self._repository.get_passage(str(session["passage_id"]))
        analysis = self._repository.get_selected_analysis(session_id)
        if passage is None or analysis is None or analysis["status"] not in {
            "completed",
            "partial",
        }:
            raise ResultNotReady

        analysis_id = str(analysis["analysis_id"])
        events = self._repository.list_reading_events(analysis_id)
        tokens = self._repository.list_passage_tokens(str(session["passage_id"]))
        token_positions = {
            str(token["token_id"]): int(token["position"]) for token in tokens
        }
        tokens_by_position = {
            int(token["position"]): str(token["token_text"]) for token in tokens
        }

        counts = {event_type: 0 for event_type in ("correct", *MISCUE_TYPES)}
        details: dict[str, list[MiscueDetail]] = {}
        for event in events:
            event_type = event.get("reviewed_type") or event.get("detected_type")
            if event_type not in counts:
                continue
            counts[event_type] += 1
            if event_type == "correct":
                continue
            start = token_positions.get(str(event.get("expected_start_token_id")))
            end = token_positions.get(str(event.get("expected_end_token_id")))
            expected = ""
            if start is not None and end is not None and end >= start:
                expected = " ".join(
                    tokens_by_position[position]
                    for position in range(start, end + 1)
                    if position in tokens_by_position
                )
            details.setdefault(event_type, []).append(
                MiscueDetail(said=event.get("heard_text"), expected=expected)
            )

        observations = self._repository.list_behavior_observations(analysis_id)
        behavior_values: dict[str, bool | None] = {
            behavior_type: None for behavior_type in BEHAVIOR_TYPES
        }
        for observation in observations:
            observation_type = observation.get("type")
            if observation_type not in behavior_values:
                continue
            outcome = observation.get("outcome")
            behavior_values[observation_type] = (
                True
                if outcome == "detected"
                else False
                if outcome == "not_detected"
                else None
            )

        attempt = self._repository.get_latest_attempt(session_id)
        comprehension_level: int | None = None
        if attempt is not None and attempt.get("status") == "submitted":
            comprehension_level = _comprehension_level(
                Decimal(str(attempt["score_earned"])),
                Decimal(str(attempt["score_possible"])),
            )

        return SessionResultResponse(
            session_id=session_id,
            passage={"id": passage["passage_id"], "title": passage["title"]},
            wpm=_optional_float(analysis.get("wpm")),
            word_recognition_pct=_optional_float(analysis.get("word_recognition_pct")),
            reading_level=_capitalized_level(analysis.get("reading_level")),
            comprehension_level=comprehension_level,
            correct=counts["correct"],
            mispronunciation=counts["mispronunciation"],
            substitution=counts["substitution"],
            omission=counts["omission"],
            insertion=counts["insertion"],
            repetition=counts["repetition"],
            refusal_to_pronounce=counts["refusal_to_pronounce"],
            miscue_details=details,
            finger_pointing=behavior_values["finger_pointing"],
            loss_of_place=behavior_values["loss_of_place"],
            monotone_reading=behavior_values["monotone_reading"],
            word_by_word_reading=behavior_values["word_by_word_reading"],
            inaudible_reading=behavior_values["inaudible_reading"],
        )

    def _get_owned_session(self, learner_id: str, session_id: str) -> dict[str, Any]:
        session = self._repository.get_owned_session(learner_id, session_id)
        if session is None:
            raise SessionNotFound
        return session

    def _reset_session_for_retry(self, learner_id: str, session_id: str) -> None:
        self._repository.update_session(
            learner_id,
            session_id,
            {
                "status": "assigned",
                "session_timestamp": None,
                "processing_started_at": None,
            },
        )


def _analysis_endpoint(value: str) -> str:
    endpoint = value.rstrip("/")
    return endpoint if endpoint.endswith("/analyze") else f"{endpoint}/analyze"


def _comprehension_level(earned: Decimal, possible: Decimal) -> int:
    if possible <= 0:
        return 1
    percentage = earned * Decimal("100") / possible
    if percentage >= Decimal("80"):
        return 3
    if percentage >= Decimal("59"):
        return 2
    return 1


def _capitalized_level(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:1].upper() + value[1:].lower()


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None
