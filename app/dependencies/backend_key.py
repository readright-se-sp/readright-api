import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_backend_key(
    backend_key: str | None = Header(default=None, alias="X-Backend-Key"),
) -> None:
    """Restrict full-table CRUD to trusted server-side callers."""
    expected_key = get_settings().BACKEND_API_KEY
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend CRUD access is not configured",
        )
    if backend_key is None or not secrets.compare_digest(backend_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid X-Backend-Key header required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

