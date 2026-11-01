import asyncio
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from botocore.exceptions import BotoCoreError
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from supabase import Client

from app.config import Settings, get_settings
from app.dependencies.backend_key import require_backend_key
from app.dependencies.supabase import get_supabase_client
from app.features.mai.models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatus,
    AnalysisSubmission,
    ErrorResponse,
)
from app.features.mai.queue import enqueue_analysis
from app.features.mai.repository import MaiRepository

logger = logging.getLogger(__name__)


class MaiController:
    """Accepts MAI work asynchronously and exposes its persisted status."""

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1/mai",
            tags=["MAI"],
            dependencies=[Depends(require_backend_key)],
        )
        self.router.add_api_route(
            "/analyses",
            self.create_analysis,
            methods=["POST"],
            status_code=202,
            response_model=AnalysisResponse | AnalysisSubmission,
            responses={
                200: {"model": AnalysisResponse, "description": "Previously completed result."},
                202: {"model": AnalysisSubmission, "description": "Accepted for background processing."},
                400: {"model": ErrorResponse, "description": "Malformed or mismatched request."},
                503: {"model": ErrorResponse, "description": "Queue or analysis storage unavailable."},
            },
            summary="Submit an MAI analysis",
            description=(
                "Queues the MAI request and returns 202. Poll the returned status_url "
                "for the result. The worker calls MAI synchronously and persists the "
                "validated result."
            ),
        )
        self.router.add_api_route(
            "/analyses/{request_id}",
            self.get_analysis_status,
            methods=["GET"],
            response_model=AnalysisStatus,
            responses={
                404: {"model": ErrorResponse, "description": "Unknown request ID."},
                503: {"model": ErrorResponse, "description": "Analysis storage unavailable."},
            },
            summary="Get MAI analysis status",
        )

    async def create_analysis(
        self,
        payload: AnalysisRequest,
        client: Client = Depends(get_supabase_client),
        settings: Settings = Depends(get_settings),
    ) -> AnalysisResponse | AnalysisSubmission | JSONResponse:
        if not settings.MAI_QUEUE_URL:
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "MAI background processing is not configured."
            )

        request_id = str(payload.request_id)
        request_body = payload.model_dump(mode="json", exclude_none=True)
        request_hash = _logical_request_hash(request_body)
        persistence_request = {
            "request_id": request_body["request_id"],
            "passage_title": request_body["passage_title"],
            "passage_content": request_body["passage_content"],
        }
        repository = MaiRepository(client)

        try:
            start = await asyncio.to_thread(
                repository.start_analysis,
                request_id,
                request_hash,
                persistence_request,
                settings.MAI_SERVICE_NAME,
            )
        except Exception as exc:
            logger.warning("MAI analysis could not start for %s", request_id)
            if _is_request_conflict(exc):
                return _error_response(
                    400,
                    "INVALID_REQUEST",
                    "The request ID is already used, or the passage does not match this analysis.",
                )
            logger.exception("Supabase could not start MAI analysis %s", request_id)
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "Analysis storage is temporarily unavailable."
            )

        if start.get("state") == "completed":
            try:
                stored_response = start.get("response")
                AnalysisResponse.model_validate(stored_response)
                return JSONResponse(status_code=200, content=stored_response)
            except Exception:
                logger.exception("Stored MAI response is invalid for %s", request_id)
                return _error_response(
                    500, "INTERNAL_ERROR", "The stored analysis response is invalid."
                )

        attempt_number = int(start.get("attempt_number", 0))
        if start.get("state") in {"started", "dispatching"}:
            try:
                await asyncio.to_thread(
                    enqueue_analysis,
                    settings.MAI_QUEUE_URL,
                    request_body,
                    attempt_number,
                )
            except BotoCoreError:
                logger.exception("Could not queue MAI analysis %s", request_id)
                await _record_failure(
                    repository,
                    request_id,
                    attempt_number,
                    "SERVICE_UNAVAILABLE",
                    "MAI request could not be placed on the processing queue.",
                )
                return _error_response(
                    503, "SERVICE_UNAVAILABLE", "MAI processing could not be queued."
                )

        if start.get("state") in {"started", "dispatching", "in_progress"}:
            return _accepted_response(request_id)

        logger.error("Unexpected MAI start state for %s", request_id)
        return _error_response(
            503, "SERVICE_UNAVAILABLE", "MAI processing could not be started."
        )

    async def get_analysis_status(
        self,
        request_id: UUID,
        client: Client = Depends(get_supabase_client),
    ) -> AnalysisStatus | JSONResponse:
        try:
            record = await asyncio.to_thread(
                MaiRepository(client).get_status, str(request_id)
            )
        except Exception:
            logger.exception("Could not read MAI status for %s", request_id)
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "Analysis storage is temporarily unavailable."
            )
        if record is None:
            return _error_response(404, "INVALID_REQUEST", "Unknown MAI request_id.")

        job_status = record.get("status")
        if job_status in {"pending", "dispatching"}:
            result: dict[str, Any] = {
                "request_id": str(request_id),
                "status": "queued",
            }
        elif job_status == "running":
            result = {"request_id": str(request_id), "status": "running"}
        elif job_status == "succeeded":
            stored_response = record.get("response_payload")
            try:
                AnalysisResponse.model_validate(stored_response)
            except Exception:
                logger.exception("Stored MAI response is invalid for %s", request_id)
                return _error_response(
                    500, "INTERNAL_ERROR", "The stored analysis response is invalid."
                )
            result = {
                "request_id": str(request_id),
                "status": "completed",
                "result": stored_response,
            }
        else:
            failure_code = record.get("failure_code") or "PROCESSING_FAILED"
            if failure_code not in {
                "INVALID_REQUEST",
                "VIDEO_DOWNLOAD_FAILED",
                "VIDEO_URL_EXPIRED",
                "UNSUPPORTED_MEDIA",
                "NO_SPEECH_DETECTED",
                "REQUEST_IN_PROGRESS",
                "RATE_LIMITED",
                "TIMEOUT",
                "PROCESSING_FAILED",
                "UPLOAD_FAILED",
                "SERVICE_UNAVAILABLE",
                "INTERNAL_ERROR",
            }:
                failure_code = "INTERNAL_ERROR"
            result = {
                "request_id": str(request_id),
                "status": "failed",
                "error": {
                    "code": failure_code,
                    "message": record.get("failure_message") or "MAI analysis failed.",
                },
            }
        return JSONResponse(status_code=200, content=result)


def _logical_request_hash(request: dict[str, Any]) -> str:
    # Do not include the short-lived video URL in the durable request hash.
    logical_request = {key: value for key, value in request.items() if key != "video_url"}
    canonical = json.dumps(
        logical_request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _record_failure(
    repository: MaiRepository,
    request_id: str,
    attempt_number: int,
    failure_code: str,
    failure_message: str,
) -> None:
    try:
        await asyncio.to_thread(
            repository.fail_analysis,
            request_id,
            attempt_number,
            "failed",
            failure_code,
            failure_message,
        )
    except Exception:
        logger.exception("Could not persist MAI failure for %s", request_id)


def _accepted_response(request_id: str) -> JSONResponse:
    status_url = f"/v1/mai/analyses/{request_id}"
    return JSONResponse(
        status_code=202,
        content={"request_id": request_id, "status": "accepted", "status_url": status_url},
        headers={"Location": status_url, "Retry-After": "2"},
    )


def _error_response(
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _exception_text(exc: Exception) -> str:
    return str(getattr(exc, "message", exc)).lower()


def _is_request_conflict(exc: Exception) -> bool:
    message = _exception_text(exc)
    return any(
        text in message
        for text in (
            "does not match a reading analysis",
            "request_id does not match the reading analysis",
            "requires the analysis source recording to be video",
            "selected analysis cannot be rerun through mai",
            "does not match the analysis passage",
            "requires a fresh analysis without other service results",
            "already used for a different request",
        )
    )
