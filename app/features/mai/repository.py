from typing import Any

from supabase import Client


class MaiRepository:
    """Calls transaction-backed Supabase functions for MAI job persistence."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def start_analysis(
        self,
        request_id: str,
        request_sha256: str,
        request: dict[str, Any],
        service_name: str,
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "start_mai_analysis",
            {
                "p_request_id": request_id,
                "p_request_sha256": request_sha256,
                "p_request": request,
                "p_service_name": service_name,
            },
        ).execute()
        return _as_object(response.data)

    def claim_analysis(
        self, request_id: str, attempt_number: int, service_name: str
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "claim_mai_analysis",
            {
                "p_request_id": request_id,
                "p_attempt_number": attempt_number,
                "p_service_name": service_name,
            },
        ).execute()
        return _as_object(response.data)

    def release_analysis(
        self, request_id: str, attempt_number: int, retry_after_seconds: int
    ) -> None:
        self._client.rpc(
            "release_mai_analysis",
            {
                "p_request_id": request_id,
                "p_attempt_number": attempt_number,
                "p_retry_after_seconds": retry_after_seconds,
            },
        ).execute()

    def get_status(self, request_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table("service_jobs")
            .select("analysis_id, status, response_payload, failure_code, failure_message")
            .eq("idempotency_key", request_id)
            .eq("kind", "mai")
            .maybe_single()
            .execute()
        )
        return response.data if isinstance(response.data, dict) else None

    def complete_analysis(
        self, request_id: str, attempt_number: int, response_body: dict[str, Any]
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "complete_mai_analysis",
            {
                "p_request_id": request_id,
                "p_attempt_number": attempt_number,
                "p_response": response_body,
            },
        ).execute()
        return _as_object(response.data)

    def fail_analysis(
        self,
        request_id: str,
        attempt_number: int,
        status: str,
        failure_code: str,
        failure_message: str,
    ) -> None:
        self._client.rpc(
            "fail_mai_analysis",
            {
                "p_request_id": request_id,
                "p_attempt_number": attempt_number,
                "p_status": status,
                "p_failure_code": failure_code,
                "p_failure_message": failure_message,
            },
        ).execute()


def _as_object(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        value = value[0]
    if not isinstance(value, dict):
        raise RuntimeError("Supabase MAI persistence function returned an invalid result")
    return value
