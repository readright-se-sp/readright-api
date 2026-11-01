import asyncio
import json
import logging
import time
from typing import Any

from app.config import get_settings
from app.dependencies.supabase import get_supabase_client, init_supabase_client
from app.features.mai.client import MaiServiceFailure, request_analysis
from app.features.mai.models import AnalysisRequest, AnalysisResponse
from app.features.mai.queue import delay_analysis_retry
from app.features.mai.repository import MaiRepository

logger = logging.getLogger(__name__)
MAX_RECEIVE_COUNT = 3


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    """Process queued MAI requests and report only messages needing retry."""
    del context
    init_supabase_client()
    repository = MaiRepository(get_supabase_client())
    settings = get_settings()
    failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        message_id = str(record.get("messageId", ""))
        receive_count = int(
            record.get("attributes", {}).get("ApproximateReceiveCount", "1")
        )
        try:
            should_retry = _process_record(
                record, repository, settings, receive_count
            )
            if should_retry:
                failures.append({"itemIdentifier": message_id})
        except Exception:
            logger.exception("MAI queue message processing failed")
            if receive_count >= MAX_RECEIVE_COUNT:
                try:
                    _fail_record_after_retries(record, repository)
                    continue
                except Exception:
                    logger.exception("Could not persist exhausted MAI retry for %s", message_id)
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}


def _process_record(
    record: dict[str, Any],
    repository: MaiRepository,
    settings: Any,
    receive_count: int,
) -> bool:
    envelope = json.loads(record["body"])
    attempt_number = int(envelope["attempt_number"])
    request = AnalysisRequest.model_validate(envelope["request"])
    request_id = str(request.request_id)

    claim = repository.claim_analysis(
        request_id, attempt_number, settings.MAI_SERVICE_NAME
    )
    if claim.get("state") in {"completed", "in_progress", "stale"}:
        return False
    if claim.get("state") != "started":
        raise RuntimeError("MAI worker received an invalid claim state")

    if not settings.MAI_API_KEY:
        _fail(
            repository,
            request_id,
            attempt_number,
            "failed",
            "SERVICE_UNAVAILABLE",
        )
        return False

    request_body = request.model_dump(mode="json", exclude_none=True)
    try:
        raw_response = asyncio.run(request_analysis(request_body, settings))
        AnalysisResponse.model_validate(raw_response)
    except MaiServiceFailure as exc:
        if exc.retryable and receive_count < MAX_RECEIVE_COUNT:
            retry_after = exc.retry_after_seconds
            if retry_after is None or retry_after < 1:
                retry_after = min(15 * (2 ** (receive_count - 1)), 300)
            attributes = record.get("attributes", {})
            sent_timestamp = int(attributes.get("SentTimestamp", "0"))
            if sent_timestamp:
                age_seconds = max(0, int(time.time() * 1000 - sent_timestamp) // 1000)
                remaining_retention = max(1, 3_600 - age_seconds - 5)
            else:
                remaining_retention = 3_300
            retry_delay = min(retry_after, 3_300, remaining_retention)
            repository.release_analysis(
                request_id, attempt_number, retry_delay
            )
            delay_analysis_retry(
                settings.MAI_QUEUE_URL,
                record["receiptHandle"],
                retry_delay,
            )
            return True
        job_status = "timed_out" if exc.code == "TIMEOUT" else "failed"
        _fail(repository, request_id, attempt_number, job_status, exc.code)
        return False

    repository.complete_analysis(request_id, attempt_number, raw_response)
    return False


def _fail(
    repository: MaiRepository,
    request_id: str,
    attempt_number: int,
    status_value: str,
    failure_code: str,
) -> None:
    repository.fail_analysis(
        request_id,
        attempt_number,
        status_value,
        failure_code,
        f"MAI request failed with {failure_code}; response details were not persisted.",
    )


def _fail_record_after_retries(
    record: dict[str, Any], repository: MaiRepository
) -> None:
    envelope = json.loads(record["body"])
    request = AnalysisRequest.model_validate(envelope["request"])
    request_id = str(request.request_id)
    attempt_number = int(envelope["attempt_number"])
    _fail(
        repository,
        request_id,
        attempt_number,
        "failed",
        "INTERNAL_ERROR",
    )
