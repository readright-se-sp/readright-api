from fastapi import Depends
from supabase import Client

from app.dependencies.supabase import get_supabase_client
from app.features.service_jobs.repository import ServiceJobsRepository
from app.features.shared.service import ResourceCrudService


def get_service_jobs_service(
    client: Client = Depends(get_supabase_client),
) -> ResourceCrudService:
    return ResourceCrudService(ServiceJobsRepository(client))

