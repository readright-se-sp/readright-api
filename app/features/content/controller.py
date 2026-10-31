from fastapi import APIRouter, Depends

from app.dependencies.backend_key import require_backend_key
from app.features.content.models import RESOURCES
from app.features.content.service import get_content_service
from app.features.shared.controller import register_crud_routes


class ContentController:
    """CRUD routes for passages and their assessment content."""

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1/content",
            tags=["content"],
            dependencies=[Depends(require_backend_key)],
        )
        for path, resource in RESOURCES:
            register_crud_routes(self.router, path, resource, get_content_service)

