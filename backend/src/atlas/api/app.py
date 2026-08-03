from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.errors import register_error_handlers
from atlas.api.middleware import CorrelationIdMiddleware
from atlas.api.routes import health, platform
from atlas.core.config import Settings, get_settings
from atlas.core.persistence.database import DatabaseHealthProbe
from atlas.modules.platform.application.service import PlatformStatusService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    database_probe = DatabaseHealthProbe(resolved_settings)
    status_service = PlatformStatusService(
        service_name=resolved_settings.service_name,
        service_version=__version__,
        environment=resolved_settings.environment,
        probes=(database_probe,),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.platform_status_service = status_service
        yield
        await database_probe.close()

    app = FastAPI(
        title="Project Atlas API",
        version=__version__,
        docs_url="/docs" if resolved_settings.enable_api_docs else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in resolved_settings.cors_origins],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(platform.router, prefix="/api/v1")
    return app
