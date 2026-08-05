from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from hashlib import sha256

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.errors import register_error_handlers
from atlas.api.middleware import ApiCredentialNoStoreMiddleware, CorrelationIdMiddleware
from atlas.api.routes import (
    ai,
    api_credentials,
    approvals,
    audit_export,
    bootstrap_artifacts,
    bootstrap_configuration,
    bootstrap_data,
    bootstrap_handoff,
    bootstrap_identity,
    bootstrap_integrations,
    bootstrap_invalidation,
    bootstrap_plan,
    bootstrap_services,
    bootstrap_state,
    bootstrap_trust,
    bootstrap_verification,
    change_reviews,
    deployment_configuration,
    graph,
    health,
    health_checks,
    identity,
    identity_governance,
    investigations,
    mcp_builder,
    platform,
    rca,
    recommendations,
    recovery,
    release_preflight,
    reports,
    security_export,
    sessions,
    storage,
    support_bundles,
    upgrades,
    workload_identities,
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
from atlas.modules.change_review.adapters.completion_receipt_memory import (
    InMemoryCompletionReceiptRepository,
)
from atlas.modules.change_review.adapters.completion_receipt_postgres import (
    PostgreSQLCompletionReceiptRepository,
)
from atlas.modules.change_review.adapters.human_review_memory import (
    InMemoryHumanReviewRepository,
)
from atlas.modules.change_review.adapters.human_review_postgres import (
    PostgreSQLHumanReviewRepository,
)
from atlas.modules.change_review.adapters.memory import InMemoryChangeReviewPacketRepository
from atlas.modules.change_review.adapters.postgres import (
    PostgreSQLChangeReviewPacketRepository,
)
from atlas.modules.change_review.application.completion_receipt_service import (
    CompletionReceiptService,
)
from atlas.modules.change_review.application.human_review_service import HumanReviewService
from atlas.modules.change_review.application.service import ChangeReviewService
from atlas.modules.graph.adapters.synthetic import build_synthetic_graph_snapshot
from atlas.modules.graph.application.engine import InMemoryGraphImpactAnalyzer
from atlas.modules.graph.application.service import GraphImpactService
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
    build_synthetic_latest_runs,
)
from atlas.modules.health_checks.application.service import HealthCheckService
from atlas.modules.identity.adapters.api_credentials import InMemoryApiCredentialRepository
from atlas.modules.identity.adapters.development import DevelopmentIdentityProvider
from atlas.modules.identity.adapters.directory import build_directory_identity_provider
from atlas.modules.identity.adapters.identity_status import InMemoryIdentityStatusRepository
from atlas.modules.identity.adapters.sessions import InMemorySessionRepository
from atlas.modules.identity.adapters.workload_identities import (
    InMemoryWorkloadIdentityRepository,
)
from atlas.modules.identity.application.api_credentials import ApiCredentialService
from atlas.modules.identity.application.governance import IdentityGovernanceService
from atlas.modules.identity.application.identity_status_ports import IdentityStatusRepository
from atlas.modules.identity.application.ports import IdentityProvider
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionService
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.investigations.adapters.synthetic import SyntheticInvestigationAssembler
from atlas.modules.investigations.application.service import InvestigationService
from atlas.modules.knowledge.adapters.memory import InMemoryKnowledgeRetriever
from atlas.modules.knowledge.adapters.synthetic import build_synthetic_knowledge_chunks
from atlas.modules.knowledge.application.service import KnowledgeRetrievalService
from atlas.modules.mcp_builder.adapters.design_review_memory import (
    InMemoryMcpBuilderDesignCheckpointRepository,
)
from atlas.modules.mcp_builder.adapters.design_review_postgres import (
    PostgreSQLMcpBuilderDesignCheckpointRepository,
)
from atlas.modules.mcp_builder.adapters.memory import InMemoryMcpBuilderProjectRepository
from atlas.modules.mcp_builder.adapters.postgres import PostgreSQLMcpBuilderProjectRepository
from atlas.modules.mcp_builder.application.service import McpBuilderService
from atlas.modules.platform.adapters.bootstrap_artifact_filesystem import (
    FileSystemReleaseArtifactPublisher,
    MemoryArtifactContentSource,
)
from atlas.modules.platform.adapters.bootstrap_configuration_filesystem import (
    FilesystemEffectiveConfigurationPublisher,
)
from atlas.modules.platform.adapters.bootstrap_data_filesystem import FilesystemBootstrapDataTarget
from atlas.modules.platform.adapters.bootstrap_data_synthetic import SyntheticBootstrapDataCatalog
from atlas.modules.platform.adapters.bootstrap_handoff_filesystem import (
    FilesystemBootstrapHandoffTarget,
)
from atlas.modules.platform.adapters.bootstrap_identity_filesystem import (
    FilesystemBootstrapIdentityTarget,
)
from atlas.modules.platform.adapters.bootstrap_identity_synthetic import (
    SyntheticBootstrapIdentityCatalog,
)
from atlas.modules.platform.adapters.bootstrap_integrations_filesystem import (
    FilesystemBootstrapIntegrationTarget,
)
from atlas.modules.platform.adapters.bootstrap_integrations_synthetic import (
    SyntheticBootstrapIntegrationCatalog,
)
from atlas.modules.platform.adapters.bootstrap_services_filesystem import (
    FilesystemBootstrapServiceTarget,
)
from atlas.modules.platform.adapters.bootstrap_services_synthetic import (
    SyntheticBootstrapServiceCatalog,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_trust_filesystem import (
    FilesystemBootstrapTrustPublisher,
)
from atlas.modules.platform.adapters.bootstrap_trust_synthetic import SyntheticBootstrapTrustSource
from atlas.modules.platform.adapters.bootstrap_verification_filesystem import (
    FilesystemBootstrapVerificationTarget,
)
from atlas.modules.platform.adapters.release_preflight import (
    SYNTHETIC_ARTIFACT_CONTENT,
    LabHmacReleaseSignatureVerifier,
    SyntheticPreflightHostProbe,
    SyntheticReleaseArtifactInventory,
    build_synthetic_release_manifest,
)
from atlas.modules.platform.application.bootstrap_artifact_acquisition import (
    BootstrapArtifactAcquisitionService,
)
from atlas.modules.platform.application.bootstrap_configuration_rendering import (
    BootstrapConfigurationRenderingService,
)
from atlas.modules.platform.application.bootstrap_data_initialization import (
    BootstrapDataInitializationService,
    BootstrapDataPlanService,
)
from atlas.modules.platform.application.bootstrap_end_to_end_verification import (
    BootstrapEndToEndVerificationService,
    BootstrapVerificationPlanService,
)
from atlas.modules.platform.application.bootstrap_identity_handoff import (
    BootstrapIdentityHandoffService,
    BootstrapIdentityPlanService,
)
from atlas.modules.platform.application.bootstrap_integration_validation import (
    BootstrapIntegrationPlanService,
    BootstrapIntegrationValidationService,
)
from atlas.modules.platform.application.bootstrap_invalidation import BootstrapInvalidationService
from atlas.modules.platform.application.bootstrap_operational_handoff import (
    BootstrapHandoffPlanService,
    BootstrapOperationalHandoffService,
)
from atlas.modules.platform.application.bootstrap_plan import BootstrapPlanService
from atlas.modules.platform.application.bootstrap_service_deployment import (
    BootstrapServiceDeploymentService,
    BootstrapServicePlanService,
)
from atlas.modules.platform.application.bootstrap_state import BootstrapStateService
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
    BootstrapTrustProvisioningService,
)
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.application.release_preflight import ReleasePreflightService
from atlas.modules.platform.application.service import PlatformStatusService
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import RcaService
from atlas.modules.recommendations.adapters.synthetic import (
    SyntheticStorageRecommendationAssembler,
)
from atlas.modules.recommendations.application.service import RecommendationService
from atlas.modules.recovery.adapters.filesystem import FilesystemBackupArchiveStore
from atlas.modules.recovery.adapters.memory import InMemoryRecoveryRepository
from atlas.modules.recovery.adapters.postgres import PostgreSQLRecoveryRepository
from atlas.modules.recovery.application.service import RecoveryService
from atlas.modules.reports.adapters.synthetic import SyntheticTechnicalReportAssembler
from atlas.modules.reports.application.service import ReportService
from atlas.modules.security_export.adapters.synthetic import (
    SyntheticTlsSyslogTransport,
    build_synthetic_syslog_destinations,
)
from atlas.modules.security_export.application.service import SecurityExportService
from atlas.modules.storage.adapters.synthetic import build_synthetic_storage_overview
from atlas.modules.storage.application.service import StorageOperationsService
from atlas.modules.support.adapters.filesystem import FilesystemSupportBundlePublisher
from atlas.modules.support.adapters.memory import InMemorySupportBundleExportRepository
from atlas.modules.support.adapters.postgres import PostgreSQLSupportBundleExportRepository
from atlas.modules.support.application.service import SupportBundleService
from atlas.modules.upgrade.adapters.memory import InMemoryUpgradeSimulationRepository
from atlas.modules.upgrade.adapters.postgres import PostgreSQLUpgradeSimulationRepository
from atlas.modules.upgrade.application.service import UpgradeService


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
    api_credential_service: ApiCredentialService | None = None,
    identity_governance_service: IdentityGovernanceService | None = None,
    identity_status_repository: IdentityStatusRepository | None = None,
    workload_identity_service: WorkloadIdentityService | None = None,
    release_preflight_service: ReleasePreflightService | None = None,
    deployment_configuration_service: DeploymentConfigurationService | None = None,
    bootstrap_plan_service: BootstrapPlanService | None = None,
    bootstrap_state_service: BootstrapStateService | None = None,
    bootstrap_invalidation_service: BootstrapInvalidationService | None = None,
    bootstrap_artifact_acquisition_service: BootstrapArtifactAcquisitionService | None = None,
    bootstrap_configuration_rendering_service: BootstrapConfigurationRenderingService | None = None,
    bootstrap_trust_plan_service: BootstrapTrustPlanService | None = None,
    bootstrap_trust_provisioning_service: BootstrapTrustProvisioningService | None = None,
    bootstrap_data_plan_service: BootstrapDataPlanService | None = None,
    bootstrap_data_initialization_service: BootstrapDataInitializationService | None = None,
    bootstrap_service_plan_service: BootstrapServicePlanService | None = None,
    bootstrap_service_deployment_service: BootstrapServiceDeploymentService | None = None,
    bootstrap_identity_plan_service: BootstrapIdentityPlanService | None = None,
    bootstrap_identity_handoff_service: BootstrapIdentityHandoffService | None = None,
    bootstrap_integration_plan_service: BootstrapIntegrationPlanService | None = None,
    bootstrap_integration_validation_service: BootstrapIntegrationValidationService | None = None,
    bootstrap_verification_plan_service: BootstrapVerificationPlanService | None = None,
    bootstrap_end_to_end_verification_service: BootstrapEndToEndVerificationService | None = None,
    bootstrap_handoff_plan_service: BootstrapHandoffPlanService | None = None,
    bootstrap_operational_handoff_service: BootstrapOperationalHandoffService | None = None,
    support_bundle_service: SupportBundleService | None = None,
    recovery_service: RecoveryService | None = None,
    upgrade_service: UpgradeService | None = None,
    change_review_service: ChangeReviewService | None = None,
    human_review_service: HumanReviewService | None = None,
    completion_receipt_service: CompletionReceiptService | None = None,
    mcp_builder_service: McpBuilderService | None = None,
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
    resolved_identity_status_repository = (
        identity_status_repository or InMemoryIdentityStatusRepository()
    )
    identity_service = IdentityService(
        provider=resolved_identity_provider,
        audit_sink=resolved_audit_sink,
        status_repository=resolved_identity_status_repository,
    )
    session_repository = InMemorySessionRepository()
    api_credential_repository = InMemoryApiCredentialRepository()
    resolved_session_service = session_service or SessionService(
        identity_service=identity_service,
        repository=session_repository,
        audit_sink=resolved_audit_sink,
        absolute_timeout=timedelta(minutes=resolved_settings.session_absolute_timeout_minutes),
        idle_timeout=timedelta(minutes=resolved_settings.session_idle_timeout_minutes),
        max_sessions_per_subject=resolved_settings.session_max_per_subject,
        status_repository=resolved_identity_status_repository,
    )
    resolved_api_credential_service = api_credential_service or ApiCredentialService(
        repository=api_credential_repository,
        audit_sink=resolved_audit_sink,
        max_lifetime=timedelta(minutes=resolved_settings.api_credential_max_lifetime_minutes),
        max_active_per_subject=resolved_settings.api_credential_max_active_per_subject,
        status_repository=resolved_identity_status_repository,
    )
    resolved_identity_governance_service = identity_governance_service or IdentityGovernanceService(
        session_repository=session_repository,
        api_credential_repository=api_credential_repository,
        audit_sink=resolved_audit_sink,
        identity_status_repository=resolved_identity_status_repository,
    )
    resolved_workload_identity_service = workload_identity_service or WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=resolved_audit_sink,
        environment_id=f"environment.{resolved_settings.environment}",
    )
    release_key = sha256(b"atlas-synthetic-release-verifier").digest()
    release_manifest = build_synthetic_release_manifest(release_key)
    resolved_release_preflight_service = release_preflight_service or ReleasePreflightService(
        manifest=release_manifest,
        signature_verifier=LabHmacReleaseSignatureVerifier(release_key),
        artifact_inventory=SyntheticReleaseArtifactInventory(release_manifest),
        host_probe=SyntheticPreflightHostProbe(),
        audit_sink=resolved_audit_sink,
        environment_id=f"environment.{resolved_settings.environment}",
    )
    resolved_deployment_configuration_service = (
        deployment_configuration_service
        or DeploymentConfigurationService(
            release_id=release_manifest.release_id,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
            audit_sink=resolved_audit_sink,
        )
    )
    resolved_bootstrap_plan_service = bootstrap_plan_service or BootstrapPlanService(
        environment_id=f"environment.{resolved_settings.environment}",
        site_id="site.local",
        audit_sink=resolved_audit_sink,
    )
    if bootstrap_state_service is not None:
        resolved_bootstrap_state_service = bootstrap_state_service
    else:
        bootstrap_state_repository = (
            PostgreSQLBootstrapStateRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryBootstrapStateRepository()
        )
        resolved_bootstrap_state_service = BootstrapStateService(
            repository=bootstrap_state_repository,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
            audit_sink=resolved_audit_sink,
        )
    resolved_bootstrap_invalidation_service = (
        bootstrap_invalidation_service
        or BootstrapInvalidationService(
            repository=resolved_bootstrap_state_service.repository,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
            audit_sink=resolved_audit_sink,
        )
    )
    resolved_bootstrap_artifact_acquisition_service = (
        bootstrap_artifact_acquisition_service
        or BootstrapArtifactAcquisitionService(
            repository=resolved_bootstrap_state_service.repository,
            preflight_service=resolved_release_preflight_service,
            publisher=FileSystemReleaseArtifactPublisher(
                root=resolved_settings.bootstrap_artifact_root,
                source=MemoryArtifactContentSource(SYNTHETIC_ARTIFACT_CONTENT),
                max_total_bytes=resolved_settings.bootstrap_artifact_max_total_bytes,
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_configuration_rendering_service = (
        bootstrap_configuration_rendering_service
        or BootstrapConfigurationRenderingService(
            repository=resolved_bootstrap_state_service.repository,
            configuration_service=resolved_deployment_configuration_service,
            publisher=FilesystemEffectiveConfigurationPublisher(
                root=resolved_settings.bootstrap_configuration_root,
                max_bytes=resolved_settings.bootstrap_configuration_max_bytes,
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_trust_plan_service = (
        bootstrap_trust_plan_service
        or BootstrapTrustPlanService(
            source=SyntheticBootstrapTrustSource(),
            configuration_service=resolved_deployment_configuration_service,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_trust_provisioning_service = (
        bootstrap_trust_provisioning_service
        or BootstrapTrustProvisioningService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_trust_plan_service,
            publisher=FilesystemBootstrapTrustPublisher(
                root=resolved_settings.bootstrap_trust_root,
                max_total_bytes=resolved_settings.bootstrap_trust_max_total_bytes,
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_data_target = FilesystemBootstrapDataTarget(
        root=resolved_settings.bootstrap_data_root,
        max_state_bytes=resolved_settings.bootstrap_data_max_state_bytes,
    )
    resolved_bootstrap_data_plan_service = bootstrap_data_plan_service or BootstrapDataPlanService(
        catalog=SyntheticBootstrapDataCatalog(),
        target=resolved_bootstrap_data_target,
        configuration_service=resolved_deployment_configuration_service,
        trust_plan_service=resolved_bootstrap_trust_plan_service,
        environment_id=f"environment.{resolved_settings.environment}",
        site_id="site.local",
    )
    resolved_bootstrap_data_initialization_service = (
        bootstrap_data_initialization_service
        or BootstrapDataInitializationService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_data_plan_service,
            target=resolved_bootstrap_data_target,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_service_target = FilesystemBootstrapServiceTarget(
        root=resolved_settings.bootstrap_service_root,
        max_state_bytes=resolved_settings.bootstrap_service_max_state_bytes,
    )
    resolved_bootstrap_service_plan_service = (
        bootstrap_service_plan_service
        or BootstrapServicePlanService(
            catalog=SyntheticBootstrapServiceCatalog(),
            target=resolved_bootstrap_service_target,
            data_plan_service=resolved_bootstrap_data_plan_service,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_service_deployment_service = (
        bootstrap_service_deployment_service
        or BootstrapServiceDeploymentService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_service_plan_service,
            target=resolved_bootstrap_service_target,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_identity_target = FilesystemBootstrapIdentityTarget(
        root=resolved_settings.bootstrap_identity_root,
        max_state_bytes=resolved_settings.bootstrap_identity_max_state_bytes,
    )
    resolved_bootstrap_identity_plan_service = (
        bootstrap_identity_plan_service
        or BootstrapIdentityPlanService(
            catalog=SyntheticBootstrapIdentityCatalog(),
            target=resolved_bootstrap_identity_target,
            service_plan_service=resolved_bootstrap_service_plan_service,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_identity_handoff_service = (
        bootstrap_identity_handoff_service
        or BootstrapIdentityHandoffService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_identity_plan_service,
            target=resolved_bootstrap_identity_target,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_integration_target = FilesystemBootstrapIntegrationTarget(
        root=resolved_settings.bootstrap_integration_root,
        max_state_bytes=resolved_settings.bootstrap_integration_max_state_bytes,
    )
    resolved_bootstrap_integration_plan_service = (
        bootstrap_integration_plan_service
        or BootstrapIntegrationPlanService(
            catalog=SyntheticBootstrapIntegrationCatalog(),
            target=resolved_bootstrap_integration_target,
            identity_plan_service=resolved_bootstrap_identity_plan_service,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_integration_validation_service = (
        bootstrap_integration_validation_service
        or BootstrapIntegrationValidationService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_integration_plan_service,
            target=resolved_bootstrap_integration_target,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_verification_target = FilesystemBootstrapVerificationTarget(
        root=resolved_settings.bootstrap_verification_root,
        max_report_bytes=resolved_settings.bootstrap_verification_max_report_bytes,
    )
    resolved_bootstrap_verification_plan_service = (
        bootstrap_verification_plan_service
        or BootstrapVerificationPlanService(
            repository=resolved_bootstrap_state_service.repository,
            target=resolved_bootstrap_verification_target,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_end_to_end_verification_service = (
        bootstrap_end_to_end_verification_service
        or BootstrapEndToEndVerificationService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_verification_plan_service,
            target=resolved_bootstrap_verification_target,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_handoff_target = FilesystemBootstrapHandoffTarget(
        root=resolved_settings.bootstrap_handoff_root,
        max_report_bytes=resolved_settings.bootstrap_handoff_max_report_bytes,
    )
    resolved_bootstrap_handoff_plan_service = (
        bootstrap_handoff_plan_service
        or BootstrapHandoffPlanService(
            repository=resolved_bootstrap_state_service.repository,
            target=resolved_bootstrap_handoff_target,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    resolved_bootstrap_operational_handoff_service = (
        bootstrap_operational_handoff_service
        or BootstrapOperationalHandoffService(
            repository=resolved_bootstrap_state_service.repository,
            plan_service=resolved_bootstrap_handoff_plan_service,
            target=resolved_bootstrap_handoff_target,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    if support_bundle_service is not None:
        resolved_support_bundle_service = support_bundle_service
    else:
        support_repository = (
            PostgreSQLSupportBundleExportRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemorySupportBundleExportRepository()
        )
        resolved_support_bundle_service = SupportBundleService(
            bootstrap_repository=resolved_bootstrap_state_service.repository,
            export_repository=support_repository,
            publisher=FilesystemSupportBundlePublisher(
                root=resolved_settings.support_bundle_root,
                max_archive_bytes=resolved_settings.support_bundle_max_archive_bytes,
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
            max_content_bytes=resolved_settings.support_bundle_max_content_bytes,
        )
    if recovery_service is not None:
        resolved_recovery_service = recovery_service
    else:
        recovery_repository = (
            PostgreSQLRecoveryRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryRecoveryRepository()
        )
        resolved_recovery_service = RecoveryService(
            bootstrap_repository=resolved_bootstrap_state_service.repository,
            repository=recovery_repository,
            archive_store=FilesystemBackupArchiveStore(
                root=resolved_settings.logical_backup_root,
                max_archive_bytes=resolved_settings.logical_backup_max_archive_bytes,
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
            max_content_bytes=resolved_settings.logical_backup_max_content_bytes,
            max_archive_bytes=resolved_settings.logical_backup_max_archive_bytes,
        )
    if upgrade_service is not None:
        resolved_upgrade_service = upgrade_service
    else:
        upgrade_repository = (
            PostgreSQLUpgradeSimulationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryUpgradeSimulationRepository()
        )
        resolved_upgrade_service = UpgradeService(
            bootstrap_repository=resolved_bootstrap_state_service.repository,
            recovery_repository=resolved_recovery_service.repository,
            simulation_repository=upgrade_repository,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    if change_review_service is not None:
        resolved_change_review_service = change_review_service
    else:
        change_review_repository = (
            PostgreSQLChangeReviewPacketRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryChangeReviewPacketRepository()
        )
        resolved_change_review_service = ChangeReviewService(
            upgrade_service=resolved_upgrade_service,
            simulation_repository=resolved_upgrade_service.simulation_repository,
            packet_repository=change_review_repository,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    if human_review_service is not None:
        resolved_human_review_service = human_review_service
    else:
        human_review_repository = (
            PostgreSQLHumanReviewRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryHumanReviewRepository()
        )
        resolved_human_review_service = HumanReviewService(
            packet_repository=resolved_change_review_service.packet_repository,
            review_repository=human_review_repository,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    if completion_receipt_service is not None:
        resolved_completion_receipt_service = completion_receipt_service
    else:
        completion_receipt_repository = (
            PostgreSQLCompletionReceiptRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryCompletionReceiptRepository()
        )
        resolved_completion_receipt_service = CompletionReceiptService(
            packet_repository=resolved_change_review_service.packet_repository,
            review_repository=resolved_human_review_service.repository,
            receipt_repository=completion_receipt_repository,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    if mcp_builder_service is not None:
        resolved_mcp_builder_service = mcp_builder_service
    else:
        mcp_builder_repository = (
            PostgreSQLMcpBuilderProjectRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderProjectRepository()
        )
        mcp_builder_design_repository = (
            PostgreSQLMcpBuilderDesignCheckpointRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderDesignCheckpointRepository()
        )
        resolved_mcp_builder_service = McpBuilderService(
            repository=mcp_builder_repository,
            design_repository=mcp_builder_design_repository,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
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
        app.state.api_credential_service = resolved_api_credential_service
        app.state.identity_governance_service = resolved_identity_governance_service
        app.state.identity_status_repository = resolved_identity_status_repository
        app.state.workload_identity_service = resolved_workload_identity_service
        app.state.release_preflight_service = resolved_release_preflight_service
        app.state.deployment_configuration_service = resolved_deployment_configuration_service
        app.state.bootstrap_plan_service = resolved_bootstrap_plan_service
        app.state.bootstrap_state_service = resolved_bootstrap_state_service
        app.state.bootstrap_invalidation_service = resolved_bootstrap_invalidation_service
        app.state.bootstrap_artifact_acquisition_service = (
            resolved_bootstrap_artifact_acquisition_service
        )
        app.state.bootstrap_configuration_rendering_service = (
            resolved_bootstrap_configuration_rendering_service
        )
        app.state.bootstrap_trust_plan_service = resolved_bootstrap_trust_plan_service
        app.state.bootstrap_trust_provisioning_service = (
            resolved_bootstrap_trust_provisioning_service
        )
        app.state.bootstrap_data_plan_service = resolved_bootstrap_data_plan_service
        app.state.bootstrap_data_initialization_service = (
            resolved_bootstrap_data_initialization_service
        )
        app.state.bootstrap_service_plan_service = resolved_bootstrap_service_plan_service
        app.state.bootstrap_service_deployment_service = (
            resolved_bootstrap_service_deployment_service
        )
        app.state.bootstrap_identity_plan_service = resolved_bootstrap_identity_plan_service
        app.state.bootstrap_identity_handoff_service = resolved_bootstrap_identity_handoff_service
        app.state.bootstrap_integration_plan_service = resolved_bootstrap_integration_plan_service
        app.state.bootstrap_integration_validation_service = (
            resolved_bootstrap_integration_validation_service
        )
        app.state.bootstrap_verification_plan_service = resolved_bootstrap_verification_plan_service
        app.state.bootstrap_end_to_end_verification_service = (
            resolved_bootstrap_end_to_end_verification_service
        )
        app.state.bootstrap_handoff_plan_service = resolved_bootstrap_handoff_plan_service
        app.state.bootstrap_operational_handoff_service = (
            resolved_bootstrap_operational_handoff_service
        )
        app.state.support_bundle_service = resolved_support_bundle_service
        app.state.recovery_service = resolved_recovery_service
        app.state.upgrade_service = resolved_upgrade_service
        app.state.change_review_service = resolved_change_review_service
        app.state.human_review_service = resolved_human_review_service
        app.state.completion_receipt_service = resolved_completion_receipt_service
        app.state.mcp_builder_service = resolved_mcp_builder_service
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
        await resolved_mcp_builder_service.close()
        await resolved_completion_receipt_service.close()
        await resolved_human_review_service.close()
        await resolved_change_review_service.close()
        await resolved_upgrade_service.close()
        await resolved_recovery_service.close()
        await resolved_support_bundle_service.close()
        await resolved_bootstrap_state_service.close()
        await database_probe.close()

    app = FastAPI(
        title="Project Atlas API",
        version=__version__,
        docs_url="/docs" if resolved_settings.enable_api_docs else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(ApiCredentialNoStoreMiddleware)
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
    app.include_router(api_credentials.router, prefix="/api/v1")
    app.include_router(identity.router, prefix="/api/v1")
    app.include_router(identity_governance.router, prefix="/api/v1")
    app.include_router(workload_identities.router, prefix="/api/v1")
    app.include_router(platform.router, prefix="/api/v1")
    app.include_router(release_preflight.router, prefix="/api/v1")
    app.include_router(deployment_configuration.router, prefix="/api/v1")
    app.include_router(bootstrap_plan.router, prefix="/api/v1")
    app.include_router(bootstrap_invalidation.router, prefix="/api/v1")
    app.include_router(bootstrap_state.router, prefix="/api/v1")
    app.include_router(bootstrap_artifacts.router, prefix="/api/v1")
    app.include_router(bootstrap_configuration.router, prefix="/api/v1")
    app.include_router(bootstrap_trust.router, prefix="/api/v1")
    app.include_router(bootstrap_data.router, prefix="/api/v1")
    app.include_router(bootstrap_services.router, prefix="/api/v1")
    app.include_router(bootstrap_identity.router, prefix="/api/v1")
    app.include_router(bootstrap_integrations.router, prefix="/api/v1")
    app.include_router(bootstrap_verification.router, prefix="/api/v1")
    app.include_router(bootstrap_handoff.router, prefix="/api/v1")
    app.include_router(support_bundles.router, prefix="/api/v1")
    app.include_router(recovery.router, prefix="/api/v1")
    app.include_router(upgrades.router, prefix="/api/v1")
    app.include_router(mcp_builder.router, prefix="/api/v1")
    app.include_router(change_reviews.router, prefix="/api/v1")
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
    app.include_router(audit_export.router, prefix="/api/v1")
    return app
