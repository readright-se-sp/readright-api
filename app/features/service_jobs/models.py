from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.features.shared.models import ResourceDefinition

SERVICE_JOBS = ResourceDefinition(
    model_name="ServiceJob",
    slug="service-jobs",
    table="service_jobs",
    primary_key="service_job_id",
    field_types={
        "session_id": UUID,
        "analysis_id": UUID,
        "input_recording_id": UUID,
        "kind": Literal["asr", "vision", "prosody", "pronunciation"],
        "service_name": str,
        "attempt_number": int,
        "is_current": bool,
        "required_for_completion": bool,
        "status": Literal[
            "pending", "dispatching", "running", "succeeded", "failed", "timed_out", "cancelled"
        ],
        "external_job_id": str | None,
        "request_schema_version": str,
        "result_schema_version": str | None,
        "model_version": str | None,
        "request_sha256": str,
        "response_payload": Any,
        "failure_code": str | None,
        "failure_message": str | None,
        "started_at": datetime | None,
        "deadline_at": datetime | None,
        "lease_expires_at": datetime | None,
        "finished_at": datetime | None,
    },
    create_fields=(
        "session_id",
        "analysis_id",
        "input_recording_id",
        "kind",
        "service_name",
        "attempt_number",
        "is_current",
        "required_for_completion",
        "status",
        "external_job_id",
        "request_schema_version",
        "result_schema_version",
        "model_version",
        "request_sha256",
        "response_payload",
        "failure_code",
        "failure_message",
        "started_at",
        "deadline_at",
        "lease_expires_at",
        "finished_at",
    ),
    required_create_fields=(
        "session_id",
        "analysis_id",
        "input_recording_id",
        "kind",
        "service_name",
        "attempt_number",
        "required_for_completion",
        "request_schema_version",
        "request_sha256",
    ),
    update_fields=(
        "is_current",
        "status",
        "external_job_id",
        "result_schema_version",
        "model_version",
        "response_payload",
        "failure_code",
        "failure_message",
        "started_at",
        "deadline_at",
        "lease_expires_at",
        "finished_at",
    ),
)

RESOURCES = (("/jobs", SERVICE_JOBS),)

