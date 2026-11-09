import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.dependencies.supabase import get_supabase_client, init_supabase_client
from app.features.me.repository import MeRepository

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    """Mark sessions processing longer than the configured limit as failed."""
    del event, context
    init_supabase_client()
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.PROCESSING_TIMEOUT_MINUTES)
    expired = MeRepository(get_supabase_client()).expire_processing_sessions(
        cutoff.isoformat()
    )
    if expired:
        logger.warning("Marked %s stuck reading sessions as failed", len(expired))
    return {"timed_out_sessions": len(expired)}
