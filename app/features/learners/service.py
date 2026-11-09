from fastapi import Depends
from supabase import Client

from app.dependencies.supabase import get_supabase_client
from app.features.learners.repository import LearnersRepository
from app.features.shared.service import ResourceCrudService


def get_learners_service(
    client: Client = Depends(get_supabase_client),
) -> ResourceCrudService:
    return ResourceCrudService(LearnersRepository(client))

