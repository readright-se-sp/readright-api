from supabase import Client

from app.features.shared.repository import SupabaseCrudRepository


class ServiceJobsRepository(SupabaseCrudRepository):
    """Persistence adapter for external-service job records."""

    def __init__(self, client: Client) -> None:
        super().__init__(client)

