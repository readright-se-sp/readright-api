import logging
import re
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.dependencies.supabase import get_supabase_client

logger = logging.getLogger(__name__)
bearer_auth = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedLearner:
    """A Supabase-authenticated user with a persisted learner profile."""

    user_id: str
    current_grade_id: int


def get_authenticated_learner(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
    client: Client = Depends(get_supabase_client),
) -> AuthenticatedLearner:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = client.auth.get_user(credentials.credentials)
        user = getattr(response, "user", None)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        response_status = getattr(exc, "status", None) or getattr(
            exc, "status_code", None
        )
        if str(response_status) in {"400", "401", "403"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        logger.exception("Supabase access-token verification failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from exc

    user_id = str(user.id)
    try:
        profile = _load_learner(client, user_id)
        if profile is None:
            profile = _create_learner_from_metadata(
                client,
                user_id,
                getattr(user, "user_metadata", None),
            )
        return AuthenticatedLearner(
            user_id=user_id,
            current_grade_id=int(profile["current_grade_id"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load or create learner profile for %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Learner profile is temporarily unavailable",
        ) from exc


def _load_learner(client: Client, user_id: str) -> dict[str, Any] | None:
    response = (
        client.table("learners")
        .select("user_id,current_grade_id")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return response.data if isinstance(response.data, dict) else None


def _create_learner_from_metadata(
    client: Client, user_id: str, metadata: Any
) -> dict[str, Any]:
    user_metadata = metadata if isinstance(metadata, dict) else {}
    grade_id = _metadata_grade_id(user_metadata.get("grade_level"))
    if grade_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Learner profile is missing a valid grade_level in user metadata",
        )

    grade_response = (
        client.table("grade_levels")
        .select("grade_id")
        .eq("grade_id", grade_id)
        .maybe_single()
        .execute()
    )
    if not isinstance(grade_response.data, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Learner grade is not configured",
        )

    display_name = user_metadata.get("display_name")
    if not isinstance(display_name, str):
        display_name = None

    learner = {
        "user_id": user_id,
        "current_grade_id": grade_id,
        "display_name": display_name,
    }
    try:
        created = client.table("learners").insert(learner).execute()
        if isinstance(created.data, list) and created.data:
            return created.data[0]
        if isinstance(created.data, dict):
            return created.data
    except Exception:
        # A concurrent first request may have inserted this row already.
        existing = _load_learner(client, user_id)
        if existing is not None:
            return existing
        raise

    existing = _load_learner(client, user_id)
    if existing is not None:
        return existing
    raise RuntimeError("Learner insert returned no row")


def _metadata_grade_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match is not None:
            return int(match.group())
    return None
