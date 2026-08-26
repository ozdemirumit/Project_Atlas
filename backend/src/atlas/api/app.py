from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

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
    bundled_connector_catalog,
    capability_enablements,
    change_reviews,
    configuration_validations,
    connector_connection_tests,
    connector_validations,
    connectors,
    content_policy_scans,
    contract_validations,
    conversations,
    correction_resubmissions,
    credential_assignments,
    deployment_configuration,
    deterministic_chunking,
    draft_review_requests,
    embedding_generation,
    evidence_drafts,
    final_recommendation_dispositions,
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
    inventory_devices,
    investigations,
    invocation_authorizations,
    invocation_evidence,
    itsm_integrations,
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
    recommendation_correction_resubmissions,
    recommendation_finding_presentations,
    recommendation_human_review_findings,
    recommendation_promotions,
    recommendation_protected_contents,
    recommendation_protected_inspections,
    recommendation_readiness,
    recommendation_review_decisions,
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
    workflows,
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
from atlas.modules.connectors.adapters.bundled_connection_configuration_memory import (
    InMemoryBundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.adapters.bundled_operator_state_postgres import (
    PostgreSQLBundledConnectionConfigurationRepository,
    PostgreSQLBundledConnectorRuntimeStateRepository,
    PostgreSQLConnectorConnectionTestResultRepository,
)
from atlas.modules.connectors.adapters.bundled_runtime_state_memory import (
    InMemoryBundledConnectorRuntimeStateRepository,
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
from atlas.modules.connectors.adapters.connection_test_credential_environment import (
    DevelopmentEnvironmentCredentialMaterializer,
)
from atlas.modules.connectors.adapters.connection_test_memory import (
    InMemoryConnectorConnectionTestResultRepository,
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
    DevelopmentConnectorInvocationEvidenceStore,
    DevelopmentConnectorInvocationInputEnvelopeSource,
    DevelopmentConnectorInvocationProfileSource,
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
from atlas.modules.connectors.adapters.runtime_deactivation_memory import (
    InMemoryConnectorRuntimeDeactivationRepository,
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
from atlas.modules.connectors.adapters.upgrade_approval_memory import (
    InMemoryConnectorUpgradeApprovalPolicySource,
    InMemoryConnectorUpgradeApprovalRepository,
    InMemoryConnectorUpgradeAuditReadinessSource,
    InMemoryConnectorUpgradeItsmChangeEvidenceSource,
    InMemoryConnectorUpgradeMaintenanceWindowEvidenceSource,
    InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource,
)
from atlas.modules.connectors.adapters.upgrade_approval_postgres import (
    PostgreSQLConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.adapters.upgrade_evidence_authenticity_memory import (
    NonProductionHmacUpgradeEvidenceAuthenticityProvider,
    UnavailableUpgradeEvidenceAuthenticityProvider,
)
from atlas.modules.connectors.adapters.upgrade_onboarding_policy_authenticity_memory import (
    HmacConnectorUpgradeSigningProviderOnboardingPolicyVerifier,
    InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource,
    InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource,
    UnavailableConnectorUpgradeSigningProviderOnboardingPolicyVerifier,
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
from atlas.modules.connectors.application.bundled_catalog import (
    BundledConnectorCatalogService,
    build_hitachi_ops_center_bundled_descriptor,
)
from atlas.modules.connectors.application.bundled_connection_configuration import (
    BundledConnectionConfigurationService,
)
from atlas.modules.connectors.application.bundled_runtime_state import (
    BundledConnectorRuntimeStateService,
)
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementService,
    build_development_connector_capability_enablement_policy,
)
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationService,
    build_development_connector_configuration_validation_policy,
)
from atlas.modules.connectors.application.connection_test import ConnectorConnectionTestService
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
from atlas.modules.connectors.application.instance_lifecycle import (
    ConnectorInstanceLifecycleService,
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
from atlas.modules.connectors.application.runtime_deactivation import (
    ConnectorRuntimeDeactivationService,
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
from atlas.modules.connectors.application.upgrade_approval import (
    ConnectorUpgradeApprovalService,
    build_development_connector_upgrade_approval_policy,
    build_development_connector_upgrade_signing_provider_onboarding_policy,
    build_development_connector_upgrade_signing_provider_onboarding_policy_attestation,
    build_development_connector_upgrade_signing_provider_onboarding_policy_trust_key,
)
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeSigningProviderOnboardingPolicyVerifier,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
    PackageInstallationUpgradeSource,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.application.vulnerability_analysis import (
    PackageVulnerabilityAnalysisService,
    build_bootstrap_advisory_snapshot,
)
from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeEvidenceSigningKey,
    ConnectorUpgradeEvidenceSigningKeyState,
    ConnectorUpgradeSigningProviderOnboardingPolicyAttestation,
    ConnectorUpgradeSigningProviderOnboardingPolicySnapshot,
    ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.connection_test_https import (
    HitachiOpsCenterConnectionTestHttpsFactory,
)
from atlas.modules.conversations.adapters.grounded import GroundedConversationGenerator
from atlas.modules.conversations.adapters.memory import InMemoryConversationRepository
from atlas.modules.conversations.adapters.postgres import PostgreSQLConversationRepository
from atlas.modules.conversations.adapters.targets import (
    DevelopmentConversationTargetAccessSource,
    EmptyConversationTargetAccessSource,
)
from atlas.modules.conversations.adapters.unavailable import UnavailableConversationRepository
from atlas.modules.conversations.application.ports import ConversationTargetAccessSource
from atlas.modules.conversations.application.service import ConversationService
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationScope,
)
from atlas.modules.graph.adapters.synthetic import build_synthetic_graph_snapshot
from atlas.modules.graph.application.engine import InMemoryGraphImpactAnalyzer
from atlas.modules.graph.application.service import GraphImpactService
from atlas.modules.health_checks.adapters.configured_hitachi import (
    ConfiguredHitachiHealthExecutor,
)
from atlas.modules.health_checks.adapters.hitachi import (
    CAPACITY_DEFINITION_ID,
    CONTROLLER_DEFINITION_ID,
)
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
from atlas.modules.inventory.adapters.memory import InMemoryInventoryDeviceRepository
from atlas.modules.inventory.adapters.postgres import PostgreSQLInventoryDeviceRepository
from atlas.modules.inventory.application.service import InventoryDeviceService
from atlas.modules.investigations.adapters.synthetic import SyntheticInvestigationAssembler
from atlas.modules.investigations.application.service import InvestigationService
from atlas.modules.itsm.adapters.memory import InMemoryItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.onboarding import (
    DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource,
    EmptyItsmSandboxOnboardingEvidenceSource,
    InMemoryItsmSandboxOnboardingPolicyProvenanceSource,
    InMemoryItsmSandboxOnboardingPolicySource,
    InMemoryItsmSandboxOnboardingPolicyTrustSource,
    UnavailableItsmSandboxOnboardingPolicyVerifier,
    build_development_itsm_sandbox_onboarding_policy,
    build_development_itsm_sandbox_onboarding_policy_authenticity,
)
from atlas.modules.itsm.adapters.postgres import PostgreSQLItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.sandbox import (
    DeterministicNoNetworkItsmSandboxConformanceAdapter,
    UnavailableItsmSandboxConformanceAdapter,
)
from atlas.modules.itsm.application.service import ItsmIntegrationService
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
from atlas.modules.platform.domain.advisory_posture import (
    assert_advisory_only_component_registry,
    assert_advisory_only_composition,
)
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import RcaService
from atlas.modules.recommendations.adapters.correction_resubmission_memory import (
    InMemoryRecommendationCorrectionPolicySource,
    InMemoryRecommendationCorrectionRepository,
)
from atlas.modules.recommendations.adapters.correction_resubmission_permission import (
    AuthorizationRecommendationCorrectionPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.correction_resubmission_postgres import (
    PostgreSQLRecommendationCorrectionRepository,
)
from atlas.modules.recommendations.adapters.correction_resubmission_synthetic import (
    SyntheticRecommendationCorrectionAdapter,
    UnavailableRecommendationCorrectionAdapter,
)
from atlas.modules.recommendations.adapters.final_disposition_memory import (
    InMemoryFinalRecommendationDispositionPolicySource,
    InMemoryFinalRecommendationDispositionRepository,
)
from atlas.modules.recommendations.adapters.final_disposition_permission import (
    AuthorizationFinalRecommendationDispositionPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.final_disposition_postgres import (
    PostgreSQLFinalRecommendationDispositionRepository,
)
from atlas.modules.recommendations.adapters.final_disposition_synthetic import (
    SyntheticFinalRecommendationDispositionAttestor,
    UnavailableFinalRecommendationDispositionAttestor,
)
from atlas.modules.recommendations.adapters.finding_presentation_memory import (
    InMemoryRecommendationFindingPresentationPolicySource,
    InMemoryRecommendationFindingPresentationRepository,
)
from atlas.modules.recommendations.adapters.finding_presentation_permission import (
    AuthorizationRecommendationFindingPresentationPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.finding_presentation_postgres import (
    PostgreSQLRecommendationFindingPresentationRepository,
)
from atlas.modules.recommendations.adapters.finding_presentation_synthetic import (
    SyntheticRecommendationFindingPresenter,
    UnavailableRecommendationFindingPresenter,
)
from atlas.modules.recommendations.adapters.human_review_finding_memory import (
    InMemoryRecommendationHumanReviewFindingPolicySource,
    InMemoryRecommendationHumanReviewFindingRepository,
)
from atlas.modules.recommendations.adapters.human_review_finding_permission import (
    AuthorizationRecommendationHumanReviewFindingPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.human_review_finding_postgres import (
    PostgreSQLRecommendationHumanReviewFindingRepository,
)
from atlas.modules.recommendations.adapters.human_review_finding_synthetic import (
    SyntheticRecommendationHumanReviewFindingRecorder,
    UnavailableRecommendationHumanReviewFindingRecorder,
)
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
from atlas.modules.recommendations.adapters.protected_content_memory import (
    InMemoryRecommendationProtectedContentPolicySource,
    InMemoryRecommendationProtectedContentRepository,
)
from atlas.modules.recommendations.adapters.protected_content_permission import (
    AuthorizationRecommendationProtectedContentPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.protected_content_postgres import (
    PostgreSQLRecommendationProtectedContentRepository,
)
from atlas.modules.recommendations.adapters.protected_content_synthetic import (
    SyntheticRecommendationProtectedContentPresenter,
    UnavailableRecommendationProtectedContentPresenter,
)
from atlas.modules.recommendations.adapters.protected_inspection_memory import (
    InMemoryRecommendationProtectedInspectionPolicySource,
    InMemoryRecommendationProtectedInspectionRepository,
)
from atlas.modules.recommendations.adapters.protected_inspection_permission import (
    AuthorizationRecommendationProtectedInspectionPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.protected_inspection_postgres import (
    PostgreSQLRecommendationProtectedInspectionRepository,
)
from atlas.modules.recommendations.adapters.protected_inspection_synthetic import (
    SyntheticRecommendationProtectedInspectionBroker,
    UnavailableRecommendationProtectedInspectionBroker,
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
from atlas.modules.recommendations.adapters.readiness_promotion_source import (
    RecommendationReadinessPromotionSourceRouter,
)
from atlas.modules.recommendations.adapters.readiness_synthetic import (
    SyntheticTrustedRecommendationReadinessEvaluator,
    UnavailableTrustedRecommendationReadinessEvaluator,
)
from atlas.modules.recommendations.adapters.review_decision_memory import (
    InMemoryRecommendationTrackReviewDecisionPolicySource,
    InMemoryRecommendationTrackReviewDecisionRepository,
)
from atlas.modules.recommendations.adapters.review_decision_permission import (
    AuthorizationRecommendationTrackReviewDecisionPermissionAuthorizer,
)
from atlas.modules.recommendations.adapters.review_decision_postgres import (
    PostgreSQLRecommendationTrackReviewDecisionRepository,
)
from atlas.modules.recommendations.adapters.review_decision_synthetic import (
    SyntheticRecommendationTrackReviewDecisionAttestor,
    UnavailableRecommendationTrackReviewDecisionAttestor,
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
from atlas.modules.recommendations.application.correction_resubmission import (
    RecommendationCorrectionService,
    build_development_recommendation_correction_policy,
)
from atlas.modules.recommendations.application.final_disposition import (
    FinalRecommendationDispositionService,
    build_development_final_recommendation_disposition_policy,
)
from atlas.modules.recommendations.application.finding_presentation import (
    RecommendationFindingPresentationService,
    build_development_recommendation_finding_presentation_policy,
)
from atlas.modules.recommendations.application.finding_presentation_ports import (
    RecommendationFindingPresenter,
)
from atlas.modules.recommendations.application.human_review_finding import (
    RecommendationHumanReviewFindingService,
    build_development_recommendation_human_review_finding_policy,
)
from atlas.modules.recommendations.application.human_review_finding_ports import (
    RecommendationHumanReviewFindingRecorder,
)
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
    build_development_recommendation_promotion_policy,
)
from atlas.modules.recommendations.application.protected_content import (
    RecommendationProtectedContentService,
    build_development_recommendation_protected_content_policy,
)
from atlas.modules.recommendations.application.protected_inspection import (
    RecommendationProtectedInspectionService,
    build_development_recommendation_protected_inspection_policy,
)
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
    build_development_recommendation_readiness_policy,
)
from atlas.modules.recommendations.application.review_decision import (
    RecommendationTrackReviewDecisionService,
    build_development_recommendation_track_review_decision_policy,
)
from atlas.modules.recommendations.application.review_decision_ports import (
    RecommendationTrackReviewDecisionAttestor,
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
from atlas.modules.reports.adapters.handoff_review_memory import (
    InMemoryItsmHandoffReviewRepository,
)
from atlas.modules.reports.adapters.handoff_review_postgres import (
    PostgreSQLItsmHandoffReviewRepository,
)
from atlas.modules.reports.adapters.memory import InMemoryTechnicalReportRepository
from atlas.modules.reports.adapters.postgres import PostgreSQLTechnicalReportRepository
from atlas.modules.reports.adapters.synthetic import SyntheticTechnicalReportAssembler
from atlas.modules.reports.application.handoff_review_service import ItsmHandoffReviewService
from atlas.modules.reports.application.service import ReportService
from atlas.modules.security_export.adapters.synthetic import (
    SyntheticTlsSyslogTransport,
    build_synthetic_syslog_destinations,
)
from atlas.modules.security_export.application.service import SecurityExportService
from atlas.modules.storage.adapters.configured_hitachi import ConfiguredHitachiStorageProvider
from atlas.modules.storage.adapters.synthetic import SyntheticStorageOverviewProvider
from atlas.modules.storage.application.service import StorageOperationsService
from atlas.modules.support.adapters.filesystem import FilesystemSupportBundlePublisher
from atlas.modules.support.adapters.memory import InMemorySupportBundleExportRepository
from atlas.modules.support.adapters.postgres import PostgreSQLSupportBundleExportRepository
from atlas.modules.support.application.service import SupportBundleService
from atlas.modules.upgrade.adapters.memory import InMemoryUpgradeSimulationRepository
from atlas.modules.upgrade.adapters.postgres import PostgreSQLUpgradeSimulationRepository
from atlas.modules.upgrade.application.service import UpgradeService
from atlas.modules.workflows.adapters import (
    DenyAllWorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier,
    DenyAllWorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier,
    DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier,
    DenyAllWorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier,
    SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors,
    SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener,
    UnavailableWorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleOpenabilityAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter,
    UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener,
    UnavailableWorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor,
)
from atlas.modules.workflows.adapters.credential_materialization_synthetic import (
    SyntheticWorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.adapters.credential_materialization_unavailable import (
    UnavailableWorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.adapters.endpoint_materialization_synthetic import (
    SyntheticWorkflowPhysicalTransportEndpointMaterializer,
)
from atlas.modules.workflows.adapters.endpoint_materialization_unavailable import (
    UnavailableWorkflowPhysicalTransportEndpointMaterializer,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.protected_resident_context_accessors import (
    DenyAllWorkflowProtectedResidentContextAccessorReadinessSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedResidentContextAccessorReadinessAttestor,
    DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor,
    UnavailableWorkflowProtectedResidentContextAccessorReadinessAttestor,
    UnavailableWorkflowProtectedResidentContextTrustedAccessor,
)
from atlas.modules.workflows.adapters.protected_resident_context_lifecycle_attestors import (
    DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor,
    UnavailableWorkflowProtectedResidentContextLifecycleAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_context_injectors import (
    DenyAllWorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeSlotReadinessSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector,
    DeterministicDevelopmentWorkflowProtectedRuntimeSlotReadinessAttestor,
    UnavailableWorkflowProtectedRuntimeContextTrustedInjector,
    UnavailableWorkflowProtectedRuntimeSlotReadinessAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_context_users import (
    DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier,
    DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeContextTrustedUser,
    UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_handle_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_process_creation_lifecycle_attestors import (  # noqa: E501
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeProcessCreationLifecycleAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_process_creators import (
    DenyAllWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator,
    UnavailableWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    UnavailableWorkflowProtectedRuntimeProcessCreator,
)
from atlas.modules.workflows.adapters.protected_runtime_process_resume_state_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessResumeStateAttestor,
    UnavailableWorkflowProtectedRuntimeProcessResumeStateAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_process_schedulers import (
    DenyAllWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeProcessScheduler,
    UnavailableWorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
)
from atlas.modules.workflows.adapters.protected_runtime_process_scheduling_state_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingStateAttestor,
    UnavailableWorkflowProtectedRuntimeProcessSchedulingStateAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_readiness_assessors import (
    DenyAllWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeReadinessAssessor,
    UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner,
)
from atlas.modules.workflows.adapters.protected_runtime_readiness_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeReadinessLifecycleAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_slot_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeSlotLifecycleAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_start_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeStartLifecycleAttestor,
)
from atlas.modules.workflows.adapters.protected_runtime_starters import (
    DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeStarter,
    DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeStarter,
    UnavailableWorkflowProtectedRuntimeStartInstructionSigner,
)
from atlas.modules.workflows.adapters.target_context_access_status_attestors import (
    DenyAllWorkflowProtectedArtifactStatusSignatureVerifier,
    UnavailableWorkflowProtectedCredentialStatusAttestor,
    UnavailableWorkflowProtectedEndpointStatusAttestor,
)
from atlas.modules.workflows.adapters.target_context_artifact_opener_unavailable import (
    UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener,
)
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    DeploymentEventTransportProfileRegistry,
    DeploymentEventTransportRouteRegistry,
    DeploymentPhysicalTransportCredentialAssignmentRegistry,
    DeploymentPhysicalTransportCredentialAssignmentSynchronizer,
    WorkflowAttemptMaterializationRepository,
    WorkflowAttemptMaterializationService,
    WorkflowDispatchEventEnvelopeRepository,
    WorkflowDispatchEventEnvelopeService,
    WorkflowDispatchIntentStagingRepository,
    WorkflowDispatchIntentStagingService,
    WorkflowEventByteArtifactRepository,
    WorkflowEventByteArtifactService,
    WorkflowEventLogicalChannelBindingRepository,
    WorkflowEventLogicalChannelBindingService,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
    WorkflowEventPhysicalTransportCredentialMaterializationRepository,
    WorkflowEventPhysicalTransportCredentialMaterializationService,
    WorkflowEventPhysicalTransportEndpointMaterializationRepository,
    WorkflowEventPhysicalTransportEndpointMaterializationService,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    WorkflowEventPhysicalTransportRouteBindingRepository,
    WorkflowEventPhysicalTransportRouteBindingService,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
    WorkflowEventPhysicalTransportTargetContextBindingRepository,
    WorkflowEventPhysicalTransportTargetContextBindingService,
    WorkflowEventTransportAdmissionRepository,
    WorkflowEventTransportAdmissionService,
    WorkflowEventTransportCompatibilityAdmissionRepository,
    WorkflowEventTransportCompatibilityAdmissionService,
    WorkflowOrchestrationLeaseRepository,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseRepository,
    WorkflowOutboxPublicationLeaseService,
    WorkflowPlanningService,
    WorkflowPlanRepository,
    WorkflowProtectedResidentContextAccessAuthorizationRepository,
    WorkflowProtectedResidentContextAccessAuthorizationService,
    WorkflowProtectedResidentContextAccessConsumptionRepository,
    WorkflowProtectedResidentContextAccessConsumptionService,
    WorkflowProtectedResidentContextLifecycleAttestor,
    WorkflowProtectedResidentContextLifecycleSignatureVerifier,
    WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier,
    WorkflowProtectedRuntimeContextInjectionAuthorizationRepository,
    WorkflowProtectedRuntimeContextInjectionAuthorizationService,
    WorkflowProtectedRuntimeContextInjectionConsumptionRepository,
    WorkflowProtectedRuntimeContextInjectionConsumptionService,
    WorkflowProtectedRuntimeContextTrustedInjector,
    WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService,
    WorkflowProtectedRuntimeContextUseAuthorizationRepository,
    WorkflowProtectedRuntimeContextUseAuthorizationService,
    WorkflowProtectedRuntimeContextUseRepository,
    WorkflowProtectedRuntimeContextUseService,
    WorkflowProtectedRuntimeHandleLifecycleAttestation,
    WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
    WorkflowProtectedRuntimeHandleLifecycleAttestor,
    WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
    WorkflowProtectedRuntimeSlotLifecycleAttestor,
    WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier,
    WorkflowProtectedRuntimeSlotReadinessAttestor,
    WorkflowProtectedRuntimeSlotReadinessSignatureVerifier,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
    WorkflowProtectedTransportTargetContextCapsuleHandoffService,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService,
    WorkflowProtectedTransportTargetContextCapsuleOpeningService,
    WorkflowRunMaterializationRepository,
    WorkflowRunMaterializationService,
    WorkflowTargetContextAccessAuthorizationLeaseRepository,
    WorkflowTargetContextCapsuleHandoffRepository,
    WorkflowTargetContextCapsuleOpeningRepository,
    WorkflowTransportCredentialAccessAuthorizationLeaseRepository,
    WorkflowTransportCredentialAssignmentBindingRepository,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository,
    WorkflowTransportCredentialAssignmentSnapshotRepository,
    WorkflowTransportCredentialAssignmentSnapshotService,
    WorkflowTransportProfileSnapshotRepository,
    WorkflowTransportProfileSnapshotService,
    WorkflowTransportRouteSnapshotRepository,
    WorkflowTransportRouteSnapshotService,
)
from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E501
    WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationAuthorizationRepository,
    WorkflowProtectedRuntimeProcessCreationLifecycleAttestor,
    WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_authorizations import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationConsumptionRepository,
    WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    WorkflowProtectedRuntimeProcessCreationInstructionSigner,
    WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    WorkflowProtectedRuntimeProcessCreator,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumptions import (
    WorkflowProtectedRuntimeProcessCreationConsumptionService,
)
from atlas.modules.workflows.application.protected_runtime_process_resume_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessResumeAuthorizationRepository,
    WorkflowProtectedRuntimeProcessResumeStateAttestor,
    WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_process_resume_authorizations import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository,
    WorkflowProtectedRuntimeProcessSchedulingStateAttestor,
    WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_authorizations import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessScheduler,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository,
    WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier,
    WorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
    WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumptions import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionService,
)
from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationRepository,
    WorkflowProtectedRuntimeReadinessLifecycleAttestor,
    WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_readiness_authorizations import (
    WorkflowProtectedRuntimeReadinessAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessAssessor,
    WorkflowProtectedRuntimeReadinessConsumptionRepository,
    WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier,
    WorkflowProtectedRuntimeReadinessInstructionSigner,
    WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumptions import (
    WorkflowProtectedRuntimeReadinessConsumptionService,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationRepository,
    WorkflowProtectedRuntimeStartLifecycleAttestor,
    WorkflowProtectedRuntimeStartLifecycleSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_start_authorizations import (
    WorkflowProtectedRuntimeStartAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionRepository,
    WorkflowProtectedRuntimeStarter,
    WorkflowProtectedRuntimeStartInstructionSignatureVerifier,
    WorkflowProtectedRuntimeStartInstructionSigner,
    WorkflowProtectedRuntimeStartReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_start_consumptions import (
    WorkflowProtectedRuntimeStartConsumptionService,
)
from atlas.modules.workflows.application.target_context_artifact_opening_ports import (
    WorkflowTargetContextArtifactOpeningRepository,
)
from atlas.modules.workflows.application.target_context_artifact_openings import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
)
from atlas.modules.workflows.application.target_context_capsule_consumer_binding_ports import (
    WorkflowTargetContextCapsuleConsumerBindingRepository,
)
from atlas.modules.workflows.application.target_context_capsule_consumer_bindings import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportProfile,
    DeploymentEventTransportRoute,
    DeploymentEventTransportRouteSelectionHead,
    DeploymentPhysicalTransportCredentialAssignment,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)


class _WorkflowCredentialAccessAuthorizationNoStoreMiddleware(BaseHTTPMiddleware):
    _PATHS = frozenset(
        {
            "/api/v1/workflows/physical-transport-credential-access-authorization-leases",
            "/api/v1/workflows/physical-transport-credential-materializations",
            "/api/v1/workflows/physical-transport-target-context-bindings",
            ("/api/v1/workflows/physical-transport-target-context-access-authorization-leases"),
            "/api/v1/workflows/physical-transport-target-context-artifact-openings",
            "/api/v1/workflows/physical-transport-target-context-capsule-consumer-bindings",
            (
                "/api/v1/workflows/"
                "physical-transport-target-context-capsule-handoff-authorization-leases"
            ),
            "/api/v1/workflows/physical-transport-target-context-capsule-handoffs",
            (
                "/api/v1/workflows/"
                "physical-transport-target-context-capsule-opening-authorization-leases"
            ),
            "/api/v1/workflows/physical-transport-target-context-capsule-openings",
            "/api/v1/workflows/protected-resident-context-access-authorizations",
            "/api/v1/workflows/protected-resident-context-access-consumptions",
            "/api/v1/workflows/protected-runtime-context-injection-authorizations",
            "/api/v1/workflows/protected-runtime-context-injection-consumptions",
            "/api/v1/workflows/protected-runtime-context-use-authorizations",
            ("/api/v1/workflows/protected-runtime-context-use-authorization-consumptions"),
            "/api/v1/workflows/protected-runtime-readiness-authorizations",
            "/api/v1/workflows/protected-runtime-readiness-consumptions",
            "/api/v1/workflows/protected-runtime-process-creation-authorizations",
            "/api/v1/workflows/protected-runtime-process-scheduling-authorizations",
            "/api/v1/workflows/protected-runtime-process-resume-authorizations",
            "/api/v1/workflows/protected-runtime-start-authorizations",
            "/api/v1/workflows/protected-runtime-start-consumptions",
        }
    )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        if request.url.path in self._PATHS:
            response.headers.update(
                {
                    "Cache-Control": "no-store, max-age=0",
                    "Pragma": "no-cache",
                    "Referrer-Policy": "no-referrer",
                }
            )
        return response


class _UnavailableWorkflowTargetContextArtifactOpeningRepository:
    """Fail-closed composition placeholder; it never falls back to memory state."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("target-context artifact opening repository is unavailable")


class _UnavailableWorkflowTargetContextCapsuleConsumerBindingRepository:
    """Fail-closed composition placeholder; it never falls back to memory state."""

    @property
    def durable(self) -> bool:
        return False

    async def bind_target_context_capsule_consumer(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule consumer binding repository is unavailable")

    async def list_target_context_capsule_consumer_bindings(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule consumer binding repository is unavailable")


class _UnavailableWorkflowTargetContextCapsuleHandoffAuthorizationLeaseRepository:
    """Fail-closed handoff authorization placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("target-context capsule handoff repository is unavailable")

    async def get_target_context_capsule_consumer_binding_by_id(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule handoff repository is unavailable")

    async def authorize_target_context_capsule_handoff(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule handoff repository is unavailable")

    async def list_target_context_capsule_handoff_authorization_leases(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule handoff repository is unavailable")


class _UnavailableWorkflowTargetContextCapsuleOpeningAuthorizationLeaseRepository:
    """Fail-closed opening authorization placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("target-context capsule opening authorization is unavailable")

    async def get_target_context_capsule_opening_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule opening authorization is unavailable")

    async def authorize_target_context_capsule_opening(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule opening authorization is unavailable")

    async def list_target_context_capsule_opening_authorization_leases(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule opening authorization is unavailable")


class _UnavailableWorkflowProtectedResidentContextAccessAuthorizationRepository:
    """Fail-closed IMP-216 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("protected access authorization is unavailable")

    async def preflight_protected_resident_context_access_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access authorization is unavailable")

    async def get_protected_resident_context_access_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access authorization is unavailable")

    async def authorize_protected_resident_context_access(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected access authorization is unavailable")

    async def list_protected_resident_context_access_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access authorization is unavailable")


class _UnavailableWorkflowProtectedResidentContextAccessConsumptionRepository:
    """Fail-closed ADR-167 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("protected access consumption is unavailable")

    async def lookup_protected_resident_context_access_consumption_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access consumption is unavailable")

    async def get_protected_resident_context_access_consumption_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access consumption is unavailable")

    async def claim_protected_resident_context_access_consumption(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access consumption is unavailable")

    async def record_protected_resident_context_access_consumption_result(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access consumption is unavailable")

    async def list_protected_resident_context_access_consumption_attempts(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access consumption is unavailable")

    async def get_protected_resident_context_access_consumption_results(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected access consumption is unavailable")


class _UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor:
    """Fail-closed production/default lifecycle evidence boundary."""

    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_handle_lifecycle(
        self, request: WorkflowProtectedRuntimeHandleLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeHandleLifecycleAttestation:
        del request
        raise RuntimeError("protected runtime-handle lifecycle attestor is unavailable")

    def verify_runtime_handle_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    ) -> bool:
        del attestation
        return False


class _UnavailableWorkflowProtectedRuntimeContextInjectionAuthorizationRepository:
    """Fail-closed ADR-168 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("runtime-context injection authorization is unavailable")

    async def preflight_protected_runtime_context_injection_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection authorization is unavailable")

    async def get_protected_runtime_context_injection_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection authorization is unavailable")

    async def authorize_protected_runtime_context_injection(self, *_: object, **__: object) -> None:
        raise RuntimeError("runtime-context injection authorization is unavailable")

    async def list_protected_runtime_context_injection_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeContextInjectionConsumptionRepository:
    """Fail-closed ADR-169 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("runtime-context injection consumption is unavailable")

    async def lookup_protected_runtime_context_injection_consumption_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection consumption is unavailable")

    async def get_protected_runtime_context_injection_consumption_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection consumption is unavailable")

    async def claim_protected_runtime_context_injection_consumption(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection consumption is unavailable")

    async def record_protected_runtime_context_injection_consumption_result(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection consumption is unavailable")

    async def list_protected_runtime_context_injection_consumption_attempts(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection consumption is unavailable")

    async def get_protected_runtime_context_injection_consumption_results(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context injection consumption is unavailable")


class _UnavailableWorkflowProtectedRuntimeContextUseAuthorizationRepository:
    """Fail-closed ADR-170 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("runtime-context use authorization is unavailable")

    async def preflight_protected_runtime_context_use_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context use authorization is unavailable")

    async def get_protected_runtime_context_use_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context use authorization is unavailable")

    async def authorize_protected_runtime_context_use(self, *_: object, **__: object) -> None:
        raise RuntimeError("runtime-context use authorization is unavailable")

    async def list_protected_runtime_context_use_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context use authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository:
    """Fail-closed ADR-171 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("runtime-context use-authorization consumption is unavailable")

    async def lookup_protected_runtime_context_use_authorization_consumption_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context use-authorization consumption is unavailable")

    async def consume_protected_runtime_context_use_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context use-authorization consumption is unavailable")

    async def list_protected_runtime_context_use_authorization_consumption_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("runtime-context use-authorization consumption is unavailable")


class _UnavailableWorkflowProtectedRuntimeContextUseRepository:
    """Fail-closed ADR-172 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("protected runtime-context use is unavailable")

    async def lookup_protected_runtime_context_use_replay(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-context use is unavailable")

    async def get_protected_runtime_context_use_source(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-context use is unavailable")

    async def claim_protected_runtime_context_use(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-context use is unavailable")

    async def record_protected_runtime_context_use_result(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-context use is unavailable")

    async def list_protected_runtime_context_use_attempts(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-context use is unavailable")

    async def get_protected_runtime_context_use_results(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-context use is unavailable")


class _UnavailableWorkflowProtectedRuntimeStartAuthorizationRepository:
    """Fail-closed ADR-173 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("protected runtime-start authorization is unavailable")

    async def preflight_protected_runtime_start_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-start authorization is unavailable")

    async def get_protected_runtime_start_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-start authorization is unavailable")

    async def authorize_protected_runtime_start(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-start authorization is unavailable")

    async def list_protected_runtime_start_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-start authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeStartConsumptionRepository:
    """Fail-closed ADR-174 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")

    async def lookup_protected_runtime_start_consumption_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")

    async def get_protected_runtime_start_consumption_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")

    async def claim_protected_runtime_start_consumption(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")

    async def record_protected_runtime_start_consumption_result(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")

    async def list_protected_runtime_start_attempts(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")

    async def get_protected_runtime_start_results(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-start consumption is unavailable")


class _UnavailableWorkflowProtectedRuntimeReadinessAuthorizationRepository:
    """Fail-closed ADR-175 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("protected runtime-readiness authorization is unavailable")

    async def preflight_protected_runtime_readiness_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-readiness authorization is unavailable")

    async def get_protected_runtime_readiness_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-readiness authorization is unavailable")

    async def authorize_protected_runtime_readiness(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-readiness authorization is unavailable")

    async def list_protected_runtime_readiness_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-readiness authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeReadinessConsumptionRepository:
    """Fail-closed ADR-176 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")

    async def lookup_protected_runtime_readiness_consumption_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")

    async def get_protected_runtime_readiness_consumption_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")

    async def claim_protected_runtime_readiness_consumption(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")

    async def record_protected_runtime_readiness_consumption_result(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")

    async def list_protected_runtime_readiness_attempts(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")

    async def get_protected_runtime_readiness_results(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime-readiness consumption is unavailable")


class _UnavailableWorkflowProtectedRuntimeProcessCreationAuthorizationRepository:
    """Fail-closed ADR-177 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("protected runtime process-creation authorization is unavailable")

    async def preflight_protected_runtime_process_creation_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation authorization is unavailable")

    async def get_protected_runtime_process_creation_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation authorization is unavailable")

    async def authorize_protected_runtime_process_creation(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime process-creation authorization is unavailable")

    async def list_protected_runtime_process_creation_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository:
    """Fail-closed ADR-179 repository with no process-local authority."""

    @property
    def durable(self) -> bool:
        return False

    @property
    async def get_authoritative_time(self) -> None:
        raise RuntimeError("protected runtime process-scheduling authorization is unavailable")

    async def preflight_protected_runtime_process_scheduling_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling authorization is unavailable")

    async def get_protected_runtime_process_scheduling_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling authorization is unavailable")

    async def authorize_protected_runtime_process_scheduling(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling authorization is unavailable")

    async def list_protected_runtime_process_scheduling_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeProcessResumeAuthorizationRepository:
    """Fail-closed ADR-181 repository with no process-local authority."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> None:
        raise RuntimeError("protected runtime process-resume authorization is unavailable")

    async def preflight_protected_runtime_process_resume_authorization(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-resume authorization is unavailable")

    async def get_protected_runtime_process_resume_authorization_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-resume authorization is unavailable")

    async def authorize_protected_runtime_process_resume(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime process-resume authorization is unavailable")

    async def list_protected_runtime_process_resume_authorization_presentations(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-resume authorization is unavailable")


class _UnavailableWorkflowProtectedRuntimeProcessCreationConsumptionRepository:
    """Fail-closed ADR-178 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")

    async def lookup_protected_runtime_process_creation_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")

    async def get_protected_runtime_process_creation_consumption_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")

    async def claim_protected_runtime_process_creation(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")

    async def record_protected_runtime_process_creation_result(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")

    async def list_protected_runtime_process_creation_attempts(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")

    async def get_protected_runtime_process_creation_results(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-creation consumption is unavailable")


class _UnavailableWorkflowProtectedRuntimeProcessSchedulingConsumptionRepository:
    """Fail-closed ADR-180 composition placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")

    async def lookup_protected_runtime_process_scheduling_replay(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")

    async def get_protected_runtime_process_scheduling_consumption_source(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")

    async def claim_protected_runtime_process_scheduling(self, *_: object, **__: object) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")

    async def record_protected_runtime_process_scheduling_result(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")

    async def list_protected_runtime_process_scheduling_attempts(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")

    async def get_protected_runtime_process_scheduling_results(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("protected runtime process-scheduling consumption is unavailable")


class _WorkflowProtectedResidentContextOpeningReceiptSignatureVerifierAdapter:
    """Expose an opener's offline receipt verification through the IMP-216 port."""

    def __init__(self, verifier: object) -> None:
        self._verifier = verifier

    def verify_opening_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt
    ) -> bool:
        verify = getattr(self._verifier, "verify_receipt", None)
        return callable(verify) and bool(verify(receipt))


class _UnavailableWorkflowTargetContextCapsuleOpeningRepository:
    """Fail-closed capsule opening placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("target-context capsule opening is unavailable")

    async def get_target_context_capsule_opening_source(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule opening is unavailable")

    async def lookup_target_context_capsule_opening_replay(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule opening is unavailable")

    async def claim_target_context_capsule_opening(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule opening is unavailable")

    async def record_target_context_capsule_opening_result(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule opening is unavailable")

    async def list_target_context_capsule_opening_attempts(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule opening is unavailable")

    async def get_target_context_capsule_opening_results_by_opening_ids(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule opening is unavailable")


class _UnavailableWorkflowTargetContextCapsuleHandoffRepository:
    """Fail-closed capsule handoff placeholder with no memory fallback."""

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def get_target_context_capsule_handoff_authorization_lease_by_id(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def get_target_context_capsule_consumer_binding_by_id(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def lookup_target_context_capsule_handoff_replay(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def claim_target_context_capsule_handoff(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def record_target_context_capsule_handoff_result(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def list_target_context_capsule_handoff_attempts(self, *_: object, **__: object) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")

    async def get_target_context_capsule_handoff_results_by_handoff_ids(
        self, *_: object, **__: object
    ) -> None:
        raise RuntimeError("target-context capsule handoff consumption is unavailable")


class _ConfiguredDeploymentEventTransportProfileRegistry:
    def __init__(self, profiles: tuple[DeploymentEventTransportProfile, ...]) -> None:
        self._profiles = profiles

    @property
    def durable(self) -> bool:
        return True

    @property
    def profiles(self) -> tuple[DeploymentEventTransportProfile, ...]:
        return self._profiles

    async def get_active_transport_profile(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> DeploymentEventTransportProfile | None:
        return next(
            (
                profile
                for profile in self._profiles
                if profile.transport_profile_id == transport_profile_id
                and profile.transport_profile_revision == transport_profile_revision
                and profile.active
            ),
            None,
        )


class _ConfiguredDeploymentEventTransportRouteRegistry:
    def __init__(self, routes: tuple[DeploymentEventTransportRoute, ...]) -> None:
        self._routes = routes

    @property
    def durable(self) -> bool:
        return True

    @property
    def routes(self) -> tuple[DeploymentEventTransportRoute, ...]:
        return self._routes

    async def get_active_transport_route(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> DeploymentEventTransportRoute | None:
        return next(
            (
                route
                for route in self._routes
                if route.route_id == route_id
                and route.route_revision == route_revision
                and route.active
            ),
            None,
        )


def _deployment_event_transport_profiles(
    settings: Settings,
) -> tuple[DeploymentEventTransportProfile, ...]:
    if settings.environment != "development":
        return ()
    scope = WorkflowScope(
        organization_id=settings.development_organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    values: dict[str, Any] = {
        "transport_profile_id": "transport-profile.workflow.internal",
        "transport_profile_revision": "revision.1",
        "deployment_release_id": f"release.project-atlas.{__version__}",
        "deployment_profile": "developer",
        "scope": scope,
        "transport_resource_id": "transport-resource.workflow.internal",
        "transport_resource_digest": sha256(
            f"transport-resource.workflow.internal:{settings.environment}".encode()
        ).hexdigest(),
        "transport_implementation_id": "transport.nats-jetstream",
        "transport_implementation_version": "version.1",
        "adapter_contract_id": "adapter.workflow-event-transport",
        "adapter_contract_version": "version.1",
        "adapter_contract_digest": sha256(
            b"adapter.workflow-event-transport:version.1"
        ).hexdigest(),
        "supported_event_contracts": (
            "WorkflowStepDispatchRequested|1.0|"
            "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        ),
        "supported_classifications": ("internal",),
        "supported_representations": ("canonical-json",),
        "supported_encodings": ("utf-8",),
        "supported_delivery_semantics": ("at-least-once",),
        "durable_delivery_supported": True,
        "supported_ordering_key_kinds": ("workflow-run",),
        "supported_retention_classes": ("workflow-operational",),
        "maximum_message_byte_count": 65_536,
        "transport_encryption_required": True,
        "restricted_network_supported": True,
        "active": True,
    }
    digest_payload = {
        key: value.canonical_value() if isinstance(value, WorkflowScope) else value
        for key, value in values.items()
    }
    return (
        DeploymentEventTransportProfile(
            **values,
            canonical_digest=canonical_digest(digest_payload),
        ),
    )


def _deployment_event_transport_routes(
    settings: Settings,
) -> tuple[DeploymentEventTransportRoute, ...]:
    if settings.environment != "development":
        return ()
    scope = WorkflowScope(
        organization_id=settings.development_organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    values: dict[str, Any] = {
        "route_id": "transport-route.workflow.internal.primary",
        "route_revision": "revision.1",
        "route_set_id": "transport-route-set.workflow.internal",
        "route_set_revision": "revision.1",
        "selection_epoch_id": "selection-epoch.workflow.internal",
        "selection_epoch_revision": "revision.1",
        "deployment_release_id": f"release.project-atlas.{__version__}",
        "deployment_profile": "developer",
        "scope": scope,
        "transport_profile_id": "transport-profile.workflow.internal",
        "transport_profile_revision": "revision.1",
        "transport_resource_id": "transport-resource.workflow.internal",
        "transport_resource_digest": sha256(
            f"transport-resource.workflow.internal:{settings.environment}".encode()
        ).hexdigest(),
        "transport_implementation_id": "transport.nats-jetstream",
        "transport_implementation_version": "version.1",
        "adapter_contract_id": "adapter.workflow-event-transport",
        "adapter_contract_version": "version.1",
        "adapter_contract_digest": sha256(
            b"adapter.workflow-event-transport:version.1"
        ).hexdigest(),
        "route_kind": "message-broker",
        "endpoint_set_id": "endpoint-set.workflow-route.primary",
        "endpoint_set_revision": "revision.1",
        "destination_id": "destination.workflow-route.primary",
        "destination_revision": "revision.1",
        "routing_contract_id": "routing-contract.workflow-route.primary",
        "routing_contract_revision": "revision.1",
        "private_route_descriptor_commitment": sha256(
            b"private-route-descriptor.workflow-route.primary:revision.1"
        ).hexdigest(),
        "transport_security_policy_id": "policy.transport-security.workflow-internal",
        "transport_security_policy_version": "version.1",
        "transport_security_policy_digest": sha256(
            b"policy.transport-security.workflow-internal:version.1"
        ).hexdigest(),
        "minimum_tls_version": "1.3",
        "server_authentication_required": True,
        "client_authentication_required": True,
        "plaintext_fallback_prohibited": True,
        "network_policy_id": "policy.network.workflow-restricted",
        "network_policy_version": "version.1",
        "network_policy_digest": sha256(
            b"policy.network.workflow-restricted:version.1"
        ).hexdigest(),
        "source_zone_class": "zone.workload-internal",
        "destination_zone_class": "zone.event-backbone-internal",
        "restricted_network_enforced": True,
        "public_egress_prohibited": True,
        "proxy_mode": "prohibited",
        "credential_requirement_profile_id": "credential-requirement.workflow-service",
        "credential_requirement_profile_version": "version.1",
        "credential_requirement_profile_digest": sha256(
            b"credential-requirement.workflow-service:version.1"
        ).hexdigest(),
        "authentication_mechanism_class": "mutual-tls",
        "principal_class": "service-workload",
        "active": True,
    }
    digest_payload = {
        key: value.canonical_value() if isinstance(value, WorkflowScope) else value
        for key, value in values.items()
    }
    return (
        DeploymentEventTransportRoute(
            **values,
            canonical_digest=canonical_digest(digest_payload),
        ),
    )


def _deployment_physical_transport_credential_assignments(
    settings: Settings,
    routes: tuple[DeploymentEventTransportRoute, ...],
) -> tuple[DeploymentPhysicalTransportCredentialAssignment, ...]:
    if settings.workflow_transport_credential_assignments:
        configured: list[DeploymentPhysicalTransportCredentialAssignment] = []
        for item in settings.workflow_transport_credential_assignments:
            raw = item.model_dump()
            scope = WorkflowScope(
                organization_id=cast(str, raw.pop("organization_id")),
                environment_id=cast(str, raw.pop("environment_id")),
                site_id=cast(str, raw.pop("site_id")),
            )
            configured_values: dict[str, Any] = {**raw, "scope": scope}
            payload = {
                key: value.canonical_value()
                if isinstance(value, WorkflowScope)
                else value.isoformat()
                if isinstance(value, datetime)
                else value
                for key, value in configured_values.items()
            }
            configured.append(
                DeploymentPhysicalTransportCredentialAssignment(
                    **configured_values,
                    canonical_digest=canonical_digest(payload),
                )
            )
        return tuple(configured)
    if settings.environment != "development":
        return ()
    assignments: list[DeploymentPhysicalTransportCredentialAssignment] = []
    for route in routes:
        if not route.active:
            continue
        values: dict[str, Any] = {
            "assignment_id": "credential-assignment.workflow.internal.primary",
            "assignment_revision": "revision.1",
            "scope": route.scope,
            "route_id": route.route_id,
            "route_revision": route.route_revision,
            "source_route_digest": route.canonical_digest,
            "credential_requirement_profile_id": route.credential_requirement_profile_id,
            "credential_requirement_profile_version": (
                route.credential_requirement_profile_version
            ),
            "credential_requirement_profile_digest": (route.credential_requirement_profile_digest),
            "credential_profile_id": "credential-profile.workflow-service.read-only",
            "credential_profile_version": "version.1",
            "credential_profile_digest": sha256(
                b"credential-profile.workflow-service.read-only:version.1"
            ).hexdigest(),
            "authentication_mechanism_class": route.authentication_mechanism_class,
            "principal_class": route.principal_class,
            "privilege_class": "read-only",
            "target_scope_commitment": sha256(
                f"target-scope:{route.route_id}:{route.route_revision}".encode()
            ).hexdigest(),
            "credential_generation": 1,
            "rotation_epoch": 1,
            "activated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "expires_at": datetime(2099, 1, 1, tzinfo=UTC),
            "revoked": False,
            "active": True,
            "broker_policy_id": "policy.credential-broker.workflow-service",
            "broker_policy_version": "version.1",
            "broker_policy_digest": sha256(
                b"policy.credential-broker.workflow-service:version.1"
            ).hexdigest(),
        }
        assignments.append(
            DeploymentPhysicalTransportCredentialAssignment(
                **values,
                canonical_digest=canonical_digest(
                    {
                        key: value.canonical_value()
                        if isinstance(value, WorkflowScope)
                        else value.isoformat()
                        if isinstance(value, datetime)
                        else value
                        for key, value in values.items()
                    }
                ),
            )
        )
    return tuple(assignments)


def _deployment_event_transport_route_selection_heads(
    settings: Settings,
    routes: tuple[DeploymentEventTransportRoute, ...],
) -> tuple[DeploymentEventTransportRouteSelectionHead, ...]:
    if settings.environment != "development":
        return ()
    active_routes = tuple(route for route in routes if route.active)
    route_set_keys = tuple(
        (
            route.scope.organization_id,
            route.scope.environment_id,
            route.scope.site_id,
            route.route_set_id,
        )
        for route in active_routes
    )
    if len(route_set_keys) != len(set(route_set_keys)):
        raise ValueError("deployment transport route selection heads must be unique")
    heads: list[DeploymentEventTransportRouteSelectionHead] = []
    for route in active_routes:
        values: dict[str, Any] = {
            "head_id": f"transport-route-selection-head.{route.route_set_id}",
            "generation": 1,
            "route_set_id": route.route_set_id,
            "route_set_revision": route.route_set_revision,
            "selection_epoch_id": route.selection_epoch_id,
            "selection_epoch_revision": route.selection_epoch_revision,
            "selected_route_id": route.route_id,
            "selected_route_revision": route.route_revision,
            "selected_route_digest": route.canonical_digest,
            "fencing_token_digest": sha256(
                (
                    f"development-route-selection-head:{route.route_set_id}:"
                    f"{route.route_revision}:{route.canonical_digest}"
                ).encode()
            ).hexdigest(),
            "selection_active": True,
            "selection_eligible": True,
            "selection_suspended": False,
            "selection_withdrawn": False,
            "selection_superseded": False,
            "scope": route.scope,
            "current": True,
        }
        digest_payload = {
            key: value.canonical_value() if isinstance(value, WorkflowScope) else value
            for key, value in values.items()
        }
        heads.append(
            DeploymentEventTransportRouteSelectionHead(
                **values,
                canonical_digest=canonical_digest(digest_payload),
            )
        )
    return tuple(heads)


def create_app(
    settings: Settings | None = None,
    *,
    audit_sink: AuditSink | None = None,
    identity_provider: IdentityProvider | None = None,
    authorization_service: AuthorizationService | None = None,
    storage_operations_service: StorageOperationsService | None = None,
    inventory_device_service: InventoryDeviceService | None = None,
    itsm_integration_service: ItsmIntegrationService | None = None,
    graph_impact_service: GraphImpactService | None = None,
    health_check_service: HealthCheckService | None = None,
    investigation_service: InvestigationService | None = None,
    rca_service: RcaService | None = None,
    recommendation_service: RecommendationService | None = None,
    approval_service: ApprovalService | None = None,
    report_service: ReportService | None = None,
    itsm_handoff_review_service: ItsmHandoffReviewService | None = None,
    grounded_answer_service: GroundedAnswerService | None = None,
    conversation_service: ConversationService | None = None,
    conversation_target_access_source: ConversationTargetAccessSource | None = None,
    workflow_planning_service: WorkflowPlanningService | None = None,
    workflow_orchestration_lease_service: WorkflowOrchestrationLeaseService | None = None,
    workflow_run_materialization_service: WorkflowRunMaterializationService | None = None,
    workflow_attempt_materialization_service: WorkflowAttemptMaterializationService | None = None,
    workflow_dispatch_intent_staging_service: WorkflowDispatchIntentStagingService | None = None,
    workflow_outbox_publication_lease_service: WorkflowOutboxPublicationLeaseService | None = None,
    workflow_dispatch_event_envelope_service: WorkflowDispatchEventEnvelopeService | None = None,
    workflow_event_transport_admission_service: WorkflowEventTransportAdmissionService
    | None = None,
    workflow_event_byte_artifact_service: WorkflowEventByteArtifactService | None = None,
    workflow_event_logical_channel_binding_service: WorkflowEventLogicalChannelBindingService
    | None = None,
    workflow_event_transport_compatibility_admission_service: (
        WorkflowEventTransportCompatibilityAdmissionService | None
    ) = None,
    workflow_event_physical_transport_route_binding_service: (
        WorkflowEventPhysicalTransportRouteBindingService | None
    ) = None,
    workflow_event_physical_transport_credential_assignment_binding_service: (
        WorkflowEventPhysicalTransportCredentialAssignmentBindingService | None
    ) = None,
    workflow_event_physical_transport_credential_assignment_freshness_admission_service: (
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService | None
    ) = None,
    workflow_event_physical_transport_credential_access_authorization_lease_service: (
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService | None
    ) = None,
    workflow_event_physical_transport_route_freshness_admission_service: (
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionService | None
    ) = None,
    workflow_event_physical_transport_endpoint_resolution_authorization_lease_service: (
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService | None
    ) = None,
    workflow_event_physical_transport_endpoint_materialization_service: (
        WorkflowEventPhysicalTransportEndpointMaterializationService | None
    ) = None,
    workflow_event_physical_transport_credential_materialization_service: (
        WorkflowEventPhysicalTransportCredentialMaterializationService | None
    ) = None,
    workflow_event_physical_transport_target_context_binding_service: (
        WorkflowEventPhysicalTransportTargetContextBindingService | None
    ) = None,
    workflow_event_physical_transport_target_context_access_authorization_lease_service: (
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService | None
    ) = None,
    workflow_event_physical_transport_target_context_artifact_opening_service: (
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningService | None
    ) = None,
    workflow_protected_transport_target_context_capsule_consumer_binding_service: (
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService | None
    ) = None,
    workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service: (
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService | None
    ) = None,
    workflow_protected_transport_target_context_capsule_handoff_service: (
        WorkflowProtectedTransportTargetContextCapsuleHandoffService | None
    ) = None,
    workflow_protected_transport_target_context_capsule_opening_authorization_lease_service: (
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService | None
    ) = None,
    workflow_protected_resident_context_access_authorization_service: (
        WorkflowProtectedResidentContextAccessAuthorizationService | None
    ) = None,
    workflow_protected_resident_context_access_consumption_service: (
        WorkflowProtectedResidentContextAccessConsumptionService | None
    ) = None,
    workflow_protected_runtime_context_injection_authorization_service: (
        WorkflowProtectedRuntimeContextInjectionAuthorizationService | None
    ) = None,
    workflow_protected_runtime_context_injection_consumption_service: (
        WorkflowProtectedRuntimeContextInjectionConsumptionService | None
    ) = None,
    workflow_protected_runtime_context_use_authorization_service: (
        WorkflowProtectedRuntimeContextUseAuthorizationService | None
    ) = None,
    workflow_protected_runtime_context_use_authorization_consumption_service: (
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService | None
    ) = None,
    workflow_protected_runtime_context_use_service: (
        WorkflowProtectedRuntimeContextUseService | None
    ) = None,
    workflow_protected_runtime_start_authorization_service: (
        WorkflowProtectedRuntimeStartAuthorizationService | None
    ) = None,
    workflow_protected_runtime_start_consumption_service: (
        WorkflowProtectedRuntimeStartConsumptionService | None
    ) = None,
    workflow_protected_runtime_readiness_authorization_service: (
        WorkflowProtectedRuntimeReadinessAuthorizationService | None
    ) = None,
    workflow_protected_runtime_readiness_consumption_service: (
        WorkflowProtectedRuntimeReadinessConsumptionService | None
    ) = None,
    workflow_protected_runtime_process_creation_authorization_service: (
        WorkflowProtectedRuntimeProcessCreationAuthorizationService | None
    ) = None,
    workflow_protected_runtime_process_scheduling_authorization_service: (
        WorkflowProtectedRuntimeProcessSchedulingAuthorizationService | None
    ) = None,
    workflow_protected_runtime_process_scheduling_state_attestor: (
        WorkflowProtectedRuntimeProcessSchedulingStateAttestor | None
    ) = None,
    workflow_protected_runtime_process_scheduling_state_signature_verifier: (
        WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_process_resume_authorization_service: (
        WorkflowProtectedRuntimeProcessResumeAuthorizationService | None
    ) = None,
    workflow_protected_runtime_process_resume_state_attestor: (
        WorkflowProtectedRuntimeProcessResumeStateAttestor | None
    ) = None,
    workflow_protected_runtime_process_resume_state_signature_verifier: (
        WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_process_creation_consumption_service: (
        WorkflowProtectedRuntimeProcessCreationConsumptionService | None
    ) = None,
    workflow_protected_runtime_process_scheduling_consumption_service: (
        WorkflowProtectedRuntimeProcessSchedulingConsumptionService | None
    ) = None,
    workflow_protected_runtime_handle_lifecycle_attestor: (
        WorkflowProtectedRuntimeHandleLifecycleAttestor | None
    ) = None,
    workflow_protected_runtime_handle_lifecycle_signature_verifier: (
        WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_slot_readiness_attestor: (
        WorkflowProtectedRuntimeSlotReadinessAttestor | None
    ) = None,
    workflow_protected_runtime_slot_readiness_signature_verifier: (
        WorkflowProtectedRuntimeSlotReadinessSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_slot_lifecycle_attestor: (
        WorkflowProtectedRuntimeSlotLifecycleAttestor | None
    ) = None,
    workflow_protected_runtime_slot_lifecycle_signature_verifier: (
        WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_start_lifecycle_attestor: (
        WorkflowProtectedRuntimeStartLifecycleAttestor | None
    ) = None,
    workflow_protected_runtime_start_lifecycle_signature_verifier: (
        WorkflowProtectedRuntimeStartLifecycleSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_readiness_lifecycle_attestor: (
        WorkflowProtectedRuntimeReadinessLifecycleAttestor | None
    ) = None,
    workflow_protected_runtime_readiness_lifecycle_signature_verifier: (
        WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_process_creation_lifecycle_attestor: (
        WorkflowProtectedRuntimeProcessCreationLifecycleAttestor | None
    ) = None,
    workflow_protected_runtime_process_creation_lifecycle_signature_verifier: (
        WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_start_receipt_signature_verifier: (
        WorkflowProtectedRuntimeStartReceiptSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_context_use_receipt_signature_verifier: (
        WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier | None
    ) = None,
    workflow_protected_runtime_context_trusted_injector: (
        WorkflowProtectedRuntimeContextTrustedInjector | None
    ) = None,
    workflow_protected_runtime_context_trusted_injector_receipt_signature_verifier: (
        WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier | None
    ) = None,
    workflow_protected_resident_context_trusted_accessor_receipt_signature_verifier: (
        WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier | None
    ) = None,
    workflow_protected_transport_target_context_capsule_opening_service: (
        WorkflowProtectedTransportTargetContextCapsuleOpeningService | None
    ) = None,
    workflow_transport_profile_snapshot_service: WorkflowTransportProfileSnapshotService
    | None = None,
    deployment_event_transport_profiles: tuple[DeploymentEventTransportProfile, ...] | None = None,
    workflow_transport_route_snapshot_service: WorkflowTransportRouteSnapshotService | None = None,
    deployment_event_transport_routes: tuple[DeploymentEventTransportRoute, ...] | None = None,
    workflow_transport_credential_assignment_snapshot_service: (
        WorkflowTransportCredentialAssignmentSnapshotService | None
    ) = None,
    deployment_physical_transport_credential_assignments: (
        tuple[DeploymentPhysicalTransportCredentialAssignment, ...] | None
    ) = None,
    deployment_event_transport_route_selection_heads: (
        tuple[DeploymentEventTransportRouteSelectionHead, ...] | None
    ) = None,
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
    connector_upgrade_approval_service: ConnectorUpgradeApprovalService | None = None,
    target_configuration_service: ConnectorTargetConfigurationService | None = None,
    credential_assignment_service: ConnectorCredentialAssignmentService | None = None,
    configuration_validation_service: ConnectorConfigurationValidationService | None = None,
    capability_enablement_service: ConnectorCapabilityEnablementService | None = None,
    runtime_trust_service: ConnectorRuntimeTrustService | None = None,
    secret_brokerage_service: ConnectorSecretBrokerageService | None = None,
    runtime_activation_service: ConnectorRuntimeActivationService | None = None,
    runtime_deactivation_service: ConnectorRuntimeDeactivationService | None = None,
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
    recommendation_protected_inspection_service: (
        RecommendationProtectedInspectionService | None
    ) = None,
    recommendation_protected_content_service: RecommendationProtectedContentService | None = None,
    recommendation_human_review_finding_service: (
        RecommendationHumanReviewFindingService | None
    ) = None,
    recommendation_finding_presentation_service: (
        RecommendationFindingPresentationService | None
    ) = None,
    recommendation_track_review_decision_service: (
        RecommendationTrackReviewDecisionService | None
    ) = None,
    recommendation_correction_service: RecommendationCorrectionService | None = None,
    final_recommendation_disposition_service: (FinalRecommendationDispositionService | None) = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    operational_posture = assert_advisory_only_composition()
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
    resolved_connector_instance_lifecycle_service = ConnectorInstanceLifecycleService(
        repository=resolved_connector_instance_creation_service.repository,
        target_repository=resolved_target_configuration_service.repository,
        audit_sink=resolved_audit_sink,
        environment_id=resolved_connector_instance_creation_service.environment_id,
    )
    resolved_connector_upgrade_readiness_service = ConnectorUpgradeReadinessService(
        instance_repository=resolved_connector_instance_creation_service.repository,
        target_repository=resolved_target_configuration_service.repository,
        package_source=PackageInstallationUpgradeSource(resolved_package_installation_service),
        audit_sink=resolved_audit_sink,
        environment_id=resolved_connector_instance_creation_service.environment_id,
    )
    if connector_upgrade_approval_service is not None:
        resolved_connector_upgrade_approval_service = connector_upgrade_approval_service
    else:
        connector_upgrade_approval_repository = (
            PostgreSQLConnectorUpgradeApprovalRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryConnectorUpgradeApprovalRepository()
        )
        connector_upgrade_approval_policies = (
            ()
            if is_production
            else (
                build_development_connector_upgrade_approval_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        onboarding_policy_authenticity_key_material = sha256(
            (
                "atlas-nonproduction-onboarding-policy-verifier:"
                f"{resolved_settings.development_organization_id}:"
                f"{resolved_settings.environment}"
            ).encode("ascii")
        ).digest()
        connector_upgrade_signing_provider_onboarding_policies: tuple[
            ConnectorUpgradeSigningProviderOnboardingPolicySnapshot, ...
        ]
        onboarding_policy_trust_keys: tuple[
            ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey, ...
        ]
        onboarding_policy_attestations: tuple[
            ConnectorUpgradeSigningProviderOnboardingPolicyAttestation, ...
        ]
        onboarding_policy_verifier: ConnectorUpgradeSigningProviderOnboardingPolicyVerifier
        if is_production:
            connector_upgrade_signing_provider_onboarding_policies = ()
            onboarding_policy_trust_keys = ()
            onboarding_policy_attestations = ()
            onboarding_policy_verifier = (
                UnavailableConnectorUpgradeSigningProviderOnboardingPolicyVerifier()
            )
        else:
            onboarding_policy = (
                build_development_connector_upgrade_signing_provider_onboarding_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                )
            )
            onboarding_policy_trust_key = (
                build_development_connector_upgrade_signing_provider_onboarding_policy_trust_key(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    not_before=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                )
            )
            connector_upgrade_signing_provider_onboarding_policies = (onboarding_policy,)
            onboarding_policy_trust_keys = (onboarding_policy_trust_key,)
            onboarding_policy_attestations = (
                build_development_connector_upgrade_signing_provider_onboarding_policy_attestation(
                    policy=onboarding_policy,
                    trust_key=onboarding_policy_trust_key,
                    key_material=onboarding_policy_authenticity_key_material,
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
            onboarding_policy_verifier = (
                HmacConnectorUpgradeSigningProviderOnboardingPolicyVerifier(
                    key_id=onboarding_policy_trust_key.key_id,
                    key_version=onboarding_policy_trust_key.key_version,
                    key_material=onboarding_policy_authenticity_key_material,
                )
            )
        resolved_connector_upgrade_approval_service = ConnectorUpgradeApprovalService(
            repository=connector_upgrade_approval_repository,
            policy_source=InMemoryConnectorUpgradeApprovalPolicySource(
                connector_upgrade_approval_policies
            ),
            upgrade_service=resolved_connector_upgrade_readiness_service,
            audit_sink=resolved_audit_sink,
            environment_id=resolved_connector_instance_creation_service.environment_id,
            audit_readiness_source=InMemoryConnectorUpgradeAuditReadinessSource(),
            itsm_change_evidence_source=InMemoryConnectorUpgradeItsmChangeEvidenceSource(),
            maintenance_window_evidence_source=(
                InMemoryConnectorUpgradeMaintenanceWindowEvidenceSource()
            ),
            signing_provider_onboarding_policy_source=(
                InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource(
                    connector_upgrade_signing_provider_onboarding_policies
                )
            ),
            signing_provider_onboarding_policy_attestation_source=(
                InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource(
                    onboarding_policy_attestations
                )
            ),
            signing_provider_onboarding_policy_trust_source=(
                InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource(
                    onboarding_policy_trust_keys
                )
            ),
            signing_provider_onboarding_policy_verifier=onboarding_policy_verifier,
            evidence_authenticity_provider=(
                UnavailableUpgradeEvidenceAuthenticityProvider()
                if is_production
                else NonProductionHmacUpgradeEvidenceAuthenticityProvider(
                    key=ConnectorUpgradeEvidenceSigningKey(
                        key_id="key.connector-upgrade-evidence.nonproduction",
                        key_version="version.1",
                        signer_profile_id="signer-profile.nonproduction-hmac",
                        signer_workload_id="workload.connector-upgrade-evidence-signer",
                        algorithm="algorithm.hmac-sha256-nonproduction",
                        organization_id=resolved_settings.development_organization_id,
                        environment_id=(
                            resolved_connector_instance_creation_service.environment_id
                        ),
                        state=ConnectorUpgradeEvidenceSigningKeyState.ACTIVE,
                        not_before=datetime(2026, 8, 1, tzinfo=UTC),
                        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                    ),
                    key_material=sha256(
                        (
                            "atlas-nonproduction-upgrade-evidence-signer:"
                            f"{resolved_settings.development_organization_id}:"
                            f"{resolved_settings.environment}"
                        ).encode("ascii")
                    ).digest(),
                )
            ),
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
    resolved_bundled_connector_catalog_service = BundledConnectorCatalogService(
        descriptors=(() if is_production else (build_hitachi_ops_center_bundled_descriptor(),)),
        repository=resolved_connector_instance_creation_service.repository,
        audit_sink=resolved_audit_sink,
        environment_id=resolved_connector_instance_creation_service.environment_id,
    )
    bundled_connection_configuration_repository = (
        PostgreSQLBundledConnectionConfigurationRepository.from_url(resolved_settings.database_url)
        if resolved_settings.database_url
        else InMemoryBundledConnectionConfigurationRepository()
    )
    bundled_runtime_state_repository = (
        PostgreSQLBundledConnectorRuntimeStateRepository.from_url(resolved_settings.database_url)
        if resolved_settings.database_url
        else InMemoryBundledConnectorRuntimeStateRepository()
    )
    resolved_bundled_connection_configuration_service = BundledConnectionConfigurationService(
        repository=bundled_connection_configuration_repository,
        instance_repository=resolved_connector_instance_creation_service.repository,
        audit_sink=resolved_audit_sink,
        environment_id=resolved_connector_instance_creation_service.environment_id,
        deployment_environment=resolved_settings.environment,
        runtime_state_repository=bundled_runtime_state_repository,
    )
    hitachi_credential_materializer = DevelopmentEnvironmentCredentialMaterializer(
        deployment_environment=resolved_settings.environment,
        reference_environment_variables={"secret.hitachi.readonly": "ATLAS_HITACHI_AUTHORIZATION"},
    )
    hitachi_transport_factory = HitachiOpsCenterConnectionTestHttpsFactory()
    connector_connection_test_result_repository = (
        PostgreSQLConnectorConnectionTestResultRepository.from_url(resolved_settings.database_url)
        if resolved_settings.database_url
        else InMemoryConnectorConnectionTestResultRepository()
    )
    resolved_connector_connection_test_service = ConnectorConnectionTestService(
        configuration_repository=bundled_connection_configuration_repository,
        result_repository=connector_connection_test_result_repository,
        instance_repository=resolved_connector_instance_creation_service.repository,
        credential_materializer=hitachi_credential_materializer,
        transport_factory=hitachi_transport_factory,
        audit_sink=resolved_audit_sink,
        environment_id=resolved_connector_instance_creation_service.environment_id,
        deployment_environment=resolved_settings.environment,
    )
    resolved_bundled_connector_runtime_state_service = BundledConnectorRuntimeStateService(
        repository=bundled_runtime_state_repository,
        configuration_repository=bundled_connection_configuration_repository,
        connection_test_repository=connector_connection_test_result_repository,
        instance_repository=resolved_connector_instance_creation_service.repository,
        audit_sink=resolved_audit_sink,
        environment_id=resolved_connector_instance_creation_service.environment_id,
        deployment_environment=resolved_settings.environment,
    )
    if runtime_deactivation_service is not None:
        resolved_runtime_deactivation_service = runtime_deactivation_service
    else:
        resolved_runtime_deactivation_service = ConnectorRuntimeDeactivationService(
            repository=InMemoryConnectorRuntimeDeactivationRepository(),
            activation_source=resolved_runtime_activation_service,
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    resolved_runtime_activation_service.bind_deactivation_source(
        resolved_runtime_deactivation_service.repository
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
        development_invocation_evidence = (
            None if is_production else DevelopmentConnectorInvocationEvidenceStore()
        )
        resolved_invocation_authorization_service = ConnectorInvocationAuthorizationService(
            repository=invocation_authorization_repository,
            source=resolved_target_session_service,
            profile_source=(
                InMemoryConnectorInvocationProfileSource(())
                if development_invocation_evidence is None
                else DevelopmentConnectorInvocationProfileSource(development_invocation_evidence)
            ),
            envelope_source=(
                InMemoryConnectorInvocationInputEnvelopeSource(())
                if development_invocation_evidence is None
                else DevelopmentConnectorInvocationInputEnvelopeSource(
                    development_invocation_evidence
                )
            ),
            policy_source=InMemoryConnectorInvocationAuthorizationPolicySource(
                invocation_authorization_policies
            ),
            evidence_preparer=development_invocation_evidence,
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
    recommendation_readiness_promotion_source = RecommendationReadinessPromotionSourceRouter(
        primary=resolved_recommendation_promotion_service
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
            promotion_source=recommendation_readiness_promotion_source,
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
    if recommendation_protected_inspection_service is not None:
        resolved_recommendation_protected_inspection_service = (
            recommendation_protected_inspection_service
        )
    else:
        recommendation_protected_inspection_repository = (
            PostgreSQLRecommendationProtectedInspectionRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryRecommendationProtectedInspectionRepository()
        )
        recommendation_protected_inspection_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_protected_inspection_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_protected_inspection_service = (
            RecommendationProtectedInspectionService(
                repository=recommendation_protected_inspection_repository,
                source=resolved_recommendation_reviewer_assignment_service,
                policy_source=InMemoryRecommendationProtectedInspectionPolicySource(
                    recommendation_protected_inspection_policies
                ),
                permission_authorizer=(
                    AuthorizationRecommendationProtectedInspectionPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                broker=(
                    UnavailableRecommendationProtectedInspectionBroker()
                    if is_production
                    else SyntheticRecommendationProtectedInspectionBroker()
                ),
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if recommendation_protected_content_service is not None:
        resolved_recommendation_protected_content_service = recommendation_protected_content_service
    else:
        recommendation_protected_content_repository = (
            PostgreSQLRecommendationProtectedContentRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryRecommendationProtectedContentRepository()
        )
        recommendation_protected_content_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_protected_content_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_protected_content_service = RecommendationProtectedContentService(
            repository=recommendation_protected_content_repository,
            source=resolved_recommendation_protected_inspection_service,
            policy_source=InMemoryRecommendationProtectedContentPolicySource(
                recommendation_protected_content_policies
            ),
            permission_authorizer=(
                AuthorizationRecommendationProtectedContentPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            presenter=(
                UnavailableRecommendationProtectedContentPresenter()
                if is_production
                else SyntheticRecommendationProtectedContentPresenter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    recommendation_human_review_finding_recorder: (
        RecommendationHumanReviewFindingRecorder | None
    ) = None
    if recommendation_human_review_finding_service is not None:
        resolved_recommendation_human_review_finding_service = (
            recommendation_human_review_finding_service
        )
    else:
        recommendation_human_review_finding_repository = (
            PostgreSQLRecommendationHumanReviewFindingRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryRecommendationHumanReviewFindingRepository()
        )
        recommendation_human_review_finding_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_human_review_finding_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        recommendation_human_review_finding_recorder = (
            UnavailableRecommendationHumanReviewFindingRecorder()
            if is_production
            else SyntheticRecommendationHumanReviewFindingRecorder()
        )
        resolved_recommendation_human_review_finding_service = (
            RecommendationHumanReviewFindingService(
                repository=recommendation_human_review_finding_repository,
                source=resolved_recommendation_protected_content_service,
                policy_source=InMemoryRecommendationHumanReviewFindingPolicySource(
                    recommendation_human_review_finding_policies
                ),
                permission_authorizer=(
                    AuthorizationRecommendationHumanReviewFindingPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                recorder=recommendation_human_review_finding_recorder,
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if recommendation_finding_presentation_service is not None:
        resolved_recommendation_finding_presentation_service = (
            recommendation_finding_presentation_service
        )
    else:
        recommendation_finding_presentation_repository = (
            PostgreSQLRecommendationFindingPresentationRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryRecommendationFindingPresentationRepository()
        )
        recommendation_finding_presentation_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_finding_presentation_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        recommendation_finding_presenter: RecommendationFindingPresenter = (
            SyntheticRecommendationFindingPresenter(
                recorder=recommendation_human_review_finding_recorder
            )
            if isinstance(
                recommendation_human_review_finding_recorder,
                SyntheticRecommendationHumanReviewFindingRecorder,
            )
            else UnavailableRecommendationFindingPresenter()
        )
        resolved_recommendation_finding_presentation_service = (
            RecommendationFindingPresentationService(
                repository=recommendation_finding_presentation_repository,
                source=resolved_recommendation_human_review_finding_service,
                policy_source=InMemoryRecommendationFindingPresentationPolicySource(
                    recommendation_finding_presentation_policies
                ),
                permission_authorizer=(
                    AuthorizationRecommendationFindingPresentationPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                presenter=recommendation_finding_presenter,
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if recommendation_track_review_decision_service is not None:
        resolved_recommendation_track_review_decision_service = (
            recommendation_track_review_decision_service
        )
    else:
        recommendation_track_review_decision_repository = (
            PostgreSQLRecommendationTrackReviewDecisionRepository.from_url(
                resolved_settings.database_url
            )
            if resolved_settings.database_url
            else InMemoryRecommendationTrackReviewDecisionRepository()
        )
        recommendation_track_review_decision_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_track_review_decision_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        recommendation_track_review_decision_attestor: RecommendationTrackReviewDecisionAttestor = (
            UnavailableRecommendationTrackReviewDecisionAttestor()
            if is_production
            else SyntheticRecommendationTrackReviewDecisionAttestor()
        )
        resolved_recommendation_track_review_decision_service = (
            RecommendationTrackReviewDecisionService(
                repository=recommendation_track_review_decision_repository,
                source=resolved_recommendation_finding_presentation_service,
                policy_source=InMemoryRecommendationTrackReviewDecisionPolicySource(
                    recommendation_track_review_decision_policies
                ),
                permission_authorizer=(
                    AuthorizationRecommendationTrackReviewDecisionPermissionAuthorizer(
                        service=resolved_authorization_service,
                        environment=resolved_settings.environment,
                    )
                ),
                attestor=recommendation_track_review_decision_attestor,
                audit_sink=resolved_audit_sink,
                environment_id=f"environment.{resolved_settings.environment}",
            )
        )
    if recommendation_correction_service is not None:
        resolved_recommendation_correction_service = recommendation_correction_service
    else:
        recommendation_correction_policies = (
            ()
            if is_production
            else (
                build_development_recommendation_correction_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_recommendation_correction_service = RecommendationCorrectionService(
            repository=(
                PostgreSQLRecommendationCorrectionRepository.from_url(
                    resolved_settings.database_url
                )
                if resolved_settings.database_url
                else InMemoryRecommendationCorrectionRepository()
            ),
            source=resolved_recommendation_track_review_decision_service,
            policy_source=InMemoryRecommendationCorrectionPolicySource(
                recommendation_correction_policies
            ),
            permission_authorizer=AuthorizationRecommendationCorrectionPermissionAuthorizer(
                service=resolved_authorization_service,
                environment=resolved_settings.environment,
            ),
            adapter=(
                UnavailableRecommendationCorrectionAdapter()
                if is_production
                else SyntheticRecommendationCorrectionAdapter()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    recommendation_readiness_promotion_source.register_correction_source(
        resolved_recommendation_correction_service
    )
    if final_recommendation_disposition_service is not None:
        resolved_final_recommendation_disposition_service = final_recommendation_disposition_service
    else:
        final_recommendation_disposition_policies = (
            ()
            if is_production
            else (
                build_development_final_recommendation_disposition_policy(
                    organization_id=resolved_settings.development_organization_id,
                    environment_id=f"environment.{resolved_settings.environment}",
                    issued_at=datetime(2026, 8, 1, tzinfo=UTC),
                    expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                ),
            )
        )
        resolved_final_recommendation_disposition_service = FinalRecommendationDispositionService(
            repository=(
                PostgreSQLFinalRecommendationDispositionRepository.from_url(
                    resolved_settings.database_url
                )
                if resolved_settings.database_url
                else InMemoryFinalRecommendationDispositionRepository()
            ),
            source=resolved_recommendation_track_review_decision_service,
            policy_source=InMemoryFinalRecommendationDispositionPolicySource(
                final_recommendation_disposition_policies
            ),
            permission_authorizer=(
                AuthorizationFinalRecommendationDispositionPermissionAuthorizer(
                    service=resolved_authorization_service,
                    environment=resolved_settings.environment,
                )
            ),
            attestor=(
                UnavailableFinalRecommendationDispositionAttestor()
                if is_production
                else SyntheticFinalRecommendationDispositionAttestor()
            ),
            audit_sink=resolved_audit_sink,
            environment_id=f"environment.{resolved_settings.environment}",
        )
    database_probe = DatabaseHealthProbe(resolved_settings)
    status_service = PlatformStatusService(
        service_name=resolved_settings.service_name,
        service_version=__version__,
        environment=resolved_settings.environment,
        probes=(database_probe,),
        operational_posture=operational_posture,
    )
    resolved_inventory_device_service = inventory_device_service or InventoryDeviceService(
        repository=(
            PostgreSQLInventoryDeviceRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryInventoryDeviceRepository()
        ),
        audit_sink=resolved_audit_sink,
        environment_id=f"environment.{resolved_settings.environment}",
    )
    development_itsm_onboarding_policy = (
        None
        if is_production
        else build_development_itsm_sandbox_onboarding_policy(
            organization_id=resolved_settings.development_organization_id,
            environment_id=f"environment.{resolved_settings.environment}",
            site_id="site.local",
        )
    )
    development_itsm_policy_authenticity = (
        None
        if development_itsm_onboarding_policy is None
        else build_development_itsm_sandbox_onboarding_policy_authenticity(
            development_itsm_onboarding_policy
        )
    )
    resolved_itsm_integration_service = itsm_integration_service or ItsmIntegrationService(
        repository=(
            PostgreSQLItsmIntegrationProfileRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryItsmIntegrationProfileRepository()
        ),
        audit_sink=resolved_audit_sink,
        environment_id=f"environment.{resolved_settings.environment}",
        sandbox_conformance_adapter=(
            UnavailableItsmSandboxConformanceAdapter()
            if is_production
            else DeterministicNoNetworkItsmSandboxConformanceAdapter()
        ),
        sandbox_onboarding_evidence_source=(
            EmptyItsmSandboxOnboardingEvidenceSource()
            if is_production
            else DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource()
        ),
        sandbox_onboarding_policy_source=(
            InMemoryItsmSandboxOnboardingPolicySource()
            if development_itsm_onboarding_policy is None
            else InMemoryItsmSandboxOnboardingPolicySource((development_itsm_onboarding_policy,))
        ),
        sandbox_onboarding_policy_provenance_source=(
            InMemoryItsmSandboxOnboardingPolicyProvenanceSource()
            if development_itsm_policy_authenticity is None
            else InMemoryItsmSandboxOnboardingPolicyProvenanceSource(
                (development_itsm_policy_authenticity[0],)
            )
        ),
        sandbox_onboarding_policy_trust_source=(
            InMemoryItsmSandboxOnboardingPolicyTrustSource()
            if development_itsm_policy_authenticity is None
            else InMemoryItsmSandboxOnboardingPolicyTrustSource(
                (development_itsm_policy_authenticity[1],)
            )
        ),
        sandbox_onboarding_policy_verifier=(
            UnavailableItsmSandboxOnboardingPolicyVerifier()
            if development_itsm_policy_authenticity is None
            else development_itsm_policy_authenticity[2]
        ),
    )
    resolved_graph_impact_service = graph_impact_service or GraphImpactService(
        analyzer=resolved_graph_analyzer,
        audit_sink=resolved_audit_sink,
    )
    base_health_check_definitions = build_synthetic_health_check_definitions(
        organization_id=resolved_settings.development_organization_id,
        environment=resolved_settings.environment,
    )
    configured_hitachi_health_enabled = resolved_settings.environment == "development"
    health_check_definitions = (
        tuple(
            replace(
                definition,
                connector_id="connector.hitachi.opscenter.configuration-manager",
                connector_version="0.1.0",
                target_id="target.hitachi.opscenter.configured",
            )
            if definition.definition_id in {CONTROLLER_DEFINITION_ID, CAPACITY_DEFINITION_ID}
            else definition
            for definition in base_health_check_definitions
        )
        if configured_hitachi_health_enabled
        else base_health_check_definitions
    )
    synthetic_latest_runs = build_synthetic_latest_runs(health_check_definitions)
    resolved_health_check_service = health_check_service or HealthCheckService(
        definitions=health_check_definitions,
        latest_runs=tuple(
            run
            for run in synthetic_latest_runs
            if not configured_hitachi_health_enabled
            or run.definition_id not in {CONTROLLER_DEFINITION_ID, CAPACITY_DEFINITION_ID}
        ),
        executor=(
            ConfiguredHitachiHealthExecutor(
                configuration_repository=bundled_connection_configuration_repository,
                instance_repository=resolved_connector_instance_creation_service.repository,
                inventory_repository=resolved_inventory_device_service.repository,
                credential_materializer=hitachi_credential_materializer,
                transport_factory=hitachi_transport_factory,
                fallback_executor=SyntheticStorageHealthExecutor(),
                organization_id=resolved_settings.development_organization_id,
                environment_id=f"environment.{resolved_settings.environment}",
                runtime_state_repository=bundled_runtime_state_repository,
            )
            if configured_hitachi_health_enabled
            else SyntheticStorageHealthExecutor()
        ),
        audit_sink=resolved_audit_sink,
        data_profile=(
            "configured_hitachi_read_only" if configured_hitachi_health_enabled else "synthetic_lab"
        ),
    )
    resolved_storage_operations_service = storage_operations_service or StorageOperationsService(
        provider=(
            ConfiguredHitachiStorageProvider(
                configuration_repository=bundled_connection_configuration_repository,
                instance_repository=resolved_connector_instance_creation_service.repository,
                inventory_repository=resolved_inventory_device_service.repository,
                credential_materializer=hitachi_credential_materializer,
                transport_factory=hitachi_transport_factory,
                organization_id=resolved_settings.development_organization_id,
                environment_id=f"environment.{resolved_settings.environment}",
                runtime_state_repository=bundled_runtime_state_repository,
            )
            if configured_hitachi_health_enabled
            else SyntheticStorageOverviewProvider(
                organization_id=resolved_settings.development_organization_id,
                environment=resolved_settings.environment,
            )
        ),
        organization_id=resolved_settings.development_organization_id,
        environment_id=f"environment.{resolved_settings.environment}",
        site_id="site.local",
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
        repository=(
            PostgreSQLTechnicalReportRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryTechnicalReportRepository()
        ),
    )
    resolved_itsm_handoff_review_service = itsm_handoff_review_service or ItsmHandoffReviewService(
        report_source=resolved_report_service,
        repository=(
            PostgreSQLItsmHandoffReviewRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else InMemoryItsmHandoffReviewRepository()
        ),
        audit_sink=resolved_audit_sink,
        environment_id=f"environment.{resolved_settings.environment}",
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
    resolved_conversation_service = conversation_service or ConversationService(
        repository=(
            PostgreSQLConversationRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else (
                UnavailableConversationRepository()
                if resolved_settings.environment == "production"
                else InMemoryConversationRepository()
            )
        ),
        generator=GroundedConversationGenerator(
            grounded_answer_service=resolved_grounded_answer_service,
        ),
        audit_sink=resolved_audit_sink,
    )
    resolved_conversation_target_access_source = conversation_target_access_source or (
        DevelopmentConversationTargetAccessSource(
            subject_id=resolved_settings.development_subject_id,
            required_principal_ids=frozenset(resolved_settings.development_role_ids),
            scope=ConversationScope(
                organization_id=resolved_settings.development_organization_id,
                environment_id=f"environment.{resolved_settings.environment}",
                site_id="site.local",
            ),
            targets=(
                AuthorizedConversationTarget(
                    target_id="asset.storage.lab.vsp-g400",
                    display_name="VSP G400 Lab",
                    description="Authorized synthetic enterprise storage target.",
                ),
                AuthorizedConversationTarget(
                    target_id="asset.storage.lab.vsp-one-b28",
                    display_name="VSP One B28 Lab",
                    description="Authorized synthetic enterprise storage target.",
                ),
            ),
        )
        if resolved_settings.environment == "development"
        else EmptyConversationTargetAccessSource()
    )
    workflow_repository: WorkflowPlanRepository
    if workflow_planning_service is None:
        workflow_repository = (
            PostgreSQLWorkflowPlanRepository.from_url(resolved_settings.database_url)
            if resolved_settings.database_url
            else (
                UnavailableWorkflowPlanRepository()
                if resolved_settings.environment == "production"
                else InMemoryWorkflowPlanRepository()
            )
        )
        resolved_workflow_planning_service = WorkflowPlanningService(
            registry=code_owned_workflow_registry(),
            repository=workflow_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_planning_service = workflow_planning_service
        workflow_repository = workflow_planning_service.repository
    if workflow_orchestration_lease_service is None:
        lease_repository_methods = (
            "get_lease_by_plan_id",
            "get_lease_acquire_request",
            "acquire_lease",
            "heartbeat_lease",
            "release_lease",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in lease_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement orchestration leases; "
                "inject workflow_orchestration_lease_service explicitly"
            )
        workflow_lease_repository = cast(
            WorkflowOrchestrationLeaseRepository,
            workflow_repository,
        )
        resolved_workflow_orchestration_lease_service = WorkflowOrchestrationLeaseService(
            plan_repository=workflow_repository,
            lease_repository=workflow_lease_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_orchestration_lease_service = workflow_orchestration_lease_service
    if workflow_run_materialization_service is None:
        run_repository_methods = (
            "get_materialized_run_by_plan_id",
            "get_run_materialization_request",
            "materialize_run",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in run_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement run materialization; "
                "inject workflow_run_materialization_service explicitly"
            )
        workflow_run_repository = cast(
            WorkflowRunMaterializationRepository,
            workflow_repository,
        )
        resolved_workflow_run_materialization_service = WorkflowRunMaterializationService(
            registry=resolved_workflow_planning_service.registry,
            plan_repository=workflow_repository,
            lease_repository=resolved_workflow_orchestration_lease_service.repository,
            run_repository=workflow_run_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_run_materialization_service = workflow_run_materialization_service
    if workflow_attempt_materialization_service is None:
        attempt_repository_methods = (
            "list_attempts_by_run_id",
            "get_attempt_materialization_request",
            "materialize_attempt",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in attempt_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement attempt materialization; "
                "inject workflow_attempt_materialization_service explicitly"
            )
        workflow_attempt_repository = cast(
            WorkflowAttemptMaterializationRepository,
            workflow_repository,
        )
        resolved_workflow_attempt_materialization_service = WorkflowAttemptMaterializationService(
            plan_repository=workflow_repository,
            lease_repository=resolved_workflow_orchestration_lease_service.repository,
            run_repository=resolved_workflow_run_materialization_service.repository,
            attempt_repository=workflow_attempt_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_attempt_materialization_service = workflow_attempt_materialization_service
    if workflow_dispatch_intent_staging_service is None:
        dispatch_intent_repository_methods = (
            "list_dispatch_intents_by_run_id",
            "list_dispatch_outbox_entries_by_run_id",
            "get_dispatch_intent_staging_request",
            "stage_dispatch_intent",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in dispatch_intent_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement dispatch intent staging; "
                "inject workflow_dispatch_intent_staging_service explicitly"
            )
        workflow_dispatch_intent_repository = cast(
            WorkflowDispatchIntentStagingRepository,
            workflow_repository,
        )
        resolved_workflow_dispatch_intent_staging_service = WorkflowDispatchIntentStagingService(
            plan_repository=workflow_repository,
            lease_repository=resolved_workflow_orchestration_lease_service.repository,
            run_repository=resolved_workflow_run_materialization_service.repository,
            attempt_repository=resolved_workflow_attempt_materialization_service.repository,
            dispatch_intent_repository=workflow_dispatch_intent_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_dispatch_intent_staging_service = workflow_dispatch_intent_staging_service
    if workflow_outbox_publication_lease_service is None:
        publication_lease_repository_methods = (
            "get_outbox_entry_by_id",
            "get_publication_lease_by_outbox_entry_id",
            "get_publication_lease_acquire_request",
            "acquire_publication_lease",
            "heartbeat_publication_lease",
            "release_publication_lease",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in publication_lease_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement outbox publication leases; "
                "inject workflow_outbox_publication_lease_service explicitly"
            )
        workflow_outbox_publication_lease_repository = cast(
            WorkflowOutboxPublicationLeaseRepository,
            workflow_repository,
        )
        resolved_workflow_outbox_publication_lease_service = WorkflowOutboxPublicationLeaseService(
            plan_repository=workflow_repository,
            orchestration_lease_repository=(
                resolved_workflow_orchestration_lease_service.repository
            ),
            publication_lease_repository=workflow_outbox_publication_lease_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_outbox_publication_lease_service = (
            workflow_outbox_publication_lease_service
        )
    if workflow_dispatch_event_envelope_service is None:
        event_envelope_repository_methods = (
            "get_outbox_entry_by_id",
            "get_publication_lease_by_outbox_entry_id",
            "get_dispatch_event_envelope_by_outbox_entry_id",
            "get_dispatch_event_envelope_prepare_request",
            "prepare_dispatch_event_envelope",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in event_envelope_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement dispatch event envelopes; "
                "inject workflow_dispatch_event_envelope_service explicitly"
            )
        workflow_dispatch_event_envelope_repository = cast(
            WorkflowDispatchEventEnvelopeRepository,
            workflow_repository,
        )
        resolved_workflow_dispatch_event_envelope_service = WorkflowDispatchEventEnvelopeService(
            plan_repository=workflow_repository,
            orchestration_lease_repository=(
                resolved_workflow_orchestration_lease_service.repository
            ),
            event_envelope_repository=workflow_dispatch_event_envelope_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_dispatch_event_envelope_service = workflow_dispatch_event_envelope_service
    if workflow_event_transport_admission_service is None:
        transport_admission_repository_methods = (
            "get_outbox_entry_by_id",
            "get_publication_lease_by_outbox_entry_id",
            "get_dispatch_event_envelope_by_outbox_entry_id",
            "get_event_transport_admission_by_event_id",
            "get_event_transport_admission_request",
            "admit_event_transport",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in transport_admission_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement event transport admission; "
                "inject workflow_event_transport_admission_service explicitly"
            )
        workflow_event_transport_admission_repository = cast(
            WorkflowEventTransportAdmissionRepository,
            workflow_repository,
        )
        resolved_workflow_event_transport_admission_service = (
            WorkflowEventTransportAdmissionService(
                plan_repository=workflow_repository,
                orchestration_lease_repository=(
                    resolved_workflow_orchestration_lease_service.repository
                ),
                transport_admission_repository=(workflow_event_transport_admission_repository),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_event_transport_admission_service = (
            workflow_event_transport_admission_service
        )
    if workflow_event_byte_artifact_service is None:
        byte_artifact_repository_methods = (
            "get_outbox_entry_by_id",
            "get_publication_lease_by_outbox_entry_id",
            "get_dispatch_event_envelope_by_outbox_entry_id",
            "get_event_transport_admission_by_event_id",
            "get_event_byte_artifact_by_admission_id",
            "get_event_byte_artifact_request",
            "materialize_event_byte_artifact",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in byte_artifact_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement event byte artifacts; "
                "inject workflow_event_byte_artifact_service explicitly"
            )
        workflow_event_byte_artifact_repository = cast(
            WorkflowEventByteArtifactRepository,
            workflow_repository,
        )
        resolved_workflow_event_byte_artifact_service = WorkflowEventByteArtifactService(
            plan_repository=workflow_repository,
            orchestration_lease_repository=(
                resolved_workflow_orchestration_lease_service.repository
            ),
            byte_artifact_repository=workflow_event_byte_artifact_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_event_byte_artifact_service = workflow_event_byte_artifact_service
    if workflow_event_logical_channel_binding_service is None:
        logical_channel_binding_repository_methods = (
            "get_outbox_entry_by_id",
            "get_publication_lease_by_outbox_entry_id",
            "get_event_transport_admission_by_event_id",
            "get_event_byte_artifact_by_id",
            "get_event_logical_channel_binding_by_artifact_id",
            "get_event_logical_channel_binding_request",
            "bind_event_logical_channel",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in logical_channel_binding_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement logical channel bindings; "
                "inject workflow_event_logical_channel_binding_service explicitly"
            )
        workflow_event_logical_channel_binding_repository = cast(
            WorkflowEventLogicalChannelBindingRepository,
            workflow_repository,
        )
        resolved_workflow_event_logical_channel_binding_service = (
            WorkflowEventLogicalChannelBindingService(
                plan_repository=workflow_repository,
                orchestration_lease_repository=(
                    resolved_workflow_orchestration_lease_service.repository
                ),
                logical_channel_binding_repository=(
                    workflow_event_logical_channel_binding_repository
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_event_logical_channel_binding_service = (
            workflow_event_logical_channel_binding_service
        )
    configured_transport_profiles = (
        _deployment_event_transport_profiles(resolved_settings)
        if deployment_event_transport_profiles is None
        else tuple(deployment_event_transport_profiles)
    )
    profile_keys = tuple(
        (profile.transport_profile_id, profile.transport_profile_revision)
        for profile in configured_transport_profiles
    )
    if len(profile_keys) != len(set(profile_keys)):
        raise ValueError("deployment transport profile revisions must be unique")
    expected_profile_environment = f"environment.{resolved_settings.environment}"
    if any(
        profile.scope.environment_id != expected_profile_environment
        for profile in configured_transport_profiles
    ):
        raise ValueError("deployment transport profile scope does not match the environment")
    if workflow_transport_profile_snapshot_service is None:
        transport_profile_snapshot_repository_methods = (
            "get_transport_profile_snapshot",
            "get_transport_profile_snapshot_request",
            "snapshot_transport_profile",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in transport_profile_snapshot_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement transport profile snapshots; "
                "inject workflow_transport_profile_snapshot_service explicitly"
            )
        transport_profile_snapshot_repository = cast(
            WorkflowTransportProfileSnapshotRepository,
            workflow_repository,
        )
        transport_profile_registry: DeploymentEventTransportProfileRegistry = (
            _ConfiguredDeploymentEventTransportProfileRegistry(configured_transport_profiles)
        )
        resolved_workflow_transport_profile_snapshot_service = (
            WorkflowTransportProfileSnapshotService(
                transport_profile_registry=transport_profile_registry,
                snapshot_repository=transport_profile_snapshot_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_transport_profile_snapshot_service = (
            workflow_transport_profile_snapshot_service
        )
    configured_transport_routes = (
        _deployment_event_transport_routes(resolved_settings)
        if deployment_event_transport_routes is None
        else tuple(deployment_event_transport_routes)
    )
    route_keys = tuple(
        (route.route_id, route.route_revision) for route in configured_transport_routes
    )
    if len(route_keys) != len(set(route_keys)):
        raise ValueError("deployment transport route revisions must be unique")
    expected_route_environment = f"environment.{resolved_settings.environment}"
    if any(
        route.scope.environment_id != expected_route_environment
        for route in configured_transport_routes
    ):
        raise ValueError("deployment transport route scope does not match the environment")
    if workflow_transport_route_snapshot_service is None:
        transport_route_snapshot_repository_methods = (
            "get_transport_route_snapshot",
            "get_transport_route_snapshot_request",
            "snapshot_transport_route",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in transport_route_snapshot_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement transport route snapshots; "
                "inject workflow_transport_route_snapshot_service explicitly"
            )
        transport_route_snapshot_repository = cast(
            WorkflowTransportRouteSnapshotRepository,
            workflow_repository,
        )
        transport_route_registry: DeploymentEventTransportRouteRegistry = (
            _ConfiguredDeploymentEventTransportRouteRegistry(configured_transport_routes)
        )
        resolved_workflow_transport_route_snapshot_service = WorkflowTransportRouteSnapshotService(
            transport_route_registry=transport_route_registry,
            snapshot_repository=transport_route_snapshot_repository,
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_workflow_transport_route_snapshot_service = (
            workflow_transport_route_snapshot_service
        )
    configured_transport_credential_assignments = (
        _deployment_physical_transport_credential_assignments(
            resolved_settings,
            configured_transport_routes,
        )
        if deployment_physical_transport_credential_assignments is None
        else tuple(deployment_physical_transport_credential_assignments)
    )
    assignment_keys = tuple(
        (assignment.assignment_id, assignment.assignment_revision)
        for assignment in configured_transport_credential_assignments
    )
    if len(assignment_keys) != len(set(assignment_keys)):
        raise ValueError("deployment credential assignment revisions must be unique")
    assignment_head_ranks = tuple(
        (assignment.assignment_id, assignment.rotation_epoch, assignment.credential_generation)
        for assignment in configured_transport_credential_assignments
    )
    if len(assignment_head_ranks) != len(set(assignment_head_ranks)):
        raise ValueError("deployment credential assignment head generations must be unique")
    if any(
        assignment.scope.environment_id != expected_route_environment
        for assignment in configured_transport_credential_assignments
    ):
        raise ValueError("deployment credential assignment scope does not match the environment")
    if workflow_transport_credential_assignment_snapshot_service is None:
        credential_assignment_snapshot_repository_methods = (
            "get_active_credential_assignment",
            "get_credential_assignment_snapshot",
            "get_credential_assignment_snapshot_request",
            "list_credential_assignment_snapshots",
            "snapshot_credential_assignment",
            "synchronize_credential_assignments",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in credential_assignment_snapshot_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement credential assignment snapshots; "
                "inject workflow_transport_credential_assignment_snapshot_service explicitly"
            )
        credential_assignment_snapshot_repository = cast(
            WorkflowTransportCredentialAssignmentSnapshotRepository,
            workflow_repository,
        )
        credential_assignment_registry: DeploymentPhysicalTransportCredentialAssignmentRegistry = (
            cast(DeploymentPhysicalTransportCredentialAssignmentRegistry, workflow_repository)
        )
        resolved_workflow_transport_credential_assignment_snapshot_service = (
            WorkflowTransportCredentialAssignmentSnapshotService(
                credential_assignment_registry=credential_assignment_registry,
                route_snapshot_reader=(
                    resolved_workflow_transport_route_snapshot_service.repository
                ),
                snapshot_repository=credential_assignment_snapshot_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_transport_credential_assignment_snapshot_service = (
            workflow_transport_credential_assignment_snapshot_service
        )
    synchronize_transport_credential_assignments = (
        workflow_transport_credential_assignment_snapshot_service is None
        and bool(configured_transport_credential_assignments)
    )
    if workflow_event_transport_compatibility_admission_service is None:
        transport_compatibility_admission_repository_methods = (
            "get_event_logical_channel_binding_by_id",
            "get_transport_profile_snapshot_by_id",
            "get_transport_compatibility_admission",
            "get_transport_compatibility_admission_request",
            "admit_transport_compatibility",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in transport_compatibility_admission_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement transport compatibility "
                "admissions; inject "
                "workflow_event_transport_compatibility_admission_service explicitly"
            )
        workflow_event_transport_compatibility_admission_repository = cast(
            WorkflowEventTransportCompatibilityAdmissionRepository,
            workflow_repository,
        )
        resolved_workflow_event_transport_compatibility_admission_service = (
            WorkflowEventTransportCompatibilityAdmissionService(
                admission_repository=(workflow_event_transport_compatibility_admission_repository),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_event_transport_compatibility_admission_service = (
            workflow_event_transport_compatibility_admission_service
        )
    if workflow_event_physical_transport_route_binding_service is None:
        physical_transport_route_binding_repository_methods = (
            "get_event_logical_channel_binding_by_id",
            "get_transport_profile_snapshot_by_id",
            "get_transport_compatibility_admission_by_id",
            "get_transport_route_snapshot_by_id",
            "get_physical_transport_route_binding",
            "list_physical_transport_route_bindings",
            "get_physical_transport_route_binding_request",
            "bind_physical_transport_route",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in physical_transport_route_binding_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement physical transport route "
                "bindings; inject workflow_event_physical_transport_route_binding_service "
                "explicitly"
            )
        physical_transport_route_binding_repository = cast(
            WorkflowEventPhysicalTransportRouteBindingRepository,
            workflow_repository,
        )
        resolved_workflow_event_physical_transport_route_binding_service = (
            WorkflowEventPhysicalTransportRouteBindingService(
                binding_repository=physical_transport_route_binding_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_event_physical_transport_route_binding_service = (
            workflow_event_physical_transport_route_binding_service
        )
    if workflow_event_physical_transport_credential_assignment_binding_service is None:
        physical_transport_credential_assignment_binding_repository_methods = (
            "get_physical_transport_route_binding_by_id",
            "get_transport_route_snapshot_by_id",
            "get_credential_assignment_snapshot_by_id",
            "get_credential_assignment_binding",
            "list_credential_assignment_bindings",
            "get_credential_assignment_binding_request",
            "bind_credential_assignment",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in physical_transport_credential_assignment_binding_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement physical transport "
                "credential-assignment bindings; inject "
                "workflow_event_physical_transport_credential_assignment_binding_service "
                "explicitly"
            )
        physical_transport_credential_assignment_binding_repository = cast(
            WorkflowTransportCredentialAssignmentBindingRepository,
            workflow_repository,
        )
        resolved_workflow_event_physical_transport_credential_assignment_binding_service = (
            WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
                binding_repository=(physical_transport_credential_assignment_binding_repository),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_event_physical_transport_credential_assignment_binding_service = (
            workflow_event_physical_transport_credential_assignment_binding_service
        )
    if workflow_event_physical_transport_credential_assignment_freshness_admission_service is None:
        credential_assignment_freshness_repository_methods = (
            "get_credential_assignment_binding_by_id",
            "get_credential_assignment_snapshot_by_id",
            "get_current_credential_assignment_head",
            "list_credential_assignment_freshness_admissions",
            "get_credential_assignment_freshness_admission_request",
            "admit_credential_assignment_freshness",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in credential_assignment_freshness_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement physical transport "
                "credential-assignment freshness admissions; inject "
                "workflow_event_physical_transport_credential_assignment_freshness_"
                "admission_service explicitly"
            )
        credential_assignment_freshness_repository = cast(
            WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository,
            workflow_repository,
        )
        resolved_credential_assignment_freshness_service = (
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService(
                admission_repository=credential_assignment_freshness_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_credential_assignment_freshness_service = (
            workflow_event_physical_transport_credential_assignment_freshness_admission_service
        )
    if workflow_event_physical_transport_credential_access_authorization_lease_service is None:
        credential_access_authorization_repository_methods = (
            "get_authoritative_time",
            "get_credential_assignment_freshness_admission_by_id",
            "get_credential_assignment_binding_by_id",
            "get_credential_assignment_snapshot_by_id",
            "get_current_credential_assignment_head",
            "list_credential_access_authorization_leases",
            "authorize_credential_access",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in credential_access_authorization_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement physical transport "
                "credential-access authorization leases; inject "
                "workflow_event_physical_transport_credential_access_authorization_lease_"
                "service explicitly"
            )
        credential_access_authorization_repository = cast(
            WorkflowTransportCredentialAccessAuthorizationLeaseRepository,
            workflow_repository,
        )
        resolved_credential_access_authorization_lease_service = (
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
                authorization_repository=credential_access_authorization_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_credential_access_authorization_lease_service = (
            workflow_event_physical_transport_credential_access_authorization_lease_service
        )
    if workflow_event_physical_transport_route_freshness_admission_service is None:
        physical_transport_route_freshness_repository_methods = (
            "get_physical_transport_route_binding_by_id",
            "get_transport_route_snapshot_by_id",
            "get_current_route_selection_head",
            "get_route_freshness_admission",
            "list_route_freshness_admissions",
            "get_route_freshness_admission_request",
            "admit_physical_transport_route_freshness",
            "synchronize_route_selection_heads",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in physical_transport_route_freshness_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement physical transport route "
                "freshness admissions; inject "
                "workflow_event_physical_transport_route_freshness_admission_service explicitly"
            )
        physical_transport_route_freshness_repository = cast(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository,
            workflow_repository,
        )
        resolved_workflow_event_physical_transport_route_freshness_admission_service = (
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionService(
                admission_repository=physical_transport_route_freshness_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_workflow_event_physical_transport_route_freshness_admission_service = (
            workflow_event_physical_transport_route_freshness_admission_service
        )
    if workflow_event_physical_transport_endpoint_resolution_authorization_lease_service is None:
        endpoint_resolution_authorization_repository_methods = (
            "get_authoritative_time",
            "get_route_freshness_admission_by_id",
            "get_physical_transport_route_binding_by_id",
            "get_transport_route_snapshot_by_id",
            "get_current_route_selection_head",
            "get_endpoint_resolution_authorization_lease",
            "list_endpoint_resolution_authorization_leases",
            "get_endpoint_resolution_authorization_lease_request",
            "authorize_endpoint_resolution",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in endpoint_resolution_authorization_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement physical transport endpoint "
                "resolution authorization leases; inject "
                "workflow_event_physical_transport_endpoint_resolution_authorization_lease_"
                "service explicitly"
            )
        endpoint_resolution_authorization_repository = cast(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository,
            workflow_repository,
        )
        resolved_endpoint_resolution_authorization_lease_service = (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService(
                authorization_repository=endpoint_resolution_authorization_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_endpoint_resolution_authorization_lease_service = (
            workflow_event_physical_transport_endpoint_resolution_authorization_lease_service
        )
    if workflow_event_physical_transport_endpoint_materialization_service is None:
        endpoint_materialization_repository_methods = (
            "get_authoritative_time",
            "get_endpoint_resolution_authorization_lease_by_id",
            "get_route_freshness_admission_by_id",
            "get_physical_transport_route_binding_by_id",
            "get_transport_route_snapshot_by_id",
            "get_current_route_selection_head",
            "get_endpoint_materialization_claim_by_lease",
            "get_endpoint_materialization_attempt_by_lease",
            "list_endpoint_materialization_attempts",
            "get_endpoint_materialization_result_by_lease",
            "claim_endpoint_materialization",
            "record_endpoint_materialization_result",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in endpoint_materialization_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement protected endpoint "
                "materializations; inject "
                "workflow_event_physical_transport_endpoint_materialization_service explicitly"
            )
        endpoint_materialization_repository = cast(
            WorkflowEventPhysicalTransportEndpointMaterializationRepository,
            workflow_repository,
        )
        endpoint_materializer = (
            SyntheticWorkflowPhysicalTransportEndpointMaterializer()
            if resolved_settings.environment == "development"
            else UnavailableWorkflowPhysicalTransportEndpointMaterializer()
        )
        resolved_endpoint_materialization_service = (
            WorkflowEventPhysicalTransportEndpointMaterializationService(
                repository=endpoint_materialization_repository,
                materializer=endpoint_materializer,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_endpoint_materialization_service = (
            workflow_event_physical_transport_endpoint_materialization_service
        )
    if workflow_event_physical_transport_credential_materialization_service is None:
        credential_materialization_repository_methods = (
            "get_authoritative_time",
            "get_credential_access_authorization_lease_by_id",
            "get_credential_assignment_freshness_admission_by_id",
            "get_credential_assignment_binding_by_id",
            "get_credential_assignment_snapshot_by_id",
            "get_current_credential_assignment_head",
            "get_credential_materialization_claim_by_lease",
            "get_credential_materialization_attempt_by_lease",
            "list_credential_materialization_attempts",
            "get_credential_materialization_result_by_lease",
            "claim_credential_materialization",
            "record_credential_materialization_result",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in credential_materialization_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement protected credential "
                "materializations; inject workflow_event_physical_transport_credential_"
                "materialization_service explicitly"
            )
        credential_materialization_repository = cast(
            WorkflowEventPhysicalTransportCredentialMaterializationRepository,
            workflow_repository,
        )
        credential_materializer = (
            SyntheticWorkflowPhysicalTransportCredentialMaterializer()
            if resolved_settings.environment == "development"
            else UnavailableWorkflowPhysicalTransportCredentialMaterializer()
        )
        resolved_credential_materialization_service = (
            WorkflowEventPhysicalTransportCredentialMaterializationService(
                repository=credential_materialization_repository,
                materializer=credential_materializer,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_credential_materialization_service = (
            workflow_event_physical_transport_credential_materialization_service
        )
    if workflow_event_physical_transport_target_context_binding_service is None:
        target_context_binding_repository_methods = (
            "bind_target_context",
            "list_target_context_bindings",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_binding_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement protected transport "
                "target-context bindings; inject workflow_event_physical_transport_target_"
                "context_binding_service explicitly"
            )
        target_context_binding_repository = cast(
            WorkflowEventPhysicalTransportTargetContextBindingRepository,
            workflow_repository,
        )
        resolved_target_context_binding_service = (
            WorkflowEventPhysicalTransportTargetContextBindingService(
                binding_repository=target_context_binding_repository,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_target_context_binding_service = (
            workflow_event_physical_transport_target_context_binding_service
        )
    if workflow_event_physical_transport_target_context_access_authorization_lease_service is None:
        target_context_access_authorization_repository_methods = (
            "get_authoritative_time",
            "get_target_context_binding_by_id",
            "list_target_context_access_authorization_leases",
            "authorize_target_context_access",
        )
        if not all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_access_authorization_repository_methods
        ):
            raise ValueError(
                "workflow planning repository does not implement protected transport "
                "target-context access authorization leases; inject "
                "workflow_event_physical_transport_target_context_access_authorization_"
                "lease_service explicitly"
            )
        target_context_access_authorization_repository = cast(
            WorkflowTargetContextAccessAuthorizationLeaseRepository,
            workflow_repository,
        )
        resolved_target_context_access_authorization_lease_service = (
            WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService(
                authorization_repository=target_context_access_authorization_repository,
                endpoint_status_attestor=UnavailableWorkflowProtectedEndpointStatusAttestor(),
                credential_status_attestor=(UnavailableWorkflowProtectedCredentialStatusAttestor()),
                status_signature_verifier=(
                    DenyAllWorkflowProtectedArtifactStatusSignatureVerifier()
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_target_context_access_authorization_lease_service = (
            workflow_event_physical_transport_target_context_access_authorization_lease_service
        )
    if workflow_event_physical_transport_target_context_artifact_opening_service is None:
        target_context_artifact_opening_repository_methods = (
            "get_authoritative_time",
            "get_target_context_access_authorization_lease_by_id",
            "get_target_context_binding_by_id",
            "get_endpoint_materialization_result_by_id",
            "get_credential_materialization_result_by_id",
            "lookup_target_context_artifact_opening_replay",
            "claim_target_context_artifact_opening",
            "record_target_context_artifact_opening_result",
            "list_target_context_artifact_opening_attempts",
            "get_target_context_artifact_opening_results_by_opening_ids",
            "list_target_context_artifact_opening_results",
        )
        if all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_artifact_opening_repository_methods
        ):
            target_context_artifact_opening_repository = cast(
                WorkflowTargetContextArtifactOpeningRepository,
                workflow_repository,
            )
        else:
            target_context_artifact_opening_repository = cast(
                WorkflowTargetContextArtifactOpeningRepository,
                _UnavailableWorkflowTargetContextArtifactOpeningRepository(),
            )
        resolved_target_context_artifact_opening_service = (
            WorkflowEventPhysicalTransportTargetContextArtifactOpeningService(
                repository=target_context_artifact_opening_repository,
                endpoint_status_attestor=UnavailableWorkflowProtectedEndpointStatusAttestor(),
                credential_status_attestor=(UnavailableWorkflowProtectedCredentialStatusAttestor()),
                status_signature_verifier=(
                    DenyAllWorkflowProtectedArtifactStatusSignatureVerifier()
                ),
                opener=UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener(),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_target_context_artifact_opening_service = (
            workflow_event_physical_transport_target_context_artifact_opening_service
        )
    if workflow_protected_transport_target_context_capsule_consumer_binding_service is None:
        target_context_capsule_consumer_binding_repository_methods = (
            "bind_target_context_capsule_consumer",
            "list_target_context_capsule_consumer_bindings",
        )
        if all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_capsule_consumer_binding_repository_methods
        ):
            target_context_capsule_consumer_binding_repository = cast(
                WorkflowTargetContextCapsuleConsumerBindingRepository,
                workflow_repository,
            )
        else:
            target_context_capsule_consumer_binding_repository = cast(
                WorkflowTargetContextCapsuleConsumerBindingRepository,
                _UnavailableWorkflowTargetContextCapsuleConsumerBindingRepository(),
            )
        resolved_target_context_capsule_consumer_binding_service = (
            WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
                repository=target_context_capsule_consumer_binding_repository,
            )
        )
    else:
        resolved_target_context_capsule_consumer_binding_service = (
            workflow_protected_transport_target_context_capsule_consumer_binding_service
        )
    if (
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service
        is None
    ):
        target_context_capsule_handoff_repository_methods = (
            "get_authoritative_time",
            "get_target_context_capsule_consumer_binding_by_id",
            "authorize_target_context_capsule_handoff",
            "list_target_context_capsule_handoff_authorization_leases",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_capsule_handoff_repository_methods
        ):
            target_context_capsule_handoff_repository = cast(
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository,
                workflow_repository,
            )
        else:
            target_context_capsule_handoff_repository = cast(
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository,
                _UnavailableWorkflowTargetContextCapsuleHandoffAuthorizationLeaseRepository(),
            )
        resolved_target_context_capsule_handoff_authorization_lease_service = (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService(
                authorization_repository=target_context_capsule_handoff_repository,
                lifecycle_status_attestor=(
                    UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor()
                ),
                lifecycle_signature_verifier=(
                    DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier()
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_target_context_capsule_handoff_authorization_lease_service = (
            workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service
        )
    if workflow_protected_transport_target_context_capsule_handoff_service is None:
        target_context_capsule_handoff_consumption_methods = (
            "get_authoritative_time",
            "get_target_context_capsule_handoff_authorization_lease_by_id",
            "get_target_context_capsule_consumer_binding_by_id",
            "lookup_target_context_capsule_handoff_replay",
            "claim_target_context_capsule_handoff",
            "record_target_context_capsule_handoff_result",
            "list_target_context_capsule_handoff_attempts",
            "get_target_context_capsule_handoff_results_by_handoff_ids",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_capsule_handoff_consumption_methods
        ):
            target_context_capsule_handoff_consumption_repository = cast(
                WorkflowTargetContextCapsuleHandoffRepository,
                workflow_repository,
            )
        else:
            target_context_capsule_handoff_consumption_repository = cast(
                WorkflowTargetContextCapsuleHandoffRepository,
                _UnavailableWorkflowTargetContextCapsuleHandoffRepository(),
            )
        resolved_target_context_capsule_handoff_service = WorkflowProtectedTransportTargetContextCapsuleHandoffService(  # noqa: E501
            repository=target_context_capsule_handoff_consumption_repository,
            lifecycle_attestor=(
                UnavailableWorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor()
            ),
            acceptance_attestor=(
                UnavailableWorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor()
            ),
            attestation_signature_verifier=(
                DenyAllWorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier()
            ),
            adapter=UnavailableWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter(),
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_target_context_capsule_handoff_service = (
            workflow_protected_transport_target_context_capsule_handoff_service
        )
    if (
        workflow_protected_transport_target_context_capsule_opening_authorization_lease_service
        is None
    ):
        opening_repository_methods = (
            "get_authoritative_time",
            "get_target_context_capsule_opening_authorization_source",
            "authorize_target_context_capsule_opening",
            "list_target_context_capsule_opening_authorization_leases",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in opening_repository_methods
        ):
            opening_repository = cast(
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository,
                workflow_repository,
            )
        else:
            opening_repository = cast(
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository,
                _UnavailableWorkflowTargetContextCapsuleOpeningAuthorizationLeaseRepository(),
            )
        resolved_target_context_capsule_opening_authorization_lease_service = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService(  # noqa: E501
            authorization_repository=opening_repository,
            custody_attestor=(
                UnavailableWorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor()
            ),
            custody_signature_verifier=(
                DenyAllWorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier()
            ),
            audit_sink=resolved_audit_sink,
        )
    else:
        resolved_target_context_capsule_opening_authorization_lease_service = (
            workflow_protected_transport_target_context_capsule_opening_authorization_lease_service
        )
    if workflow_protected_transport_target_context_capsule_opening_service is None:
        target_context_capsule_opening_methods = (
            "get_authoritative_time",
            "get_target_context_capsule_opening_source",
            "lookup_target_context_capsule_opening_replay",
            "claim_target_context_capsule_opening",
            "record_target_context_capsule_opening_result",
            "list_target_context_capsule_opening_attempts",
            "get_target_context_capsule_opening_results_by_opening_ids",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in target_context_capsule_opening_methods
        ):
            target_context_capsule_opening_repository = cast(
                WorkflowTargetContextCapsuleOpeningRepository,
                workflow_repository,
            )
        else:
            target_context_capsule_opening_repository = cast(
                WorkflowTargetContextCapsuleOpeningRepository,
                _UnavailableWorkflowTargetContextCapsuleOpeningRepository(),
            )
        opening_service_factory = WorkflowProtectedTransportTargetContextCapsuleOpeningService
        if (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        ):
            development_opening_attestors = (
                SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors(test_enabled=True)
            )
            resolved_target_context_capsule_opening_service = opening_service_factory(
                repository=target_context_capsule_opening_repository,
                custody_attestor=development_opening_attestors,
                openability_attestor=development_opening_attestors,
                attestation_signature_verifier=development_opening_attestors,
                opener=SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener(
                    test_enabled=True
                ),
                audit_sink=resolved_audit_sink,
            )
        else:
            resolved_target_context_capsule_opening_service = opening_service_factory(
                repository=target_context_capsule_opening_repository,
                custody_attestor=(
                    UnavailableWorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor()
                ),
                openability_attestor=(
                    UnavailableWorkflowProtectedTargetContextCapsuleOpenabilityAttestor()
                ),
                attestation_signature_verifier=(
                    DenyAllWorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier()
                ),
                opener=(UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener()),
                audit_sink=resolved_audit_sink,
            )
    else:
        resolved_target_context_capsule_opening_service = (
            workflow_protected_transport_target_context_capsule_opening_service
        )
    if workflow_protected_resident_context_access_authorization_service is None:
        resident_context_access_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_resident_context_access_authorization",
            "get_protected_resident_context_access_authorization_source",
            "authorize_protected_resident_context_access",
            "list_protected_resident_context_access_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in resident_context_access_repository_methods
        ):
            resident_context_access_repository = cast(
                WorkflowProtectedResidentContextAccessAuthorizationRepository,
                workflow_repository,
            )
        else:
            resident_context_access_repository = cast(
                WorkflowProtectedResidentContextAccessAuthorizationRepository,
                _UnavailableWorkflowProtectedResidentContextAccessAuthorizationRepository(),
            )
        resident_context_lifecycle_attestor: WorkflowProtectedResidentContextLifecycleAttestor
        resident_context_lifecycle_signature_verifier: (
            WorkflowProtectedResidentContextLifecycleSignatureVerifier
        )
        resident_context_opening_receipt_signature_verifier: (
            WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier
        )
        if (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        ):
            development_lifecycle_attestor = (
                DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor(
                    development_enabled=True
                )
            )
            resident_context_lifecycle_attestor = development_lifecycle_attestor
            resident_context_lifecycle_signature_verifier = development_lifecycle_attestor
            resident_context_opening_receipt_signature_verifier = (
                _WorkflowProtectedResidentContextOpeningReceiptSignatureVerifierAdapter(
                    SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener(test_enabled=True)
                )
            )
        else:
            resident_context_lifecycle_attestor = (
                UnavailableWorkflowProtectedResidentContextLifecycleAttestor()
            )
            resident_context_lifecycle_signature_verifier = (
                DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier()
            )
            resident_context_opening_receipt_signature_verifier = (
                _WorkflowProtectedResidentContextOpeningReceiptSignatureVerifierAdapter(
                    UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener()
                )
            )
        resolved_protected_resident_context_access_authorization_service = (
            WorkflowProtectedResidentContextAccessAuthorizationService(
                authorization_repository=resident_context_access_repository,
                lifecycle_attestor=resident_context_lifecycle_attestor,
                lifecycle_signature_verifier=(resident_context_lifecycle_signature_verifier),
                opening_receipt_signature_verifier=(
                    resident_context_opening_receipt_signature_verifier
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_resident_context_access_authorization_service = (
            workflow_protected_resident_context_access_authorization_service
        )
    shared_accessor_receipt_signature_verifier = (
        workflow_protected_resident_context_trusted_accessor_receipt_signature_verifier
    )
    if workflow_protected_resident_context_access_consumption_service is None:
        resident_context_access_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_resident_context_access_consumption_replay",
            "get_protected_resident_context_access_consumption_source",
            "claim_protected_resident_context_access_consumption",
            "record_protected_resident_context_access_consumption_result",
            "list_protected_resident_context_access_consumption_attempts",
            "get_protected_resident_context_access_consumption_results",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in resident_context_access_consumption_repository_methods
        ):
            resident_context_access_consumption_repository = cast(
                WorkflowProtectedResidentContextAccessConsumptionRepository,
                workflow_repository,
            )
        else:
            resident_context_access_consumption_repository = cast(
                WorkflowProtectedResidentContextAccessConsumptionRepository,
                _UnavailableWorkflowProtectedResidentContextAccessConsumptionRepository(),
            )
        if (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        ):
            development_lifecycle_attestor = (
                DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor(
                    development_enabled=True
                )
            )
            development_readiness_attestor = (
                DeterministicDevelopmentWorkflowProtectedResidentContextAccessorReadinessAttestor(
                    development_enabled=True
                )
            )
            development_accessor = (
                DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor(
                    development_enabled=True
                )
            )
            shared_accessor_receipt_signature_verifier = development_accessor
            if isinstance(
                resident_context_access_consumption_repository,
                PostgreSQLWorkflowPlanRepository,
            ):
                resident_context_access_consumption_repository.bind_protected_resident_context_access_receipt_signature_verifier(
                    development_accessor
                )
            resolved_protected_resident_context_access_consumption_service = (
                WorkflowProtectedResidentContextAccessConsumptionService(
                    repository=resident_context_access_consumption_repository,
                    lifecycle_attestor=development_lifecycle_attestor,
                    readiness_attestor=development_readiness_attestor,
                    lifecycle_signature_verifier=development_lifecycle_attestor,
                    readiness_signature_verifier=development_readiness_attestor,
                    accessor=development_accessor,
                    audit_sink=resolved_audit_sink,
                )
            )
        else:
            unavailable_accessor = UnavailableWorkflowProtectedResidentContextTrustedAccessor()
            shared_accessor_receipt_signature_verifier = (
                shared_accessor_receipt_signature_verifier or unavailable_accessor
            )
            if isinstance(
                resident_context_access_consumption_repository,
                PostgreSQLWorkflowPlanRepository,
            ):
                resident_context_access_consumption_repository.bind_protected_resident_context_access_receipt_signature_verifier(
                    shared_accessor_receipt_signature_verifier
                )
            resolved_protected_resident_context_access_consumption_service = (
                WorkflowProtectedResidentContextAccessConsumptionService(
                    repository=resident_context_access_consumption_repository,
                    lifecycle_attestor=(
                        UnavailableWorkflowProtectedResidentContextLifecycleAttestor()
                    ),
                    readiness_attestor=(
                        UnavailableWorkflowProtectedResidentContextAccessorReadinessAttestor()
                    ),
                    lifecycle_signature_verifier=(
                        DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier()
                    ),
                    readiness_signature_verifier=(
                        DenyAllWorkflowProtectedResidentContextAccessorReadinessSignatureVerifier()
                    ),
                    accessor=unavailable_accessor,
                    audit_sink=resolved_audit_sink,
                )
            )
    else:
        resolved_protected_resident_context_access_consumption_service = (
            workflow_protected_resident_context_access_consumption_service
        )
    if workflow_protected_runtime_context_injection_authorization_service is None:
        runtime_context_injection_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_context_injection_authorization",
            "get_protected_runtime_context_injection_authorization_source",
            "authorize_protected_runtime_context_injection",
            "list_protected_runtime_context_injection_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_context_injection_authorization_repository_methods
        ):
            runtime_context_injection_authorization_repository = cast(
                WorkflowProtectedRuntimeContextInjectionAuthorizationRepository,
                workflow_repository,
            )
        else:
            runtime_context_injection_authorization_repository = cast(
                WorkflowProtectedRuntimeContextInjectionAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeContextInjectionAuthorizationRepository(),
            )
        unavailable_runtime_handle_lifecycle_attestor = (
            _UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor()
        )
        runtime_handle_lifecycle_attestor: WorkflowProtectedRuntimeHandleLifecycleAttestor
        runtime_handle_lifecycle_signature_verifier: (
            WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier
        )
        runtime_context_injection_accessor_receipt_verifier: (
            WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier
        )
        if (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        ):
            development_runtime_handle_lifecycle_attestor = (
                DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor(
                    development_enabled=True
                )
            )
            runtime_handle_lifecycle_attestor = (
                workflow_protected_runtime_handle_lifecycle_attestor
                if workflow_protected_runtime_handle_lifecycle_attestor is not None
                else development_runtime_handle_lifecycle_attestor
            )
            if workflow_protected_runtime_handle_lifecycle_signature_verifier is not None:
                runtime_handle_lifecycle_signature_verifier = (
                    workflow_protected_runtime_handle_lifecycle_signature_verifier
                )
            elif callable(
                getattr(
                    runtime_handle_lifecycle_attestor,
                    "verify_runtime_handle_lifecycle_attestation",
                    None,
                )
            ):
                runtime_handle_lifecycle_signature_verifier = cast(
                    WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
                    runtime_handle_lifecycle_attestor,
                )
            else:
                runtime_handle_lifecycle_signature_verifier = (
                    unavailable_runtime_handle_lifecycle_attestor
                )
            runtime_context_injection_accessor_receipt_verifier = (
                shared_accessor_receipt_signature_verifier
                if shared_accessor_receipt_signature_verifier is not None
                else DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor(
                    development_enabled=True,
                )
            )
        else:
            runtime_handle_lifecycle_attestor = (
                workflow_protected_runtime_handle_lifecycle_attestor
                if workflow_protected_runtime_handle_lifecycle_attestor is not None
                else unavailable_runtime_handle_lifecycle_attestor
            )
            if workflow_protected_runtime_handle_lifecycle_signature_verifier is not None:
                runtime_handle_lifecycle_signature_verifier = (
                    workflow_protected_runtime_handle_lifecycle_signature_verifier
                )
            elif workflow_protected_runtime_handle_lifecycle_attestor is not None and callable(
                getattr(
                    workflow_protected_runtime_handle_lifecycle_attestor,
                    "verify_runtime_handle_lifecycle_attestation",
                    None,
                )
            ):
                runtime_handle_lifecycle_signature_verifier = cast(
                    WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
                    workflow_protected_runtime_handle_lifecycle_attestor,
                )
            else:
                runtime_handle_lifecycle_signature_verifier = (
                    unavailable_runtime_handle_lifecycle_attestor
                )
            runtime_context_injection_accessor_receipt_verifier = (
                shared_accessor_receipt_signature_verifier
                if shared_accessor_receipt_signature_verifier is not None
                else UnavailableWorkflowProtectedResidentContextTrustedAccessor()
            )
        if isinstance(
            runtime_context_injection_authorization_repository,
            PostgreSQLWorkflowPlanRepository,
        ):
            runtime_context_injection_authorization_repository.bind_protected_resident_context_access_receipt_signature_verifier(
                runtime_context_injection_accessor_receipt_verifier
            )
        resolved_protected_runtime_context_injection_authorization_service = (
            WorkflowProtectedRuntimeContextInjectionAuthorizationService(
                authorization_repository=(runtime_context_injection_authorization_repository),
                lifecycle_attestor=runtime_handle_lifecycle_attestor,
                lifecycle_signature_verifier=(runtime_handle_lifecycle_signature_verifier),
                accessor_receipt_signature_verifier=(
                    runtime_context_injection_accessor_receipt_verifier
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_context_injection_authorization_service = (
            workflow_protected_runtime_context_injection_authorization_service
        )
    if workflow_protected_runtime_context_injection_consumption_service is None:
        runtime_context_injection_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_context_injection_consumption_replay",
            "get_protected_runtime_context_injection_consumption_source",
            "claim_protected_runtime_context_injection_consumption",
            "record_protected_runtime_context_injection_consumption_result",
            "list_protected_runtime_context_injection_consumption_attempts",
            "get_protected_runtime_context_injection_consumption_results",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_context_injection_consumption_repository_methods
        ):
            runtime_context_injection_consumption_repository = cast(
                WorkflowProtectedRuntimeContextInjectionConsumptionRepository,
                workflow_repository,
            )
        else:
            runtime_context_injection_consumption_repository = cast(
                WorkflowProtectedRuntimeContextInjectionConsumptionRepository,
                _UnavailableWorkflowProtectedRuntimeContextInjectionConsumptionRepository(),
            )

        development_injection_consumption = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_runtime_handle_lifecycle = (
            _UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor()
        )
        default_runtime_handle_lifecycle: WorkflowProtectedRuntimeHandleLifecycleAttestor
        default_slot_readiness: WorkflowProtectedRuntimeSlotReadinessAttestor
        default_injector: WorkflowProtectedRuntimeContextTrustedInjector
        if development_injection_consumption:
            default_runtime_handle_lifecycle = (
                DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor(
                    development_enabled=True
                )
            )
            default_slot_readiness = (
                DeterministicDevelopmentWorkflowProtectedRuntimeSlotReadinessAttestor(
                    development_enabled=True
                )
            )
            default_injector = (
                DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector(
                    development_enabled=True
                )
            )
        else:
            default_runtime_handle_lifecycle = unavailable_runtime_handle_lifecycle
            default_slot_readiness = UnavailableWorkflowProtectedRuntimeSlotReadinessAttestor()
            default_injector = UnavailableWorkflowProtectedRuntimeContextTrustedInjector()

        injection_consumption_lifecycle_attestor = (
            workflow_protected_runtime_handle_lifecycle_attestor or default_runtime_handle_lifecycle
        )
        if workflow_protected_runtime_handle_lifecycle_signature_verifier is not None:
            injection_consumption_lifecycle_verifier = (
                workflow_protected_runtime_handle_lifecycle_signature_verifier
            )
        elif callable(
            getattr(
                injection_consumption_lifecycle_attestor,
                "verify_runtime_handle_lifecycle_attestation",
                None,
            )
        ):
            injection_consumption_lifecycle_verifier = cast(
                WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
                injection_consumption_lifecycle_attestor,
            )
        else:
            injection_consumption_lifecycle_verifier = unavailable_runtime_handle_lifecycle

        injection_consumption_slot_attestor = (
            workflow_protected_runtime_slot_readiness_attestor or default_slot_readiness
        )
        if workflow_protected_runtime_slot_readiness_signature_verifier is not None:
            injection_consumption_slot_verifier = (
                workflow_protected_runtime_slot_readiness_signature_verifier
            )
        elif callable(
            getattr(
                injection_consumption_slot_attestor,
                "verify_runtime_slot_readiness_attestation",
                None,
            )
        ):
            injection_consumption_slot_verifier = cast(
                WorkflowProtectedRuntimeSlotReadinessSignatureVerifier,
                injection_consumption_slot_attestor,
            )
        else:
            injection_consumption_slot_verifier = (
                DenyAllWorkflowProtectedRuntimeSlotReadinessSignatureVerifier()
            )

        injection_consumption_injector = (
            workflow_protected_runtime_context_trusted_injector or default_injector
        )
        if (
            workflow_protected_runtime_context_trusted_injector_receipt_signature_verifier
            is not None
        ):
            injection_consumption_receipt_verifier = (
                workflow_protected_runtime_context_trusted_injector_receipt_signature_verifier
            )
        elif callable(getattr(injection_consumption_injector, "verify_receipt", None)):
            injection_consumption_receipt_verifier = cast(
                WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
                injection_consumption_injector,
            )
        else:
            injection_consumption_receipt_verifier = (
                DenyAllWorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier()
            )

        bind_injection_receipt_verifier = getattr(
            runtime_context_injection_consumption_repository,
            "bind_protected_runtime_context_injection_receipt_signature_verifier",
            None,
        )
        if callable(bind_injection_receipt_verifier):
            bind_injection_receipt_verifier(injection_consumption_receipt_verifier)
        resolved_protected_runtime_context_injection_consumption_service = (
            WorkflowProtectedRuntimeContextInjectionConsumptionService(
                repository=runtime_context_injection_consumption_repository,
                lifecycle_attestor=injection_consumption_lifecycle_attestor,
                slot_readiness_attestor=injection_consumption_slot_attestor,
                lifecycle_signature_verifier=injection_consumption_lifecycle_verifier,
                slot_readiness_signature_verifier=injection_consumption_slot_verifier,
                injector=injection_consumption_injector,
                receipt_signature_verifier=injection_consumption_receipt_verifier,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_context_injection_consumption_service = (
            workflow_protected_runtime_context_injection_consumption_service
        )
    if workflow_protected_runtime_context_use_authorization_service is None:
        runtime_context_use_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_context_use_authorization",
            "get_protected_runtime_context_use_authorization_source",
            "authorize_protected_runtime_context_use",
            "list_protected_runtime_context_use_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_context_use_authorization_repository_methods
        ):
            runtime_context_use_authorization_repository = cast(
                WorkflowProtectedRuntimeContextUseAuthorizationRepository,
                workflow_repository,
            )
        else:
            runtime_context_use_authorization_repository = cast(
                WorkflowProtectedRuntimeContextUseAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeContextUseAuthorizationRepository(),
            )

        development_runtime_context_use_authorization = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_slot_lifecycle = UnavailableWorkflowProtectedRuntimeSlotLifecycleAttestor()
        default_slot_lifecycle: WorkflowProtectedRuntimeSlotLifecycleAttestor
        default_use_receipt_verifier: (
            WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier
        )
        if development_runtime_context_use_authorization:
            default_slot_lifecycle = (
                DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor(
                    development_enabled=True
                )
            )
            default_use_receipt_verifier = (
                DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector(
                    development_enabled=True
                )
            )
        else:
            default_slot_lifecycle = unavailable_slot_lifecycle
            default_use_receipt_verifier = (
                DenyAllWorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier()
            )

        runtime_context_use_slot_attestor = (
            workflow_protected_runtime_slot_lifecycle_attestor or default_slot_lifecycle
        )
        if workflow_protected_runtime_slot_lifecycle_signature_verifier is not None:
            runtime_context_use_slot_verifier = (
                workflow_protected_runtime_slot_lifecycle_signature_verifier
            )
        elif callable(
            getattr(
                runtime_context_use_slot_attestor,
                "verify_runtime_slot_lifecycle_attestation",
                None,
            )
        ):
            runtime_context_use_slot_verifier = cast(
                WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier,
                runtime_context_use_slot_attestor,
            )
        else:
            runtime_context_use_slot_verifier = unavailable_slot_lifecycle

        already_bound_use_receipt_verifier = getattr(
            runtime_context_use_authorization_repository,
            "_protected_runtime_context_injection_receipt_signature_verifier",
            None,
        )
        if (
            workflow_protected_runtime_context_trusted_injector_receipt_signature_verifier
            is not None
        ):
            runtime_context_use_receipt_verifier = (
                workflow_protected_runtime_context_trusted_injector_receipt_signature_verifier
            )
        elif already_bound_use_receipt_verifier is not None:
            runtime_context_use_receipt_verifier = cast(
                WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
                already_bound_use_receipt_verifier,
            )
        elif workflow_protected_runtime_context_trusted_injector is not None and callable(
            getattr(workflow_protected_runtime_context_trusted_injector, "verify_receipt", None)
        ):
            runtime_context_use_receipt_verifier = cast(
                WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
                workflow_protected_runtime_context_trusted_injector,
            )
        else:
            runtime_context_use_receipt_verifier = default_use_receipt_verifier

        bind_use_receipt_verifier = getattr(
            runtime_context_use_authorization_repository,
            "bind_protected_runtime_context_injection_receipt_signature_verifier",
            None,
        )
        if callable(bind_use_receipt_verifier):
            bind_use_receipt_verifier(runtime_context_use_receipt_verifier)
        resolved_protected_runtime_context_use_authorization_service = (
            WorkflowProtectedRuntimeContextUseAuthorizationService(
                authorization_repository=runtime_context_use_authorization_repository,
                lifecycle_attestor=runtime_context_use_slot_attestor,
                lifecycle_signature_verifier=runtime_context_use_slot_verifier,
                injector_receipt_signature_verifier=runtime_context_use_receipt_verifier,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_context_use_authorization_service = (
            workflow_protected_runtime_context_use_authorization_service
        )
    if workflow_protected_runtime_context_use_authorization_consumption_service is None:
        runtime_context_use_authorization_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_context_use_authorization_consumption_replay",
            "consume_protected_runtime_context_use_authorization",
            "list_protected_runtime_context_use_authorization_consumption_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in (runtime_context_use_authorization_consumption_repository_methods)
        ):
            runtime_context_use_authorization_consumption_repository = cast(
                WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository,
                workflow_repository,
            )
        else:
            runtime_context_use_authorization_consumption_repository = cast(
                WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository,
                _UnavailableWorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository(),
            )
        resolved_protected_runtime_context_use_authorization_consumption_service = (
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
                repository=runtime_context_use_authorization_consumption_repository
            )
        )
    else:
        resolved_protected_runtime_context_use_authorization_consumption_service = (
            workflow_protected_runtime_context_use_authorization_consumption_service
        )
    if workflow_protected_runtime_context_use_service is None:
        runtime_context_use_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_context_use_replay",
            "get_protected_runtime_context_use_source",
            "claim_protected_runtime_context_use",
            "record_protected_runtime_context_use_result",
            "list_protected_runtime_context_use_attempts",
            "get_protected_runtime_context_use_results",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_context_use_repository_methods
        ):
            runtime_context_use_repository = cast(
                WorkflowProtectedRuntimeContextUseRepository,
                workflow_repository,
            )
        else:
            runtime_context_use_repository = cast(
                WorkflowProtectedRuntimeContextUseRepository,
                _UnavailableWorkflowProtectedRuntimeContextUseRepository(),
            )
        resolved_protected_runtime_context_use_service = WorkflowProtectedRuntimeContextUseService(
            repository=runtime_context_use_repository,
            eligibility_attestor=(
                UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor()
            ),
            eligibility_signature_verifier=(
                DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier()
            ),
            trusted_user=UnavailableWorkflowProtectedRuntimeContextTrustedUser(),
            receipt_signature_verifier=(
                DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier()
            ),
        )
    else:
        resolved_protected_runtime_context_use_service = (
            workflow_protected_runtime_context_use_service
        )
    if workflow_protected_runtime_start_authorization_service is None:
        runtime_start_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_start_authorization",
            "get_protected_runtime_start_authorization_source",
            "authorize_protected_runtime_start",
            "list_protected_runtime_start_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_start_authorization_repository_methods
        ):
            runtime_start_authorization_repository = cast(
                WorkflowProtectedRuntimeStartAuthorizationRepository,
                workflow_repository,
            )
        else:
            runtime_start_authorization_repository = cast(
                WorkflowProtectedRuntimeStartAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeStartAuthorizationRepository(),
            )

        development_runtime_start_authorization = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_runtime_start_lifecycle = (
            UnavailableWorkflowProtectedRuntimeStartLifecycleAttestor()
        )
        default_runtime_start_lifecycle: WorkflowProtectedRuntimeStartLifecycleAttestor = (
            DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor(
                development_enabled=True
            )
            if development_runtime_start_authorization
            else unavailable_runtime_start_lifecycle
        )
        runtime_start_lifecycle_attestor = (
            workflow_protected_runtime_start_lifecycle_attestor or default_runtime_start_lifecycle
        )
        if workflow_protected_runtime_start_lifecycle_signature_verifier is not None:
            runtime_start_lifecycle_verifier = (
                workflow_protected_runtime_start_lifecycle_signature_verifier
            )
        elif callable(
            getattr(
                runtime_start_lifecycle_attestor,
                "verify_runtime_start_lifecycle_attestation",
                None,
            )
        ):
            runtime_start_lifecycle_verifier = cast(
                WorkflowProtectedRuntimeStartLifecycleSignatureVerifier,
                runtime_start_lifecycle_attestor,
            )
        else:
            runtime_start_lifecycle_verifier = unavailable_runtime_start_lifecycle

        runtime_start_use_receipt_verifier = (
            workflow_protected_runtime_context_use_receipt_signature_verifier
            or DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier()
        )
        bind_use_receipt_verifier = getattr(
            runtime_start_authorization_repository,
            "bind_protected_runtime_context_use_receipt_signature_verifier",
            None,
        )
        if callable(bind_use_receipt_verifier):
            bind_use_receipt_verifier(runtime_start_use_receipt_verifier)
        resolved_protected_runtime_start_authorization_service = (
            WorkflowProtectedRuntimeStartAuthorizationService(
                authorization_repository=runtime_start_authorization_repository,
                lifecycle_attestor=runtime_start_lifecycle_attestor,
                lifecycle_signature_verifier=runtime_start_lifecycle_verifier,
                use_receipt_signature_verifier=runtime_start_use_receipt_verifier,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_start_authorization_service = (
            workflow_protected_runtime_start_authorization_service
        )
    development_runtime_start_receipts = (
        resolved_settings.environment == "development"
        and resolved_settings.development_identity_enabled
    )
    if workflow_protected_runtime_start_receipt_signature_verifier is not None:
        resolved_runtime_start_receipt_verifier = (
            workflow_protected_runtime_start_receipt_signature_verifier
        )
    elif development_runtime_start_receipts:
        resolved_runtime_start_receipt_verifier = (
            DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier(
                development_enabled=True
            )
        )
    else:
        resolved_runtime_start_receipt_verifier = (
            DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier()
        )
    if workflow_protected_runtime_start_consumption_service is None:
        runtime_start_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_start_consumption_replay",
            "get_protected_runtime_start_consumption_source",
            "claim_protected_runtime_start_consumption",
            "record_protected_runtime_start_consumption_result",
            "list_protected_runtime_start_attempts",
            "get_protected_runtime_start_results",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_start_consumption_repository_methods
        ):
            runtime_start_consumption_repository = cast(
                WorkflowProtectedRuntimeStartConsumptionRepository,
                workflow_repository,
            )
        else:
            runtime_start_consumption_repository = cast(
                WorkflowProtectedRuntimeStartConsumptionRepository,
                _UnavailableWorkflowProtectedRuntimeStartConsumptionRepository(),
            )
        development_runtime_start_consumption = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        runtime_start_instruction_signer: WorkflowProtectedRuntimeStartInstructionSigner
        runtime_start_instruction_verifier: (
            WorkflowProtectedRuntimeStartInstructionSignatureVerifier
        )
        runtime_start_receipt_verifier: WorkflowProtectedRuntimeStartReceiptSignatureVerifier
        runtime_starter: WorkflowProtectedRuntimeStarter
        if development_runtime_start_consumption:
            runtime_start_instruction_signer = (
                DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner(
                    development_enabled=True
                )
            )
            runtime_start_instruction_verifier = (
                DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier(
                    development_enabled=True
                )
            )
            runtime_start_receipt_verifier = resolved_runtime_start_receipt_verifier
            runtime_starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
                development_enabled=True,
                instruction_signature_verifier=runtime_start_instruction_verifier,
            )
        else:
            runtime_start_instruction_signer = (
                UnavailableWorkflowProtectedRuntimeStartInstructionSigner()
            )
            runtime_start_instruction_verifier = (
                DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier()
            )
            runtime_start_receipt_verifier = resolved_runtime_start_receipt_verifier
            runtime_starter = UnavailableWorkflowProtectedRuntimeStarter()
        bind_runtime_start_receipt_verifier = getattr(
            runtime_start_consumption_repository,
            "bind_protected_runtime_start_receipt_signature_verifier",
            None,
        )
        if callable(bind_runtime_start_receipt_verifier):
            bind_runtime_start_receipt_verifier(runtime_start_receipt_verifier)
        resolved_protected_runtime_start_consumption_service = (
            WorkflowProtectedRuntimeStartConsumptionService(
                repository=runtime_start_consumption_repository,
                starter=runtime_starter,
                instruction_signer=runtime_start_instruction_signer,
                instruction_signature_verifier=runtime_start_instruction_verifier,
                receipt_signature_verifier=runtime_start_receipt_verifier,
            )
        )
    else:
        resolved_protected_runtime_start_consumption_service = (
            workflow_protected_runtime_start_consumption_service
        )
    if workflow_protected_runtime_readiness_authorization_service is None:
        runtime_readiness_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_readiness_authorization",
            "get_protected_runtime_readiness_authorization_source",
            "authorize_protected_runtime_readiness",
            "list_protected_runtime_readiness_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_readiness_authorization_repository_methods
        ):
            runtime_readiness_authorization_repository = cast(
                WorkflowProtectedRuntimeReadinessAuthorizationRepository,
                workflow_repository,
            )
        else:
            runtime_readiness_authorization_repository = cast(
                WorkflowProtectedRuntimeReadinessAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeReadinessAuthorizationRepository(),
            )

        development_runtime_readiness_authorization = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_runtime_readiness_lifecycle = (
            UnavailableWorkflowProtectedRuntimeReadinessLifecycleAttestor()
        )
        default_runtime_readiness_lifecycle: WorkflowProtectedRuntimeReadinessLifecycleAttestor = (
            DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor(
                development_enabled=True
            )
            if development_runtime_readiness_authorization
            else unavailable_runtime_readiness_lifecycle
        )
        runtime_readiness_lifecycle_attestor = (
            workflow_protected_runtime_readiness_lifecycle_attestor
            or default_runtime_readiness_lifecycle
        )
        if workflow_protected_runtime_readiness_lifecycle_signature_verifier is not None:
            runtime_readiness_lifecycle_verifier = (
                workflow_protected_runtime_readiness_lifecycle_signature_verifier
            )
        elif callable(
            getattr(
                runtime_readiness_lifecycle_attestor,
                "verify_runtime_readiness_lifecycle_attestation",
                None,
            )
        ):
            runtime_readiness_lifecycle_verifier = cast(
                WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier,
                runtime_readiness_lifecycle_attestor,
            )
        else:
            runtime_readiness_lifecycle_verifier = unavailable_runtime_readiness_lifecycle

        bind_runtime_start_receipt_verifier = getattr(
            runtime_readiness_authorization_repository,
            "bind_protected_runtime_start_receipt_signature_verifier",
            None,
        )
        if callable(bind_runtime_start_receipt_verifier):
            bind_runtime_start_receipt_verifier(resolved_runtime_start_receipt_verifier)
        resolved_protected_runtime_readiness_authorization_service = (
            WorkflowProtectedRuntimeReadinessAuthorizationService(
                authorization_repository=runtime_readiness_authorization_repository,
                lifecycle_attestor=runtime_readiness_lifecycle_attestor,
                lifecycle_signature_verifier=runtime_readiness_lifecycle_verifier,
                start_receipt_signature_verifier=resolved_runtime_start_receipt_verifier,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_readiness_authorization_service = (
            workflow_protected_runtime_readiness_authorization_service
        )
    if workflow_protected_runtime_readiness_consumption_service is None:
        runtime_readiness_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_readiness_consumption_replay",
            "get_protected_runtime_readiness_consumption_source",
            "claim_protected_runtime_readiness_consumption",
            "record_protected_runtime_readiness_consumption_result",
            "list_protected_runtime_readiness_attempts",
            "get_protected_runtime_readiness_results",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in runtime_readiness_consumption_repository_methods
        ):
            runtime_readiness_consumption_repository = cast(
                WorkflowProtectedRuntimeReadinessConsumptionRepository,
                workflow_repository,
            )
        else:
            runtime_readiness_consumption_repository = cast(
                WorkflowProtectedRuntimeReadinessConsumptionRepository,
                _UnavailableWorkflowProtectedRuntimeReadinessConsumptionRepository(),
            )

        development_runtime_readiness_consumption = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        readiness_instruction_signer: WorkflowProtectedRuntimeReadinessInstructionSigner
        readiness_instruction_verifier: (
            WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier
        )
        readiness_receipt_verifier: WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier
        readiness_assessor: WorkflowProtectedRuntimeReadinessAssessor
        if development_runtime_readiness_consumption:
            readiness_instruction_signer = (
                DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner(
                    development_enabled=True
                )
            )
            readiness_instruction_verifier_type = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier  # noqa: E501
            readiness_instruction_verifier = readiness_instruction_verifier_type(
                development_enabled=True
            )
            readiness_receipt_verifier = (
                DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier(
                    development_enabled=True
                )
            )
            readiness_assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
                development_enabled=True,
                instruction_signature_verifier=readiness_instruction_verifier,
            )
        else:
            readiness_instruction_signer = (
                UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner()
            )
            readiness_instruction_verifier = (
                DenyAllWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier()
            )
            readiness_receipt_verifier = (
                DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier()
            )
            readiness_assessor = UnavailableWorkflowProtectedRuntimeReadinessAssessor()
        bind_readiness_receipt_verifier = getattr(
            runtime_readiness_consumption_repository,
            "bind_protected_runtime_readiness_receipt_signature_verifier",
            None,
        )
        if callable(bind_readiness_receipt_verifier):
            bind_readiness_receipt_verifier(readiness_receipt_verifier)
        resolved_protected_runtime_readiness_consumption_service = (
            WorkflowProtectedRuntimeReadinessConsumptionService(
                repository=runtime_readiness_consumption_repository,
                assessor=readiness_assessor,
                instruction_signer=readiness_instruction_signer,
                instruction_signature_verifier=readiness_instruction_verifier,
                receipt_signature_verifier=readiness_receipt_verifier,
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_readiness_consumption_service = (
            workflow_protected_runtime_readiness_consumption_service
        )
    if workflow_protected_runtime_process_creation_authorization_service is None:
        process_creation_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_process_creation_authorization",
            "get_protected_runtime_process_creation_authorization_source",
            "authorize_protected_runtime_process_creation",
            "list_protected_runtime_process_creation_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in process_creation_authorization_repository_methods
        ):
            process_creation_authorization_repository = cast(
                WorkflowProtectedRuntimeProcessCreationAuthorizationRepository,
                workflow_repository,
            )
        else:
            process_creation_authorization_repository = cast(
                WorkflowProtectedRuntimeProcessCreationAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeProcessCreationAuthorizationRepository(),
            )

        development_process_creation_authorization = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_process_creation_lifecycle = (
            UnavailableWorkflowProtectedRuntimeProcessCreationLifecycleAttestor()
        )
        default_process_creation_lifecycle = (
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationLifecycleAttestor(
                development_enabled=True
            )
            if development_process_creation_authorization
            else unavailable_process_creation_lifecycle
        )
        process_creation_lifecycle_attestor = (
            workflow_protected_runtime_process_creation_lifecycle_attestor
            or default_process_creation_lifecycle
        )
        if workflow_protected_runtime_process_creation_lifecycle_signature_verifier is not None:
            process_creation_lifecycle_verifier = (
                workflow_protected_runtime_process_creation_lifecycle_signature_verifier
            )
        elif callable(
            getattr(
                process_creation_lifecycle_attestor,
                "verify_runtime_process_creation_lifecycle_attestation",
                None,
            )
        ):
            process_creation_lifecycle_verifier = cast(
                WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier,
                process_creation_lifecycle_attestor,
            )
        else:
            process_creation_lifecycle_verifier = unavailable_process_creation_lifecycle

        process_creation_readiness_receipt_verifier = (
            DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier(
                development_enabled=True
            )
            if development_process_creation_authorization
            else DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier()
        )
        bind_readiness_receipt_verifier = getattr(
            process_creation_authorization_repository,
            "bind_protected_runtime_readiness_receipt_signature_verifier",
            None,
        )
        if callable(bind_readiness_receipt_verifier):
            bind_readiness_receipt_verifier(process_creation_readiness_receipt_verifier)
        resolved_protected_runtime_process_creation_authorization_service = (
            WorkflowProtectedRuntimeProcessCreationAuthorizationService(
                authorization_repository=process_creation_authorization_repository,
                lifecycle_attestor=process_creation_lifecycle_attestor,
                lifecycle_signature_verifier=process_creation_lifecycle_verifier,
                readiness_receipt_signature_verifier=(process_creation_readiness_receipt_verifier),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_process_creation_authorization_service = (
            workflow_protected_runtime_process_creation_authorization_service
        )
    if workflow_protected_runtime_process_creation_consumption_service is None:
        process_creation_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_process_creation_replay",
            "get_protected_runtime_process_creation_consumption_source",
            "claim_protected_runtime_process_creation",
            "record_protected_runtime_process_creation_result",
            "list_protected_runtime_process_creation_attempts",
            "get_protected_runtime_process_creation_results",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in process_creation_consumption_repository_methods
        ):
            process_creation_consumption_repository = cast(
                WorkflowProtectedRuntimeProcessCreationConsumptionRepository,
                workflow_repository,
            )
        else:
            process_creation_consumption_repository = cast(
                WorkflowProtectedRuntimeProcessCreationConsumptionRepository,
                _UnavailableWorkflowProtectedRuntimeProcessCreationConsumptionRepository(),
            )

        development_process_creation_consumption = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        process_creation_instruction_signer: (
            WorkflowProtectedRuntimeProcessCreationInstructionSigner
        )
        process_creation_instruction_verifier: (
            WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier
        )
        process_creation_receipt_verifier: (
            WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier
        )
        process_creator: WorkflowProtectedRuntimeProcessCreator
        if development_process_creation_consumption:
            process_creation_instruction_signer = (
                DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner(
                    development_enabled=True
                )
            )
            instruction_verifier_type = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier  # noqa: E501
            process_creation_instruction_verifier = instruction_verifier_type(
                development_enabled=True
            )
            receipt_verifier_type = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier  # noqa: E501
            process_creation_receipt_verifier = receipt_verifier_type(development_enabled=True)
            process_creator = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
                development_enabled=True,
                instruction_signature_verifier=process_creation_instruction_verifier,
            )
        else:
            process_creation_instruction_signer = (
                UnavailableWorkflowProtectedRuntimeProcessCreationInstructionSigner()
            )
            process_creation_instruction_verifier = (
                DenyAllWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier()
            )
            process_creation_receipt_verifier = (
                DenyAllWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier()
            )
            process_creator = UnavailableWorkflowProtectedRuntimeProcessCreator()
        bind_process_creation_receipt_verifier = getattr(
            process_creation_consumption_repository,
            "bind_protected_runtime_process_creation_receipt_signature_verifier",
            None,
        )
        if callable(bind_process_creation_receipt_verifier):
            bind_process_creation_receipt_verifier(process_creation_receipt_verifier)
        resolved_protected_runtime_process_creation_consumption_service = (
            WorkflowProtectedRuntimeProcessCreationConsumptionService(
                repository=process_creation_consumption_repository,
                instruction_signer=process_creation_instruction_signer,
                instruction_signature_verifier=process_creation_instruction_verifier,
                receipt_signature_verifier=process_creation_receipt_verifier,
                creator=process_creator,
            )
        )
        resolved_process_creation_consumption_repository = process_creation_consumption_repository
    else:
        resolved_protected_runtime_process_creation_consumption_service = (
            workflow_protected_runtime_process_creation_consumption_service
        )
        resolved_process_creation_consumption_repository = cast(
            WorkflowProtectedRuntimeProcessCreationConsumptionRepository,
            getattr(
                workflow_protected_runtime_process_creation_consumption_service,
                "repository",
                _UnavailableWorkflowProtectedRuntimeProcessCreationConsumptionRepository(),
            ),
        )
    if workflow_protected_runtime_process_scheduling_authorization_service is None:
        process_scheduling_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_process_scheduling_authorization",
            "get_protected_runtime_process_scheduling_authorization_source",
            "authorize_protected_runtime_process_scheduling",
            "list_protected_runtime_process_scheduling_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in process_scheduling_authorization_repository_methods
        ):
            process_scheduling_authorization_repository = cast(
                WorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository,
                workflow_repository,
            )
        else:
            process_scheduling_authorization_repository = cast(
                WorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository(),
            )
        development_process_scheduling_authorization = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_process_scheduling_state_attestor = (
            UnavailableWorkflowProtectedRuntimeProcessSchedulingStateAttestor()
        )
        default_process_scheduling_state_attestor = (
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingStateAttestor(
                development_enabled=True
            )
            if development_process_scheduling_authorization
            else unavailable_process_scheduling_state_attestor
        )
        process_scheduling_state_attestor = (
            workflow_protected_runtime_process_scheduling_state_attestor
            or default_process_scheduling_state_attestor
        )
        process_scheduling_state_signature_verifier = cast(
            WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier,
            workflow_protected_runtime_process_scheduling_state_signature_verifier
            or process_scheduling_state_attestor,
        )
        scheduling_process_creation_receipt_verifier = cast(
            WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
            getattr(
                resolved_protected_runtime_process_creation_consumption_service,
                "_receipt_signature_verifier",
                DenyAllWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(),
            ),
        )
        resolved_protected_runtime_process_scheduling_authorization_service = (
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationService(
                authorization_repository=process_scheduling_authorization_repository,
                process_state_attestor=process_scheduling_state_attestor,
                process_state_signature_verifier=process_scheduling_state_signature_verifier,
                process_creation_receipt_signature_verifier=(
                    scheduling_process_creation_receipt_verifier
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_process_scheduling_authorization_service = (
            workflow_protected_runtime_process_scheduling_authorization_service
        )
    if workflow_protected_runtime_process_scheduling_consumption_service is None:
        process_scheduling_consumption_repository_methods = (
            "get_authoritative_time",
            "lookup_protected_runtime_process_scheduling_replay",
            "get_protected_runtime_process_scheduling_consumption_source",
            "claim_protected_runtime_process_scheduling",
            "record_protected_runtime_process_scheduling_result",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in process_scheduling_consumption_repository_methods
        ):
            process_scheduling_consumption_repository = cast(
                WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository,
                workflow_repository,
            )
        else:
            process_scheduling_consumption_repository = cast(
                WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository,
                _UnavailableWorkflowProtectedRuntimeProcessSchedulingConsumptionRepository(),
            )

        development_process_scheduling_consumption = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        process_scheduling_instruction_signer: (
            WorkflowProtectedRuntimeProcessSchedulingInstructionSigner
        )
        process_scheduling_instruction_verifier: (
            WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier
        )
        process_scheduling_receipt_verifier: (
            WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
        )
        process_scheduler: WorkflowProtectedRuntimeProcessScheduler
        if development_process_scheduling_consumption:
            process_scheduling_instruction_signer = (
                DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner(
                    development_enabled=True
                )
            )
            scheduling_instruction_verifier_type = DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier  # noqa: E501
            process_scheduling_instruction_verifier = scheduling_instruction_verifier_type(
                development_enabled=True
            )
            scheduling_receipt_verifier_type = DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier  # noqa: E501
            process_scheduling_receipt_verifier = scheduling_receipt_verifier_type(
                development_enabled=True
            )
            process_scheduler = DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler(
                development_enabled=True,
                instruction_signature_verifier=process_scheduling_instruction_verifier,
            )
        else:
            process_scheduling_instruction_signer = (
                UnavailableWorkflowProtectedRuntimeProcessSchedulingInstructionSigner()
            )
            process_scheduling_instruction_verifier = (
                DenyAllWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier()
            )
            process_scheduling_receipt_verifier = (
                DenyAllWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier()
            )
            process_scheduler = UnavailableWorkflowProtectedRuntimeProcessScheduler()
        bind_process_scheduling_receipt_verifier = getattr(
            process_scheduling_consumption_repository,
            "bind_protected_runtime_process_scheduling_receipt_signature_verifier",
            None,
        )
        if callable(bind_process_scheduling_receipt_verifier):
            bind_process_scheduling_receipt_verifier(process_scheduling_receipt_verifier)
        resolved_protected_runtime_process_scheduling_consumption_service = (
            WorkflowProtectedRuntimeProcessSchedulingConsumptionService(
                repository=process_scheduling_consumption_repository,
                instruction_signer=process_scheduling_instruction_signer,
                instruction_signature_verifier=process_scheduling_instruction_verifier,
                receipt_signature_verifier=process_scheduling_receipt_verifier,
                scheduler=process_scheduler,
            )
        )
        resolved_process_scheduling_consumption_repository = (
            process_scheduling_consumption_repository
        )
    else:
        resolved_protected_runtime_process_scheduling_consumption_service = (
            workflow_protected_runtime_process_scheduling_consumption_service
        )
        resolved_process_scheduling_consumption_repository = cast(
            WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository,
            getattr(
                workflow_protected_runtime_process_scheduling_consumption_service,
                "repository",
                _UnavailableWorkflowProtectedRuntimeProcessSchedulingConsumptionRepository(),
            ),
        )
    if workflow_protected_runtime_process_resume_authorization_service is None:
        process_resume_authorization_repository_methods = (
            "get_authoritative_time",
            "preflight_protected_runtime_process_resume_authorization",
            "get_protected_runtime_process_resume_authorization_source",
            "authorize_protected_runtime_process_resume",
            "list_protected_runtime_process_resume_authorization_presentations",
        )
        if isinstance(workflow_repository, PostgreSQLWorkflowPlanRepository) and all(
            callable(getattr(workflow_repository, method_name, None))
            for method_name in process_resume_authorization_repository_methods
        ):
            process_resume_authorization_repository = cast(
                WorkflowProtectedRuntimeProcessResumeAuthorizationRepository,
                workflow_repository,
            )
        else:
            process_resume_authorization_repository = cast(
                WorkflowProtectedRuntimeProcessResumeAuthorizationRepository,
                _UnavailableWorkflowProtectedRuntimeProcessResumeAuthorizationRepository(),
            )
        development_process_resume_authorization = (
            resolved_settings.environment == "development"
            and resolved_settings.development_identity_enabled
        )
        unavailable_process_resume_state_attestor = (
            UnavailableWorkflowProtectedRuntimeProcessResumeStateAttestor()
        )
        default_process_resume_state_attestor = (
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessResumeStateAttestor(
                development_enabled=True
            )
            if development_process_resume_authorization
            else unavailable_process_resume_state_attestor
        )
        process_resume_state_attestor = (
            workflow_protected_runtime_process_resume_state_attestor
            or default_process_resume_state_attestor
        )
        process_resume_state_signature_verifier = cast(
            WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier,
            workflow_protected_runtime_process_resume_state_signature_verifier
            or process_resume_state_attestor,
        )
        resume_process_scheduling_receipt_verifier = cast(
            WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
            getattr(
                resolved_protected_runtime_process_scheduling_consumption_service,
                "_receipt_signature_verifier",
                DenyAllWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier(),
            ),
        )
        resolved_protected_runtime_process_resume_authorization_service = (
            WorkflowProtectedRuntimeProcessResumeAuthorizationService(
                authorization_repository=process_resume_authorization_repository,
                process_state_attestor=process_resume_state_attestor,
                process_state_signature_verifier=process_resume_state_signature_verifier,
                process_scheduling_receipt_signature_verifier=(
                    resume_process_scheduling_receipt_verifier
                ),
                audit_sink=resolved_audit_sink,
            )
        )
    else:
        resolved_protected_runtime_process_resume_authorization_service = (
            workflow_protected_runtime_process_resume_authorization_service
        )
    configured_transport_route_selection_heads = (
        _deployment_event_transport_route_selection_heads(
            resolved_settings,
            configured_transport_routes,
        )
        if deployment_event_transport_route_selection_heads is None
        else tuple(deployment_event_transport_route_selection_heads)
    )
    synchronize_transport_route_selection_heads = (
        resolved_settings.environment == "development"
        or deployment_event_transport_route_selection_heads is not None
    )
    selection_head_keys = tuple(
        (
            head.scope.organization_id,
            head.scope.environment_id,
            head.scope.site_id,
            head.route_set_id,
        )
        for head in configured_transport_route_selection_heads
    )
    if len(selection_head_keys) != len(set(selection_head_keys)):
        raise ValueError("deployment transport route selection heads must be unique")
    if any(
        head.scope.environment_id != expected_route_environment
        for head in configured_transport_route_selection_heads
    ):
        raise ValueError(
            "deployment transport route selection head scope does not match environment"
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        route_freshness_repository = (
            resolved_workflow_event_physical_transport_route_freshness_admission_service.repository
        )
        if synchronize_transport_route_selection_heads:
            await route_freshness_repository.synchronize_route_selection_heads(
                configured_transport_route_selection_heads
            )
        if synchronize_transport_credential_assignments:
            assignment_synchronizer = cast(
                DeploymentPhysicalTransportCredentialAssignmentSynchronizer,
                resolved_workflow_transport_credential_assignment_snapshot_service.repository,
            )
            await assignment_synchronizer.synchronize_credential_assignments(
                configured_transport_credential_assignments
            )
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
        app.state.bundled_connector_catalog_service = resolved_bundled_connector_catalog_service
        app.state.bundled_connection_configuration_service = (
            resolved_bundled_connection_configuration_service
        )
        app.state.connector_connection_test_service = resolved_connector_connection_test_service
        app.state.bundled_connector_runtime_state_service = (
            resolved_bundled_connector_runtime_state_service
        )
        app.state.connector_instance_lifecycle_service = (
            resolved_connector_instance_lifecycle_service
        )
        app.state.connector_upgrade_readiness_service = resolved_connector_upgrade_readiness_service
        app.state.connector_upgrade_approval_service = resolved_connector_upgrade_approval_service
        app.state.target_configuration_service = resolved_target_configuration_service
        app.state.credential_assignment_service = resolved_credential_assignment_service
        app.state.configuration_validation_service = resolved_configuration_validation_service
        app.state.capability_enablement_service = resolved_capability_enablement_service
        app.state.runtime_trust_service = resolved_runtime_trust_service
        app.state.secret_brokerage_service = resolved_secret_brokerage_service
        app.state.runtime_activation_service = resolved_runtime_activation_service
        app.state.runtime_deactivation_service = resolved_runtime_deactivation_service
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
        app.state.recommendation_protected_inspection_service = (
            resolved_recommendation_protected_inspection_service
        )
        app.state.recommendation_protected_content_service = (
            resolved_recommendation_protected_content_service
        )
        app.state.recommendation_human_review_finding_service = (
            resolved_recommendation_human_review_finding_service
        )
        app.state.recommendation_finding_presentation_service = (
            resolved_recommendation_finding_presentation_service
        )
        app.state.recommendation_track_review_decision_service = (
            resolved_recommendation_track_review_decision_service
        )
        app.state.recommendation_correction_service = resolved_recommendation_correction_service
        app.state.final_recommendation_disposition_service = (
            resolved_final_recommendation_disposition_service
        )
        app.state.authorization_service = resolved_authorization_service
        app.state.platform_status_service = status_service
        app.state.storage_operations_service = resolved_storage_operations_service
        app.state.inventory_device_service = resolved_inventory_device_service
        app.state.itsm_integration_service = resolved_itsm_integration_service
        app.state.graph_impact_service = resolved_graph_impact_service
        app.state.health_check_service = resolved_health_check_service
        app.state.investigation_service = resolved_investigation_service
        app.state.rca_service = resolved_rca_service
        app.state.recommendation_service = resolved_recommendation_service
        app.state.approval_service = resolved_approval_service
        app.state.report_service = resolved_report_service
        app.state.itsm_handoff_review_service = resolved_itsm_handoff_review_service
        app.state.grounded_answer_service = resolved_grounded_answer_service
        app.state.conversation_service = resolved_conversation_service
        app.state.conversation_target_access_source = resolved_conversation_target_access_source
        app.state.workflow_planning_service = resolved_workflow_planning_service
        app.state.workflow_orchestration_lease_service = (
            resolved_workflow_orchestration_lease_service
        )
        app.state.workflow_orchestration_lease_repository = (
            resolved_workflow_orchestration_lease_service.repository
        )
        app.state.workflow_run_materialization_service = (
            resolved_workflow_run_materialization_service
        )
        app.state.workflow_run_materialization_repository = (
            resolved_workflow_run_materialization_service.repository
        )
        app.state.workflow_attempt_materialization_service = (
            resolved_workflow_attempt_materialization_service
        )
        app.state.workflow_attempt_materialization_repository = (
            resolved_workflow_attempt_materialization_service.repository
        )
        app.state.workflow_dispatch_intent_staging_service = (
            resolved_workflow_dispatch_intent_staging_service
        )
        app.state.workflow_dispatch_intent_staging_repository = (
            resolved_workflow_dispatch_intent_staging_service.repository
        )
        app.state.workflow_outbox_publication_lease_service = (
            resolved_workflow_outbox_publication_lease_service
        )
        app.state.workflow_outbox_publication_lease_repository = (
            resolved_workflow_outbox_publication_lease_service.repository
        )
        app.state.workflow_dispatch_event_envelope_service = (
            resolved_workflow_dispatch_event_envelope_service
        )
        app.state.workflow_dispatch_event_envelope_repository = (
            resolved_workflow_dispatch_event_envelope_service.repository
        )
        app.state.workflow_event_transport_admission_service = (
            resolved_workflow_event_transport_admission_service
        )
        app.state.workflow_event_transport_admission_repository = (
            resolved_workflow_event_transport_admission_service.repository
        )
        app.state.workflow_event_byte_artifact_service = (
            resolved_workflow_event_byte_artifact_service
        )
        app.state.workflow_event_byte_artifact_repository = (
            resolved_workflow_event_byte_artifact_service.repository
        )
        app.state.workflow_event_logical_channel_binding_service = (
            resolved_workflow_event_logical_channel_binding_service
        )
        app.state.workflow_event_logical_channel_binding_repository = (
            resolved_workflow_event_logical_channel_binding_service.repository
        )
        app.state.workflow_transport_profile_snapshot_service = (
            resolved_workflow_transport_profile_snapshot_service
        )
        app.state.workflow_transport_profile_snapshot_repository = (
            resolved_workflow_transport_profile_snapshot_service.repository
        )
        app.state.workflow_transport_profile_source_profiles = configured_transport_profiles
        app.state.workflow_transport_route_snapshot_service = (
            resolved_workflow_transport_route_snapshot_service
        )
        app.state.workflow_transport_route_snapshot_repository = (
            resolved_workflow_transport_route_snapshot_service.repository
        )
        app.state.workflow_transport_credential_assignment_snapshot_service = (
            resolved_workflow_transport_credential_assignment_snapshot_service
        )
        app.state.workflow_transport_credential_assignment_snapshot_repository = (
            resolved_workflow_transport_credential_assignment_snapshot_service.repository
        )
        app.state.workflow_transport_credential_assignment_source_assignments = (
            configured_transport_credential_assignments
        )
        app.state.workflow_event_physical_transport_route_binding_service = (
            resolved_workflow_event_physical_transport_route_binding_service
        )
        app.state.workflow_event_physical_transport_route_binding_repository = (
            resolved_workflow_event_physical_transport_route_binding_service.repository
        )
        credential_assignment_binding_service = (
            resolved_workflow_event_physical_transport_credential_assignment_binding_service
        )
        for binding_state_name, binding_state_value in (
            (
                "workflow_event_physical_transport_credential_assignment_binding_service",
                credential_assignment_binding_service,
            ),
            (
                "workflow_event_physical_transport_credential_assignment_binding_repository",
                credential_assignment_binding_service.repository,
            ),
        ):
            setattr(app.state, binding_state_name, binding_state_value)
        credential_assignment_freshness_service = resolved_credential_assignment_freshness_service
        for freshness_state_name, freshness_state_value in (
            (
                "workflow_event_physical_transport_credential_assignment_freshness_admission_service",
                credential_assignment_freshness_service,
            ),
            (
                "workflow_event_physical_transport_credential_assignment_freshness_admission_repository",
                credential_assignment_freshness_service.repository,
            ),
        ):
            setattr(app.state, freshness_state_name, freshness_state_value)
        app.state.workflow_credential_access_authorization_lease_service = (
            resolved_credential_access_authorization_lease_service
        )
        app.state.workflow_credential_access_authorization_lease_repository = (
            resolved_credential_access_authorization_lease_service.repository
        )
        app.state.workflow_event_physical_transport_route_freshness_admission_service = (
            resolved_workflow_event_physical_transport_route_freshness_admission_service
        )
        app.state.workflow_event_physical_transport_route_freshness_admission_repository = (
            resolved_workflow_event_physical_transport_route_freshness_admission_service.repository
        )
        app.state.workflow_endpoint_resolution_authorization_lease_service = (
            resolved_endpoint_resolution_authorization_lease_service
        )
        app.state.workflow_endpoint_resolution_authorization_lease_repository = (
            resolved_endpoint_resolution_authorization_lease_service.repository
        )
        app.state.workflow_endpoint_materialization_service = (
            resolved_endpoint_materialization_service
        )
        app.state.workflow_endpoint_materialization_repository = (
            resolved_endpoint_materialization_service.repository
        )
        app.state.workflow_credential_materialization_service = (
            resolved_credential_materialization_service
        )
        app.state.workflow_credential_materialization_repository = (
            resolved_credential_materialization_service.repository
        )
        app.state.workflow_target_context_binding_service = resolved_target_context_binding_service
        app.state.workflow_target_context_binding_repository = (
            resolved_target_context_binding_service.repository
        )
        app.state.workflow_target_context_access_authorization_lease_service = (
            resolved_target_context_access_authorization_lease_service
        )
        app.state.workflow_target_context_access_authorization_lease_repository = (
            resolved_target_context_access_authorization_lease_service.repository
        )
        app.state.workflow_target_context_artifact_opening_service = (
            resolved_target_context_artifact_opening_service
        )
        app.state.workflow_target_context_artifact_opening_repository = (
            resolved_target_context_artifact_opening_service.repository
        )
        app.state.workflow_target_context_capsule_consumer_binding_service = (
            resolved_target_context_capsule_consumer_binding_service
        )
        app.state.workflow_target_context_capsule_consumer_binding_repository = (
            resolved_target_context_capsule_consumer_binding_service.repository
        )
        app.state.workflow_target_context_capsule_handoff_authorization_lease_service = (
            resolved_target_context_capsule_handoff_authorization_lease_service
        )
        app.state.workflow_target_context_capsule_handoff_authorization_lease_repository = (
            resolved_target_context_capsule_handoff_authorization_lease_service.repository
        )
        app.state.workflow_target_context_capsule_handoff_service = (
            resolved_target_context_capsule_handoff_service
        )
        app.state.workflow_target_context_capsule_handoff_repository = (
            resolved_target_context_capsule_handoff_service.repository
        )
        app.state.workflow_target_context_capsule_opening_authorization_lease_service = (
            resolved_target_context_capsule_opening_authorization_lease_service
        )
        app.state.workflow_target_context_capsule_opening_authorization_lease_repository = (
            resolved_target_context_capsule_opening_authorization_lease_service.repository
        )
        app.state.workflow_target_context_capsule_opening_service = (
            resolved_target_context_capsule_opening_service
        )
        app.state.workflow_target_context_capsule_opening_repository = (
            resolved_target_context_capsule_opening_service.repository
        )
        app.state.workflow_protected_resident_context_access_authorization_service = (
            resolved_protected_resident_context_access_authorization_service
        )
        app.state.workflow_protected_resident_context_access_authorization_repository = (
            resolved_protected_resident_context_access_authorization_service.repository
        )
        app.state.workflow_protected_resident_context_access_consumption_service = (
            resolved_protected_resident_context_access_consumption_service
        )
        app.state.workflow_protected_resident_context_access_consumption_repository = (
            resolved_protected_resident_context_access_consumption_service.repository
        )
        app.state.workflow_protected_runtime_context_injection_authorization_service = (
            resolved_protected_runtime_context_injection_authorization_service
        )
        app.state.workflow_protected_runtime_context_injection_authorization_repository = (
            resolved_protected_runtime_context_injection_authorization_service.repository
        )
        app.state.workflow_protected_runtime_context_injection_consumption_service = (
            resolved_protected_runtime_context_injection_consumption_service
        )
        app.state.workflow_protected_runtime_context_injection_consumption_repository = (
            resolved_protected_runtime_context_injection_consumption_service.repository
        )
        app.state.workflow_protected_runtime_context_use_authorization_service = (
            resolved_protected_runtime_context_use_authorization_service
        )
        app.state.workflow_protected_runtime_context_use_authorization_repository = (
            resolved_protected_runtime_context_use_authorization_service.repository
        )
        app.state.workflow_protected_runtime_context_use_authorization_consumption_service = (
            resolved_protected_runtime_context_use_authorization_consumption_service
        )
        app.state.workflow_protected_runtime_context_use_authorization_consumption_repository = (
            resolved_protected_runtime_context_use_authorization_consumption_service.repository
        )
        app.state.workflow_protected_runtime_context_use_service = (
            resolved_protected_runtime_context_use_service
        )
        app.state.workflow_protected_runtime_context_use_repository = (
            resolved_protected_runtime_context_use_service.repository
        )
        app.state.workflow_protected_runtime_start_authorization_service = (
            resolved_protected_runtime_start_authorization_service
        )
        app.state.workflow_protected_runtime_start_authorization_repository = (
            resolved_protected_runtime_start_authorization_service.repository
        )
        app.state.workflow_protected_runtime_start_consumption_service = (
            resolved_protected_runtime_start_consumption_service
        )
        app.state.workflow_protected_runtime_start_consumption_repository = (
            resolved_protected_runtime_start_consumption_service.repository
        )
        app.state.workflow_protected_runtime_readiness_authorization_service = (
            resolved_protected_runtime_readiness_authorization_service
        )
        app.state.workflow_protected_runtime_readiness_authorization_repository = (
            resolved_protected_runtime_readiness_authorization_service.repository
        )
        app.state.workflow_protected_runtime_readiness_consumption_service = (
            resolved_protected_runtime_readiness_consumption_service
        )
        app.state.workflow_protected_runtime_readiness_consumption_repository = (
            resolved_protected_runtime_readiness_consumption_service.repository
        )
        app.state.workflow_protected_runtime_process_creation_authorization_service = (
            resolved_protected_runtime_process_creation_authorization_service
        )
        app.state.workflow_protected_runtime_process_creation_authorization_repository = (
            resolved_protected_runtime_process_creation_authorization_service.repository
        )
        app.state.workflow_protected_runtime_process_scheduling_authorization_service = (
            resolved_protected_runtime_process_scheduling_authorization_service
        )
        app.state.workflow_protected_runtime_process_scheduling_authorization_repository = (
            resolved_protected_runtime_process_scheduling_authorization_service.repository
        )
        app.state.workflow_protected_runtime_process_resume_authorization_service = (
            resolved_protected_runtime_process_resume_authorization_service
        )
        app.state.workflow_protected_runtime_process_resume_authorization_repository = (
            resolved_protected_runtime_process_resume_authorization_service.repository
        )
        app.state.workflow_protected_runtime_process_creation_consumption_service = (
            resolved_protected_runtime_process_creation_consumption_service
        )
        app.state.workflow_protected_runtime_process_creation_consumption_repository = (
            resolved_process_creation_consumption_repository
        )
        app.state.workflow_protected_runtime_process_scheduling_consumption_service = (
            resolved_protected_runtime_process_scheduling_consumption_service
        )
        app.state.workflow_protected_runtime_process_scheduling_consumption_repository = (
            resolved_process_scheduling_consumption_repository
        )
        app.state.workflow_transport_route_selection_heads = (
            configured_transport_route_selection_heads
        )
        app.state.workflow_transport_route_source_routes = configured_transport_routes
        app.state.workflow_event_transport_compatibility_admission_service = (
            resolved_workflow_event_transport_compatibility_admission_service
        )
        app.state.workflow_event_transport_compatibility_admission_repository = (
            resolved_workflow_event_transport_compatibility_admission_service.repository
        )
        assert_advisory_only_component_registry(app.state._state)
        yield
        await resolved_workflow_planning_service.close()
        await resolved_conversation_service.close()
        await resolved_recommendation_correction_service.close()
        await resolved_final_recommendation_disposition_service.close()
        await resolved_recommendation_track_review_decision_service.close()
        await resolved_recommendation_finding_presentation_service.close()
        await resolved_recommendation_human_review_finding_service.close()
        await resolved_recommendation_protected_content_service.close()
        await resolved_recommendation_protected_inspection_service.close()
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
        if isinstance(
            connector_connection_test_result_repository,
            PostgreSQLConnectorConnectionTestResultRepository,
        ):
            await connector_connection_test_result_repository.close()
        if isinstance(
            bundled_runtime_state_repository,
            PostgreSQLBundledConnectorRuntimeStateRepository,
        ):
            await bundled_runtime_state_repository.close()
        if isinstance(
            bundled_connection_configuration_repository,
            PostgreSQLBundledConnectionConfigurationRepository,
        ):
            await bundled_connection_configuration_repository.close()
        await resolved_runtime_deactivation_service.close()
        await resolved_runtime_activation_service.close()
        await resolved_secret_brokerage_service.close()
        await resolved_runtime_trust_service.close()
        await resolved_capability_enablement_service.close()
        await resolved_configuration_validation_service.close()
        await resolved_credential_assignment_service.close()
        await resolved_target_configuration_service.close()
        await resolved_connector_upgrade_approval_service.close()
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
        await resolved_inventory_device_service.close()
        await resolved_itsm_integration_service.close()
        await resolved_itsm_handoff_review_service.close()
        await resolved_report_service.close()
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
    app.add_middleware(_WorkflowCredentialAccessAuthorizationNoStoreMiddleware)
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
            "X-Atlas-Audience",
            "X-Atlas-Environment",
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
    app.include_router(inventory_devices.router, prefix="/api/v1")
    app.include_router(itsm_integrations.router, prefix="/api/v1")
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
    app.include_router(conversations.router, prefix="/api/v1")
    app.include_router(workflows.router, prefix="/api/v1")
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
    app.include_router(bundled_connector_catalog.router, prefix="/api/v1")
    app.include_router(connector_connection_tests.router, prefix="/api/v1")
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
    app.include_router(recommendation_protected_inspections.router, prefix="/api/v1")
    app.include_router(recommendation_protected_contents.router, prefix="/api/v1")
    app.include_router(recommendation_human_review_findings.router, prefix="/api/v1")
    app.include_router(recommendation_finding_presentations.router, prefix="/api/v1")
    app.include_router(recommendation_review_decisions.router, prefix="/api/v1")
    app.include_router(recommendation_correction_resubmissions.router, prefix="/api/v1")
    app.include_router(final_recommendation_dispositions.router, prefix="/api/v1")
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
