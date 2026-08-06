from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
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
    authority_behavior_validations,
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
    connector_validations,
    connectors,
    content_policy_scans,
    contract_validations,
    deployment_configuration,
    final_validations,
    graph,
    health,
    health_checks,
    identity,
    identity_governance,
    instance_creation,
    investigations,
    lab_self_tests,
    license_analyses,
    malware_analyses,
    mcp_builder,
    package_approvals,
    package_installations,
    package_registrations,
    package_signing,
    platform,
    publisher_attestations,
    rca,
    recommendations,
    recovery,
    registry_publications,
    release_preflight,
    reports,
    runner_validations,
    schema_semantics_validations,
    security_export,
    sessions,
    static_dependency_analyses,
    storage,
    supply_chain_inventories,
    support_bundles,
    upgrades,
    vulnerability_analyses,
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
from atlas.modules.connectors.adapters.acquisition_archive_filesystem import (
    FileSystemAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.acquisition_memory import (
    InMemoryPackageAcquisitionRepository,
)
from atlas.modules.connectors.adapters.acquisition_postgres import (
    PostgreSQLPackageAcquisitionRepository,
)
from atlas.modules.connectors.adapters.authority_behavior_validation_memory import (
    InMemoryPackageAuthorityBehaviorValidationRepository,
)
from atlas.modules.connectors.adapters.authority_behavior_validation_postgres import (
    PostgreSQLPackageAuthorityBehaviorValidationRepository,
)
from atlas.modules.connectors.adapters.content_policy_scan_memory import (
    InMemoryPackageContentPolicyScanRepository,
)
from atlas.modules.connectors.adapters.content_policy_scan_postgres import (
    PostgreSQLPackageContentPolicyScanRepository,
)
from atlas.modules.connectors.adapters.contract_validation_memory import (
    InMemoryPackageContractValidationRepository,
)
from atlas.modules.connectors.adapters.contract_validation_postgres import (
    PostgreSQLPackageContractValidationRepository,
)
from atlas.modules.connectors.adapters.final_validation_memory import (
    InMemoryFinalValidationPolicySource,
    InMemoryPackageFinalValidationRepository,
)
from atlas.modules.connectors.adapters.final_validation_postgres import (
    PostgreSQLPackageFinalValidationRepository,
)
from atlas.modules.connectors.adapters.instance_creation_memory import (
    InMemoryConnectorInstanceCreationPolicySource,
    InMemoryConnectorInstanceRepository,
)
from atlas.modules.connectors.adapters.instance_creation_postgres import (
    PostgreSQLConnectorInstanceRepository,
)
from atlas.modules.connectors.adapters.lab_mock_target import MockTargetConnectorLabRunner
from atlas.modules.connectors.adapters.lab_self_test_memory import (
    InMemoryConnectorLabPlanSource,
    InMemoryLabAccessBroker,
    InMemoryPackageLabSelfTestRepository,
)
from atlas.modules.connectors.adapters.lab_self_test_postgres import (
    PostgreSQLPackageLabSelfTestRepository,
)
from atlas.modules.connectors.adapters.license_analysis_memory import (
    InMemoryPackageLicenseAnalysisRepository,
    StaticLicensePolicySnapshotProvider,
)
from atlas.modules.connectors.adapters.license_analysis_postgres import (
    PostgreSQLPackageLicenseAnalysisRepository,
)
from atlas.modules.connectors.adapters.malware_analysis_memory import (
    InMemoryPackageMalwareAnalysisRepository,
    StaticMalwareDefinitionSnapshotProvider,
)
from atlas.modules.connectors.adapters.malware_analysis_postgres import (
    PostgreSQLPackageMalwareAnalysisRepository,
)
from atlas.modules.connectors.adapters.package_approval_memory import (
    InMemoryPackageApprovalPolicySource,
    InMemoryPackageApprovalRepository,
)
from atlas.modules.connectors.adapters.package_approval_postgres import (
    PostgreSQLPackageApprovalRepository,
)
from atlas.modules.connectors.adapters.package_installation_memory import (
    InMemoryNonExecutingPackageInstaller,
    InMemoryPackageInstallationPolicySource,
    InMemoryPackageInstallationRepository,
    UnavailablePackageInstaller,
)
from atlas.modules.connectors.adapters.package_installation_postgres import (
    PostgreSQLPackageInstallationRepository,
)
from atlas.modules.connectors.adapters.package_registration_inspector import (
    BoundedConnectorPackageManifestInspector,
)
from atlas.modules.connectors.adapters.package_registration_memory import (
    InMemoryPackageRegistrationPolicySource,
    InMemoryPackageRegistrationRepository,
    UnavailableInternalRegistryArtifactReader,
)
from atlas.modules.connectors.adapters.package_registration_postgres import (
    PostgreSQLPackageRegistrationRepository,
)
from atlas.modules.connectors.adapters.package_signing_memory import (
    InMemoryPackageSigningPolicySource,
    InMemoryPackageSigningRepository,
    NonProductionHmacPackageSigner,
    UnavailablePackageSigner,
)
from atlas.modules.connectors.adapters.package_signing_postgres import (
    PostgreSQLPackageSigningRepository,
)
from atlas.modules.connectors.adapters.publisher_attestation_memory import (
    InMemoryPublisherAttestationPolicySource,
    InMemoryPublisherAttestationRepository,
    InMemoryPublisherClaimSource,
)
from atlas.modules.connectors.adapters.publisher_attestation_postgres import (
    PostgreSQLPublisherAttestationRepository,
)
from atlas.modules.connectors.adapters.registry_publication_filesystem import (
    FileSystemNonProductionInternalRegistryPublisher,
)
from atlas.modules.connectors.adapters.registry_publication_memory import (
    InMemoryRegistryPublicationPolicySource,
    InMemoryRegistryPublicationRepository,
    NonProductionHmacPackageSignatureVerifier,
    UnavailableInternalRegistryPublisher,
    UnavailablePackageSignatureVerifier,
)
from atlas.modules.connectors.adapters.registry_publication_postgres import (
    PostgreSQLRegistryPublicationRepository,
)
from atlas.modules.connectors.adapters.runner_subprocess import SubprocessPackageRunner
from atlas.modules.connectors.adapters.runner_validation_memory import (
    InMemoryPackageRunnerValidationRepository,
)
from atlas.modules.connectors.adapters.runner_validation_postgres import (
    PostgreSQLPackageRunnerValidationRepository,
)
from atlas.modules.connectors.adapters.schema_semantics_validation_memory import (
    InMemoryPackageSchemaSemanticsValidationRepository,
)
from atlas.modules.connectors.adapters.schema_semantics_validation_postgres import (
    PostgreSQLPackageSchemaSemanticsValidationRepository,
)
from atlas.modules.connectors.adapters.static_dependency_analysis_memory import (
    InMemoryPackageStaticDependencyAnalysisRepository,
)
from atlas.modules.connectors.adapters.static_dependency_analysis_postgres import (
    PostgreSQLPackageStaticDependencyAnalysisRepository,
)
from atlas.modules.connectors.adapters.supply_chain_inventory_memory import (
    InMemoryPackageSupplyChainInventoryRepository,
)
from atlas.modules.connectors.adapters.supply_chain_inventory_postgres import (
    PostgreSQLPackageSupplyChainInventoryRepository,
)
from atlas.modules.connectors.adapters.validation_intake_memory import (
    InMemoryPackageValidationRepository,
)
from atlas.modules.connectors.adapters.validation_intake_postgres import (
    PostgreSQLPackageValidationRepository,
)
from atlas.modules.connectors.adapters.vulnerability_analysis_memory import (
    InMemoryPackageVulnerabilityAnalysisRepository,
    StaticAdvisorySnapshotProvider,
)
from atlas.modules.connectors.adapters.vulnerability_analysis_postgres import (
    PostgreSQLPackageVulnerabilityAnalysisRepository,
)
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.authority_behavior_validation import (
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.content_policy_scan import PackageContentPolicyScanService
from atlas.modules.connectors.application.contract_validation import (
    PackageContractValidationService,
)
from atlas.modules.connectors.application.final_validation import (
    PackageFinalValidationService,
    build_development_final_validation_policy,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
    build_development_connector_instance_creation_policy,
)
from atlas.modules.connectors.application.lab_self_test import (
    PackageLabSelfTestService,
    build_development_lab_plan,
)
from atlas.modules.connectors.application.license_analysis import (
    PackageLicenseAnalysisService,
    build_bootstrap_license_policy_snapshot,
)
from atlas.modules.connectors.application.malware_analysis import (
    PackageMalwareAnalysisService,
    build_bootstrap_definition_snapshot,
)
from atlas.modules.connectors.application.package_approval import (
    PackageApprovalService,
    build_development_package_approval_policy,
)
from atlas.modules.connectors.application.package_installation import (
    PackageInstallationService,
    build_development_package_installation_policy,
)
from atlas.modules.connectors.application.package_registration import (
    PackageRegistrationService,
    build_development_package_registration_policy,
)
from atlas.modules.connectors.application.package_registration_ports import (
    InternalRegistryArtifactReader,
)
from atlas.modules.connectors.application.package_signing import (
    PackageSigningService,
    build_development_package_signing_policy,
)
from atlas.modules.connectors.application.publisher_attestation import (
    PublisherAttestationService,
    build_development_publisher_attestation_policy,
)
from atlas.modules.connectors.application.registry_publication import (
    RegistryPublicationService,
    build_development_registry_publication_policy,
)
from atlas.modules.connectors.application.registry_publication_ports import (
    InternalRegistryPublisher,
)
from atlas.modules.connectors.application.runner_validation import PackageRunnerValidationService
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.application.vulnerability_analysis import (
    PackageVulnerabilityAnalysisService,
    build_bootstrap_advisory_snapshot,
)
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
from atlas.modules.mcp_builder.adapters.candidate_archive_filesystem import (
    FileSystemMcpBuilderCandidateArchivePublisher,
)
from atlas.modules.mcp_builder.adapters.candidate_handoff_memory import (
    InMemoryMcpBuilderCandidateHandoffRepository,
)
from atlas.modules.mcp_builder.adapters.candidate_handoff_postgres import (
    PostgreSQLMcpBuilderCandidateHandoffRepository,
)
from atlas.modules.mcp_builder.adapters.design_review_memory import (
    InMemoryMcpBuilderDesignCheckpointRepository,
)
from atlas.modules.mcp_builder.adapters.design_review_postgres import (
    PostgreSQLMcpBuilderDesignCheckpointRepository,
)
from atlas.modules.mcp_builder.adapters.domain_review_memory import (
    InMemoryMcpBuilderDomainReviewRepository,
)
from atlas.modules.mcp_builder.adapters.domain_review_postgres import (
    PostgreSQLMcpBuilderDomainReviewRepository,
)
from atlas.modules.mcp_builder.adapters.generation_filesystem import (
    FileSystemMcpBuilderArtifactPublisher,
)
from atlas.modules.mcp_builder.adapters.generation_memory import (
    InMemoryMcpBuilderGenerationRepository,
)
from atlas.modules.mcp_builder.adapters.generation_postgres import (
    PostgreSQLMcpBuilderGenerationRepository,
)
from atlas.modules.mcp_builder.adapters.lab_runner_subprocess import (
    SubprocessMcpBuilderLabRunner,
)
from atlas.modules.mcp_builder.adapters.lab_validation_memory import (
    InMemoryMcpBuilderLabValidationRepository,
)
from atlas.modules.mcp_builder.adapters.lab_validation_postgres import (
    PostgreSQLMcpBuilderLabValidationRepository,
)
from atlas.modules.mcp_builder.adapters.memory import InMemoryMcpBuilderProjectRepository
from atlas.modules.mcp_builder.adapters.postgres import PostgreSQLMcpBuilderProjectRepository
from atlas.modules.mcp_builder.adapters.security_review_memory import (
    InMemoryMcpBuilderSecurityReviewRepository,
)
from atlas.modules.mcp_builder.adapters.security_review_postgres import (
    PostgreSQLMcpBuilderSecurityReviewRepository,
)
from atlas.modules.mcp_builder.adapters.validation_memory import (
    InMemoryMcpBuilderValidationRepository,
)
from atlas.modules.mcp_builder.adapters.validation_postgres import (
    PostgreSQLMcpBuilderValidationRepository,
)
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
    package_acquisition_service: PackageAcquisitionService | None = None,
    package_validation_service: PackageValidationService | None = None,
    package_supply_chain_inventory_service: PackageSupplyChainInventoryService | None = None,
    package_content_policy_scan_service: PackageContentPolicyScanService | None = None,
    package_schema_semantics_validation_service: PackageSchemaSemanticsValidationService
    | None = None,
    package_authority_behavior_validation_service: PackageAuthorityBehaviorValidationService
    | None = None,
    package_static_dependency_analysis_service: PackageStaticDependencyAnalysisService
    | None = None,
    package_vulnerability_analysis_service: PackageVulnerabilityAnalysisService | None = None,
    package_malware_analysis_service: PackageMalwareAnalysisService | None = None,
    package_license_analysis_service: PackageLicenseAnalysisService | None = None,
    package_contract_validation_service: PackageContractValidationService | None = None,
    package_runner_validation_service: PackageRunnerValidationService | None = None,
    package_lab_self_test_service: PackageLabSelfTestService | None = None,
    package_final_validation_service: PackageFinalValidationService | None = None,
    package_approval_service: PackageApprovalService | None = None,
    publisher_attestation_service: PublisherAttestationService | None = None,
    package_signing_service: PackageSigningService | None = None,
    registry_publication_service: RegistryPublicationService | None = None,
    package_registration_service: PackageRegistrationService | None = None,
    package_installation_service: PackageInstallationService | None = None,
    connector_instance_creation_service: ConnectorInstanceCreationService | None = None,
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
    mcp_builder_candidate_handoff_repository = (
        PostgreSQLMcpBuilderCandidateHandoffRepository.from_url(resolved_settings.database_url)
        if resolved_settings.database_url
        else InMemoryMcpBuilderCandidateHandoffRepository()
    )
    mcp_builder_candidate_archive_publisher = FileSystemMcpBuilderCandidateArchivePublisher(
        root=resolved_settings.mcp_builder_generation_root / "candidate-packages"
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
        mcp_builder_generation_repository = (
            PostgreSQLMcpBuilderGenerationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderGenerationRepository()
        )
        mcp_builder_validation_repository = (
            PostgreSQLMcpBuilderValidationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderValidationRepository()
        )
        mcp_builder_domain_review_repository = (
            PostgreSQLMcpBuilderDomainReviewRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderDomainReviewRepository()
        )
        mcp_builder_security_review_repository = (
            PostgreSQLMcpBuilderSecurityReviewRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderSecurityReviewRepository()
        )
        mcp_builder_lab_validation_repository = (
            PostgreSQLMcpBuilderLabValidationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryMcpBuilderLabValidationRepository()
        )
        resolved_mcp_builder_service = McpBuilderService(
            repository=mcp_builder_repository,
            design_repository=mcp_builder_design_repository,
            generation_repository=mcp_builder_generation_repository,
            validation_repository=mcp_builder_validation_repository,
            domain_review_repository=mcp_builder_domain_review_repository,
            security_review_repository=mcp_builder_security_review_repository,
            lab_validation_repository=mcp_builder_lab_validation_repository,
            lab_runner=SubprocessMcpBuilderLabRunner(),
            candidate_handoff_repository=mcp_builder_candidate_handoff_repository,
            candidate_archive_publisher=mcp_builder_candidate_archive_publisher,
            artifact_publisher=FileSystemMcpBuilderArtifactPublisher(
                root=resolved_settings.mcp_builder_generation_root
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_acquisition_service is not None:
        resolved_package_acquisition_service = package_acquisition_service
    else:
        package_acquisition_repository = (
            PostgreSQLPackageAcquisitionRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageAcquisitionRepository()
        )
        resolved_package_acquisition_service = PackageAcquisitionService(
            repository=package_acquisition_repository,
            handoff_source=mcp_builder_candidate_handoff_repository,
            archive_source=mcp_builder_candidate_archive_publisher,
            publisher=FileSystemAcquiredPackagePublisher(
                root=resolved_settings.mcp_builder_generation_root / "connector-quarantine"
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_validation_service is not None:
        resolved_package_validation_service = package_validation_service
    else:
        package_validation_repository = (
            PostgreSQLPackageValidationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageValidationRepository()
        )
        resolved_package_validation_service = PackageValidationService(
            repository=package_validation_repository,
            acquisition_source=resolved_package_acquisition_service.repository,
            archive_source=resolved_package_acquisition_service.archive_publisher,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_supply_chain_inventory_service is not None:
        resolved_package_supply_chain_inventory_service = package_supply_chain_inventory_service
    else:
        package_supply_chain_inventory_repository = (
            PostgreSQLPackageSupplyChainInventoryRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageSupplyChainInventoryRepository()
        )
        resolved_package_supply_chain_inventory_service = PackageSupplyChainInventoryService(
            repository=package_supply_chain_inventory_repository,
            validation_source=resolved_package_validation_service.repository,
            acquisition_source=resolved_package_validation_service.acquisition_source,
            archive_source=resolved_package_validation_service.archive_source,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_content_policy_scan_service is not None:
        resolved_package_content_policy_scan_service = package_content_policy_scan_service
    else:
        package_content_policy_scan_repository = (
            PostgreSQLPackageContentPolicyScanRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageContentPolicyScanRepository()
        )
        resolved_package_content_policy_scan_service = PackageContentPolicyScanService(
            repository=package_content_policy_scan_repository,
            inventory_source=resolved_package_supply_chain_inventory_service.repository,
            acquisition_source=resolved_package_supply_chain_inventory_service.acquisition_source,
            archive_source=resolved_package_supply_chain_inventory_service.archive_source,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_schema_semantics_validation_service is not None:
        resolved_package_schema_semantics_validation_service = (
            package_schema_semantics_validation_service
        )
    else:
        package_schema_semantics_validation_repository = (
            PostgreSQLPackageSchemaSemanticsValidationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryPackageSchemaSemanticsValidationRepository()
        )
        resolved_package_schema_semantics_validation_service = (
            PackageSchemaSemanticsValidationService(
                repository=package_schema_semantics_validation_repository,
                content_policy_source=resolved_package_content_policy_scan_service.repository,
                inventory_source=resolved_package_content_policy_scan_service.inventory_source,
                acquisition_source=resolved_package_content_policy_scan_service.acquisition_source,
                archive_source=resolved_package_content_policy_scan_service.archive_source,
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if package_authority_behavior_validation_service is not None:
        resolved_package_authority_behavior_validation_service = (
            package_authority_behavior_validation_service
        )
    else:
        package_authority_behavior_validation_repository = (
            PostgreSQLPackageAuthorityBehaviorValidationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryPackageAuthorityBehaviorValidationRepository()
        )
        resolved_package_authority_behavior_validation_service = (
            PackageAuthorityBehaviorValidationService(
                repository=package_authority_behavior_validation_repository,
                schema_semantics_source=(
                    resolved_package_schema_semantics_validation_service.repository
                ),
                inventory_source=(
                    resolved_package_schema_semantics_validation_service.inventory_source
                ),
                acquisition_source=(
                    resolved_package_schema_semantics_validation_service.acquisition_source
                ),
                archive_source=(
                    resolved_package_schema_semantics_validation_service.archive_source
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if package_static_dependency_analysis_service is not None:
        resolved_package_static_dependency_analysis_service = (
            package_static_dependency_analysis_service
        )
    else:
        package_static_dependency_analysis_repository = (
            PostgreSQLPackageStaticDependencyAnalysisRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryPackageStaticDependencyAnalysisRepository()
        )
        resolved_package_static_dependency_analysis_service = (
            PackageStaticDependencyAnalysisService(
                repository=package_static_dependency_analysis_repository,
                authority_behavior_source=(
                    resolved_package_authority_behavior_validation_service.repository
                ),
                inventory_source=(
                    resolved_package_schema_semantics_validation_service.inventory_source
                ),
                acquisition_source=(
                    resolved_package_schema_semantics_validation_service.acquisition_source
                ),
                archive_source=(
                    resolved_package_schema_semantics_validation_service.archive_source
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if package_vulnerability_analysis_service is not None:
        resolved_package_vulnerability_analysis_service = package_vulnerability_analysis_service
    else:
        package_vulnerability_analysis_repository = (
            PostgreSQLPackageVulnerabilityAnalysisRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryPackageVulnerabilityAnalysisRepository()
        )
        advisory_snapshot = build_bootstrap_advisory_snapshot(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            now=datetime.now(UTC),
        )
        resolved_package_vulnerability_analysis_service = PackageVulnerabilityAnalysisService(
            repository=package_vulnerability_analysis_repository,
            static_dependency_source=(
                resolved_package_static_dependency_analysis_service.repository
            ),
            inventory_source=(
                resolved_package_schema_semantics_validation_service.inventory_source
            ),
            acquisition_source=(
                resolved_package_schema_semantics_validation_service.acquisition_source
            ),
            archive_source=(resolved_package_schema_semantics_validation_service.archive_source),
            advisory_provider=StaticAdvisorySnapshotProvider(advisory_snapshot),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_malware_analysis_service is not None:
        resolved_package_malware_analysis_service = package_malware_analysis_service
    else:
        package_malware_analysis_repository = (
            PostgreSQLPackageMalwareAnalysisRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageMalwareAnalysisRepository()
        )
        definition_snapshot = build_bootstrap_definition_snapshot(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            now=datetime.now(UTC),
        )
        resolved_package_malware_analysis_service = PackageMalwareAnalysisService(
            repository=package_malware_analysis_repository,
            vulnerability_source=resolved_package_vulnerability_analysis_service.repository,
            inventory_source=(
                resolved_package_schema_semantics_validation_service.inventory_source
            ),
            acquisition_source=(
                resolved_package_schema_semantics_validation_service.acquisition_source
            ),
            archive_source=(resolved_package_schema_semantics_validation_service.archive_source),
            definition_provider=StaticMalwareDefinitionSnapshotProvider(definition_snapshot),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_license_analysis_service is not None:
        resolved_package_license_analysis_service = package_license_analysis_service
    else:
        package_license_analysis_repository = (
            PostgreSQLPackageLicenseAnalysisRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageLicenseAnalysisRepository()
        )
        license_policy_snapshot = build_bootstrap_license_policy_snapshot(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            now=datetime.now(UTC),
        )
        resolved_package_license_analysis_service = PackageLicenseAnalysisService(
            repository=package_license_analysis_repository,
            malware_source=resolved_package_malware_analysis_service.repository,
            inventory_source=(
                resolved_package_schema_semantics_validation_service.inventory_source
            ),
            acquisition_source=(
                resolved_package_schema_semantics_validation_service.acquisition_source
            ),
            archive_source=(resolved_package_schema_semantics_validation_service.archive_source),
            policy_provider=StaticLicensePolicySnapshotProvider(license_policy_snapshot),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_contract_validation_service is not None:
        resolved_package_contract_validation_service = package_contract_validation_service
    else:
        package_contract_validation_repository = (
            PostgreSQLPackageContractValidationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageContractValidationRepository()
        )
        resolved_package_contract_validation_service = PackageContractValidationService(
            repository=package_contract_validation_repository,
            license_source=resolved_package_license_analysis_service.repository,
            inventory_source=(
                resolved_package_schema_semantics_validation_service.inventory_source
            ),
            acquisition_source=(
                resolved_package_schema_semantics_validation_service.acquisition_source
            ),
            archive_source=(resolved_package_schema_semantics_validation_service.archive_source),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_runner_validation_service is not None:
        resolved_package_runner_validation_service = package_runner_validation_service
    else:
        package_runner_validation_repository = (
            PostgreSQLPackageRunnerValidationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageRunnerValidationRepository()
        )
        resolved_package_runner_validation_service = PackageRunnerValidationService(
            repository=package_runner_validation_repository,
            contract_source=resolved_package_contract_validation_service.repository,
            inventory_source=(
                resolved_package_schema_semantics_validation_service.inventory_source
            ),
            acquisition_source=(
                resolved_package_schema_semantics_validation_service.acquisition_source
            ),
            archive_source=(resolved_package_schema_semantics_validation_service.archive_source),
            runner=SubprocessPackageRunner(),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_lab_self_test_service is not None:
        resolved_package_lab_self_test_service = package_lab_self_test_service
    else:
        package_lab_self_test_repository = (
            PostgreSQLPackageLabSelfTestRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageLabSelfTestRepository()
        )
        development_plans = (
            ()
            if resolved_settings.environment == "production"
            else (
                build_development_lab_plan(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    approved_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_package_lab_self_test_service = PackageLabSelfTestService(
            repository=package_lab_self_test_repository,
            runner_source=resolved_package_runner_validation_service.repository,
            contract_source=resolved_package_contract_validation_service.repository,
            inventory_source=(
                resolved_package_schema_semantics_validation_service.inventory_source
            ),
            acquisition_source=(
                resolved_package_schema_semantics_validation_service.acquisition_source
            ),
            archive_source=(resolved_package_schema_semantics_validation_service.archive_source),
            plan_source=InMemoryConnectorLabPlanSource(development_plans),
            access_broker=InMemoryLabAccessBroker(),
            runner=MockTargetConnectorLabRunner(),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_final_validation_service is not None:
        resolved_package_final_validation_service = package_final_validation_service
    else:
        package_final_validation_repository = (
            PostgreSQLPackageFinalValidationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageFinalValidationRepository()
        )
        development_final_validation_policies = (
            ()
            if resolved_settings.environment == "production"
            else (
                build_development_final_validation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_package_final_validation_service = PackageFinalValidationService(
            repository=package_final_validation_repository,
            handoff_source=mcp_builder_candidate_handoff_repository,
            acquisition_source=resolved_package_acquisition_service.repository,
            archive_source=resolved_package_acquisition_service.archive_publisher,
            validation_source=resolved_package_validation_service.repository,
            inventory_source=resolved_package_supply_chain_inventory_service.repository,
            content_policy_source=resolved_package_content_policy_scan_service.repository,
            schema_semantics_source=resolved_package_schema_semantics_validation_service.repository,
            authority_behavior_source=(
                resolved_package_authority_behavior_validation_service.repository
            ),
            static_dependency_source=(
                resolved_package_static_dependency_analysis_service.repository
            ),
            vulnerability_source=resolved_package_vulnerability_analysis_service.repository,
            malware_source=resolved_package_malware_analysis_service.repository,
            license_source=resolved_package_license_analysis_service.repository,
            contract_source=resolved_package_contract_validation_service.repository,
            runner_source=resolved_package_runner_validation_service.repository,
            lab_source=resolved_package_lab_self_test_service.repository,
            policy_source=InMemoryFinalValidationPolicySource(
                development_final_validation_policies
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_approval_service is not None:
        resolved_package_approval_service = package_approval_service
    else:
        package_approval_repository = (
            PostgreSQLPackageApprovalRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageApprovalRepository()
        )
        development_package_approval_policies = (
            ()
            if resolved_settings.environment == "production"
            else (
                build_development_package_approval_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_package_approval_service = PackageApprovalService(
            repository=package_approval_repository,
            final_validation_source=resolved_package_final_validation_service,
            policy_source=InMemoryPackageApprovalPolicySource(
                development_package_approval_policies
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if publisher_attestation_service is not None:
        resolved_publisher_attestation_service = publisher_attestation_service
    else:
        publisher_attestation_repository = (
            PostgreSQLPublisherAttestationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPublisherAttestationRepository()
        )
        development_publisher_attestation_policies = (
            ()
            if resolved_settings.environment == "production"
            else (
                build_development_publisher_attestation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_publisher_attestation_service = PublisherAttestationService(
            repository=publisher_attestation_repository,
            approval_source=resolved_package_approval_service,
            claim_source=InMemoryPublisherClaimSource(),
            policy_source=InMemoryPublisherAttestationPolicySource(
                development_publisher_attestation_policies
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    is_production = resolved_settings.environment == "production"
    if package_signing_service is not None:
        resolved_package_signing_service = package_signing_service
    else:
        package_signing_repository = (
            PostgreSQLPackageSigningRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageSigningRepository()
        )
        development_package_signing_policies = (
            ()
            if is_production
            else (
                build_development_package_signing_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        package_signer = (
            UnavailablePackageSigner()
            if is_production
            else NonProductionHmacPackageSigner(
                key_material=sha256(
                    (
                        "atlas-nonproduction-package-signer:"
                        f"{resolved_settings.development_organization_id}:"
                        f"{resolved_settings.environment}"
                    ).encode("ascii")
                ).digest(),
                signer_workload_id="workload.connector-package-signer",
            )
        )
        resolved_package_signing_service = PackageSigningService(
            repository=package_signing_repository,
            attestation_source=resolved_publisher_attestation_service,
            policy_source=InMemoryPackageSigningPolicySource(development_package_signing_policies),
            signer=package_signer,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if registry_publication_service is not None:
        resolved_registry_publication_service = registry_publication_service
        registry_artifact_reader: InternalRegistryArtifactReader = (
            UnavailableInternalRegistryArtifactReader()
        )
    else:
        registry_publication_repository = (
            PostgreSQLRegistryPublicationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryRegistryPublicationRepository()
        )
        development_registry_publication_policies = (
            ()
            if is_production
            else (
                build_development_registry_publication_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        nonproduction_signing_key = sha256(
            (
                "atlas-nonproduction-package-signer:"
                f"{resolved_settings.development_organization_id}:"
                f"{resolved_settings.environment}"
            ).encode("ascii")
        ).digest()
        signature_verifier = (
            UnavailablePackageSignatureVerifier()
            if is_production
            else NonProductionHmacPackageSignatureVerifier(
                key_material=nonproduction_signing_key,
                verifier_workload_id="workload.connector-package-signature-verifier",
            )
        )
        registry_publisher: InternalRegistryPublisher
        if is_production:
            registry_publisher = UnavailableInternalRegistryPublisher()
            registry_artifact_reader = UnavailableInternalRegistryArtifactReader()
        else:
            filesystem_registry = FileSystemNonProductionInternalRegistryPublisher(
                root=(
                    resolved_settings.mcp_builder_generation_root / "connector-internal-registry"
                ),
                registry_profile_id="registry-profile.nonproduction-internal",
                publisher_workload_id="workload.connector-registry-publisher",
            )
            registry_publisher = filesystem_registry
            registry_artifact_reader = filesystem_registry
        resolved_registry_publication_service = RegistryPublicationService(
            repository=registry_publication_repository,
            signing_source=resolved_package_signing_service,
            approval_source=resolved_package_approval_service,
            final_source=resolved_package_final_validation_service,
            policy_source=InMemoryRegistryPublicationPolicySource(
                development_registry_publication_policies
            ),
            signature_verifier=signature_verifier,
            publisher=registry_publisher,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_registration_service is not None:
        resolved_package_registration_service = package_registration_service
    else:
        package_registration_repository = (
            PostgreSQLPackageRegistrationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageRegistrationRepository()
        )
        development_package_registration_policies = (
            ()
            if is_production
            else (
                build_development_package_registration_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_package_registration_service = PackageRegistrationService(
            repository=package_registration_repository,
            publication_source=resolved_registry_publication_service,
            policy_source=InMemoryPackageRegistrationPolicySource(
                development_package_registration_policies
            ),
            artifact_reader=registry_artifact_reader,
            manifest_inspector=BoundedConnectorPackageManifestInspector(),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if package_installation_service is not None:
        resolved_package_installation_service = package_installation_service
    else:
        package_installation_repository = (
            PostgreSQLPackageInstallationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryPackageInstallationRepository()
        )
        development_package_installation_policies = (
            ()
            if is_production
            else (
                build_development_package_installation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        package_installer = (
            UnavailablePackageInstaller()
            if is_production
            else InMemoryNonExecutingPackageInstaller()
        )
        resolved_package_installation_service = PackageInstallationService(
            repository=package_installation_repository,
            registration_source=resolved_package_registration_service,
            policy_source=InMemoryPackageInstallationPolicySource(
                development_package_installation_policies
            ),
            artifact_reader=registry_artifact_reader,
            manifest_inspector=BoundedConnectorPackageManifestInspector(),
            installer=package_installer,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if connector_instance_creation_service is not None:
        resolved_connector_instance_creation_service = connector_instance_creation_service
    else:
        connector_instance_repository = (
            PostgreSQLConnectorInstanceRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorInstanceRepository()
        )
        development_connector_instance_policies = (
            ()
            if is_production
            else (
                build_development_connector_instance_creation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_connector_instance_creation_service = ConnectorInstanceCreationService(
            repository=connector_instance_repository,
            installation_source=resolved_package_installation_service,
            policy_source=InMemoryConnectorInstanceCreationPolicySource(
                development_connector_instance_policies
            ),
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
        app.state.package_acquisition_service = resolved_package_acquisition_service
        app.state.package_validation_service = resolved_package_validation_service
        app.state.package_supply_chain_inventory_service = (
            resolved_package_supply_chain_inventory_service
        )
        app.state.package_content_policy_scan_service = resolved_package_content_policy_scan_service
        app.state.package_schema_semantics_validation_service = (
            resolved_package_schema_semantics_validation_service
        )
        app.state.package_authority_behavior_validation_service = (
            resolved_package_authority_behavior_validation_service
        )
        app.state.package_static_dependency_analysis_service = (
            resolved_package_static_dependency_analysis_service
        )
        app.state.package_vulnerability_analysis_service = (
            resolved_package_vulnerability_analysis_service
        )
        app.state.package_malware_analysis_service = resolved_package_malware_analysis_service
        app.state.package_license_analysis_service = resolved_package_license_analysis_service
        app.state.package_contract_validation_service = resolved_package_contract_validation_service
        app.state.package_runner_validation_service = resolved_package_runner_validation_service
        app.state.package_lab_self_test_service = resolved_package_lab_self_test_service
        app.state.package_final_validation_service = resolved_package_final_validation_service
        app.state.package_approval_service = resolved_package_approval_service
        app.state.publisher_attestation_service = resolved_publisher_attestation_service
        app.state.package_signing_service = resolved_package_signing_service
        app.state.registry_publication_service = resolved_registry_publication_service
        app.state.package_registration_service = resolved_package_registration_service
        app.state.package_installation_service = resolved_package_installation_service
        app.state.connector_instance_creation_service = resolved_connector_instance_creation_service
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
        await resolved_connector_instance_creation_service.close()
        await resolved_package_installation_service.close()
        await resolved_package_registration_service.close()
        await resolved_registry_publication_service.close()
        await resolved_package_signing_service.close()
        await resolved_publisher_attestation_service.close()
        await resolved_package_approval_service.close()
        await resolved_package_final_validation_service.close()
        await resolved_package_lab_self_test_service.close()
        await resolved_package_runner_validation_service.close()
        await resolved_package_contract_validation_service.close()
        await resolved_package_license_analysis_service.close()
        await resolved_package_malware_analysis_service.close()
        await resolved_package_vulnerability_analysis_service.close()
        await resolved_package_static_dependency_analysis_service.close()
        await resolved_package_authority_behavior_validation_service.close()
        await resolved_package_schema_semantics_validation_service.close()
        await resolved_package_content_policy_scan_service.close()
        await resolved_package_supply_chain_inventory_service.close()
        await resolved_package_validation_service.close()
        await resolved_package_acquisition_service.close()
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
    app.include_router(connectors.router, prefix="/api/v1")
    app.include_router(connector_validations.router, prefix="/api/v1")
    app.include_router(supply_chain_inventories.router, prefix="/api/v1")
    app.include_router(content_policy_scans.router, prefix="/api/v1")
    app.include_router(schema_semantics_validations.router, prefix="/api/v1")
    app.include_router(authority_behavior_validations.router, prefix="/api/v1")
    app.include_router(static_dependency_analyses.router, prefix="/api/v1")
    app.include_router(vulnerability_analyses.router, prefix="/api/v1")
    app.include_router(malware_analyses.router, prefix="/api/v1")
    app.include_router(license_analyses.router, prefix="/api/v1")
    app.include_router(contract_validations.router, prefix="/api/v1")
    app.include_router(runner_validations.router, prefix="/api/v1")
    app.include_router(lab_self_tests.router, prefix="/api/v1")
    app.include_router(final_validations.router, prefix="/api/v1")
    app.include_router(package_approvals.router, prefix="/api/v1")
    app.include_router(publisher_attestations.router, prefix="/api/v1")
    app.include_router(package_signing.router, prefix="/api/v1")
    app.include_router(registry_publications.router, prefix="/api/v1")
    app.include_router(package_registrations.router, prefix="/api/v1")
    app.include_router(package_installations.router, prefix="/api/v1")
    app.include_router(instance_creation.router, prefix="/api/v1")
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
