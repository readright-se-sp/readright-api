import asyncio
import hashlib
import json
import logging
from typing import Any

from app.config import Settings
from app.features.mai.client import MaiServiceFailure, request_analysis
from app.features.mai.models import AnalysisRequest
from app.features.mai.repository import MaiRepository

logger = logging.getLogger(__name__)


class MaiAnalysisInProgress(Exception):
    """The logical MAI request already has an active service job."""


async def run_inline_analysis(
    request: dict[str, Any], repository: MaiRepository, settings: Settings
) -> dict[str, Any]:
    """Run one MAI request and persist its service job and result."""
    request_body = AnalysisRequest.model_validate(request).model_dump(
        mode="json", exclude_none=True
    )
    request_id = str(request_body["request_id"])
    logical_request = {
        key: value for key, value in request_body.items() if key != "video_url"
    }
    canonical = json.dumps(
        logical_request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    start = await asyncio.to_thread(
        repository.start_analysis,
        request_id,
        request_hash,
        request_body,
        settings.MAI_SERVICE_NAME,
    )
    if start.get("state") == "completed":
        return start["response"]
    if start.get("state") in {"in_progress", "dispatching"}:
        raise MaiAnalysisInProgress
    if start.get("state") != "started":
        raise RuntimeError("MAI returned an invalid start state")

    attempt_number = int(start["attempt_number"])
    if not settings.MAI_API_KEY:
        await _record_failure(
            repository,
            request_id,
            attempt_number,
            "failed",
            "SERVICE_UNAVAILABLE",
            "MAI_API_KEY is not configured.",
        )
        raise MaiServiceFailure(
            503,
            "SERVICE_UNAVAILABLE",
            "MAI integration is not configured.",
        )

    claim = await asyncio.to_thread(
        repository.claim_analysis,
        request_id,
        attempt_number,
        settings.MAI_SERVICE_NAME,
    )
    if claim.get("state") == "completed":
        return claim["response"]
    if claim.get("state") == "in_progress":
        raise MaiAnalysisInProgress
    if claim.get("state") != "started":
        raise RuntimeError("MAI returned an invalid claim state")

    try:
        response_body = await request_analysis(request_body, settings)
    except MaiServiceFailure as exc:
        await _record_failure(
            repository,
            request_id,
            attempt_number,
            "timed_out" if exc.code == "TIMEOUT" else "failed",
            exc.code,
            f"MAI request failed with {exc.code}; response details were not persisted.",
        )
        raise

    try:
        await asyncio.to_thread(
            repository.complete_analysis,
            request_id,
            attempt_number,
            response_body,
        )
    except Exception as exc:
        logger.exception("Could not persist MAI result for %s", request_id)
        await _record_failure(
            repository,
            request_id,
            attempt_number,
            "failed",
            "SERVICE_UNAVAILABLE",
            "MAI completed, but its result could not be saved.",
        )
        raise MaiServiceFailure(
            503,
            "SERVICE_UNAVAILABLE",
            "The MAI result could not be saved.",
        ) from exc
    return response_body


async def _record_failure(
    repository: MaiRepository,
    request_id: str,
    attempt_number: int,
    status: str,
    failure_code: str,
    message: str,
) -> None:
    try:
        await asyncio.to_thread(
            repository.fail_analysis,
            request_id,
            attempt_number,
            status,
            failure_code,
            message,
        )
    except Exception:
        logger.exception("Could not persist MAI failure for %s", request_id)
