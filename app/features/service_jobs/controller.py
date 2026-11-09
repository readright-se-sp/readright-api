from fastapi import APIRouter, Depends

from app.dependencies.backend_key import require_backend_key
from app.features.service_jobs.models import RESOURCES
from app.features.service_jobs.service import get_service_jobs_service
from app.features.shared.controller import register_crud_routes


class ServiceJobsController:
    """CRUD routes for service attempts and callback results."""

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1/services",
            tags=["services"],
            dependencies=[Depends(require_backend_key)],
        )
        for path, resource in RESOURCES:
            register_crud_routes(
                self.router, path, resource, get_service_jobs_service
            )

