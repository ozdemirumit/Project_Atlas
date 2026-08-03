from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.errors import register_error_handlers
from atlas.api.middleware import CorrelationIdMiddleware
from atlas.api.routes import health, identity, platform, storage
from atlas.core.audit import AuditSink, LoggingAuditSink
from atlas.core.config import Settings, get_settings
from atlas.core.persistence.database import DatabaseHealthProbe
from atlas.modules.authorization.application.bootstrap import (
    build_development_authorization_service,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.identity.adapters.development import DevelopmentIdentityProvider
from atlas.modules.identity.application.ports import IdentityProvider
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.platform.application.service import PlatformStatusService
from atlas.modules.storage.adapters.synthetic import build_synthetic_storage_overview
from atlas.modules.storage.application.service import StorageOperationsService


def create_app(
    settings: Settings | None = None,
    *,
    audit_sink: AuditSink | None = None,
    identity_provider: IdentityProvider | None = None,
    authorization_service: AuthorizationService | None = None,
    storage_operations_service: StorageOperationsService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_audit_sink = audit_sink or LoggingAuditSink(resolved_settings.logger)
    resolved_identity_provider = identity_provider or DevelopmentIdentityProvider(resolved_settings)
    identity_service = IdentityService(
        provider=resolved_identity_provider,
        audit_sink=resolved_audit_sink,
    )
    resolved_authorization_service = (
        authorization_service
        or build_development_authorization_service(resolved_settings, resolved_audit_sink)
    )
    database_probe = DatabaseHealthProbe(resolved_settings)
    status_service = PlatformStatusService(
        service_name=resolved_settings.service_name,
        service_version=__version__,
        environment=resolved_settings.environment,
        probes=(database_probe,),
    )
    resolved_storage_operations_service = storage_operations_service or StorageOperationsService(
        overview=build_synthetic_storage_overview(
            organization_id=resolved_settings.development_organization_id,
            environment=resolved_settings.environment,
        ),
        audit_sink=resolved_audit_sink,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.audit_sink = resolved_audit_sink
        app.state.identity_service = identity_service
        app.state.authorization_service = resolved_authorization_service
        app.state.platform_status_service = status_service
        app.state.storage_operations_service = resolved_storage_operations_service
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
        allow_headers=["Accept", "Authorization", "Content-Type", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(identity.router, prefix="/api/v1")
    app.include_router(platform.router, prefix="/api/v1")
    app.include_router(storage.router, prefix="/api/v1")
    return app
