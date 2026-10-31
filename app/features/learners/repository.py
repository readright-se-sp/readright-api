from supabase import Client

from app.features.shared.repository import SupabaseCrudRepository


class LearnersRepository(SupabaseCrudRepository):
    """Persistence adapter for learner and grade-level records."""

    def __init__(self, client: Client) -> None:
        super().__init__(client)

