import json
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config


@lru_cache(maxsize=1)
def _sqs_client() -> Any:
    return boto3.client(
        "sqs",
        config=Config(
            connect_timeout=2,
            read_timeout=5,
            retries={"total_max_attempts": 2, "mode": "standard"},
        ),
    )


def enqueue_analysis(
    queue_url: str,
    request_body: dict[str, Any],
    attempt_number: int,
) -> None:
    """Queue one MAI request; the worker owns all downstream processing."""
    _sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(
            {"attempt_number": attempt_number, "request": request_body},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )


def delay_analysis_retry(queue_url: str, receipt_handle: str, delay_seconds: int) -> None:
    """Set SQS visibility for a failed attempt so MAI Retry-After is respected."""
    _sqs_client().change_message_visibility(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
        VisibilityTimeout=max(1, min(delay_seconds, 43_200)),
    )
