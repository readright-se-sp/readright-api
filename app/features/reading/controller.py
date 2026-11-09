from fastapi import APIRouter, Depends

from app.dependencies.backend_key import require_backend_key
from app.features.reading.models import RESOURCES
from app.features.reading.service import get_reading_service
from app.features.shared.controller import register_crud_routes


class ReadingController:
    """CRUD routes for sessions, recordings, and reading evidence."""

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1/reading",
            tags=["reading"],
            dependencies=[Depends(require_backend_key)],
        )
        for path, resource in RESOURCES:
            register_crud_routes(self.router, path, resource, get_reading_service)

