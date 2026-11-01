import asyncio
import hashlib
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from supabase import Client

from app.config import Settings, get_settings
from app.dependencies.backend_key import require_backend_key
from app.dependencies.supabase import get_supabase_client
from app.features.mai.models import AnalysisRequest, AnalysisResponse, ErrorResponse
from app.features.mai.repository import MaiRepository

logger = logging.getLogger(__name__)


class MaiController:
    """Runs MAI synchronously and stores its response as one database transaction."""

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
            response_model=AnalysisResponse,
            responses={
                400: {"model": ErrorResponse, "description": "Malformed MAI request."},
                401: {"model": ErrorResponse, "description": "MAI API key rejected."},
                409: {"model": ErrorResponse, "description": "Request is already in progress."},
                415: {"model": ErrorResponse, "description": "Unsupported media."},
                422: {"model": ErrorResponse, "description": "Recording cannot be analyzed."},
                429: {"model": ErrorResponse, "description": "MAI capacity limit."},
                500: {"model": ErrorResponse, "description": "MAI processing failed."},
                503: {"model": ErrorResponse, "description": "MAI unavailable."},
                504: {"model": ErrorResponse, "description": "MAI timeout."},
            },
            summary="Run a synchronous MAI analysis",
            description=(
                "Calls the configured MAI service and atomically persists its result. "
                "Use the Lambda Function URL for this route; API Gateway HTTP APIs "
                "cannot keep the connection open for the MAI 120-second SLA."
            ),
        )

    async def create_analysis(
        self,
        payload: AnalysisRequest,
        client: Client = Depends(get_supabase_client),
        settings: Settings = Depends(get_settings),
    ) -> AnalysisResponse | JSONResponse:
        if not settings.MAI_API_KEY:
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "MAI integration is not configured."
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
        if start.get("state") == "in_progress":
            return _error_response(
                409,
                "REQUEST_IN_PROGRESS",
                "An analysis with this request ID is still in progress.",
                retry_after="2",
            )

        endpoint = f"{settings.MAI_BASE_URL.rstrip('/')}/analyses"
        timeout = httpx.Timeout(
            connect=settings.MAI_CONNECT_TIMEOUT_SECONDS,
            read=settings.MAI_READ_TIMEOUT_SECONDS,
            write=10.0,
            pool=5.0,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as http:
                upstream = await http.post(
                    endpoint,
                    json=request_body,
                    headers={"X-API-Key": settings.MAI_API_KEY},
                )
        except httpx.TimeoutException:
            await _record_failure(
                repository,
                request_id,
                "timed_out",
                "TIMEOUT",
                "MAI response exceeded the client timeout.",
            )
            return _error_response(
                504, "TIMEOUT", "MAI did not return within the allowed response window."
            )
        except httpx.RequestError:
            await _record_failure(
                repository,
                request_id,
                "failed",
                "SERVICE_UNAVAILABLE",
                "The MAI service could not be reached.",
            )
            return _error_response(
                503, "SERVICE_UNAVAILABLE", "The MAI service is temporarily unavailable."
            )

        if upstream.status_code == 200:
            try:
                raw_result = upstream.json()
                result = AnalysisResponse.model_validate(raw_result)
                if result.request_id != payload.request_id:
                    raise ValueError("MAI response request_id does not match")
            except Exception:
                logger.exception("MAI returned an invalid result for %s", request_id)
                await _record_failure(
                    repository,
                    request_id,
                    "failed",
                    "PROCESSING_FAILED",
                    "MAI response did not match the configured contract.",
                )
                return _error_response(
                    502, "INTERNAL_ERROR", "MAI returned a response that does not match its contract."
                )
            try:
                persisted = await asyncio.to_thread(
                    repository.complete_analysis,
                    request_id,
                    raw_result,
                )
                AnalysisResponse.model_validate(persisted)
                return JSONResponse(status_code=200, content=persisted)
            except Exception:
                # The database call may have committed before its response was
                # interrupted. Leave the job untouched; a retry reads the
                # idempotently stored response if the commit succeeded.
                logger.exception("Could not persist MAI result for %s", request_id)
                return _error_response(
                    503, "SERVICE_UNAVAILABLE", "The analysis result could not be confirmed in storage."
                )

        try:
            error = ErrorResponse.model_validate(upstream.json())
            body = error.model_dump(mode="json", exclude_none=True)
            code = error.error.code
        except Exception:
            code = "SERVICE_UNAVAILABLE" if upstream.status_code == 503 else "INTERNAL_ERROR"
            body = {
                "error": {
                    "code": code,
                    "message": "MAI returned an invalid error response.",
                }
            }

        failure_status = "timed_out" if code == "TIMEOUT" else "failed"
        await _record_failure(
            repository,
            request_id,
            failure_status,
            code,
            f"MAI request failed with {code}; response details were not persisted.",
        )
        if upstream.status_code not in {400, 401, 409, 415, 422, 429, 500, 503, 504}:
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "INTERNAL_ERROR", "message": "MAI returned an unexpected HTTP status."}},
            )

        headers: dict[str, str] = {}
        retry_after = upstream.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            headers["Retry-After"] = retry_after
        return JSONResponse(status_code=upstream.status_code, content=body, headers=headers)


def _logical_request_hash(request: dict[str, Any]) -> str:
    # A presigned URL is a short-lived capability. Exclude it so refreshing the
    # URL for an idempotent retry does not create a different logical request.
    logical_request = {key: value for key, value in request.items() if key != "video_url"}
    canonical = json.dumps(
        logical_request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _record_failure(
    repository: MaiRepository,
    request_id: str,
    status_value: str,
    failure_code: str,
    failure_message: str,
) -> None:
    try:
        await asyncio.to_thread(
            repository.fail_analysis,
            request_id,
            status_value,
            failure_code,
            failure_message,
        )
    except Exception:
        logger.exception("Could not persist MAI failure for %s", request_id)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    retry_after: str | None = None,
) -> JSONResponse:
    headers = {"Retry-After": retry_after} if retry_after else None
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
        headers=headers,
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
