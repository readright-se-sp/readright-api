from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import get_settings

_client: Client | None = None


def init_supabase_client() -> None:
    """Initialize the shared Supabase client when credentials are configured."""
    global _client
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def get_supabase_client() -> Client:
    """FastAPI dependency for routes that require Supabase access."""
    if _client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured",
        )
    return _client
