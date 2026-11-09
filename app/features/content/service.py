from fastapi import Depends
from supabase import Client

from app.dependencies.supabase import get_supabase_client
from app.features.content.repository import ContentRepository
from app.features.shared.service import ResourceCrudService


def get_content_service(
    client: Client = Depends(get_supabase_client),
) -> ResourceCrudService:
    return ResourceCrudService(ContentRepository(client))

