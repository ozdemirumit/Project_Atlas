from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.errors import register_error_handlers
from atlas.api.middleware import CorrelationIdMiddleware
from atlas.api.routes import (
    ai,
    approvals,
    graph,
    health,
    health_checks,
    identity,
    investigations,
    platform,
    rca,
    recommendations,
    reports,
    security_export,
    sessions,
    storage,
)
from atlas.core.audit import AuditSink, LoggingAuditSink
from atlas.core.classification import DataClassification
from atlas.core.config import Settings, get_settings
from atlas.core.persistence.database import DatabaseHealthProbe
from atlas.modules.ai.adapters.openai_compatible import OpenAICompatibleTransport
from atlas.modules.ai.adapters.synthetic import SyntheticOpenAICompatibleTransport
from atlas.modules.ai.application.gateway import ModelGateway
from atlas.modules.ai.application.ports import ModelTransport
from atlas.modules.ai.application.service import GroundedAnswerService
from atlas.modules.ai.domain.models import (
    EndpointLifecycle,
    EvaluationStatus,
    ModelEndpointProfile,
    TaskClass,
)
from atlas.modules.approvals.application.service import ApprovalService
from atlas.modules.authorization.application.bootstrap import (
    build_development_authorization_service,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.graph.adapters.synthetic import build_synthetic_graph_snapshot
from atlas.modules.graph.application.engine import InMemoryGraphImpactAnalyzer
from atlas.modules.graph.application.service import GraphImpactService
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
    build_synthetic_latest_runs,
)
from atlas.modules.health_checks.application.service import HealthCheckService
from atlas.modules.identity.adapters.development import DevelopmentIdentityProvider
from atlas.modules.identity.adapters.directory import build_directory_identity_provider
from atlas.modules.identity.adapters.sessions import InMemorySessionRepository
from atlas.modules.identity.application.ports import IdentityProvider
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionService
from atlas.modules.investigations.adapters.synthetic import SyntheticInvestigationAssembler
from atlas.modules.investigations.application.service import InvestigationService
from atlas.modules.knowledge.adapters.memory import InMemoryKnowledgeRetriever
from atlas.modules.knowledge.adapters.synthetic import build_synthetic_knowledge_chunks
from atlas.modules.knowledge.application.service import KnowledgeRetrievalService
from atlas.modules.platform.application.service import PlatformStatusService
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import RcaService
from atlas.modules.recommendations.adapters.synthetic import (
    SyntheticStorageRecommendationAssembler,
)
from atlas.modules.recommendations.application.service import RecommendationService
from atlas.modules.reports.adapters.synthetic import SyntheticTechnicalReportAssembler
from atlas.modules.reports.application.service import ReportService
from atlas.modules.security_export.adapters.synthetic import (
    SyntheticTlsSyslogTransport,
    build_synthetic_syslog_destinations,
)
from atlas.modules.security_export.application.service import SecurityExportService
from atlas.modules.storage.adapters.synthetic import build_synthetic_storage_overview
from atlas.modules.storage.application.service import StorageOperationsService


def create_app(
    settings: Settings | None = None,
    *,
    audit_sink: AuditSink | None = None,
    identity_provider: IdentityProvider | None = None,
    authorization_service: AuthorizationService | None = None,
    storage_operations_service: StorageOperationsService | None = None,
    graph_impact_service: GraphImpactService | None = None,
    health_check_service: HealthCheckService | None = None,
    investigation_service: InvestigationService | None = None,
    rca_service: RcaService | None = None,
    recommendation_service: RecommendationService | None = None,
    approval_service: ApprovalService | None = None,
    report_service: ReportService | None = None,
    grounded_answer_service: GroundedAnswerService | None = None,
    security_export_service: SecurityExportService | None = None,
    session_service: SessionService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    base_audit_sink = audit_sink or LoggingAuditSink(resolved_settings.logger)
    resolved_security_export_service = security_export_service or SecurityExportService(
        delegate=base_audit_sink,
        destinations=build_synthetic_syslog_destinations(),
        transport=SyntheticTlsSyslogTransport(),
        environment_id=f"environment.{resolved_settings.environment}",
        site_id="site.local",
    )
    resolved_audit_sink: AuditSink = resolved_security_export_service
    if identity_provider is not None:
        resolved_identity_provider = identity_provider
    elif resolved_settings.directory_identity_enabled:
        resolved_identity_provider = build_directory_identity_provider(resolved_settings)
    else:
        resolved_identity_provider = DevelopmentIdentityProvider(resolved_settings)
    identity_service = IdentityService(
        provider=resolved_identity_provider,
        audit_sink=resolved_audit_sink,
    )
    resolved_session_service = session_service or SessionService(
        identity_service=identity_service,
        repository=InMemorySessionRepository(),
        audit_sink=resolved_audit_sink,
        absolute_timeout=timedelta(minutes=resolved_settings.session_absolute_timeout_minutes),
        idle_timeout=timedelta(minutes=resolved_settings.session_idle_timeout_minutes),
        max_sessions_per_subject=resolved_settings.session_max_per_subject,
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
    resolved_graph_impact_service = graph_impact_service or GraphImpactService(
        analyzer=InMemoryGraphImpactAnalyzer(
            snapshot=build_synthetic_graph_snapshot(
                organization_id=resolved_settings.development_organization_id,
                environment=resolved_settings.environment,
            )
        ),
        audit_sink=resolved_audit_sink,
    )
    health_check_definitions = build_synthetic_health_check_definitions(
        organization_id=resolved_settings.development_organization_id,
        environment=resolved_settings.environment,
    )
    resolved_health_check_service = health_check_service or HealthCheckService(
        definitions=health_check_definitions,
        latest_runs=build_synthetic_latest_runs(health_check_definitions),
        executor=SyntheticStorageHealthExecutor(),
        audit_sink=resolved_audit_sink,
    )
    resolved_investigation_service = investigation_service or InvestigationService(
        assembler=SyntheticInvestigationAssembler(),
        audit_sink=resolved_audit_sink,
    )
    resolved_rca_service = rca_service or RcaService(
        assembler=SyntheticStorageRcaAssembler(),
        audit_sink=resolved_audit_sink,
    )
    resolved_recommendation_service = recommendation_service or RecommendationService(
        source_provider=resolved_rca_service,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=resolved_audit_sink,
    )
    resolved_report_service = report_service or ReportService(
        source_provider=resolved_recommendation_service,
        assembler=SyntheticTechnicalReportAssembler(),
        audit_sink=resolved_audit_sink,
    )
    resolved_approval_service = approval_service or ApprovalService(
        recommendation_provider=resolved_recommendation_service,
        audit_sink=resolved_audit_sink,
    )
    synthetic_model_id = "atlas-local-synthetic"
    model_transport: ModelTransport
    if resolved_settings.local_model_enabled:
        assert resolved_settings.local_model_base_url is not None
        assert resolved_settings.local_model_id is not None
        assert resolved_settings.local_model_reader_token is not None
        model_id = resolved_settings.local_model_id
        model_base_url = str(resolved_settings.local_model_base_url).rstrip("/")
        model_secret_reference = resolved_settings.local_model_secret_reference_id
        model_transport = OpenAICompatibleTransport(
            bearer_token=resolved_settings.local_model_reader_token.get_secret_value()
        )
        model_data_profile = "configured_local_model"
        model_endpoint_id = "endpoint.model.configured-local"
    else:
        model_id = synthetic_model_id
        model_base_url = "http://127.0.0.1:11434/v1"
        model_secret_reference = "secret.model.synthetic-reader"
        model_transport = SyntheticOpenAICompatibleTransport()
        model_data_profile = "synthetic_lab"
        model_endpoint_id = "endpoint.model.synthetic-local"
    resolved_grounded_answer_service = grounded_answer_service or GroundedAnswerService(
        retrieval_service=KnowledgeRetrievalService(
            retriever=InMemoryKnowledgeRetriever(
                chunks=build_synthetic_knowledge_chunks(
                    organization_id=resolved_settings.development_organization_id,
                    environment=resolved_settings.environment,
                )
            ),
            audit_sink=resolved_audit_sink,
        ),
        model_gateway=ModelGateway(
            endpoint=ModelEndpointProfile(
                endpoint_id=model_endpoint_id,
                owner="Project Atlas development",
                provider_type="openai_compatible",
                base_url=model_base_url,
                secret_reference_id=model_secret_reference,
                approved_model_ids=frozenset({model_id}),
                approved_task_classes=frozenset({TaskClass.GROUNDED_ANSWER}),
                classification_ceiling=DataClassification.INTERNAL,
                network_boundary="development-loopback",
                max_context_characters=32_000,
                max_output_tokens=1024,
                timeout_seconds=10.0,
                lifecycle=EndpointLifecycle.ACTIVE,
                evaluation_status=EvaluationStatus.APPROVED,
            ),
            transport=model_transport,
        ),
        audit_sink=resolved_audit_sink,
        model_id=model_id,
        data_profile=model_data_profile,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.audit_sink = resolved_audit_sink
        app.state.security_export_service = resolved_security_export_service
        app.state.identity_service = identity_service
        app.state.session_service = resolved_session_service
        app.state.authorization_service = resolved_authorization_service
        app.state.platform_status_service = status_service
        app.state.storage_operations_service = resolved_storage_operations_service
        app.state.graph_impact_service = resolved_graph_impact_service
        app.state.health_check_service = resolved_health_check_service
        app.state.investigation_service = resolved_investigation_service
        app.state.rca_service = resolved_rca_service
        app.state.recommendation_service = resolved_recommendation_service
        app.state.approval_service = resolved_approval_service
        app.state.report_service = resolved_report_service
        app.state.grounded_answer_service = resolved_grounded_answer_service
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
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "Idempotency-Key",
            resolved_settings.csrf_header_name,
        ],
        expose_headers=["X-Correlation-ID", resolved_settings.csrf_header_name],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(identity.router, prefix="/api/v1")
    app.include_router(platform.router, prefix="/api/v1")
    app.include_router(storage.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(health_checks.router, prefix="/api/v1")
    app.include_router(investigations.router, prefix="/api/v1")
    app.include_router(rca.router, prefix="/api/v1")
    app.include_router(recommendations.router, prefix="/api/v1")
    app.include_router(approvals.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(ai.router, prefix="/api/v1")
    app.include_router(security_export.router, prefix="/api/v1")
    return app
