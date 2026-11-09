import asyncio
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from supabase import Client

from app.config import Settings, get_settings
from app.dependencies.backend_key import require_backend_key
from app.dependencies.supabase import get_supabase_client
from app.features.mai.client import MaiServiceFailure, request_analysis
from app.features.mai.models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatus,
    AnalysisSubmission,
    ErrorResponse,
)
from app.features.mai.repository import MaiRepository

logger = logging.getLogger(__name__)


class MaiController:
    """Runs MAI requests synchronously and exposes their persisted status."""

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
            status_code=200,
            response_model=AnalysisResponse | AnalysisSubmission,
            responses={
                202: {
                    "model": AnalysisSubmission,
                    "description": "The same request is already running.",
                },
                400: {"model": ErrorResponse, "description": "Malformed or mismatched request."},
                409: {
                    "model": ErrorResponse,
                    "description": "MAI reports this request is still in progress.",
                },
                422: {
                    "model": ErrorResponse,
                    "description": "MAI could not process the supplied media.",
                },
                503: {
                    "model": ErrorResponse,
                    "description": "MAI or analysis storage unavailable.",
                },
                504: {
                    "model": ErrorResponse,
                    "description": "MAI did not respond before the configured timeout.",
                },
                502: {
                    "model": ErrorResponse,
                    "description": "MAI returned an invalid or unexpected response.",
                },
            },
            summary="Submit an MAI analysis",
            description=(
                "Calls MAI synchronously and returns the validated result. If the same "
                "request is already running, returns 202 with a status_url."
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

        if start.get("state") == "in_progress":
            return _accepted_response(request_id)

        if start.get("state") not in {"started", "dispatching"}:
            logger.error("Unexpected MAI start state for %s", request_id)
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "MAI processing could not be started."
            )

        attempt_number = int(start.get("attempt_number", 0))
        if not settings.MAI_API_KEY:
            await _record_failure(
                repository,
                request_id,
                attempt_number,
                "SERVICE_UNAVAILABLE",
                "MAI_API_KEY is not configured.",
            )
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "MAI integration is not configured."
            )

        try:
            claim = await asyncio.to_thread(
                repository.claim_analysis,
                request_id,
                attempt_number,
                settings.MAI_SERVICE_NAME,
            )
        except Exception:
            logger.exception("Could not claim MAI analysis %s", request_id)
            await _record_failure(
                repository,
                request_id,
                attempt_number,
                "SERVICE_UNAVAILABLE",
                "MAI analysis could not be claimed for processing.",
            )
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "Analysis storage is temporarily unavailable."
            )

        claim_state = claim.get("state")
        if claim_state == "completed":
            stored_response = claim.get("response")
            try:
                AnalysisResponse.model_validate(stored_response)
                return JSONResponse(status_code=200, content=stored_response)
            except Exception:
                logger.exception("Stored MAI response is invalid for %s", request_id)
                return _error_response(
                    500, "INTERNAL_ERROR", "The stored analysis response is invalid."
                )
        if claim_state == "in_progress":
            return _accepted_response(request_id)
        if claim_state != "started":
            logger.error(
                "Unexpected MAI claim state for %s: %s", request_id, claim_state
            )
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "MAI processing could not be started."
            )

        try:
            response_body = await request_analysis(request_body, settings)
        except MaiServiceFailure as exc:
            failure_status = "timed_out" if exc.code == "TIMEOUT" else "failed"
            await _record_failure(
                repository,
                request_id,
                attempt_number,
                exc.code,
                f"MAI request failed with {exc.code}; response details were not persisted.",
                status_value=failure_status,
            )
            logger.warning("MAI analysis failed for %s with %s", request_id, exc.code)
            return _error_response(_mai_http_status(exc), exc.code, exc.message)
        except Exception:
            logger.exception("Unexpected MAI failure for %s", request_id)
            await _record_failure(
                repository,
                request_id,
                attempt_number,
                "INTERNAL_ERROR",
                "MAI request failed unexpectedly.",
            )
            return _error_response(
                502, "INTERNAL_ERROR", "MAI returned an unexpected response."
            )

        try:
            await asyncio.to_thread(
                repository.complete_analysis,
                request_id,
                attempt_number,
                response_body,
            )
        except Exception:
            logger.exception("Could not persist MAI result for %s", request_id)
            await _record_failure(
                repository,
                request_id,
                attempt_number,
                "SERVICE_UNAVAILABLE",
                "MAI completed, but its result could not be saved.",
            )
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "The MAI result could not be saved."
            )

        return JSONResponse(status_code=200, content=response_body)

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
    *,
    status_value: str = "failed",
) -> None:
    try:
        await asyncio.to_thread(
            repository.fail_analysis,
            request_id,
            attempt_number,
            status_value,
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


def _mai_http_status(exc: MaiServiceFailure) -> int:
    if exc.code == "TIMEOUT":
        return 504
    if exc.code in {"SERVICE_UNAVAILABLE", "RATE_LIMITED"}:
        return 503
    if exc.code == "REQUEST_IN_PROGRESS":
        return 409
    if exc.code == "INVALID_REQUEST":
        return 400
    if exc.code in {
        "VIDEO_DOWNLOAD_FAILED",
        "VIDEO_URL_EXPIRED",
        "UNSUPPORTED_MEDIA",
        "NO_SPEECH_DETECTED",
    }:
        return 422
    return 502


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
