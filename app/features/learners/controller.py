from fastapi import APIRouter, Depends

from app.dependencies.backend_key import require_backend_key
from app.features.learners.models import RESOURCES
from app.features.learners.service import get_learners_service
from app.features.shared.controller import register_crud_routes


class LearnersController:
    """CRUD routes for learner profiles and grade levels."""

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1/identity",
            tags=["identity"],
            dependencies=[Depends(require_backend_key)],
        )
        for path, resource in RESOURCES:
            register_crud_routes(self.router, path, resource, get_learners_service)

