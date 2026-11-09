from fastapi import APIRouter, Depends

from app.dependencies.backend_key import require_backend_key
from app.features.comprehension.models import RESOURCES
from app.features.comprehension.service import get_comprehension_service
from app.features.shared.controller import register_crud_routes


class ComprehensionController:
    """CRUD routes for comprehension attempts and submitted answers."""

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1/comprehension",
            tags=["comprehension"],
            dependencies=[Depends(require_backend_key)],
        )
        for path, resource in RESOURCES:
            register_crud_routes(
                self.router, path, resource, get_comprehension_service
            )

