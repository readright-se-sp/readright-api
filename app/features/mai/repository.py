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

    def complete_analysis(
        self, request_id: str, response_body: dict[str, Any]
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "complete_mai_analysis",
            {"p_request_id": request_id, "p_response": response_body},
        ).execute()
        return _as_object(response.data)

    def fail_analysis(
        self,
        request_id: str,
        status: str,
        failure_code: str,
        failure_message: str,
    ) -> None:
        self._client.rpc(
            "fail_mai_analysis",
            {
                "p_request_id": request_id,
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
