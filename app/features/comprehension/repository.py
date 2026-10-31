from supabase import Client

from app.features.shared.repository import SupabaseCrudRepository


class ComprehensionRepository(SupabaseCrudRepository):
    """Persistence adapter for comprehension attempts and answers."""

    def __init__(self, client: Client) -> None:
        super().__init__(client)

