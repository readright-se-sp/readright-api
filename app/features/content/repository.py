from supabase import Client

from app.features.shared.repository import SupabaseCrudRepository


class ContentRepository(SupabaseCrudRepository):
    """Persistence adapter for passages, tokens, questions, and choices."""

    def __init__(self, client: Client) -> None:
        super().__init__(client)

