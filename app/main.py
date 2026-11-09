import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dependencies.supabase import init_supabase_client
from app.features.comprehension import ComprehensionController
from app.features.content import ContentController
from app.features.dashboard import DashboardController
from app.features.learners import LearnersController
from app.features.me import MeController
from app.features.mai.controller import MaiController
from app.features.reading import ReadingController
from app.features.service_jobs import ServiceJobsController
from app.routers.health import HealthController


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize optional backend clients at startup."""
    await asyncio.to_thread(init_supabase_client)
    yield


def create_app() -> FastAPI:
    """Create the ReadRight backend application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )

    settings = get_settings()
    app = FastAPI(title="ReadRight Backend API", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if request.url.path == "/v1/mai/analyses":
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": "Request body does not match the MAI analysis contract.",
                    }
                },
            )
        return await request_validation_exception_handler(request, exc)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(HealthController().router)
    app.include_router(DashboardController().router)
    app.include_router(MeController().router)
    app.include_router(LearnersController().router)
    app.include_router(ContentController().router)
    app.include_router(ReadingController().router)
    app.include_router(MaiController().router)
    app.include_router(ServiceJobsController().router)
    app.include_router(ComprehensionController().router)
    return app


app = create_app()
