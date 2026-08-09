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
    bounded_invocations,
    capability_enablements,
    change_reviews,
    configuration_validations,
    connector_validations,
    connectors,
    content_policy_scans,
    contract_validations,
    correction_resubmissions,
    credential_assignments,
    deployment_configuration,
    deterministic_chunking,
    draft_review_requests,
    embedding_generation,
    evidence_drafts,
    final_resolutions,
    final_validations,
    finding_presentations,
    graph,
    health,
    health_checks,
    identity,
    identity_governance,
    index_staging_validation,
    instance_creation,
    investigations,
    invocation_authorizations,
    invocation_evidence,
    lab_self_tests,
    license_analyses,
    malware_analyses,
    mcp_builder,
    model_context_assembly,
    package_approvals,
    package_installations,
    package_registrations,
    package_signing,
    platform,
    protected_answer_presentations,
    protected_candidate_impacts,
    protected_candidate_risk_recovery,
    protected_content,
    protected_draft_adjudication,
    protected_inspections,
    protected_model_invocation,
    protected_recommendation_adjudications,
    protected_recommendation_candidates,
    protected_recommendation_presentations,
    protected_retrieval,
    publication_preparations,
    publisher_attestations,
    rca,
    recommendation_promotions,
    recommendation_readiness,
    recommendation_review_requests,
    recommendation_reviewer_assignments,
    recommendations,
    recovery,
    registry_publications,
    release_preflight,
    reports,
    retrieval_index_publication,
    review_decisions,
    review_findings,
    reviewer_assignments,
    runner_validations,
    runtime_activations,
    runtime_trust_grants,
    schema_semantics_validations,
    secret_brokerage_authorizations,
    security_export,
    sessions,
    source_materializations,
    static_dependency_analyses,
    storage,
    supply_chain_inventories,
    support_bundles,
    target_configuration,
    target_session_verifications,
    upgrades,
    vulnerability_analyses,
    workload_identities,
)
from atlas.core.audit import AuditSink, LoggingAuditSink
from atlas.core.classification import DataClassification
from atlas.core.config import Settings, get_settings
from atlas.core.persistence.database import DatabaseHealthProbe
from atlas.modules.ai.adapters.openai_compatible import OpenAICompatibleTransport
from atlas.modules.ai.adapters.protected_answer_presentation_memory import (
    InMemoryProtectedAnswerPresentationPolicySource,
    MemoryProtectedAnswerPresentationRepository,
)
from atlas.modules.ai.adapters.protected_answer_presentation_permission import (
    AuthorizationProtectedAnswerPresentationPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_answer_presentation_postgres import (
    PostgreSQLProtectedAnswerPresentationRepository,
)
from atlas.modules.ai.adapters.protected_answer_presentation_synthetic import (
    SyntheticTrustedProtectedAnswerPresenter,
    UnavailableTrustedProtectedAnswerPresenter,
)
from atlas.modules.ai.adapters.protected_candidate_impact_memory import (
    InMemoryProtectedCandidateImpactPolicySource,
    MemoryProtectedCandidateImpactRepository,
)
from atlas.modules.ai.adapters.protected_candidate_impact_permission import (
    AuthorizationProtectedCandidateImpactPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_candidate_impact_postgres import (
    PostgreSQLProtectedCandidateImpactRepository,
)
from atlas.modules.ai.adapters.protected_candidate_impact_synthetic import (
    SyntheticTrustedProtectedCandidateImpactAnalyzer,
    UnavailableTrustedProtectedCandidateImpactAnalyzer,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_memory import (
    InMemoryProtectedCandidateRiskRecoveryPolicySource,
    InMemoryProtectedOperationalEvidenceSource,
    MemoryProtectedCandidateRiskRecoveryRepository,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_permission import (
    AuthorizationProtectedCandidateRiskRecoveryPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_postgres import (
    PostgreSQLProtectedCandidateRiskRecoveryRepository,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_synthetic import (
    SyntheticTrustedProtectedCandidateRiskRecoveryAssessor,
    UnavailableTrustedProtectedCandidateRiskRecoveryAssessor,
    build_development_operational_evidence_snapshot,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_memory import (
    InMemoryProtectedDraftAdjudicationPolicySource,
    MemoryProtectedDraftAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_permission import (
    AuthorizationProtectedDraftAdjudicationPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_postgres import (
    PostgreSQLProtectedDraftAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_synthetic import (
    SyntheticTrustedProtectedDraftAdjudicator,
    UnavailableTrustedProtectedDraftAdjudicator,
)
from atlas.modules.ai.adapters.protected_model_invocation_memory import (
    InMemoryProtectedModelInvocationPolicySource,
    MemoryProtectedModelInvocationRepository,
)
from atlas.modules.ai.adapters.protected_model_invocation_permission import (
    AuthorizationProtectedModelInvocationPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_model_invocation_postgres import (
    PostgreSQLProtectedModelInvocationRepository,
)
from atlas.modules.ai.adapters.protected_model_invocation_synthetic import (
    SyntheticTrustedProtectedModelGateway,
    UnavailableTrustedProtectedModelGateway,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_memory import (
    InMemoryProtectedRecommendationAdjudicationPolicySource,
    MemoryProtectedRecommendationAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_permission import (
    AuthorizationProtectedRecommendationAdjudicationPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_postgres import (
    PostgreSQLProtectedRecommendationAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_synthetic import (
    SyntheticTrustedProtectedRecommendationAdjudicator,
    UnavailableTrustedProtectedRecommendationAdjudicator,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_memory import (
    InMemoryProtectedRecommendationCandidatePolicySource,
    MemoryProtectedRecommendationCandidateRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_permission import (
    AuthorizationProtectedRecommendationCandidatePermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_postgres import (
    PostgreSQLProtectedRecommendationCandidateRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_synthetic import (
    SyntheticTrustedProtectedRecommendationCandidateGenerator,
    UnavailableTrustedProtectedRecommendationCandidateGenerator,
)
from atlas.modules.ai.adapters.protected_recommendation_presentation_memory import (
    InMemoryProtectedRecommendationPresentationPolicySource,
    MemoryProtectedRecommendationPresentationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_presentation_permission import (
    AuthorizationProtectedRecommendationPresentationPermissionAuthorizer,
)
from atlas.modules.ai.adapters.protected_recommendation_presentation_postgres import (
    PostgreSQLProtectedRecommendationPresentationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_presentation_synthetic import (
    SyntheticTrustedProtectedRecommendationPresenter,
    UnavailableTrustedProtectedRecommendationPresenter,
)
from atlas.modules.ai.adapters.synthetic import SyntheticOpenAICompatibleTransport
from atlas.modules.ai.application.gateway import ModelGateway
from atlas.modules.ai.application.ports import ModelTransport
from atlas.modules.ai.application.protected_answer_presentation import (
    GovernedProtectedAnswerPresentationService,
    build_development_protected_answer_presentation_policy,
)
from atlas.modules.ai.application.protected_candidate_impact_enrichment import (
    GovernedProtectedCandidateImpactService,
    build_development_protected_candidate_impact_policy,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion import (
    GovernedProtectedCandidateRiskRecoveryService,
    build_development_protected_candidate_risk_recovery_policy,
)
from atlas.modules.ai.application.protected_draft_adjudication import (
    GovernedProtectedDraftAdjudicationService,
    build_development_protected_draft_adjudication_policy,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
    build_development_protected_model_invocation_policy,
)
from atlas.modules.ai.application.protected_recommendation_adjudication import (
    GovernedProtectedRecommendationAdjudicationService,
    build_development_protected_recommendation_adjudication_policy,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation import (
    GovernedProtectedRecommendationCandidateService,
    build_development_protected_recommendation_candidate_policy,
)
from atlas.modules.ai.application.protected_recommendation_presentation import (
    GovernedProtectedRecommendationPresentationService,
    build_development_protected_recommendation_presentation_policy,
)
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
from atlas.modules.connectors.adapters.bounded_invocation_memory import (
    InMemoryConnectorBoundedInvocationPolicySource,
    InMemoryConnectorBoundedInvocationRepository,
)
from atlas.modules.connectors.adapters.bounded_invocation_postgres import (
    PostgreSQLConnectorBoundedInvocationRepository,
)
from atlas.modules.connectors.adapters.bounded_invocation_synthetic import (
    SyntheticConnectorBoundedInvocationAdapter,
    UnavailableConnectorBoundedInvocationAdapter,
)
from atlas.modules.connectors.adapters.capability_enablement_memory import (
    InMemoryConnectorCapabilityEnablementPolicySource,
    InMemoryConnectorCapabilityEnablementRepository,
    InMemoryConnectorCapabilityProfileSource,
)
from atlas.modules.connectors.adapters.capability_enablement_postgres import (
    PostgreSQLConnectorCapabilityEnablementRepository,
)
from atlas.modules.connectors.adapters.configuration_validation_memory import (
    InMemoryConnectorConfigurationEvidenceSource,
    InMemoryConnectorConfigurationValidationPolicySource,
    InMemoryConnectorConfigurationValidationRepository,
)
from atlas.modules.connectors.adapters.configuration_validation_postgres import (
    PostgreSQLConnectorConfigurationValidationRepository,
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
from atlas.modules.connectors.adapters.credential_assignment_memory import (
    InMemoryConnectorCredentialAssignmentPolicySource,
    InMemoryConnectorCredentialAssignmentRepository,
    InMemoryConnectorCredentialProfileSource,
)
from atlas.modules.connectors.adapters.credential_assignment_postgres import (
    PostgreSQLConnectorCredentialAssignmentRepository,
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
from atlas.modules.connectors.adapters.invocation_authorization_memory import (
    InMemoryConnectorInvocationAuthorizationPolicySource,
    InMemoryConnectorInvocationAuthorizationRepository,
    InMemoryConnectorInvocationInputEnvelopeSource,
    InMemoryConnectorInvocationProfileSource,
)
from atlas.modules.connectors.adapters.invocation_authorization_postgres import (
    PostgreSQLConnectorInvocationAuthorizationRepository,
)
from atlas.modules.connectors.adapters.invocation_evidence_memory import (
    InMemoryConnectorInvocationEvidencePolicySource,
    InMemoryConnectorInvocationEvidenceRepository,
)
from atlas.modules.connectors.adapters.invocation_evidence_postgres import (
    PostgreSQLConnectorInvocationEvidenceRepository,
)
from atlas.modules.connectors.adapters.invocation_evidence_synthetic import (
    SyntheticConnectorInvocationEvidenceAdapter,
    UnavailableConnectorInvocationEvidenceAdapter,
)
from atlas.modules.connectors.adapters.invocation_permission import (
    AuthorizationConnectorBoundedInvocationPermissionAuthorizer,
    AuthorizationConnectorCapabilityPermissionAuthorizer,
    AuthorizationConnectorInvocationEvidencePermissionAuthorizer,
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
from atlas.modules.connectors.adapters.runtime_activation_memory import (
    InMemoryConnectorRuntimeActivationPolicySource,
    InMemoryConnectorRuntimeActivationProfileSource,
    InMemoryConnectorRuntimeActivationRepository,
)
from atlas.modules.connectors.adapters.runtime_activation_postgres import (
    PostgreSQLConnectorRuntimeActivationRepository,
)
from atlas.modules.connectors.adapters.runtime_activation_synthetic import (
    SyntheticConnectorRuntimeActivator,
    UnavailableConnectorRuntimeActivator,
)
from atlas.modules.connectors.adapters.runtime_trust_memory import (
    InMemoryConnectorRuntimeTrustPolicySource,
    InMemoryConnectorRuntimeTrustProfileSource,
    InMemoryConnectorRuntimeTrustRepository,
)
from atlas.modules.connectors.adapters.runtime_trust_postgres import (
    PostgreSQLConnectorRuntimeTrustRepository,
)
from atlas.modules.connectors.adapters.schema_semantics_validation_memory import (
    InMemoryPackageSchemaSemanticsValidationRepository,
)
from atlas.modules.connectors.adapters.schema_semantics_validation_postgres import (
    PostgreSQLPackageSchemaSemanticsValidationRepository,
)
from atlas.modules.connectors.adapters.secret_brokerage_memory import (
    InMemoryConnectorSecretBrokeragePolicySource,
    InMemoryConnectorSecretBrokerageProfileSource,
    InMemoryConnectorSecretBrokerageRepository,
)
from atlas.modules.connectors.adapters.secret_brokerage_postgres import (
    PostgreSQLConnectorSecretBrokerageRepository,
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
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationPolicySource,
    InMemoryConnectorTargetConfigurationRepository,
    InMemoryConnectorTargetProfileSource,
)
from atlas.modules.connectors.adapters.target_configuration_postgres import (
    PostgreSQLConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.adapters.target_session_memory import (
    InMemoryConnectorTargetSessionPolicySource,
    InMemoryConnectorTargetSessionProfileSource,
    InMemoryConnectorTargetSessionRepository,
)
from atlas.modules.connectors.adapters.target_session_postgres import (
    PostgreSQLConnectorTargetSessionRepository,
)
from atlas.modules.connectors.adapters.target_session_synthetic import (
    SyntheticConnectorTargetSessionAdapter,
    UnavailableConnectorTargetSessionAdapter,
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
from atlas.modules.connectors.application.bounded_invocation import (
    ConnectorBoundedInvocationService,
    build_development_connector_bounded_invocation_policy,
)
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementService,
    build_development_connector_capability_enablement_policy,
)
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationService,
    build_development_connector_configuration_validation_policy,
)
from atlas.modules.connectors.application.content_policy_scan import PackageContentPolicyScanService
from atlas.modules.connectors.application.contract_validation import (
    PackageContractValidationService,
)
from atlas.modules.connectors.application.credential_assignment import (
    ConnectorCredentialAssignmentService,
    build_development_connector_credential_assignment_policy,
    build_development_connector_credential_profile,
)
from atlas.modules.connectors.application.final_validation import (
    PackageFinalValidationService,
    build_development_final_validation_policy,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
    build_development_connector_instance_creation_policy,
)
from atlas.modules.connectors.application.invocation_authorization import (
    ConnectorInvocationAuthorizationService,
    build_development_connector_invocation_authorization_policy,
)
from atlas.modules.connectors.application.invocation_evidence import (
    ConnectorInvocationEvidenceService,
    build_development_connector_invocation_evidence_policy,
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
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
    build_development_connector_runtime_activation_policy,
)
from atlas.modules.connectors.application.runtime_trust import (
    ConnectorRuntimeTrustService,
    build_development_connector_runtime_trust_policy,
)
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageService,
    build_development_connector_secret_brokerage_policy,
)
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
    build_development_connector_target_configuration_policy,
    build_development_connector_target_profile,
)
from atlas.modules.connectors.application.target_session import (
    ConnectorTargetSessionService,
    build_development_connector_target_session_policy,
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
from atlas.modules.knowledge.adapters.correction_resubmission_memory import (
    InMemoryOperationalKnowledgeCorrectionPolicySource,
    InMemoryOperationalKnowledgeCorrectionRepository,
)
from atlas.modules.knowledge.adapters.correction_resubmission_permission import (
    AuthorizationOperationalKnowledgeCorrectionPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.correction_resubmission_postgres import (
    PostgreSQLOperationalKnowledgeCorrectionRepository,
)
from atlas.modules.knowledge.adapters.correction_resubmission_synthetic import (
    SyntheticOperationalKnowledgeCorrectionAdapter,
    UnavailableOperationalKnowledgeCorrectionAdapter,
)
from atlas.modules.knowledge.adapters.deterministic_chunking_memory import (
    InMemoryOperationalKnowledgeChunkingPolicySource,
    InMemoryOperationalKnowledgeChunkingRepository,
)
from atlas.modules.knowledge.adapters.deterministic_chunking_permission import (
    AuthorizationOperationalKnowledgeChunkingPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.deterministic_chunking_postgres import (
    PostgreSQLOperationalKnowledgeChunkingRepository,
)
from atlas.modules.knowledge.adapters.deterministic_chunking_synthetic import (
    SyntheticOperationalKnowledgeChunker,
    UnavailableOperationalKnowledgeChunker,
)
from atlas.modules.knowledge.adapters.draft_review_request_memory import (
    InMemoryOperationalKnowledgeReviewRequestPolicySource,
    InMemoryOperationalKnowledgeReviewRequestRepository,
)
from atlas.modules.knowledge.adapters.draft_review_request_permission import (
    AuthorizationOperationalKnowledgeReviewRequestPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.draft_review_request_postgres import (
    PostgreSQLOperationalKnowledgeReviewRequestRepository,
)
from atlas.modules.knowledge.adapters.draft_review_request_synthetic import (
    SyntheticOperationalKnowledgeReviewRequestAdapter,
    UnavailableOperationalKnowledgeReviewRequestAdapter,
)
from atlas.modules.knowledge.adapters.embedding_generation_memory import (
    InMemoryOperationalKnowledgeEmbeddingPolicySource,
    InMemoryOperationalKnowledgeEmbeddingRepository,
)
from atlas.modules.knowledge.adapters.embedding_generation_permission import (
    AuthorizationOperationalKnowledgeEmbeddingPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.embedding_generation_postgres import (
    PostgreSQLOperationalKnowledgeEmbeddingRepository,
)
from atlas.modules.knowledge.adapters.embedding_generation_synthetic import (
    SyntheticOperationalKnowledgeEmbedder,
    UnavailableOperationalKnowledgeEmbedder,
)
from atlas.modules.knowledge.adapters.evidence_draft_memory import (
    InMemoryOperationalEvidenceKnowledgeDraftPolicySource,
    InMemoryOperationalEvidenceKnowledgeDraftRepository,
)
from atlas.modules.knowledge.adapters.evidence_draft_permission import (
    AuthorizationOperationalEvidenceKnowledgeDraftPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.evidence_draft_postgres import (
    PostgreSQLOperationalEvidenceKnowledgeDraftRepository,
)
from atlas.modules.knowledge.adapters.evidence_draft_synthetic import (
    SyntheticOperationalEvidenceKnowledgeDraftAdapter,
    UnavailableOperationalEvidenceKnowledgeDraftAdapter,
)
from atlas.modules.knowledge.adapters.final_resolution_memory import (
    InMemoryOperationalKnowledgeFinalResolutionPolicySource,
    InMemoryOperationalKnowledgeFinalResolutionRepository,
)
from atlas.modules.knowledge.adapters.final_resolution_permission import (
    AuthorizationOperationalKnowledgeFinalResolutionPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.final_resolution_postgres import (
    PostgreSQLOperationalKnowledgeFinalResolutionRepository,
)
from atlas.modules.knowledge.adapters.final_resolution_synthetic import (
    SyntheticOperationalKnowledgeFinalResolutionAttestor,
    UnavailableOperationalKnowledgeFinalResolutionAttestor,
)
from atlas.modules.knowledge.adapters.finding_presentation_memory import (
    InMemoryOperationalKnowledgeFindingPresentationPolicySource,
    InMemoryOperationalKnowledgeFindingPresentationRepository,
)
from atlas.modules.knowledge.adapters.finding_presentation_permission import (
    AuthorizationOperationalKnowledgeFindingPresentationPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.finding_presentation_postgres import (
    PostgreSQLOperationalKnowledgeFindingPresentationRepository,
)
from atlas.modules.knowledge.adapters.finding_presentation_synthetic import (
    SyntheticOperationalKnowledgeFindingPresenter,
    UnavailableOperationalKnowledgeFindingPresenter,
)
from atlas.modules.knowledge.adapters.index_staging_validation_memory import (
    InMemoryOperationalKnowledgeIndexPolicySource,
    InMemoryOperationalKnowledgeIndexRepository,
)
from atlas.modules.knowledge.adapters.index_staging_validation_permission import (
    AuthorizationOperationalKnowledgeIndexPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.index_staging_validation_postgres import (
    PostgreSQLOperationalKnowledgeIndexRepository,
)
from atlas.modules.knowledge.adapters.index_staging_validation_synthetic import (
    SyntheticOperationalKnowledgeIndexer,
    UnavailableOperationalKnowledgeIndexer,
)
from atlas.modules.knowledge.adapters.memory import InMemoryKnowledgeRetriever
from atlas.modules.knowledge.adapters.model_context_assembly_memory import (
    InMemoryProtectedModelContextPolicySource,
    MemoryProtectedModelContextRepository,
)
from atlas.modules.knowledge.adapters.model_context_assembly_permission import (
    AuthorizationProtectedModelContextPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.model_context_assembly_postgres import (
    PostgreSQLProtectedModelContextRepository,
)
from atlas.modules.knowledge.adapters.model_context_assembly_synthetic import (
    SyntheticTrustedProtectedModelContextAssembler,
    UnavailableTrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.adapters.protected_content_memory import (
    InMemoryOperationalKnowledgeProtectedContentPolicySource,
    InMemoryOperationalKnowledgeProtectedContentRepository,
)
from atlas.modules.knowledge.adapters.protected_content_permission import (
    AuthorizationOperationalKnowledgeProtectedContentPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.protected_content_postgres import (
    PostgreSQLOperationalKnowledgeProtectedContentRepository,
)
from atlas.modules.knowledge.adapters.protected_content_synthetic import (
    SyntheticOperationalKnowledgeProtectedContentPresenter,
    UnavailableOperationalKnowledgeProtectedContentPresenter,
)
from atlas.modules.knowledge.adapters.protected_inspection_memory import (
    InMemoryOperationalKnowledgeProtectedInspectionPolicySource,
    InMemoryOperationalKnowledgeProtectedInspectionRepository,
)
from atlas.modules.knowledge.adapters.protected_inspection_permission import (
    AuthorizationOperationalKnowledgeProtectedInspectionPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.protected_inspection_postgres import (
    PostgreSQLOperationalKnowledgeProtectedInspectionRepository,
)
from atlas.modules.knowledge.adapters.protected_inspection_synthetic import (
    SyntheticOperationalKnowledgeProtectedInspectionBroker,
    UnavailableOperationalKnowledgeProtectedInspectionBroker,
)
from atlas.modules.knowledge.adapters.protected_retrieval_memory import (
    InMemoryOperationalKnowledgeRetrievalPolicySource,
    MemoryOperationalKnowledgeRetrievalRepository,
)
from atlas.modules.knowledge.adapters.protected_retrieval_permission import (
    AuthorizationOperationalKnowledgeRetrievalPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.protected_retrieval_postgres import (
    PostgreSQLOperationalKnowledgeRetrievalRepository,
)
from atlas.modules.knowledge.adapters.protected_retrieval_synthetic import (
    SyntheticOperationalKnowledgeTrustedRetriever,
    UnavailableOperationalKnowledgeTrustedRetriever,
)
from atlas.modules.knowledge.adapters.publication_preparation_memory import (
    InMemoryOperationalKnowledgePublicationPreparationPolicySource,
    InMemoryOperationalKnowledgePublicationPreparationRepository,
)
from atlas.modules.knowledge.adapters.publication_preparation_permission import (
    AuthorizationOperationalKnowledgePublicationPreparationPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.publication_preparation_postgres import (
    PostgreSQLOperationalKnowledgePublicationPreparationRepository,
)
from atlas.modules.knowledge.adapters.publication_preparation_synthetic import (
    SyntheticOperationalKnowledgePublicationPreparer,
    UnavailableOperationalKnowledgePublicationPreparer,
)
from atlas.modules.knowledge.adapters.retrieval_index_publication_memory import (
    InMemoryOperationalKnowledgeRetrievalPublicationPolicySource,
    InMemoryOperationalKnowledgeRetrievalPublicationRepository,
)
from atlas.modules.knowledge.adapters.retrieval_index_publication_permission import (
    AuthorizationOperationalKnowledgeRetrievalPublicationPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.retrieval_index_publication_postgres import (
    PostgreSQLOperationalKnowledgeRetrievalPublicationRepository,
)
from atlas.modules.knowledge.adapters.retrieval_index_publication_synthetic import (
    SyntheticOperationalKnowledgeRetrievalPublisher,
    UnavailableOperationalKnowledgeRetrievalPublisher,
)
from atlas.modules.knowledge.adapters.review_decision_memory import (
    InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource,
    InMemoryOperationalKnowledgeTrackReviewDecisionRepository,
)
from atlas.modules.knowledge.adapters.review_decision_permission import (
    AuthorizationOperationalKnowledgeTrackReviewDecisionPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.review_decision_postgres import (
    PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository,
)
from atlas.modules.knowledge.adapters.review_decision_synthetic import (
    SyntheticOperationalKnowledgeTrackReviewDecisionAttestor,
    UnavailableOperationalKnowledgeTrackReviewDecisionAttestor,
)
from atlas.modules.knowledge.adapters.review_finding_memory import (
    InMemoryOperationalKnowledgeReviewFindingPolicySource,
    InMemoryOperationalKnowledgeReviewFindingRepository,
)
from atlas.modules.knowledge.adapters.review_finding_permission import (
    AuthorizationOperationalKnowledgeReviewFindingPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.review_finding_postgres import (
    PostgreSQLOperationalKnowledgeReviewFindingRepository,
)
from atlas.modules.knowledge.adapters.review_finding_synthetic import (
    SyntheticOperationalKnowledgeReviewFindingRecorder,
    UnavailableOperationalKnowledgeReviewFindingRecorder,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_memory import (
    InMemoryOperationalKnowledgeReviewerAssignmentPolicySource,
    InMemoryOperationalKnowledgeReviewerAssignmentRepository,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_permission import (
    AuthorizationOperationalKnowledgeReviewerAssignmentPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_postgres import (
    PostgreSQLOperationalKnowledgeReviewerAssignmentRepository,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_synthetic import (
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter,
    UnavailableOperationalKnowledgeReviewerAssignmentAdapter,
)
from atlas.modules.knowledge.adapters.source_materialization_memory import (
    InMemoryOperationalKnowledgeSourceMaterializationPolicySource,
    InMemoryOperationalKnowledgeSourceMaterializationRepository,
)
from atlas.modules.knowledge.adapters.source_materialization_permission import (
    AuthorizationOperationalKnowledgeSourceMaterializationPermissionAuthorizer,
)
from atlas.modules.knowledge.adapters.source_materialization_postgres import (
    PostgreSQLOperationalKnowledgeSourceMaterializationRepository,
)
from atlas.modules.knowledge.adapters.source_materialization_synthetic import (
    SyntheticOperationalKnowledgeSourceMaterializer,
    UnavailableOperationalKnowledgeSourceMaterializer,
)
from atlas.modules.knowledge.adapters.synthetic import build_synthetic_knowledge_chunks
from atlas.modules.knowledge.application.correction_resubmission import (
    OperationalKnowledgeCorrectionService,
    build_development_operational_knowledge_correction_policy,
)
from atlas.modules.knowledge.application.deterministic_chunking import (
    OperationalKnowledgeDeterministicChunkingService,
    build_development_operational_knowledge_chunking_policy,
)
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestService,
    build_development_operational_knowledge_review_request_policy,
)
from atlas.modules.knowledge.application.embedding_generation import (
    OperationalKnowledgeEmbeddingGenerationService,
    build_development_operational_knowledge_embedding_policy,
)
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftService,
    build_development_operational_evidence_knowledge_draft_policy,
)
from atlas.modules.knowledge.application.final_resolution import (
    OperationalKnowledgeFinalResolutionService,
    build_development_operational_knowledge_final_resolution_policy,
)
from atlas.modules.knowledge.application.finding_presentation import (
    OperationalKnowledgeFindingPresentationService,
    build_development_operational_knowledge_finding_presentation_policy,
)
from atlas.modules.knowledge.application.index_staging_validation import (
    OperationalKnowledgeIndexStagingValidationService,
    build_development_operational_knowledge_index_policy,
)
from atlas.modules.knowledge.application.model_context_assembly import (
    GovernedProtectedModelContextService,
    build_development_protected_model_context_policy,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    TrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.application.protected_content import (
    OperationalKnowledgeProtectedContentService,
    build_development_operational_knowledge_protected_content_policy,
)
from atlas.modules.knowledge.application.protected_inspection import (
    OperationalKnowledgeProtectedInspectionService,
    build_development_operational_knowledge_protected_inspection_policy,
)
from atlas.modules.knowledge.application.protected_retrieval import (
    OperationalKnowledgeProtectedRetrievalService,
    build_development_operational_knowledge_retrieval_policy,
)
from atlas.modules.knowledge.application.publication_preparation import (
    OperationalKnowledgePublicationPreparationService,
    build_development_operational_knowledge_publication_preparation_policy,
)
from atlas.modules.knowledge.application.retrieval_index_publication import (
    OperationalKnowledgeRetrievalIndexPublicationService,
    build_development_operational_knowledge_retrieval_publication_policy,
)
from atlas.modules.knowledge.application.review_decision import (
    OperationalKnowledgeTrackReviewDecisionService,
    build_development_operational_knowledge_track_review_decision_policy,
)
from atlas.modules.knowledge.application.review_finding import (
    OperationalKnowledgeReviewFindingService,
    build_development_operational_knowledge_review_finding_policy,
)
from atlas.modules.knowledge.application.review_finding_ports import (
    OperationalKnowledgeReviewFindingRecorder,
)
from atlas.modules.knowledge.application.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentService,
    build_development_operational_knowledge_reviewer_assignment_policy,
)
from atlas.modules.knowledge.application.service import KnowledgeRetrievalService
from atlas.modules.knowledge.application.source_materialization import (
    OperationalKnowledgeSourceMaterializationService,
    build_development_operational_knowledge_source_materialization_policy,
)
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
from atlas.modules.recommendations.adapters.promotion_memory import (
    InMemoryRecommendationPromotionPolicySource,
    MemoryRecommendationPromotionRepository,
)
from atlas.modules.recommendations.adapters.promotion_permission import (
    AuthorizationRecommendationPromotionPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.promotion_postgres import (
    PostgreSQLRecommendationPromotionRepository,
)
from atlas.modules.recommendations.adapters.promotion_synthetic import (
    SyntheticTrustedRecommendationPromoter,
    UnavailableTrustedRecommendationPromoter,
)
from atlas.modules.recommendations.adapters.readiness_memory import (
    InMemoryRecommendationReadinessPolicySource,
    MemoryRecommendationReadinessRepository,
)
from atlas.modules.recommendations.adapters.readiness_permission import (
    AuthorizationRecommendationReadinessPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.readiness_postgres import (
    PostgreSQLRecommendationReadinessRepository,
)
from atlas.modules.recommendations.adapters.readiness_synthetic import (
    SyntheticTrustedRecommendationReadinessEvaluator,
    UnavailableTrustedRecommendationReadinessEvaluator,
)
from atlas.modules.recommendations.adapters.review_request_memory import (
    InMemoryRecommendationReviewRequestPolicySource,
    MemoryRecommendationReviewRequestRepository,
)
from atlas.modules.recommendations.adapters.review_request_permission import (
    AuthorizationRecommendationReviewRequestPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.review_request_postgres import (
    PostgreSQLRecommendationReviewRequestRepository,
)
from atlas.modules.recommendations.adapters.review_request_synthetic import (
    SyntheticTrustedRecommendationReviewRequestOrchestrator,
    UnavailableTrustedRecommendationReviewRequestOrchestrator,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_memory import (
    InMemoryRecommendationReviewerAssignmentPolicySource,
    MemoryRecommendationReviewerAssignmentRepository,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_permission import (
    AuthorizationRecommendationReviewerAssignmentPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_postgres import (
    PostgreSQLRecommendationReviewerAssignmentRepository,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_synthetic import (
    SyntheticTrustedRecommendationReviewerAssignmentAdapter,
    UnavailableTrustedRecommendationReviewerAssignmentAdapter,
)
from atlas.modules.recommendations.adapters.synthetic import (
    SyntheticStorageRecommendationAssembler,
)
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
    build_development_recommendation_promotion_policy,
)
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
    build_development_recommendation_readiness_policy,
)
from atlas.modules.recommendations.application.review_request import (
    GovernedRecommendationReviewRequestService,
    build_development_recommendation_review_request_policy,
)
from atlas.modules.recommendations.application.reviewer_assignment import (
    GovernedRecommendationReviewerAssignmentService,
    build_development_recommendation_reviewer_assignment_policy,
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
    target_configuration_service: ConnectorTargetConfigurationService | None = None,
    credential_assignment_service: ConnectorCredentialAssignmentService | None = None,
    configuration_validation_service: ConnectorConfigurationValidationService | None = None,
    capability_enablement_service: ConnectorCapabilityEnablementService | None = None,
    runtime_trust_service: ConnectorRuntimeTrustService | None = None,
    secret_brokerage_service: ConnectorSecretBrokerageService | None = None,
    runtime_activation_service: ConnectorRuntimeActivationService | None = None,
    target_session_service: ConnectorTargetSessionService | None = None,
    invocation_authorization_service: ConnectorInvocationAuthorizationService | None = None,
    bounded_invocation_service: ConnectorBoundedInvocationService | None = None,
    invocation_evidence_service: ConnectorInvocationEvidenceService | None = None,
    operational_evidence_knowledge_draft_service: (
        OperationalEvidenceKnowledgeDraftService | None
    ) = None,
    operational_knowledge_review_request_service: (
        OperationalKnowledgeReviewRequestService | None
    ) = None,
    operational_knowledge_reviewer_assignment_service: (
        OperationalKnowledgeReviewerAssignmentService | None
    ) = None,
    operational_knowledge_protected_inspection_service: (
        OperationalKnowledgeProtectedInspectionService | None
    ) = None,
    operational_knowledge_protected_content_service: (
        OperationalKnowledgeProtectedContentService | None
    ) = None,
    operational_knowledge_review_finding_service: (
        OperationalKnowledgeReviewFindingService | None
    ) = None,
    operational_knowledge_finding_presentation_service: (
        OperationalKnowledgeFindingPresentationService | None
    ) = None,
    operational_knowledge_track_review_decision_service: (
        OperationalKnowledgeTrackReviewDecisionService | None
    ) = None,
    operational_knowledge_correction_service: OperationalKnowledgeCorrectionService | None = None,
    operational_knowledge_final_resolution_service: (
        OperationalKnowledgeFinalResolutionService | None
    ) = None,
    operational_knowledge_publication_preparation_service: (
        OperationalKnowledgePublicationPreparationService | None
    ) = None,
    operational_knowledge_source_materialization_service: (
        OperationalKnowledgeSourceMaterializationService | None
    ) = None,
    operational_knowledge_deterministic_chunking_service: (
        OperationalKnowledgeDeterministicChunkingService | None
    ) = None,
    operational_knowledge_embedding_generation_service: (
        OperationalKnowledgeEmbeddingGenerationService | None
    ) = None,
    operational_knowledge_index_staging_validation_service: (
        OperationalKnowledgeIndexStagingValidationService | None
    ) = None,
    operational_knowledge_retrieval_index_publication_service: (
        OperationalKnowledgeRetrievalIndexPublicationService | None
    ) = None,
    operational_knowledge_protected_retrieval_service: (
        OperationalKnowledgeProtectedRetrievalService | None
    ) = None,
    protected_model_context_service: GovernedProtectedModelContextService | None = None,
    protected_model_invocation_service: GovernedProtectedModelInvocationService | None = None,
    protected_draft_adjudication_service: GovernedProtectedDraftAdjudicationService | None = None,
    protected_answer_presentation_service: GovernedProtectedAnswerPresentationService | None = None,
    protected_recommendation_candidate_service: (
        GovernedProtectedRecommendationCandidateService | None
    ) = None,
    protected_candidate_impact_service: GovernedProtectedCandidateImpactService | None = None,
    protected_candidate_risk_recovery_service: (
        GovernedProtectedCandidateRiskRecoveryService | None
    ) = None,
    protected_recommendation_adjudication_service: (
        GovernedProtectedRecommendationAdjudicationService | None
    ) = None,
    protected_recommendation_presentation_service: (
        GovernedProtectedRecommendationPresentationService | None
    ) = None,
    recommendation_promotion_service: GovernedRecommendationPromotionService | None = None,
    recommendation_readiness_service: GovernedRecommendationReadinessService | None = None,
    recommendation_review_request_service: (
        GovernedRecommendationReviewRequestService | None
    ) = None,
    recommendation_reviewer_assignment_service: (
        GovernedRecommendationReviewerAssignmentService | None
    ) = None,
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
    if target_configuration_service is not None:
        resolved_target_configuration_service = target_configuration_service
    else:
        target_configuration_repository = (
            PostgreSQLConnectorTargetConfigurationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryConnectorTargetConfigurationRepository()
        )
        target_profiles = (
            ()
            if is_production
            else (
                build_development_connector_target_profile(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        target_policies = (
            ()
            if is_production
            else (
                build_development_connector_target_configuration_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_target_configuration_service = ConnectorTargetConfigurationService(
            repository=target_configuration_repository,
            instance_source=resolved_connector_instance_creation_service,
            target_profile_source=InMemoryConnectorTargetProfileSource(target_profiles),
            policy_source=InMemoryConnectorTargetConfigurationPolicySource(target_policies),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if credential_assignment_service is not None:
        resolved_credential_assignment_service = credential_assignment_service
    else:
        credential_assignment_repository = (
            PostgreSQLConnectorCredentialAssignmentRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryConnectorCredentialAssignmentRepository()
        )
        credential_profiles = (
            ()
            if is_production
            else (
                build_development_connector_credential_profile(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        credential_policies = (
            ()
            if is_production
            else (
                build_development_connector_credential_assignment_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_credential_assignment_service = ConnectorCredentialAssignmentService(
            repository=credential_assignment_repository,
            target_source=resolved_target_configuration_service,
            credential_profile_source=InMemoryConnectorCredentialProfileSource(credential_profiles),
            policy_source=InMemoryConnectorCredentialAssignmentPolicySource(credential_policies),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if configuration_validation_service is not None:
        resolved_configuration_validation_service = configuration_validation_service
    else:
        configuration_validation_repository = (
            PostgreSQLConnectorConfigurationValidationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryConnectorConfigurationValidationRepository()
        )
        configuration_validation_policies = (
            ()
            if is_production
            else (
                build_development_connector_configuration_validation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_configuration_validation_service = ConnectorConfigurationValidationService(
            repository=configuration_validation_repository,
            assignment_source=resolved_credential_assignment_service,
            evidence_source=InMemoryConnectorConfigurationEvidenceSource(()),
            policy_source=InMemoryConnectorConfigurationValidationPolicySource(
                configuration_validation_policies
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if capability_enablement_service is not None:
        resolved_capability_enablement_service = capability_enablement_service
    else:
        capability_enablement_repository = (
            PostgreSQLConnectorCapabilityEnablementRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryConnectorCapabilityEnablementRepository()
        )
        capability_enablement_policies = (
            ()
            if is_production
            else (
                build_development_connector_capability_enablement_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_capability_enablement_service = ConnectorCapabilityEnablementService(
            repository=capability_enablement_repository,
            validation_source=resolved_configuration_validation_service,
            profile_source=InMemoryConnectorCapabilityProfileSource(()),
            policy_source=InMemoryConnectorCapabilityEnablementPolicySource(
                capability_enablement_policies
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if runtime_trust_service is not None:
        resolved_runtime_trust_service = runtime_trust_service
    else:
        runtime_trust_repository = (
            PostgreSQLConnectorRuntimeTrustRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorRuntimeTrustRepository()
        )
        runtime_trust_policies = (
            ()
            if is_production
            else (
                build_development_connector_runtime_trust_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_runtime_trust_service = ConnectorRuntimeTrustService(
            repository=runtime_trust_repository,
            enablement_source=resolved_capability_enablement_service,
            profile_source=InMemoryConnectorRuntimeTrustProfileSource(()),
            policy_source=InMemoryConnectorRuntimeTrustPolicySource(runtime_trust_policies),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if secret_brokerage_service is not None:
        resolved_secret_brokerage_service = secret_brokerage_service
    else:
        secret_brokerage_repository = (
            PostgreSQLConnectorSecretBrokerageRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorSecretBrokerageRepository()
        )
        secret_brokerage_policies = (
            ()
            if is_production
            else (
                build_development_connector_secret_brokerage_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_secret_brokerage_service = ConnectorSecretBrokerageService(
            repository=secret_brokerage_repository,
            runtime_trust_source=resolved_runtime_trust_service,
            credential_source=resolved_credential_assignment_service,
            profile_source=InMemoryConnectorSecretBrokerageProfileSource(()),
            policy_source=InMemoryConnectorSecretBrokeragePolicySource(secret_brokerage_policies),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if runtime_activation_service is not None:
        resolved_runtime_activation_service = runtime_activation_service
    else:
        runtime_activation_repository = (
            PostgreSQLConnectorRuntimeActivationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorRuntimeActivationRepository()
        )
        runtime_activation_policies = (
            ()
            if is_production
            else (
                build_development_connector_runtime_activation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_runtime_activation_service = ConnectorRuntimeActivationService(
            repository=runtime_activation_repository,
            source=resolved_secret_brokerage_service,
            profile_source=InMemoryConnectorRuntimeActivationProfileSource(()),
            policy_source=InMemoryConnectorRuntimeActivationPolicySource(
                runtime_activation_policies
            ),
            activator=(
                UnavailableConnectorRuntimeActivator()
                if is_production
                else SyntheticConnectorRuntimeActivator()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if target_session_service is not None:
        resolved_target_session_service = target_session_service
    else:
        target_session_repository = (
            PostgreSQLConnectorTargetSessionRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorTargetSessionRepository()
        )
        target_session_policies = (
            ()
            if is_production
            else (
                build_development_connector_target_session_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_target_session_service = ConnectorTargetSessionService(
            repository=target_session_repository,
            source=resolved_runtime_activation_service,
            profile_source=InMemoryConnectorTargetSessionProfileSource(()),
            policy_source=InMemoryConnectorTargetSessionPolicySource(target_session_policies),
            adapter=(
                UnavailableConnectorTargetSessionAdapter()
                if is_production
                else SyntheticConnectorTargetSessionAdapter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    resolved_authorization_service = (
        authorization_service
        or build_development_authorization_service(resolved_settings, resolved_audit_sink)
    )
    if invocation_authorization_service is not None:
        resolved_invocation_authorization_service = invocation_authorization_service
    else:
        invocation_authorization_repository = (
            PostgreSQLConnectorInvocationAuthorizationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryConnectorInvocationAuthorizationRepository()
        )
        invocation_authorization_policies = (
            ()
            if is_production
            else (
                build_development_connector_invocation_authorization_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_invocation_authorization_service = ConnectorInvocationAuthorizationService(
            repository=invocation_authorization_repository,
            source=resolved_target_session_service,
            profile_source=InMemoryConnectorInvocationProfileSource(()),
            envelope_source=InMemoryConnectorInvocationInputEnvelopeSource(()),
            policy_source=InMemoryConnectorInvocationAuthorizationPolicySource(
                invocation_authorization_policies
            ),
            permission_authorizer=AuthorizationConnectorCapabilityPermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if bounded_invocation_service is not None:
        resolved_bounded_invocation_service = bounded_invocation_service
    else:
        bounded_invocation_repository = (
            PostgreSQLConnectorBoundedInvocationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorBoundedInvocationRepository()
        )
        bounded_invocation_policies = (
            ()
            if is_production
            else (
                build_development_connector_bounded_invocation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_bounded_invocation_service = ConnectorBoundedInvocationService(
            repository=bounded_invocation_repository,
            source=resolved_invocation_authorization_service,
            policy_source=InMemoryConnectorBoundedInvocationPolicySource(
                bounded_invocation_policies
            ),
            permission_authorizer=AuthorizationConnectorBoundedInvocationPermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            adapter=(
                UnavailableConnectorBoundedInvocationAdapter()
                if is_production
                else SyntheticConnectorBoundedInvocationAdapter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if invocation_evidence_service is not None:
        resolved_invocation_evidence_service = invocation_evidence_service
    else:
        invocation_evidence_repository = (
            PostgreSQLConnectorInvocationEvidenceRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorInvocationEvidenceRepository()
        )
        invocation_evidence_policies = (
            ()
            if is_production
            else (
                build_development_connector_invocation_evidence_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_invocation_evidence_service = ConnectorInvocationEvidenceService(
            repository=invocation_evidence_repository,
            source=resolved_bounded_invocation_service,
            policy_source=InMemoryConnectorInvocationEvidencePolicySource(
                invocation_evidence_policies
            ),
            permission_authorizer=AuthorizationConnectorInvocationEvidencePermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            adapter=(
                UnavailableConnectorInvocationEvidenceAdapter()
                if is_production
                else SyntheticConnectorInvocationEvidenceAdapter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if operational_evidence_knowledge_draft_service is not None:
        resolved_operational_evidence_knowledge_draft_service = (
            operational_evidence_knowledge_draft_service
        )
    else:
        evidence_draft_repository = (
            PostgreSQLOperationalEvidenceKnowledgeDraftRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalEvidenceKnowledgeDraftRepository()
        )
        evidence_draft_policies = (
            ()
            if is_production
            else (
                build_development_operational_evidence_knowledge_draft_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_evidence_knowledge_draft_service = (
            OperationalEvidenceKnowledgeDraftService(
                repository=evidence_draft_repository,
                source=resolved_invocation_evidence_service,
                policy_source=InMemoryOperationalEvidenceKnowledgeDraftPolicySource(
                    evidence_draft_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalEvidenceKnowledgeDraftPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                adapter=(
                    UnavailableOperationalEvidenceKnowledgeDraftAdapter()
                    if is_production
                    else SyntheticOperationalEvidenceKnowledgeDraftAdapter()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_review_request_service is not None:
        resolved_operational_knowledge_review_request_service = (
            operational_knowledge_review_request_service
        )
    else:
        review_request_repository = (
            PostgreSQLOperationalKnowledgeReviewRequestRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeReviewRequestRepository()
        )
        review_request_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_review_request_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_review_request_service = (
            OperationalKnowledgeReviewRequestService(
                repository=review_request_repository,
                source=resolved_operational_evidence_knowledge_draft_service,
                policy_source=InMemoryOperationalKnowledgeReviewRequestPolicySource(
                    review_request_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeReviewRequestPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                adapter=(
                    UnavailableOperationalKnowledgeReviewRequestAdapter()
                    if is_production
                    else SyntheticOperationalKnowledgeReviewRequestAdapter()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_reviewer_assignment_service is not None:
        resolved_operational_knowledge_reviewer_assignment_service = (
            operational_knowledge_reviewer_assignment_service
        )
    else:
        reviewer_assignment_repository = (
            PostgreSQLOperationalKnowledgeReviewerAssignmentRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeReviewerAssignmentRepository()
        )
        reviewer_assignment_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_reviewer_assignment_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_reviewer_assignment_service = (
            OperationalKnowledgeReviewerAssignmentService(
                repository=reviewer_assignment_repository,
                source=resolved_operational_knowledge_review_request_service,
                policy_source=InMemoryOperationalKnowledgeReviewerAssignmentPolicySource(
                    reviewer_assignment_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeReviewerAssignmentPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                adapter=(
                    UnavailableOperationalKnowledgeReviewerAssignmentAdapter()
                    if is_production
                    else SyntheticOperationalKnowledgeReviewerAssignmentAdapter()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_protected_inspection_service is not None:
        resolved_operational_knowledge_protected_inspection_service = (
            operational_knowledge_protected_inspection_service
        )
    else:
        protected_inspection_repository = (
            PostgreSQLOperationalKnowledgeProtectedInspectionRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeProtectedInspectionRepository()
        )
        protected_inspection_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_protected_inspection_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_protected_inspection_service = (
            OperationalKnowledgeProtectedInspectionService(
                repository=protected_inspection_repository,
                source=resolved_operational_knowledge_reviewer_assignment_service,
                policy_source=InMemoryOperationalKnowledgeProtectedInspectionPolicySource(
                    protected_inspection_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeProtectedInspectionPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                broker=(
                    UnavailableOperationalKnowledgeProtectedInspectionBroker()
                    if is_production
                    else SyntheticOperationalKnowledgeProtectedInspectionBroker()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_protected_content_service is not None:
        resolved_operational_knowledge_protected_content_service = (
            operational_knowledge_protected_content_service
        )
    else:
        protected_content_repository = (
            PostgreSQLOperationalKnowledgeProtectedContentRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeProtectedContentRepository()
        )
        protected_content_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_protected_content_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_protected_content_service = (
            OperationalKnowledgeProtectedContentService(
                repository=protected_content_repository,
                source=resolved_operational_knowledge_protected_inspection_service,
                policy_source=InMemoryOperationalKnowledgeProtectedContentPolicySource(
                    protected_content_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeProtectedContentPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                presenter=(
                    UnavailableOperationalKnowledgeProtectedContentPresenter()
                    if is_production
                    else SyntheticOperationalKnowledgeProtectedContentPresenter()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    resolved_review_finding_recorder: SyntheticOperationalKnowledgeReviewFindingRecorder | None = (
        None
    )
    if operational_knowledge_review_finding_service is not None:
        resolved_operational_knowledge_review_finding_service = (
            operational_knowledge_review_finding_service
        )
    else:
        review_finding_repository = (
            PostgreSQLOperationalKnowledgeReviewFindingRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeReviewFindingRepository()
        )
        review_finding_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_review_finding_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        review_finding_recorder: OperationalKnowledgeReviewFindingRecorder
        if is_production:
            review_finding_recorder = UnavailableOperationalKnowledgeReviewFindingRecorder()
        else:
            resolved_review_finding_recorder = SyntheticOperationalKnowledgeReviewFindingRecorder()
            review_finding_recorder = resolved_review_finding_recorder
        resolved_operational_knowledge_review_finding_service = (
            OperationalKnowledgeReviewFindingService(
                repository=review_finding_repository,
                source=resolved_operational_knowledge_protected_content_service,
                policy_source=InMemoryOperationalKnowledgeReviewFindingPolicySource(
                    review_finding_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeReviewFindingPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                recorder=review_finding_recorder,
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_finding_presentation_service is not None:
        resolved_operational_knowledge_finding_presentation_service = (
            operational_knowledge_finding_presentation_service
        )
    else:
        finding_presentation_repository = (
            PostgreSQLOperationalKnowledgeFindingPresentationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeFindingPresentationRepository()
        )
        finding_presentation_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_finding_presentation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        finding_presenter = (
            UnavailableOperationalKnowledgeFindingPresenter()
            if is_production or resolved_review_finding_recorder is None
            else SyntheticOperationalKnowledgeFindingPresenter(
                recorder=resolved_review_finding_recorder
            )
        )
        resolved_operational_knowledge_finding_presentation_service = (
            OperationalKnowledgeFindingPresentationService(
                repository=finding_presentation_repository,
                source=resolved_operational_knowledge_review_finding_service,
                policy_source=InMemoryOperationalKnowledgeFindingPresentationPolicySource(
                    finding_presentation_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeFindingPresentationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                presenter=finding_presenter,
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_track_review_decision_service is not None:
        resolved_operational_knowledge_track_review_decision_service = (
            operational_knowledge_track_review_decision_service
        )
    else:
        track_review_decision_repository = (
            PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeTrackReviewDecisionRepository()
        )
        track_review_decision_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_track_review_decision_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_track_review_decision_service = (
            OperationalKnowledgeTrackReviewDecisionService(
                repository=track_review_decision_repository,
                source=resolved_operational_knowledge_finding_presentation_service,
                policy_source=InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource(
                    track_review_decision_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeTrackReviewDecisionPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                attestor=(
                    UnavailableOperationalKnowledgeTrackReviewDecisionAttestor()
                    if is_production
                    else SyntheticOperationalKnowledgeTrackReviewDecisionAttestor()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_correction_service is not None:
        resolved_operational_knowledge_correction_service = operational_knowledge_correction_service
    else:
        correction_repository = (
            PostgreSQLOperationalKnowledgeCorrectionRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeCorrectionRepository()
        )
        correction_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_correction_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_correction_service = OperationalKnowledgeCorrectionService(
            repository=correction_repository,
            source=resolved_operational_knowledge_track_review_decision_service,
            policy_source=InMemoryOperationalKnowledgeCorrectionPolicySource(correction_policies),
            permission_authorizer=(
                AuthorizationOperationalKnowledgeCorrectionPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            adapter=(
                UnavailableOperationalKnowledgeCorrectionAdapter()
                if is_production
                else SyntheticOperationalKnowledgeCorrectionAdapter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    resolved_operational_knowledge_review_request_service.set_resubmission_source(
        resolved_operational_knowledge_correction_service
    )
    if operational_knowledge_final_resolution_service is not None:
        resolved_operational_knowledge_final_resolution_service = (
            operational_knowledge_final_resolution_service
        )
    else:
        final_resolution_repository = (
            PostgreSQLOperationalKnowledgeFinalResolutionRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeFinalResolutionRepository()
        )
        final_resolution_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_final_resolution_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_final_resolution_service = (
            OperationalKnowledgeFinalResolutionService(
                repository=final_resolution_repository,
                source=resolved_operational_knowledge_track_review_decision_service,
                policy_source=InMemoryOperationalKnowledgeFinalResolutionPolicySource(
                    final_resolution_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeFinalResolutionPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                attestor=(
                    UnavailableOperationalKnowledgeFinalResolutionAttestor()
                    if is_production
                    else SyntheticOperationalKnowledgeFinalResolutionAttestor()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_publication_preparation_service is not None:
        resolved_operational_knowledge_publication_preparation_service = (
            operational_knowledge_publication_preparation_service
        )
    else:
        publication_preparation_repository = (
            PostgreSQLOperationalKnowledgePublicationPreparationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgePublicationPreparationRepository()
        )
        publication_preparation_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_publication_preparation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_publication_preparation_service = (
            OperationalKnowledgePublicationPreparationService(
                repository=publication_preparation_repository,
                source=resolved_operational_knowledge_final_resolution_service,
                policy_source=InMemoryOperationalKnowledgePublicationPreparationPolicySource(
                    publication_preparation_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgePublicationPreparationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                preparer=(
                    UnavailableOperationalKnowledgePublicationPreparer()
                    if is_production
                    else SyntheticOperationalKnowledgePublicationPreparer()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_source_materialization_service is not None:
        resolved_operational_knowledge_source_materialization_service = (
            operational_knowledge_source_materialization_service
        )
    else:
        source_materialization_repository = (
            PostgreSQLOperationalKnowledgeSourceMaterializationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeSourceMaterializationRepository()
        )
        source_materialization_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_source_materialization_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_source_materialization_service = (
            OperationalKnowledgeSourceMaterializationService(
                repository=source_materialization_repository,
                preparation_source=resolved_operational_knowledge_publication_preparation_service,
                lineage_source=resolved_operational_knowledge_final_resolution_service,
                policy_source=InMemoryOperationalKnowledgeSourceMaterializationPolicySource(
                    source_materialization_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeSourceMaterializationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                materializer=(
                    UnavailableOperationalKnowledgeSourceMaterializer()
                    if is_production
                    else SyntheticOperationalKnowledgeSourceMaterializer()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_deterministic_chunking_service is not None:
        resolved_operational_knowledge_deterministic_chunking_service = (
            operational_knowledge_deterministic_chunking_service
        )
    else:
        chunking_repository = (
            PostgreSQLOperationalKnowledgeChunkingRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeChunkingRepository()
        )
        chunking_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_chunking_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_deterministic_chunking_service = (
            OperationalKnowledgeDeterministicChunkingService(
                repository=chunking_repository,
                materialization_source=(
                    resolved_operational_knowledge_source_materialization_service
                ),
                preparation_source=(resolved_operational_knowledge_publication_preparation_service),
                lineage_source=resolved_operational_knowledge_final_resolution_service,
                policy_source=InMemoryOperationalKnowledgeChunkingPolicySource(chunking_policies),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeChunkingPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                chunker=(
                    UnavailableOperationalKnowledgeChunker()
                    if is_production
                    else SyntheticOperationalKnowledgeChunker()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_embedding_generation_service is not None:
        resolved_operational_knowledge_embedding_generation_service = (
            operational_knowledge_embedding_generation_service
        )
    else:
        embedding_repository = (
            PostgreSQLOperationalKnowledgeEmbeddingRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeEmbeddingRepository()
        )
        embedding_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_embedding_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_operational_knowledge_embedding_generation_service = (
            OperationalKnowledgeEmbeddingGenerationService(
                repository=embedding_repository,
                chunk_source=resolved_operational_knowledge_deterministic_chunking_service,
                policy_source=InMemoryOperationalKnowledgeEmbeddingPolicySource(embedding_policies),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeEmbeddingPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                embedder=(
                    UnavailableOperationalKnowledgeEmbedder()
                    if is_production
                    else SyntheticOperationalKnowledgeEmbedder()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_index_staging_validation_service is not None:
        resolved_operational_knowledge_index_staging_validation_service = (
            operational_knowledge_index_staging_validation_service
        )
    else:
        index_repository = (
            PostgreSQLOperationalKnowledgeIndexRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeIndexRepository()
        )
        index_embedding_policy = build_development_operational_knowledge_embedding_policy(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            issued_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        index_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_index_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                    embedding_policy=index_embedding_policy,
                ),
            )
        )
        resolved_operational_knowledge_index_staging_validation_service = (
            OperationalKnowledgeIndexStagingValidationService(
                repository=index_repository,
                embedding_source=resolved_operational_knowledge_embedding_generation_service,
                policy_source=InMemoryOperationalKnowledgeIndexPolicySource(index_policies),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeIndexPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                indexer=(
                    UnavailableOperationalKnowledgeIndexer()
                    if is_production
                    else SyntheticOperationalKnowledgeIndexer()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_retrieval_index_publication_service is not None:
        resolved_operational_knowledge_retrieval_index_publication_service = (
            operational_knowledge_retrieval_index_publication_service
        )
    else:
        publication_repository = (
            PostgreSQLOperationalKnowledgeRetrievalPublicationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryOperationalKnowledgeRetrievalPublicationRepository()
        )
        publication_embedding_policy = build_development_operational_knowledge_embedding_policy(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            issued_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        publication_index_policy = build_development_operational_knowledge_index_policy(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            issued_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            embedding_policy=publication_embedding_policy,
        )
        publication_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_retrieval_publication_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                    index_policy=publication_index_policy,
                ),
            )
        )
        resolved_operational_knowledge_retrieval_index_publication_service = (
            OperationalKnowledgeRetrievalIndexPublicationService(
                repository=publication_repository,
                index_source=resolved_operational_knowledge_index_staging_validation_service,
                policy_source=InMemoryOperationalKnowledgeRetrievalPublicationPolicySource(
                    publication_policies
                ),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeRetrievalPublicationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                publisher=(
                    UnavailableOperationalKnowledgeRetrievalPublisher()
                    if is_production
                    else SyntheticOperationalKnowledgeRetrievalPublisher()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if operational_knowledge_protected_retrieval_service is not None:
        resolved_operational_knowledge_protected_retrieval_service = (
            operational_knowledge_protected_retrieval_service
        )
    else:
        retrieval_repository = (
            PostgreSQLOperationalKnowledgeRetrievalRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else MemoryOperationalKnowledgeRetrievalRepository()
        )
        retrieval_embedding_policy = build_development_operational_knowledge_embedding_policy(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            issued_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        retrieval_index_policy = build_development_operational_knowledge_index_policy(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            issued_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            embedding_policy=retrieval_embedding_policy,
        )
        retrieval_policies = (
            ()
            if is_production
            else (
                build_development_operational_knowledge_retrieval_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                    subject_digest_salt_digest=(retrieval_index_policy.subject_digest_salt_digest),
                ),
            )
        )
        resolved_operational_knowledge_protected_retrieval_service = (
            OperationalKnowledgeProtectedRetrievalService(
                repository=retrieval_repository,
                publication_source=(
                    resolved_operational_knowledge_retrieval_index_publication_service
                ),
                policy_source=InMemoryOperationalKnowledgeRetrievalPolicySource(retrieval_policies),
                permission_authorizer=(
                    AuthorizationOperationalKnowledgeRetrievalPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                retriever=(
                    UnavailableOperationalKnowledgeTrustedRetriever()
                    if is_production
                    else SyntheticOperationalKnowledgeTrustedRetriever()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    context_assembler: TrustedProtectedModelContextAssembler
    if protected_model_context_service is not None:
        resolved_protected_model_context_service = protected_model_context_service
        context_assembler = UnavailableTrustedProtectedModelContextAssembler()
    else:
        context_repository = (
            PostgreSQLProtectedModelContextRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryProtectedModelContextRepository()
        )
        context_policies = (
            ()
            if is_production
            else (
                build_development_protected_model_context_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        context_assembler = (
            UnavailableTrustedProtectedModelContextAssembler()
            if is_production
            else SyntheticTrustedProtectedModelContextAssembler()
        )
        resolved_protected_model_context_service = GovernedProtectedModelContextService(
            repository=context_repository,
            retrieval_source=resolved_operational_knowledge_protected_retrieval_service,
            policy_source=InMemoryProtectedModelContextPolicySource(context_policies),
            permission_authorizer=AuthorizationProtectedModelContextPermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            assembler=context_assembler,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if protected_model_invocation_service is not None:
        resolved_protected_model_invocation_service = protected_model_invocation_service
    else:
        invocation_repository = (
            PostgreSQLProtectedModelInvocationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryProtectedModelInvocationRepository()
        )
        invocation_policies = (
            ()
            if is_production
            else (
                build_development_protected_model_invocation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_model_invocation_service = GovernedProtectedModelInvocationService(
            repository=invocation_repository,
            context_source=resolved_protected_model_context_service,
            context_vault=context_assembler,
            policy_source=InMemoryProtectedModelInvocationPolicySource(invocation_policies),
            permission_authorizer=AuthorizationProtectedModelInvocationPermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            gateway=(
                UnavailableTrustedProtectedModelGateway()
                if is_production
                else SyntheticTrustedProtectedModelGateway()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if protected_draft_adjudication_service is not None:
        resolved_protected_draft_adjudication_service = protected_draft_adjudication_service
    else:
        adjudication_repository = (
            PostgreSQLProtectedDraftAdjudicationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryProtectedDraftAdjudicationRepository()
        )
        adjudication_policies = (
            ()
            if is_production
            else (
                build_development_protected_draft_adjudication_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_draft_adjudication_service = GovernedProtectedDraftAdjudicationService(
            repository=adjudication_repository,
            invocation_source=resolved_protected_model_invocation_service,
            context_source=resolved_protected_model_context_service,
            context_vault=context_assembler,
            policy_source=InMemoryProtectedDraftAdjudicationPolicySource(adjudication_policies),
            permission_authorizer=(
                AuthorizationProtectedDraftAdjudicationPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            adjudicator=(
                UnavailableTrustedProtectedDraftAdjudicator()
                if is_production
                else SyntheticTrustedProtectedDraftAdjudicator()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if protected_answer_presentation_service is not None:
        resolved_protected_answer_presentation_service = protected_answer_presentation_service
    else:
        presentation_repository = (
            PostgreSQLProtectedAnswerPresentationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryProtectedAnswerPresentationRepository()
        )
        presentation_policies = (
            ()
            if is_production
            else (
                build_development_protected_answer_presentation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_answer_presentation_service = GovernedProtectedAnswerPresentationService(
            repository=presentation_repository,
            adjudication_source=resolved_protected_draft_adjudication_service,
            policy_source=InMemoryProtectedAnswerPresentationPolicySource(presentation_policies),
            permission_authorizer=(
                AuthorizationProtectedAnswerPresentationPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            presenter=(
                UnavailableTrustedProtectedAnswerPresenter()
                if is_production
                else SyntheticTrustedProtectedAnswerPresenter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if protected_recommendation_candidate_service is not None:
        resolved_protected_recommendation_candidate_service = (
            protected_recommendation_candidate_service
        )
    else:
        candidate_repository = (
            PostgreSQLProtectedRecommendationCandidateRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else MemoryProtectedRecommendationCandidateRepository()
        )
        candidate_policies = (
            ()
            if is_production
            else (
                build_development_protected_recommendation_candidate_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_recommendation_candidate_service = (
            GovernedProtectedRecommendationCandidateService(
                repository=candidate_repository,
                presentation_source=resolved_protected_answer_presentation_service,
                policy_source=InMemoryProtectedRecommendationCandidatePolicySource(
                    candidate_policies
                ),
                permission_authorizer=(
                    AuthorizationProtectedRecommendationCandidatePermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                generator=(
                    UnavailableTrustedProtectedRecommendationCandidateGenerator()
                    if is_production
                    else SyntheticTrustedProtectedRecommendationCandidateGenerator()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    resolved_graph_analyzer = InMemoryGraphImpactAnalyzer(
        snapshot=build_synthetic_graph_snapshot(
            organization_id=resolved_settings.development_organization_id,
            environment=resolved_settings.environment,
        )
    )
    if protected_candidate_impact_service is not None:
        resolved_protected_candidate_impact_service = protected_candidate_impact_service
    else:
        impact_repository = (
            PostgreSQLProtectedCandidateImpactRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryProtectedCandidateImpactRepository()
        )
        impact_policies = (
            ()
            if is_production
            else (
                build_development_protected_candidate_impact_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_candidate_impact_service = GovernedProtectedCandidateImpactService(
            repository=impact_repository,
            candidate_source=resolved_protected_recommendation_candidate_service,
            policy_source=InMemoryProtectedCandidateImpactPolicySource(impact_policies),
            permission_authorizer=(
                AuthorizationProtectedCandidateImpactPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            graph_analyzer=resolved_graph_analyzer,
            analyzer=(
                UnavailableTrustedProtectedCandidateImpactAnalyzer()
                if is_production
                else SyntheticTrustedProtectedCandidateImpactAnalyzer()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if protected_candidate_risk_recovery_service is not None:
        resolved_protected_candidate_risk_recovery_service = (
            protected_candidate_risk_recovery_service
        )
    else:
        completion_repository = (
            PostgreSQLProtectedCandidateRiskRecoveryRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else MemoryProtectedCandidateRiskRecoveryRepository()
        )
        completion_policies = (
            ()
            if is_production
            else (
                build_development_protected_candidate_risk_recovery_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        evidence_snapshots = (
            ()
            if is_production
            else (
                build_development_operational_evidence_snapshot(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    generated_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_candidate_risk_recovery_service = (
            GovernedProtectedCandidateRiskRecoveryService(
                repository=completion_repository,
                impact_source=resolved_protected_candidate_impact_service,
                policy_source=InMemoryProtectedCandidateRiskRecoveryPolicySource(
                    completion_policies
                ),
                evidence_source=InMemoryProtectedOperationalEvidenceSource(evidence_snapshots),
                permission_authorizer=(
                    AuthorizationProtectedCandidateRiskRecoveryPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                assessor=(
                    UnavailableTrustedProtectedCandidateRiskRecoveryAssessor()
                    if is_production
                    else SyntheticTrustedProtectedCandidateRiskRecoveryAssessor()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if protected_recommendation_adjudication_service is not None:
        resolved_protected_recommendation_adjudication_service = (
            protected_recommendation_adjudication_service
        )
    else:
        recommendation_adjudication_repository = (
            PostgreSQLProtectedRecommendationAdjudicationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else MemoryProtectedRecommendationAdjudicationRepository()
        )
        recommendation_adjudication_policies = (
            ()
            if is_production
            else (
                build_development_protected_recommendation_adjudication_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_recommendation_adjudication_service = (
            GovernedProtectedRecommendationAdjudicationService(
                repository=recommendation_adjudication_repository,
                completion_source=resolved_protected_candidate_risk_recovery_service,
                policy_source=InMemoryProtectedRecommendationAdjudicationPolicySource(
                    recommendation_adjudication_policies
                ),
                permission_authorizer=(
                    AuthorizationProtectedRecommendationAdjudicationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                adjudicator=(
                    UnavailableTrustedProtectedRecommendationAdjudicator()
                    if is_production
                    else SyntheticTrustedProtectedRecommendationAdjudicator()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if protected_recommendation_presentation_service is not None:
        resolved_protected_recommendation_presentation_service = (
            protected_recommendation_presentation_service
        )
    else:
        recommendation_presentation_repository = (
            PostgreSQLProtectedRecommendationPresentationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else MemoryProtectedRecommendationPresentationRepository()
        )
        recommendation_presentation_policies = (
            ()
            if is_production
            else (
                build_development_protected_recommendation_presentation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_protected_recommendation_presentation_service = (
            GovernedProtectedRecommendationPresentationService(
                repository=recommendation_presentation_repository,
                adjudication_source=resolved_protected_recommendation_adjudication_service,
                policy_source=InMemoryProtectedRecommendationPresentationPolicySource(
                    recommendation_presentation_policies
                ),
                permission_authorizer=(
                    AuthorizationProtectedRecommendationPresentationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                presenter=(
                    UnavailableTrustedProtectedRecommendationPresenter()
                    if is_production
                    else SyntheticTrustedProtectedRecommendationPresenter()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if recommendation_promotion_service is not None:
        resolved_recommendation_promotion_service = recommendation_promotion_service
    else:
        recommendation_promotion_repository = (
            PostgreSQLRecommendationPromotionRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryRecommendationPromotionRepository()
        )
        recommendation_promotion_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_promotion_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_promotion_service = GovernedRecommendationPromotionService(
            repository=recommendation_promotion_repository,
            presentation_source=resolved_protected_recommendation_presentation_service,
            policy_source=InMemoryRecommendationPromotionPolicySource(
                recommendation_promotion_policies
            ),
            permission_authorizer=AuthorizationRecommendationPromotionPermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            promoter=(
                UnavailableTrustedRecommendationPromoter()
                if is_production
                else SyntheticTrustedRecommendationPromoter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if recommendation_readiness_service is not None:
        resolved_recommendation_readiness_service = recommendation_readiness_service
    else:
        recommendation_readiness_repository = (
            PostgreSQLRecommendationReadinessRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryRecommendationReadinessRepository()
        )
        recommendation_readiness_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_readiness_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_readiness_service = GovernedRecommendationReadinessService(
            repository=recommendation_readiness_repository,
            promotion_source=resolved_recommendation_promotion_service,
            policy_source=InMemoryRecommendationReadinessPolicySource(
                recommendation_readiness_policies
            ),
            permission_authorizer=(
                AuthorizationRecommendationReadinessPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            evaluator=(
                UnavailableTrustedRecommendationReadinessEvaluator()
                if is_production
                else SyntheticTrustedRecommendationReadinessEvaluator()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if recommendation_review_request_service is not None:
        resolved_recommendation_review_request_service = recommendation_review_request_service
    else:
        recommendation_review_request_repository = (
            PostgreSQLRecommendationReviewRequestRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else MemoryRecommendationReviewRequestRepository()
        )
        recommendation_review_request_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_review_request_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_review_request_service = GovernedRecommendationReviewRequestService(
            repository=recommendation_review_request_repository,
            readiness_source=resolved_recommendation_readiness_service,
            policy_source=InMemoryRecommendationReviewRequestPolicySource(
                recommendation_review_request_policies
            ),
            permission_authorizer=(
                AuthorizationRecommendationReviewRequestPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            orchestrator=(
                UnavailableTrustedRecommendationReviewRequestOrchestrator()
                if is_production
                else SyntheticTrustedRecommendationReviewRequestOrchestrator()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    if recommendation_reviewer_assignment_service is not None:
        resolved_recommendation_reviewer_assignment_service = (
            recommendation_reviewer_assignment_service
        )
    else:
        recommendation_reviewer_assignment_repository = (
            PostgreSQLRecommendationReviewerAssignmentRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else MemoryRecommendationReviewerAssignmentRepository()
        )
        recommendation_reviewer_assignment_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_reviewer_assignment_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_reviewer_assignment_service = (
            GovernedRecommendationReviewerAssignmentService(
                repository=recommendation_reviewer_assignment_repository,
                review_request_source=resolved_recommendation_review_request_service,
                policy_source=InMemoryRecommendationReviewerAssignmentPolicySource(
                    recommendation_reviewer_assignment_policies
                ),
                permission_authorizer=(
                    AuthorizationRecommendationReviewerAssignmentPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                adapter=(
                    UnavailableTrustedRecommendationReviewerAssignmentAdapter()
                    if is_production
                    else SyntheticTrustedRecommendationReviewerAssignmentAdapter()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
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
        analyzer=resolved_graph_analyzer,
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
        app.state.target_configuration_service = resolved_target_configuration_service
        app.state.credential_assignment_service = resolved_credential_assignment_service
        app.state.configuration_validation_service = resolved_configuration_validation_service
        app.state.capability_enablement_service = resolved_capability_enablement_service
        app.state.runtime_trust_service = resolved_runtime_trust_service
        app.state.secret_brokerage_service = resolved_secret_brokerage_service
        app.state.runtime_activation_service = resolved_runtime_activation_service
        app.state.target_session_service = resolved_target_session_service
        app.state.invocation_authorization_service = resolved_invocation_authorization_service
        app.state.bounded_invocation_service = resolved_bounded_invocation_service
        app.state.invocation_evidence_service = resolved_invocation_evidence_service
        app.state.operational_evidence_knowledge_draft_service = (
            resolved_operational_evidence_knowledge_draft_service
        )
        app.state.operational_knowledge_review_request_service = (
            resolved_operational_knowledge_review_request_service
        )
        app.state.operational_knowledge_reviewer_assignment_service = (
            resolved_operational_knowledge_reviewer_assignment_service
        )
        app.state.operational_knowledge_protected_inspection_service = (
            resolved_operational_knowledge_protected_inspection_service
        )
        app.state.operational_knowledge_protected_content_service = (
            resolved_operational_knowledge_protected_content_service
        )
        app.state.operational_knowledge_review_finding_service = (
            resolved_operational_knowledge_review_finding_service
        )
        app.state.operational_knowledge_finding_presentation_service = (
            resolved_operational_knowledge_finding_presentation_service
        )
        app.state.operational_knowledge_track_review_decision_service = (
            resolved_operational_knowledge_track_review_decision_service
        )
        app.state.operational_knowledge_correction_service = (
            resolved_operational_knowledge_correction_service
        )
        app.state.operational_knowledge_final_resolution_service = (
            resolved_operational_knowledge_final_resolution_service
        )
        app.state.operational_knowledge_publication_preparation_service = (
            resolved_operational_knowledge_publication_preparation_service
        )
        app.state.operational_knowledge_source_materialization_service = (
            resolved_operational_knowledge_source_materialization_service
        )
        app.state.operational_knowledge_deterministic_chunking_service = (
            resolved_operational_knowledge_deterministic_chunking_service
        )
        app.state.operational_knowledge_embedding_generation_service = (
            resolved_operational_knowledge_embedding_generation_service
        )
        app.state.operational_knowledge_index_staging_validation_service = (
            resolved_operational_knowledge_index_staging_validation_service
        )
        app.state.operational_knowledge_retrieval_index_publication_service = (
            resolved_operational_knowledge_retrieval_index_publication_service
        )
        app.state.operational_knowledge_protected_retrieval_service = (
            resolved_operational_knowledge_protected_retrieval_service
        )
        app.state.protected_model_context_service = resolved_protected_model_context_service
        app.state.protected_model_invocation_service = resolved_protected_model_invocation_service
        app.state.protected_draft_adjudication_service = (
            resolved_protected_draft_adjudication_service
        )
        app.state.protected_answer_presentation_service = (
            resolved_protected_answer_presentation_service
        )
        app.state.protected_recommendation_candidate_service = (
            resolved_protected_recommendation_candidate_service
        )
        app.state.protected_candidate_impact_service = resolved_protected_candidate_impact_service
        app.state.protected_candidate_risk_recovery_service = (
            resolved_protected_candidate_risk_recovery_service
        )
        app.state.protected_recommendation_adjudication_service = (
            resolved_protected_recommendation_adjudication_service
        )
        app.state.protected_recommendation_presentation_service = (
            resolved_protected_recommendation_presentation_service
        )
        app.state.recommendation_promotion_service = resolved_recommendation_promotion_service
        app.state.recommendation_readiness_service = resolved_recommendation_readiness_service
        app.state.recommendation_review_request_service = (
            resolved_recommendation_review_request_service
        )
        app.state.recommendation_reviewer_assignment_service = (
            resolved_recommendation_reviewer_assignment_service
        )
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
        await resolved_recommendation_reviewer_assignment_service.close()
        await resolved_recommendation_review_request_service.close()
        await resolved_recommendation_readiness_service.close()
        await resolved_recommendation_promotion_service.close()
        await resolved_protected_recommendation_presentation_service.close()
        await resolved_protected_recommendation_adjudication_service.close()
        await resolved_protected_candidate_risk_recovery_service.close()
        await resolved_protected_candidate_impact_service.close()
        await resolved_protected_recommendation_candidate_service.close()
        await resolved_protected_answer_presentation_service.close()
        await resolved_protected_draft_adjudication_service.close()
        await resolved_protected_model_invocation_service.close()
        await resolved_protected_model_context_service.close()
        await resolved_operational_knowledge_protected_retrieval_service.close()
        await resolved_operational_knowledge_retrieval_index_publication_service.close()
        await resolved_operational_knowledge_index_staging_validation_service.close()
        await resolved_operational_knowledge_embedding_generation_service.close()
        await resolved_operational_knowledge_deterministic_chunking_service.close()
        await resolved_operational_knowledge_source_materialization_service.close()
        await resolved_operational_knowledge_publication_preparation_service.close()
        await resolved_operational_knowledge_final_resolution_service.close()
        await resolved_operational_knowledge_correction_service.close()
        await resolved_operational_knowledge_track_review_decision_service.close()
        await resolved_operational_knowledge_finding_presentation_service.close()
        await resolved_operational_knowledge_review_finding_service.close()
        await resolved_operational_knowledge_protected_content_service.close()
        await resolved_operational_knowledge_protected_inspection_service.close()
        await resolved_operational_knowledge_reviewer_assignment_service.close()
        await resolved_operational_knowledge_review_request_service.close()
        await resolved_operational_evidence_knowledge_draft_service.close()
        await resolved_invocation_evidence_service.close()
        await resolved_bounded_invocation_service.close()
        await resolved_invocation_authorization_service.close()
        await resolved_target_session_service.close()
        await resolved_runtime_activation_service.close()
        await resolved_secret_brokerage_service.close()
        await resolved_runtime_trust_service.close()
        await resolved_capability_enablement_service.close()
        await resolved_configuration_validation_service.close()
        await resolved_credential_assignment_service.close()
        await resolved_target_configuration_service.close()
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
    app.include_router(target_configuration.router, prefix="/api/v1")
    app.include_router(credential_assignments.router, prefix="/api/v1")
    app.include_router(configuration_validations.router, prefix="/api/v1")
    app.include_router(capability_enablements.router, prefix="/api/v1")
    app.include_router(runtime_trust_grants.router, prefix="/api/v1")
    app.include_router(secret_brokerage_authorizations.router, prefix="/api/v1")
    app.include_router(runtime_activations.router, prefix="/api/v1")
    app.include_router(target_session_verifications.router, prefix="/api/v1")
    app.include_router(invocation_authorizations.router, prefix="/api/v1")
    app.include_router(bounded_invocations.router, prefix="/api/v1")
    app.include_router(invocation_evidence.router, prefix="/api/v1")
    app.include_router(evidence_drafts.router, prefix="/api/v1")
    app.include_router(draft_review_requests.router, prefix="/api/v1")
    app.include_router(reviewer_assignments.router, prefix="/api/v1")
    app.include_router(protected_inspections.router, prefix="/api/v1")
    app.include_router(protected_content.router, prefix="/api/v1")
    app.include_router(review_findings.router, prefix="/api/v1")
    app.include_router(finding_presentations.router, prefix="/api/v1")
    app.include_router(review_decisions.router, prefix="/api/v1")
    app.include_router(correction_resubmissions.router, prefix="/api/v1")
    app.include_router(final_resolutions.router, prefix="/api/v1")
    app.include_router(publication_preparations.router, prefix="/api/v1")
    app.include_router(source_materializations.router, prefix="/api/v1")
    app.include_router(deterministic_chunking.router, prefix="/api/v1")
    app.include_router(embedding_generation.router, prefix="/api/v1")
    app.include_router(index_staging_validation.router, prefix="/api/v1")
    app.include_router(retrieval_index_publication.router, prefix="/api/v1")
    app.include_router(protected_retrieval.router, prefix="/api/v1")
    app.include_router(model_context_assembly.router, prefix="/api/v1")
    app.include_router(protected_model_invocation.router, prefix="/api/v1")
    app.include_router(protected_draft_adjudication.router, prefix="/api/v1")
    app.include_router(protected_answer_presentations.router, prefix="/api/v1")
    app.include_router(protected_recommendation_candidates.router, prefix="/api/v1")
    app.include_router(protected_candidate_impacts.router, prefix="/api/v1")
    app.include_router(protected_candidate_risk_recovery.router, prefix="/api/v1")
    app.include_router(protected_recommendation_adjudications.router, prefix="/api/v1")
    app.include_router(protected_recommendation_presentations.router, prefix="/api/v1")
    app.include_router(recommendation_promotions.router, prefix="/api/v1")
    app.include_router(recommendation_readiness.router, prefix="/api/v1")
    app.include_router(recommendation_review_requests.router, prefix="/api/v1")
    app.include_router(recommendation_reviewer_assignments.router, prefix="/api/v1")
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
