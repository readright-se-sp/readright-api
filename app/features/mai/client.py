import asyncio
from typing import Any

import httpx

from app.config import Settings
from app.features.mai.models import AnalysisResponse, ErrorResponse


class MaiServiceFailure(Exception):
    """A validated MAI API error response or transport timeout."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


async def request_analysis(
    request_body: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    endpoint = f"{settings.MAI_BASE_URL.rstrip('/')}/analyses"
    request_id = request_body["request_id"]
    timeout = httpx.Timeout(
        connect=settings.MAI_CONNECT_TIMEOUT_SECONDS,
        read=settings.MAI_READ_TIMEOUT_SECONDS,
        write=10.0,
        pool=5.0,
    )
    retry_timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
    retry_deadline: float | None = None

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as http:
            while True:
                active_timeout = retry_timeout if retry_deadline is not None else timeout
                response = await http.post(
                    endpoint,
                    json=request_body,
                    headers={"X-API-Key": settings.MAI_API_KEY},
                    timeout=active_timeout,
                )

                if response.status_code == 200:
                    raw_response = response.json()
                    result = AnalysisResponse.model_validate(raw_response)
                    if str(result.request_id) != request_id:
                        raise MaiServiceFailure(
                            502,
                            "PROCESSING_FAILED",
                            "MAI response request_id did not match the request.",
                            retryable=True,
                        )
                    return raw_response

                code, message = _parse_error(response)
                if code == "REQUEST_IN_PROGRESS":
                    if retry_deadline is None:
                        retry_deadline = asyncio.get_running_loop().time() + 110.0
                    if asyncio.get_running_loop().time() < retry_deadline:
                        await asyncio.sleep(3.0)
                        continue
                raise MaiServiceFailure(
                    response.status_code,
                    code,
                    message,
                    retryable=(
                        response.status_code in {429, 500, 503, 504}
                        or code == "REQUEST_IN_PROGRESS"
                    ),
                    retry_after_seconds=_retry_after_seconds(
                        response.headers.get("Retry-After")
                    ),
                )
    except httpx.TimeoutException as exc:
        raise MaiServiceFailure(
            504,
            "TIMEOUT",
            "MAI did not return within its response window.",
            retryable=True,
        ) from exc
    except httpx.RequestError as exc:
        raise MaiServiceFailure(
            503,
            "SERVICE_UNAVAILABLE",
            "The MAI service could not be reached.",
            retryable=True,
        ) from exc
    except (ValueError, TypeError) as exc:
        raise MaiServiceFailure(
            502,
            "PROCESSING_FAILED",
            "MAI returned a response outside its contract.",
            retryable=True,
        ) from exc


def _parse_error(response: httpx.Response) -> tuple[str, str]:
    try:
        parsed = ErrorResponse.model_validate(response.json())
        return parsed.error.code, parsed.error.message
    except Exception:
        code = "SERVICE_UNAVAILABLE" if response.status_code == 503 else "INTERNAL_ERROR"
        message = "MAI returned an invalid error response."
        return code, message


def _retry_after_seconds(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    return int(value)
