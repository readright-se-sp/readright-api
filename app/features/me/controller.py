import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.config import Settings, get_settings
from app.dependencies.auth import AuthenticatedLearner, get_authenticated_learner
from app.dependencies.supabase import get_supabase_client
from app.features.me.models import (
    ComprehensionSubmissionRequest,
    ComprehensionSubmissionResponse,
    QuestionResponse,
    RecordingRequest,
    RecordingResponse,
    SessionResultResponse,
    SessionStatusResponse,
    StartSessionRequest,
    StartSessionResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.features.me.repository import MeRepository
from app.features.me.service import (
    AnalysisServiceUnavailable,
    AttemptAlreadySubmitted,
    InvalidAnswers,
    InvalidRecording,
    MeService,
    MediaStorageUnavailable,
    PassageNotFound,
    RecordingTooLarge,
    ResultNotReady,
    SessionConflict,
    SessionNotFound,
    UnsupportedRecording,
)

logger = logging.getLogger(__name__)


def get_me_service(
    client: Client = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> MeService:
    return MeService(MeRepository(client), settings)


class MeController:
    """Learner-facing reading, comprehension and results endpoints."""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/v1/me/sessions", tags=["learner sessions"])
        self.router.add_api_route(
            "",
            self.create_session,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=StartSessionResponse,
            responses={
                404: {"description": "No published passage exists for the requested grade."},
                422: {"description": "Invalid request or learner metadata."},
                503: {"description": "Session assignment is temporarily unavailable."},
            },
            summary="Assign a published passage to the authenticated learner",
        )
        self.router.add_api_route(
            "/{session_id}/upload-url",
            self.create_upload_url,
            methods=["POST"],
            response_model=UploadUrlResponse,
            responses={
                404: {"description": "Session not found for this learner."},
                409: {"description": "Session was already submitted."},
                415: {"description": "Unsupported video content type."},
                503: {"description": "S3 upload target could not be created."},
            },
            summary="Create a short-lived S3 upload target",
        )
        self.router.add_api_route(
            "/{session_id}/recording",
            self.submit_recording,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=RecordingResponse,
            responses={
                400: {"description": "Storage key does not belong to this learner and session."},
                404: {"description": "Session or uploaded S3 object not found."},
                409: {"description": "Session was already submitted."},
                413: {"description": "Uploaded recording size does not match or exceeds the limit."},
                415: {"description": "Uploaded content type does not match the signed type."},
                503: {"description": "Storage or analysis service is temporarily unavailable."},
            },
            summary="Confirm a recording upload and request its analysis",
        )
        self.router.add_api_route(
            "/{session_id}/questions",
            self.get_questions,
            methods=["GET"],
            response_model=list[QuestionResponse],
            responses={404: {"description": "Session not found for this learner."}},
            summary="Get comprehension questions without answer keys",
        )
        self.router.add_api_route(
            "/{session_id}/comprehension",
            self.submit_comprehension,
            methods=["POST"],
            response_model=ComprehensionSubmissionResponse,
            responses={
                404: {"description": "Session not found for this learner."},
                409: {"description": "Attempt already submitted or session is not ready."},
                422: {"description": "Answers do not match the passage questions."},
            },
            summary="Submit and score the learner's comprehension answers",
        )
        self.router.add_api_route(
            "/{session_id}/result",
            self.get_result,
            methods=["GET"],
            response_model=SessionResultResponse,
            responses={
                404: {"description": "Session not found for this learner."},
                409: {"description": "Selected reading result is not ready."},
            },
            summary="Get a completed reading result",
        )
        self.router.add_api_route(
            "/{session_id}",
            self.get_session_status,
            methods=["GET"],
            response_model=SessionStatusResponse,
            responses={404: {"description": "Session not found for this learner."}},
            summary="Get reading and comprehension processing status",
        )

    def create_session(
        self,
        payload: StartSessionRequest,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> StartSessionResponse:
        try:
            return service.start_session(learner.user_id, payload.passage_grade_id)
        except PassageNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No published passage is available for that grade",
            ) from exc
        except Exception as exc:
            _raise_service_unavailable("Could not assign a passage", exc)

    def create_upload_url(
        self,
        session_id: UUID,
        payload: UploadUrlRequest,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> UploadUrlResponse:
        try:
            return service.create_upload_url(
                learner.user_id, str(session_id), payload.content_type
            )
        except SessionNotFound as exc:
            raise _not_found() from exc
        except SessionConflict as exc:
            raise _conflict("The session has already been submitted") from exc
        except UnsupportedRecording as exc:
            raise _http_error(415, "Unsupported video content type") from exc
        except MediaStorageUnavailable as exc:
            raise _http_error(503, "Recording storage is not configured") from exc
        except Exception as exc:
            if _is_s3_client_error(exc):
                _raise_storage_unavailable(exc)
            _raise_service_unavailable("Could not create an upload target", exc)

    async def submit_recording(
        self,
        session_id: UUID,
        payload: RecordingRequest,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> RecordingResponse:
        try:
            return await service.submit_recording(
                learner_id=learner.user_id,
                session_id=str(session_id),
                storage_key=payload.storage_key,
                content_type=payload.content_type,
                size_bytes=payload.size_bytes,
                duration_seconds=payload.duration_seconds,
            )
        except SessionNotFound as exc:
            raise _not_found() from exc
        except SessionConflict as exc:
            raise _conflict("The session has already been submitted") from exc
        except InvalidRecording as exc:
            raise _http_error(400, "Recording metadata or storage key is invalid") from exc
        except RecordingTooLarge as exc:
            raise _http_error(413, "Recording size does not match or exceeds the limit") from exc
        except UnsupportedRecording as exc:
            raise _http_error(415, "Recording content type does not match the upload") from exc
        except PassageNotFound as exc:
            raise _not_found() from exc
        except AnalysisServiceUnavailable as exc:
            raise _http_error(503, "Analysis service is temporarily unavailable") from exc
        except MediaStorageUnavailable as exc:
            raise _http_error(503, "Recording storage is not configured") from exc
        except Exception as exc:
            if _is_s3_client_error(exc):
                _raise_storage_unavailable(exc)
            _raise_service_unavailable("Could not confirm the recording", exc)

    def get_questions(
        self,
        session_id: UUID,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> list[QuestionResponse]:
        try:
            return service.get_questions(learner.user_id, str(session_id))
        except SessionNotFound as exc:
            raise _not_found() from exc
        except Exception as exc:
            _raise_service_unavailable("Could not load comprehension questions", exc)

    def submit_comprehension(
        self,
        session_id: UUID,
        payload: ComprehensionSubmissionRequest,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> ComprehensionSubmissionResponse:
        try:
            answers = [answer.model_dump() for answer in payload.answers]
            return service.submit_comprehension(
                learner.user_id, str(session_id), answers
            )
        except SessionNotFound as exc:
            raise _not_found() from exc
        except SessionConflict as exc:
            raise _conflict("The session is not accepting comprehension answers") from exc
        except InvalidAnswers as exc:
            raise _http_error(422, "Answers do not match the passage questions") from exc
        except AttemptAlreadySubmitted as exc:
            raise _conflict("The comprehension attempt was already submitted") from exc
        except Exception as exc:
            _raise_service_unavailable("Could not submit comprehension answers", exc)

    def get_session_status(
        self,
        session_id: UUID,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> SessionStatusResponse:
        try:
            return service.get_session_status(learner.user_id, str(session_id))
        except SessionNotFound as exc:
            raise _not_found() from exc
        except Exception as exc:
            _raise_service_unavailable("Could not load session status", exc)

    def get_result(
        self,
        session_id: UUID,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: MeService = Depends(get_me_service),
    ) -> SessionResultResponse:
        try:
            return service.get_result(learner.user_id, str(session_id))
        except SessionNotFound as exc:
            raise _not_found() from exc
        except ResultNotReady as exc:
            raise _conflict("The reading result is not ready") from exc
        except Exception as exc:
            _raise_service_unavailable("Could not load reading result", exc)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Session not found",
    )


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _http_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _is_s3_client_error(exc: Exception) -> bool:
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return False
    return isinstance(exc, ClientError)


def _raise_storage_unavailable(exc: Exception) -> None:
    response = getattr(exc, "response", {})
    if not isinstance(response, dict):
        response = {}
    error = response.get("Error", {})
    metadata = response.get("ResponseMetadata", {})
    code = str(error.get("Code", ""))
    http_status = metadata.get("HTTPStatusCode")
    if http_status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording upload was not found in storage",
        ) from exc
    logger.exception("S3 operation failed", exc_info=exc)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Recording storage is temporarily unavailable",
    ) from exc


def _raise_service_unavailable(message: str, exc: Exception) -> None:
    logger.exception(message, exc_info=exc)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Service is temporarily unavailable",
    ) from exc
