from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.dependencies.auth import AuthenticatedLearner, get_authenticated_learner
from app.dependencies.supabase import get_supabase_client
from app.features.dashboard.models import LearnerDashboard
from app.features.dashboard.repository import DashboardRepository
from app.features.dashboard.service import (
    DashboardDataUnavailable,
    DashboardService,
    LearnerProfileNotFound,
)

def get_dashboard_service(
    client: Client = Depends(get_supabase_client),
) -> DashboardService:
    return DashboardService(DashboardRepository(client))


class DashboardController:
    """HTTP controller for the learner dashboard feature."""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])
        self.router.add_api_route(
            "",
            self.get_dashboard,
            methods=["GET"],
            response_model=LearnerDashboard,
        )

    def get_dashboard(
        self,
        learner: AuthenticatedLearner = Depends(get_authenticated_learner),
        service: DashboardService = Depends(get_dashboard_service),
    ) -> LearnerDashboard:
        try:
            return service.get_dashboard(learner.user_id)
        except LearnerProfileNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found",
            ) from exc
        except DashboardDataUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dashboard data is unavailable",
            ) from exc
