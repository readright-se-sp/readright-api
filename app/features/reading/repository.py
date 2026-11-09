from supabase import Client

from app.features.shared.repository import SupabaseCrudRepository


class ReadingRepository(SupabaseCrudRepository):
    """Persistence adapter for reading sessions and assessment results."""

    def __init__(self, client: Client) -> None:
        super().__init__(client)

