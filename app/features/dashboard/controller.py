import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.dependencies.supabase import get_supabase_client
from app.features.dashboard.models import LearnerDashboard
from app.features.dashboard.repository import DashboardRepository
from app.features.dashboard.service import (
    DashboardDataUnavailable,
    DashboardService,
    LearnerProfileNotFound,
)

logger = logging.getLogger(__name__)
bearer_auth = HTTPBearer(auto_error=False)


def authenticated_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
    client: Client = Depends(get_supabase_client),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = client.auth.get_user(credentials.credentials)
        if response is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return str(response.user.id)
    except HTTPException:
        raise
    except Exception as exc:
        response_status = getattr(exc, "status", None) or getattr(
            exc, "status_code", None
        )
        if str(response_status) in {"400", "401", "403"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        logger.exception("Supabase access-token verification failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from exc


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
        learner_id: str = Depends(authenticated_user_id),
        service: DashboardService = Depends(get_dashboard_service),
    ) -> LearnerDashboard:
        try:
            return service.get_dashboard(learner_id)
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
