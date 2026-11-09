from fastapi import Depends
from supabase import Client

from app.dependencies.supabase import get_supabase_client
from app.features.reading.repository import ReadingRepository
from app.features.shared.service import ResourceCrudService


def get_reading_service(
    client: Client = Depends(get_supabase_client),
) -> ResourceCrudService:
    return ResourceCrudService(ReadingRepository(client))

