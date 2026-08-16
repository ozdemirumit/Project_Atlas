from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.audit import AuditSink
from atlas.core.config import Settings
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    CapabilityClass,
    PermissionDefinition,
    ResourceScope,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import CredentialGrant

IDENTITY_SELF_READ = "identity.self.read"
SESSION_SELF_READ = "identity.session.self.read"
SESSION_SELF_REVOKE = "identity.session.self.revoke"
API_CREDENTIAL_SELF_CREATE = "identity.api-credential.self.create"
API_CREDENTIAL_SELF_READ = "identity.api-credential.self.read"
API_CREDENTIAL_SELF_REVOKE = "identity.api-credential.self.revoke"
IDENTITY_GOVERNANCE_READ = "identity.governance.read"
SESSION_ADMIN_REVOKE = "identity.session.admin.revoke"
API_CREDENTIAL_ADMIN_REVOKE = "identity.api-credential.admin.revoke"
IDENTITY_SUBJECT_ADMIN_DISABLE = "identity.subject.admin.disable"
WORKLOAD_IDENTITY_GOVERNANCE_READ = "identity.workload.governance.read"
WORKLOAD_IDENTITY_ADMIN_CREATE = "identity.workload.admin.create"
WORKLOAD_IDENTITY_ADMIN_ROTATE = "identity.workload.admin.rotate"
WORKLOAD_IDENTITY_ADMIN_REVOKE = "identity.workload.admin.revoke"
STORAGE_OVERVIEW_READ = "storage.overview.read"
INVENTORY_DEVICE_READ = "inventory.devices.read"
INVENTORY_DEVICE_CREATE = "inventory.devices.create"
INVENTORY_DEVICE_RETIRE = "inventory.devices.retire"
ITSM_INTEGRATION_READ = "itsm.integrations.read"
ITSM_INTEGRATION_CREATE = "itsm.integrations.create"
ITSM_INTEGRATION_RETIRE = "itsm.integrations.retire"
ITSM_SANDBOX_CONFORMANCE_READ = "itsm.integrations.sandbox-conformance.read"
ITSM_SANDBOX_CONFORMANCE_CREATE = "itsm.integrations.sandbox-conformance.create"
ITSM_SANDBOX_ONBOARDING_READ = "itsm.integrations.sandbox-onboarding.read"
AI_GROUNDED_QUERY_CREATE = "ai.grounded-query.create"
CONVERSATION_READ = "conversation.read"
CONVERSATION_CREATE = "conversation.create"
CONVERSATION_TURN_APPEND = "conversation.turn.append"
GRAPH_STORAGE_IMPACT_READ = "graph.storage-impact.read"
HEALTH_CHECK_OVERVIEW_READ = "health-check.overview.read"
HEALTH_CHECK_RUN_CREATE = "health-check.run.create"
WORKFLOW_DEFINITION_READ = "workflow.definitions.read"
WORKFLOW_PLAN_CREATE = "workflow.plans.create"
WORKFLOW_PLAN_CANCEL = "workflow.plans.cancel"
WORKFLOW_PLAN_READ = "workflow.plans.read"
WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_READ = "workflow.transport-compatibility-admissions.read"
WORKFLOW_TRANSPORT_PROFILE_READ = "workflow.transport-profiles.read"
WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_READ = "workflow.transport-route-snapshots.read"
WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_READ = (
    "workflow.transport-credential-assignment-snapshots.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_READ = "workflow.physical-transport-route-bindings.read"
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ = (
    "workflow.physical-transport-credential-assignment-bindings.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND = (
    "workflow.physical-transport-credential-assignment-bindings.bind"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_READ = (
    "workflow.physical-transport-credential-assignment-freshness-admissions.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_READ = (
    "workflow.physical-transport-credential-access-authorization-leases.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_READ = (
    "workflow.physical-transport-credential-materializations.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ = (
    "workflow.physical-transport-target-context-bindings.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_READ = (
    "workflow.physical-transport-target-context-access-authorization-leases.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_READ = (
    "workflow.physical-transport-target-context-artifact-openings.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_CONSUMER_BINDING_READ = (
    "workflow.physical-transport-target-context-capsule-consumer-bindings.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_READ = (
    "workflow.physical-transport-target-context-capsule-handoff-authorization-leases.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_READ = (
    "workflow.physical-transport-target-context-capsule-handoffs.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_READ = (
    "workflow.physical-transport-target-context-capsule-opening-authorization-leases.read"
)
WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_READ = (
    "workflow.protected-resident-context-access-authorizations.read"
)
WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_READ = (
    "workflow.protected-resident-context-access-consumptions.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_READ = (
    "workflow.physical-transport-target-context-capsule-openings.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_READ = (
    "workflow.physical-transport-route-freshness-admissions.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_READ = (
    "workflow.physical-transport-endpoint-resolution-authorization-leases.read"
)
WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_READ = (
    "workflow.physical-transport-endpoint-materializations.read"
)
INVESTIGATION_CREATE = "investigation.create"
RCA_CREATE = "rca.create"
RECOMMENDATION_CREATE = "recommendation.create"
APPROVAL_REQUEST_CREATE = "approval.request.create"
APPROVAL_REQUEST_READ = "approval.request.read"
APPROVAL_REQUEST_DECIDE = "approval.request.decide"
REPORT_CREATE = "report.create"
REPORT_READ = "report.read"
ITSM_HANDOFF_REVIEW_READ = "report.itsm-handoff-review.read"
ITSM_HANDOFF_REVIEW_DECIDE = "report.itsm-handoff-review.decide"
SECURITY_EXPORT_OVERVIEW_READ = "security-export.overview.read"
SECURITY_EXPORT_TEST_CREATE = "security-export.test.create"
AUDIT_READ = "audit.read"
AUDIT_EXPORT = "audit.export"
RELEASE_PREFLIGHT_READ = "platform.release-preflight.read"
DEPLOYMENT_CONFIGURATION_PREVIEW = "platform.deployment-configuration.preview"
BOOTSTRAP_PLAN_READ = "platform.bootstrap-plan.read"
BOOTSTRAP_STATE_READ = "platform.bootstrap-state.read"
BOOTSTRAP_STATE_MANAGE = "platform.bootstrap-state.manage"
BOOTSTRAP_INVALIDATION_PREVIEW = "platform.bootstrap-invalidation.preview"
SUPPORT_BUNDLE_PREVIEW = "support.bundle.preview"
SUPPORT_BUNDLE_EXPORT = "support.bundle.export"
BACKUP_LOGICAL_PREVIEW = "backup.logical.preview"
BACKUP_LOGICAL_CREATE = "backup.logical.create"
BACKUP_LOGICAL_RESTORE_VALIDATE = "backup.logical.restore-validate"
UPGRADE_READINESS_PREVIEW = "platform.upgrade.readiness-preview"
UPGRADE_ROLLBACK_SIMULATE = "platform.upgrade.simulate"
UPGRADE_CHANGE_REVIEW_PREVIEW = "platform.upgrade-change-review.preview"
UPGRADE_CHANGE_REVIEW_CREATE = "platform.upgrade-change-review.create"
UPGRADE_HUMAN_REVIEW_CREATE = "platform.upgrade-change-human-review.create"
UPGRADE_HUMAN_REVIEW_READ = "platform.upgrade-change-human-review.read"
UPGRADE_HUMAN_REVIEW_DECIDE = "platform.upgrade-change-human-review.decide"
UPGRADE_COMPLETION_RECEIPT_CREATE = "platform.upgrade-human-review-receipt.create"
UPGRADE_COMPLETION_RECEIPT_READ = "platform.upgrade-human-review-receipt.read"
MCP_BUILDER_PROJECT_CREATE = "mcp-builder.project.create"
MCP_BUILDER_PROJECT_READ = "mcp-builder.project.read"
MCP_BUILDER_DESIGN_CREATE = "mcp-builder.design.create"
MCP_BUILDER_DESIGN_READ = "mcp-builder.design.read"
MCP_BUILDER_GENERATION_CREATE = "mcp-builder.generation.create"
MCP_BUILDER_GENERATION_READ = "mcp-builder.generation.read"
MCP_BUILDER_VALIDATION_CREATE = "mcp-builder.validation.create"
MCP_BUILDER_VALIDATION_READ = "mcp-builder.validation.read"
MCP_BUILDER_DOMAIN_REVIEW_CREATE = "mcp-builder.domain-review.create"
MCP_BUILDER_DOMAIN_REVIEW_READ = "mcp-builder.domain-review.read"
MCP_BUILDER_SECURITY_REVIEW_CREATE = "mcp-builder.security-review.create"
MCP_BUILDER_SECURITY_REVIEW_READ = "mcp-builder.security-review.read"
MCP_BUILDER_LAB_VALIDATION_CREATE = "mcp-builder.lab-validation.create"
MCP_BUILDER_LAB_VALIDATION_READ = "mcp-builder.lab-validation.read"
MCP_BUILDER_CANDIDATE_HANDOFF_CREATE = "mcp-builder.candidate-handoff.create"
MCP_BUILDER_CANDIDATE_HANDOFF_READ = "mcp-builder.candidate-handoff.read"
MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD = "mcp-builder.candidate-handoff.download"
CONNECTOR_PACKAGE_ACQUIRE = "connectors.packages.acquire"
CONNECTOR_PACKAGE_ACQUISITION_READ = "connectors.package-acquisitions.read"
CONNECTOR_PACKAGE_VALIDATION_CREATE = "connectors.package-validations.create"
CONNECTOR_PACKAGE_VALIDATION_READ = "connectors.package-validations.read"
CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_CREATE = (
    "connectors.package-supply-chain-inventories.create"
)
CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_READ = "connectors.package-supply-chain-inventories.read"
CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_CREATE = "connectors.package-content-policy-scans.create"
CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_READ = "connectors.package-content-policy-scans.read"
CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_CREATE = (
    "connectors.package-schema-semantics-validations.create"
)
CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_READ = (
    "connectors.package-schema-semantics-validations.read"
)
CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_CREATE = (
    "connectors.package-authority-behavior-validations.create"
)
CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_READ = (
    "connectors.package-authority-behavior-validations.read"
)
CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_CREATE = (
    "connectors.package-static-dependency-analyses.create"
)
CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_READ = (
    "connectors.package-static-dependency-analyses.read"
)
CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_CREATE = "connectors.package-vulnerability-analyses.create"
CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_READ = "connectors.package-vulnerability-analyses.read"
CONNECTOR_PACKAGE_MALWARE_ANALYSIS_CREATE = "connectors.package-malware-analyses.create"
CONNECTOR_PACKAGE_MALWARE_ANALYSIS_READ = "connectors.package-malware-analyses.read"
CONNECTOR_PACKAGE_LICENSE_ANALYSIS_CREATE = "connectors.package-license-analyses.create"
CONNECTOR_PACKAGE_LICENSE_ANALYSIS_READ = "connectors.package-license-analyses.read"
CONNECTOR_PACKAGE_CONTRACT_VALIDATION_CREATE = "connectors.package-contract-validations.create"
CONNECTOR_PACKAGE_CONTRACT_VALIDATION_READ = "connectors.package-contract-validations.read"
CONNECTOR_PACKAGE_RUNNER_VALIDATION_CREATE = "connectors.package-runner-validations.create"
CONNECTOR_PACKAGE_RUNNER_VALIDATION_READ = "connectors.package-runner-validations.read"
CONNECTOR_PACKAGE_LAB_SELF_TEST_CREATE = "connectors.package-lab-self-tests.create"
CONNECTOR_PACKAGE_LAB_SELF_TEST_READ = "connectors.package-lab-self-tests.read"
CONNECTOR_PACKAGE_FINAL_VALIDATION_CREATE = "connectors.package-final-validations.create"
CONNECTOR_PACKAGE_FINAL_VALIDATION_READ = "connectors.package-final-validations.read"
CONNECTOR_PACKAGE_APPROVAL_CREATE = "connectors.package-approval-requests.create"
CONNECTOR_PACKAGE_APPROVAL_READ = "connectors.package-approval-requests.read"
CONNECTOR_PACKAGE_APPROVAL_DECIDE = "connectors.package-approval-requests.decide"
CONNECTOR_PUBLISHER_ATTESTATION_CREATE = "connectors.publisher-attestations.create"
CONNECTOR_PUBLISHER_ATTESTATION_READ = "connectors.publisher-attestations.read"
CONNECTOR_PACKAGE_SIGNING_CREATE = "connectors.package-signing-receipts.create"
CONNECTOR_PACKAGE_SIGNING_READ = "connectors.package-signing-receipts.read"
CONNECTOR_REGISTRY_PUBLICATION_CREATE = "connectors.registry-publication-receipts.create"
CONNECTOR_REGISTRY_PUBLICATION_READ = "connectors.registry-publication-receipts.read"
CONNECTOR_PACKAGE_REGISTRATION_CREATE = "connectors.package-registration-records.create"
CONNECTOR_PACKAGE_REGISTRATION_READ = "connectors.package-registration-records.read"
CONNECTOR_PACKAGE_INSTALLATION_CREATE = "connectors.package-installation-receipts.create"
CONNECTOR_PACKAGE_INSTALLATION_READ = "connectors.package-installation-receipts.read"
CONNECTOR_INSTANCE_CREATE = "connectors.instances.create"
CONNECTOR_INSTANCE_READ = "connectors.instances.read"
CONNECTOR_INSTANCE_RETIRE = "connectors.instances.retire"
CONNECTOR_UPGRADE_APPROVAL_CREATE = "connectors.upgrade-approval-requests.create"
CONNECTOR_UPGRADE_APPROVAL_READ = "connectors.upgrade-approval-requests.read"
CONNECTOR_UPGRADE_APPROVAL_DECIDE = "connectors.upgrade-approval-decisions.create"
CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_CREATE = "connectors.upgrade-approval-revalidations.create"
CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_READ = "connectors.upgrade-approval-revalidations.read"
CONNECTOR_UPGRADE_HANDOFF_READINESS_READ = "connectors.upgrade-handoff-readiness.read"
CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_CREATE = "connectors.upgrade-evidence-receipts.create"
CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_VERIFY = "connectors.upgrade-evidence-receipts.verify"
CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_CREATE = (
    "connectors.upgrade-signed-evidence-receipts.create"
)
CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_VERIFY = (
    "connectors.upgrade-signed-evidence-receipts.verify"
)
CONNECTOR_UPGRADE_SIGNING_KEY_TRUST_INVENTORY_READ = (
    "connectors.upgrade-signing-key-trust-inventory.read"
)
CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_CREATE = (
    "connectors.upgrade-signing-provider-conformance-assessments.create"
)
CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_READ = (
    "connectors.upgrade-signing-provider-conformance-assessments.read"
)
CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_READINESS_READ = (
    "connectors.upgrade-signing-provider-onboarding-readiness.read"
)
CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_POLICY_PROVENANCE_DIAGNOSTIC_READ = (
    "connectors.upgrade-signing-provider-onboarding-policy-provenance-diagnostics.read"
)
CONNECTOR_UPGRADE_CHANGE_CONTEXT_CREATE = "connectors.upgrade-change-context-drafts.create"
CONNECTOR_UPGRADE_CHANGE_CONTEXT_READ = "connectors.upgrade-change-context-drafts.read"
CONNECTOR_TARGET_CONFIGURATION_CREATE = "connectors.target-configuration-bindings.create"
CONNECTOR_TARGET_CONFIGURATION_READ = "connectors.target-configuration-bindings.read"
CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE = "connectors.credential-assignments.create"
CONNECTOR_CREDENTIAL_ASSIGNMENT_READ = "connectors.credential-assignments.read"
CONNECTOR_CONFIGURATION_VALIDATION_CREATE = "connectors.configuration-validations.create"
CONNECTOR_CONFIGURATION_VALIDATION_READ = "connectors.configuration-validations.read"
CONNECTOR_CAPABILITY_ENABLEMENT_CREATE = "connectors.capability-enablements.create"
CONNECTOR_CAPABILITY_ENABLEMENT_READ = "connectors.capability-enablements.read"
CONNECTOR_RUNTIME_TRUST_CREATE = "connectors.runtime-trust-grants.create"
CONNECTOR_RUNTIME_TRUST_READ = "connectors.runtime-trust-grants.read"
CONNECTOR_SECRET_BROKERAGE_CREATE = "connectors.secret-brokerage-authorizations.create"
CONNECTOR_SECRET_BROKERAGE_READ = "connectors.secret-brokerage-authorizations.read"
CONNECTOR_RUNTIME_ACTIVATION_CREATE = "connectors.runtime-activations.create"
CONNECTOR_RUNTIME_ACTIVATION_READ = "connectors.runtime-activations.read"
CONNECTOR_TARGET_SESSION_CREATE = "connectors.target-session-verifications.create"
CONNECTOR_TARGET_SESSION_READ = "connectors.target-session-verifications.read"
CONNECTOR_INVOCATION_AUTHORIZATION_CREATE = "connectors.invocation-authorizations.create"
CONNECTOR_INVOCATION_AUTHORIZATION_READ = "connectors.invocation-authorizations.read"
CONNECTOR_BOUNDED_INVOCATION_CREATE = "connectors.bounded-invocations.create"
CONNECTOR_BOUNDED_INVOCATION_READ = "connectors.bounded-invocations.read"
CONNECTOR_INVOCATION_EVIDENCE_CREATE = "connectors.invocation-evidence.create"
CONNECTOR_INVOCATION_EVIDENCE_READ = "connectors.invocation-evidence.read"
KNOWLEDGE_EVIDENCE_DRAFT_CREATE = "knowledge.operational-evidence-drafts.create"
KNOWLEDGE_EVIDENCE_DRAFT_READ = "knowledge.operational-evidence-drafts.read"
KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE = "knowledge.operational-review-requests.create"
KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ = "knowledge.operational-review-requests.read"
KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE = "knowledge.reviewer-assignments.create"
KNOWLEDGE_REVIEWER_ASSIGNMENT_READ = "knowledge.reviewer-assignments.read"
KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE = "knowledge.protected-inspections.leases.create"
KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ = "knowledge.protected-inspections.leases.read"
KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE = "knowledge.protected-content-presentations.create"
KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ = "knowledge.protected-content-presentations.read"
KNOWLEDGE_REVIEW_FINDING_CREATE = "knowledge.review-findings.create"
KNOWLEDGE_REVIEW_FINDING_READ = "knowledge.review-findings.read"
KNOWLEDGE_FINDING_PRESENTATION_CREATE = "knowledge.finding-presentations.create"
KNOWLEDGE_FINDING_PRESENTATION_READ = "knowledge.finding-presentations.read"
KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE = "knowledge.track-review-decisions.create"
KNOWLEDGE_TRACK_REVIEW_DECISION_READ = "knowledge.track-review-decisions.read"
KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE = "knowledge.corrections.create"
KNOWLEDGE_CORRECTION_RESUBMISSION_READ = "knowledge.corrections.read"
KNOWLEDGE_FINAL_RESOLUTION_CREATE = "knowledge.final-resolutions.create"
KNOWLEDGE_FINAL_RESOLUTION_READ = "knowledge.final-resolutions.read"
KNOWLEDGE_PUBLICATION_PREPARATION_CREATE = "knowledge.publication-preparations.create"
KNOWLEDGE_PUBLICATION_PREPARATION_READ = "knowledge.publication-preparations.read"
KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE = "knowledge.source-materializations.create"
KNOWLEDGE_SOURCE_MATERIALIZATION_READ = "knowledge.source-materializations.read"
KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE = "knowledge.deterministic-chunking.create"
KNOWLEDGE_DETERMINISTIC_CHUNKING_READ = "knowledge.deterministic-chunking.read"
KNOWLEDGE_EMBEDDING_GENERATION_CREATE = "knowledge.embedding-generation.create"
KNOWLEDGE_EMBEDDING_GENERATION_READ = "knowledge.embedding-generation.read"
KNOWLEDGE_INDEX_STAGING_CREATE = "knowledge.index-staging.create"
KNOWLEDGE_INDEX_STAGING_READ = "knowledge.index-staging.read"
KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE = "knowledge.retrieval-publication.create"
KNOWLEDGE_RETRIEVAL_PUBLICATION_READ = "knowledge.retrieval-publication.read"
KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE = "knowledge.protected-retrieval.create"
KNOWLEDGE_PROTECTED_RETRIEVAL_READ = "knowledge.protected-retrieval.read"
AI_PROTECTED_MODEL_CONTEXT_CREATE = "ai.protected-model-context.create"
AI_PROTECTED_MODEL_CONTEXT_READ = "ai.protected-model-context.read"
AI_PROTECTED_MODEL_INVOCATION_CREATE = "ai.protected-model-invocation.create"
AI_PROTECTED_MODEL_INVOCATION_READ = "ai.protected-model-invocation.read"
AI_PROTECTED_DRAFT_ADJUDICATION_CREATE = "ai.protected-draft-adjudication.create"
AI_PROTECTED_DRAFT_ADJUDICATION_READ = "ai.protected-draft-adjudication.read"
AI_PROTECTED_ANSWER_PRESENTATION_CREATE = "ai.protected-answer-presentation.create"
AI_PROTECTED_ANSWER_PRESENTATION_READ = "ai.protected-answer-presentation.read"
AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE = "ai.protected-recommendation-candidate.create"
AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ = "ai.protected-recommendation-candidate.read"
AI_PROTECTED_CANDIDATE_IMPACT_CREATE = "ai.protected-candidate-impact.create"
AI_PROTECTED_CANDIDATE_IMPACT_READ = "ai.protected-candidate-impact.read"
AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE = "ai.protected-candidate-risk-recovery.create"
AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ = "ai.protected-candidate-risk-recovery.read"
AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE = "ai.protected-recommendation-adjudication.create"
AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ = "ai.protected-recommendation-adjudication.read"
AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE = "ai.protected-recommendation-presentation.create"
AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ = "ai.protected-recommendation-presentation.read"
RECOMMENDATION_PROMOTION_CREATE = "recommendation.promotion.create"
RECOMMENDATION_PROMOTION_READ = "recommendation.promotion.read"
RECOMMENDATION_READINESS_CREATE = "recommendation.review-readiness.create"
RECOMMENDATION_READINESS_READ = "recommendation.review-readiness.read"
RECOMMENDATION_REVIEW_REQUEST_CREATE = "recommendation.human-review-request.create"
RECOMMENDATION_REVIEW_REQUEST_READ = "recommendation.human-review-request.read"
RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE = "recommendation.reviewer-assignment.create"
RECOMMENDATION_REVIEWER_ASSIGNMENT_READ = "recommendation.reviewer-assignment.read"
RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE = (
    "recommendation.protected-inspection.leases.create"
)
RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ = "recommendation.protected-inspection.leases.read"
RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE = (
    "recommendation.protected-content.presentations.create"
)
RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ = (
    "recommendation.protected-content.presentations.read"
)
RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE = "recommendation.human-review-findings.create"
RECOMMENDATION_HUMAN_REVIEW_FINDING_READ = "recommendation.human-review-findings.read"
RECOMMENDATION_FINDING_PRESENTATION_CREATE = "recommendation.finding-presentations.create"
RECOMMENDATION_FINDING_PRESENTATION_READ = "recommendation.finding-presentations.read"
RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE = "recommendation.track-review-decisions.create"
RECOMMENDATION_TRACK_REVIEW_DECISION_READ = "recommendation.track-review-decisions.read"
RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE = "recommendation.correction-resubmissions.create"
RECOMMENDATION_CORRECTION_RESUBMISSION_READ = "recommendation.correction-resubmissions.read"
RECOMMENDATION_FINAL_DISPOSITION_CREATE = "recommendation.final-dispositions.create"
RECOMMENDATION_FINAL_DISPOSITION_READ = "recommendation.final-dispositions.read"
STORAGE_HEALTH_READ = "storage.health.read"
DEVELOPMENT_ROLE_ID = "role.development.operator"
SECURITY_ADMINISTRATOR_ROLE_ID = "role.security-administrator"
SECURITY_AUDITOR_ROLE_ID = "role.security-auditor"
ITSM_REVIEWER_ROLE_ID = "role.itsm-reviewer"


def current_identity_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.identity",
        resource_id="resource.identity.self",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def session_self_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.identity",
        resource_id="resource.identity.sessions.self",
        capability_class=capability_class,
    )


def api_credential_self_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.identity",
        resource_id="resource.identity.api-credentials.self",
        capability_class=capability_class,
    )


def identity_governance_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.identity",
        resource_id="resource.identity.governance",
        capability_class=capability_class,
    )


def workload_identity_governance_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workload-identity",
        resource_id="resource.identity.workloads",
        capability_class=capability_class,
    )


def identity_governance_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return (
        PermissionDefinition(
            permission_id=IDENTITY_GOVERNANCE_READ,
            description="Read bounded secret-free identity lifecycle metadata in exact scope.",
        ),
        PermissionDefinition(
            permission_id=SESSION_ADMIN_REVOKE,
            description="Administratively revoke one exact foreign browser session.",
        ),
        PermissionDefinition(
            permission_id=API_CREDENTIAL_ADMIN_REVOKE,
            description="Administratively revoke one exact foreign personal API credential.",
        ),
        PermissionDefinition(
            permission_id=IDENTITY_SUBJECT_ADMIN_DISABLE,
            description="Disable one exact enterprise-human identity and revoke its access.",
        ),
    )


def workload_identity_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return (
        PermissionDefinition(
            permission_id=WORKLOAD_IDENTITY_GOVERNANCE_READ,
            description="Read bounded secret-free workload identity lifecycle metadata.",
        ),
        PermissionDefinition(
            permission_id=WORKLOAD_IDENTITY_ADMIN_CREATE,
            description="Create one exact Atlas workload identity and initial credential.",
        ),
        PermissionDefinition(
            permission_id=WORKLOAD_IDENTITY_ADMIN_ROTATE,
            description="Rotate credentials for one exact Atlas workload identity.",
        ),
        PermissionDefinition(
            permission_id=WORKLOAD_IDENTITY_ADMIN_REVOKE,
            description="Revoke one exact Atlas workload credential.",
        ),
    )


def inventory_device_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return (
        PermissionDefinition(
            permission_id=INVENTORY_DEVICE_READ,
            description="Read secret-free infrastructure device registry records.",
        ),
        PermissionDefinition(
            permission_id=INVENTORY_DEVICE_CREATE,
            description=(
                "Register one infrastructure device without credentials or execution authority."
            ),
        ),
        PermissionDefinition(
            permission_id=INVENTORY_DEVICE_RETIRE,
            description="Retire one exact device while preserving its audit history.",
        ),
    )


def itsm_integration_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return (
        PermissionDefinition(
            permission_id=ITSM_INTEGRATION_READ,
            description="Read secret-free ITSM integration readiness profiles.",
        ),
        PermissionDefinition(
            permission_id=ITSM_INTEGRATION_CREATE,
            description="Register one configuration-only ITSM integration profile.",
        ),
        PermissionDefinition(
            permission_id=ITSM_INTEGRATION_RETIRE,
            description="Retire one ITSM integration profile while preserving history.",
        ),
        PermissionDefinition(
            permission_id=ITSM_SANDBOX_CONFORMANCE_READ,
            description="Read minimized ITSM sandbox conformance evidence.",
        ),
        PermissionDefinition(
            permission_id=ITSM_SANDBOX_CONFORMANCE_CREATE,
            description="Run one fixed diagnostic against an exact ITSM sandbox profile.",
        ),
        PermissionDefinition(
            permission_id=ITSM_SANDBOX_ONBOARDING_READ,
            description="Read exact-profile ITSM sandbox adapter onboarding readiness.",
        ),
    )


def security_administrator_role_definition(
    *, include_workload_identity: bool = False
) -> RoleDefinition:
    workload_permissions = (
        frozenset(
            {
                WORKLOAD_IDENTITY_GOVERNANCE_READ,
                WORKLOAD_IDENTITY_ADMIN_CREATE,
                WORKLOAD_IDENTITY_ADMIN_ROTATE,
                WORKLOAD_IDENTITY_ADMIN_REVOKE,
            }
        )
        if include_workload_identity
        else frozenset()
    )
    return RoleDefinition(
        role_id=SECURITY_ADMINISTRATOR_ROLE_ID,
        version=3 if include_workload_identity else 2,
        permissions=(
            frozenset(
                {
                    IDENTITY_GOVERNANCE_READ,
                    SESSION_ADMIN_REVOKE,
                    API_CREDENTIAL_ADMIN_REVOKE,
                    IDENTITY_SUBJECT_ADMIN_DISABLE,
                }
            )
            | workload_permissions
        ),
    )


def storage_overview_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.storage",
        resource_id="resource.storage.lab-overview",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def inventory_device_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.inventory",
        resource_id="resource.inventory.devices",
        capability_class=capability_class,
    )


def itsm_integration_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.itsm",
        resource_id="resource.itsm.integrations",
        capability_class=capability_class,
    )


def release_preflight_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.release-preflight",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def deployment_configuration_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.deployment-configuration",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def bootstrap_plan_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.bootstrap-plan",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def bootstrap_state_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.bootstrap-state",
        capability_class=capability_class,
    )


def bootstrap_invalidation_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.bootstrap-invalidation",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def support_bundle_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.support",
        resource_id="resource.support.bundle",
        capability_class=capability_class,
    )


def logical_backup_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recovery",
        resource_id="resource.backup.logical",
        capability_class=capability_class,
    )


def upgrade_simulation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.upgrade-simulation",
        capability_class=capability_class,
    )


def upgrade_change_review_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.upgrade-change-review",
        capability_class=capability_class,
    )


def upgrade_human_review_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.upgrade-change-human-review",
        capability_class=capability_class,
    )


def upgrade_completion_receipt_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.platform",
        resource_id="resource.platform.upgrade-human-review-receipt",
        capability_class=capability_class,
    )


def mcp_builder_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.mcp-builder",
        resource_id="resource.mcp-builder.projects",
        capability_class=capability_class,
    )


def connector_package_acquisition_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-acquisitions",
        capability_class=capability_class,
    )


def connector_package_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-validations",
        capability_class=capability_class,
    )


def connector_package_supply_chain_inventory_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-supply-chain-inventories",
        capability_class=capability_class,
    )


def connector_package_content_policy_scan_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-content-policy-scans",
        capability_class=capability_class,
    )


def connector_package_schema_semantics_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-schema-semantics-validations",
        capability_class=capability_class,
    )


def connector_package_authority_behavior_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-authority-behavior-validations",
        capability_class=capability_class,
    )


def connector_package_static_dependency_analysis_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-static-dependency-analyses",
        capability_class=capability_class,
    )


def connector_package_vulnerability_analysis_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-vulnerability-analyses",
        capability_class=capability_class,
    )


def connector_package_malware_analysis_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-malware-analyses",
        capability_class=capability_class,
    )


def connector_package_license_analysis_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-license-analyses",
        capability_class=capability_class,
    )


def connector_package_contract_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-contract-validations",
        capability_class=capability_class,
    )


def connector_package_runner_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-runner-validations",
        capability_class=capability_class,
    )


def connector_package_lab_self_test_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-lab-self-tests",
        capability_class=capability_class,
    )


def connector_package_final_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-final-validations",
        capability_class=capability_class,
    )


def connector_package_approval_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-approval-requests",
        capability_class=capability_class,
    )


def connector_publisher_attestation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.publisher-attestations",
        capability_class=capability_class,
    )


def connector_package_signing_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-signing-receipts",
        capability_class=capability_class,
    )


def connector_registry_publication_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.registry-publication-receipts",
        capability_class=capability_class,
    )


def connector_package_registration_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-registration-records",
        capability_class=capability_class,
    )


def connector_package_installation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.package-installation-receipts",
        capability_class=capability_class,
    )


def connector_instance_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.instances",
        capability_class=capability_class,
    )


def connector_target_configuration_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.target-configuration-bindings",
        capability_class=capability_class,
    )


def connector_credential_assignment_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.credential-assignments",
        capability_class=capability_class,
    )


def connector_configuration_validation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.configuration-validations",
        capability_class=capability_class,
    )


def connector_capability_enablement_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.capability-enablements",
        capability_class=capability_class,
    )


def connector_runtime_trust_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.runtime-trust-grants",
        capability_class=capability_class,
    )


def connector_secret_brokerage_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.secret-brokerage-authorizations",
        capability_class=capability_class,
    )


def connector_runtime_activation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.runtime-activations",
        capability_class=capability_class,
    )


def connector_target_session_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.target-session-verifications",
        capability_class=capability_class,
    )


def connector_invocation_authorization_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.invocation-authorizations",
        capability_class=capability_class,
    )


def connector_capability_invocation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.capability-invocation",
        capability_class=capability_class,
    )


def connector_bounded_invocation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.bounded-invocations",
        capability_class=capability_class,
    )


def connector_invocation_evidence_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.connectors",
        resource_id="resource.connector.invocation-evidence",
        capability_class=capability_class,
    )


def operational_evidence_knowledge_draft_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-evidence-drafts",
        capability_class=capability_class,
    )


def operational_knowledge_review_request_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-review-requests",
        capability_class=capability_class,
    )


def operational_knowledge_reviewer_assignment_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-reviewer-assignments",
        capability_class=capability_class,
    )


def operational_knowledge_protected_inspection_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-protected-inspections",
        capability_class=capability_class,
    )


def operational_knowledge_protected_content_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-protected-content",
        capability_class=capability_class,
    )


def operational_knowledge_review_finding_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-review-findings",
        capability_class=capability_class,
    )


def operational_knowledge_finding_presentation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-finding-presentations",
        capability_class=capability_class,
    )


def operational_knowledge_track_review_decision_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-track-review-decisions",
        capability_class=capability_class,
    )


def operational_knowledge_correction_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-corrections",
        capability_class=capability_class,
    )


def operational_knowledge_final_resolution_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-final-resolutions",
        capability_class=capability_class,
    )


def operational_knowledge_publication_preparation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-publication-preparations",
        capability_class=capability_class,
    )


def operational_knowledge_source_materialization_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-source-materializations",
        capability_class=capability_class,
    )


def operational_knowledge_deterministic_chunking_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-deterministic-chunking",
        capability_class=capability_class,
    )


def operational_knowledge_embedding_generation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-embedding-generation",
        capability_class=capability_class,
    )


def operational_knowledge_index_staging_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-index-staging",
        capability_class=capability_class,
    )


def operational_knowledge_retrieval_publication_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-retrieval-publication",
        capability_class=capability_class,
    )


def operational_knowledge_protected_retrieval_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.knowledge",
        resource_id="resource.knowledge.operational-protected-retrieval",
        capability_class=capability_class,
    )


def ai_protected_model_context_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-model-context",
        capability_class=capability_class,
    )


def ai_protected_model_invocation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-model-invocation",
        capability_class=capability_class,
    )


def ai_protected_draft_adjudication_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-draft-adjudication",
        capability_class=capability_class,
    )


def ai_protected_answer_presentation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-answer-presentation",
        capability_class=capability_class,
    )


def ai_protected_recommendation_candidate_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-recommendation-candidate-set",
        capability_class=capability_class,
    )


def ai_protected_candidate_impact_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-candidate-impact-analysis",
        capability_class=capability_class,
    )


def ai_protected_candidate_risk_recovery_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-candidate-risk-recovery-completion",
        capability_class=capability_class,
    )


def ai_protected_recommendation_adjudication_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-recommendation-adjudication",
        capability_class=capability_class,
    )


def ai_protected_recommendation_presentation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.protected-recommendation-presentation",
        capability_class=capability_class,
    )


def recommendation_promotion_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.promotion",
        capability_class=capability_class,
    )


def recommendation_readiness_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.review-readiness",
        capability_class=capability_class,
    )


def recommendation_review_request_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.human-review-request",
        capability_class=capability_class,
    )


def recommendation_reviewer_assignment_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.reviewer-assignment",
        capability_class=capability_class,
    )


def recommendation_protected_inspection_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.protected-inspection",
        capability_class=capability_class,
    )


def recommendation_protected_content_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.protected-content",
        capability_class=capability_class,
    )


def recommendation_human_review_finding_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.human-review-findings",
        capability_class=capability_class,
    )


def recommendation_finding_presentation_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.finding-presentations",
        capability_class=capability_class,
    )


def recommendation_track_review_decision_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.track-review-decisions",
        capability_class=capability_class,
    )


def recommendation_correction_resubmission_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.correction-resubmissions",
        capability_class=capability_class,
    )


def recommendation_final_disposition_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.final-dispositions",
        capability_class=capability_class,
    )


def ai_grounded_query_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.grounded-query.synthetic",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def conversation_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.conversation",
        resource_id="resource.conversation.storage",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def graph_storage_impact_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.graph",
        resource_id="resource.graph.storage-impact.synthetic",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def health_check_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.health-check",
        resource_id="resource.health-check.storage.synthetic",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_scope(
    organization_id: str,
    environment: str,
    capability_class: CapabilityClass,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.plans",
        capability_class=capability_class,
    )


def workflow_transport_profile_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.transport-profile-snapshots",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def workflow_transport_compatibility_admission_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.transport-compatibility-admissions",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def workflow_transport_route_snapshot_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.transport-route-snapshots",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_transport_credential_assignment_snapshot_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.transport-credential-assignment-snapshots",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_route_binding_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-route-bindings",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_credential_assignment_binding_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-credential-assignment-bindings",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_credential_assignment_freshness_admission_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=(
            "resource.workflow.physical-transport-credential-assignment-freshness-admissions"
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_credential_access_authorization_lease_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=("resource.workflow.physical-transport-credential-access-authorization-leases"),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_route_freshness_admission_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-route-freshness-admissions",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_endpoint_resolution_authorization_lease_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=(
            "resource.workflow.physical-transport-endpoint-resolution-authorization-leases"
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_endpoint_materialization_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-endpoint-materializations",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_credential_materialization_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-credential-materializations",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_binding_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-target-context-bindings",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_access_authorization_lease_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=(
            "resource.workflow.physical-transport-target-context-access-authorization-leases"
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_artifact_opening_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id="resource.workflow.physical-transport-target-context-artifact-openings",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_capsule_consumer_binding_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=(
            "resource.workflow.physical-transport-target-context-capsule-consumer-bindings"
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_capsule_handoff_authorization_lease_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=(
            "resource.workflow."
            "physical-transport-target-context-capsule-handoff-authorization-leases"
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_capsule_handoff_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=("resource.workflow.physical-transport-target-context-capsule-handoffs"),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=(
            "resource.workflow."
            "physical-transport-target-context-capsule-opening-authorization-leases"
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def workflow_physical_transport_target_context_capsule_opening_scope(
    organization_id: str,
    environment: str,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.workflow",
        resource_id=("resource.workflow.physical-transport-target-context-capsule-openings"),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def investigation_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.investigation",
        resource_id="resource.investigation.storage.synthetic",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def rca_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.rca",
        resource_id="resource.rca.storage.synthetic",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def recommendation_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.recommendation",
        resource_id="resource.recommendation.storage.synthetic",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


def approval_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.approval",
        resource_id="resource.approval.storage.synthetic",
        capability_class=capability_class,
    )


def report_scope(
    organization_id: str,
    environment: str,
    capability_class: CapabilityClass = CapabilityClass.C0_INFORMATIONAL,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.report",
        resource_id="resource.report.storage.synthetic",
        capability_class=capability_class,
    )


def itsm_handoff_review_scope(
    organization_id: str, environment: str, capability_class: CapabilityClass
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.report",
        resource_id="resource.report.itsm-handoff-review",
        capability_class=capability_class,
    )


def itsm_reviewer_role_definition() -> RoleDefinition:
    return RoleDefinition(
        role_id=ITSM_REVIEWER_ROLE_ID,
        version=1,
        permissions=frozenset({ITSM_HANDOFF_REVIEW_READ, ITSM_HANDOFF_REVIEW_DECIDE}),
    )


def security_export_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.security-export",
        resource_id="resource.security-export.synthetic",
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


def audit_export_scope(
    organization_id: str,
    environment: str,
    capability_class: CapabilityClass,
) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.audit",
        resource_id="resource.audit.enterprise-events",
        capability_class=capability_class,
    )


def audit_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return (
        PermissionDefinition(
            permission_id=AUDIT_READ,
            description="Read a bounded secret-free audit inventory in one exact scope.",
        ),
        PermissionDefinition(
            permission_id=AUDIT_EXPORT,
            description="Retry bounded delivery of exact-scope audit events to an approved export.",
        ),
    )


def security_auditor_role_definition() -> RoleDefinition:
    return RoleDefinition(
        role_id=SECURITY_AUDITOR_ROLE_ID,
        version=1,
        permissions=frozenset({AUDIT_READ, AUDIT_EXPORT}),
    )


def personal_api_grant_scopes(organization_id: str, environment: str) -> dict[str, ResourceScope]:
    return {
        IDENTITY_SELF_READ: current_identity_scope(organization_id, environment),
        STORAGE_OVERVIEW_READ: storage_overview_scope(organization_id, environment),
        GRAPH_STORAGE_IMPACT_READ: graph_storage_impact_scope(organization_id, environment),
        HEALTH_CHECK_OVERVIEW_READ: health_check_scope(organization_id, environment),
        APPROVAL_REQUEST_READ: approval_scope(
            organization_id,
            environment,
            CapabilityClass.C0_INFORMATIONAL,
        ),
    }


def personal_api_grant_catalog(
    organization_id: str, environment: str
) -> dict[str, CredentialGrant]:
    scopes = personal_api_grant_scopes(organization_id, environment)
    return {
        permission_id: CredentialGrant(
            permission_id=permission_id,
            scope_reference=scope.reference,
        )
        for permission_id, scope in scopes.items()
    }


def build_development_authorization_service(
    settings: Settings, audit_sink: AuditSink
) -> AuthorizationService:
    permissions = (
        *identity_governance_permission_definitions(),
        *workload_identity_permission_definitions(),
        *inventory_device_permission_definitions(),
        *itsm_integration_permission_definitions(),
        *audit_permission_definitions(),
        PermissionDefinition(
            permission_id=IDENTITY_SELF_READ,
            description="Read the authenticated subject's own normalized identity context.",
        ),
        PermissionDefinition(
            permission_id=SESSION_SELF_READ,
            description="Read the authenticated subject's bounded session inventory.",
        ),
        PermissionDefinition(
            permission_id=SESSION_SELF_REVOKE,
            description="Revoke one exact session owned by the authenticated subject.",
        ),
        PermissionDefinition(
            permission_id=API_CREDENTIAL_SELF_CREATE,
            description="Issue one bounded personal read-only API credential.",
        ),
        PermissionDefinition(
            permission_id=API_CREDENTIAL_SELF_READ,
            description="Read the authenticated subject's API credential inventory.",
        ),
        PermissionDefinition(
            permission_id=API_CREDENTIAL_SELF_REVOKE,
            description="Revoke one exact API credential owned by the authenticated subject.",
        ),
        PermissionDefinition(
            permission_id=STORAGE_OVERVIEW_READ,
            description="Read the exact synthetic storage operations overview scope.",
        ),
        PermissionDefinition(
            permission_id=AI_GROUNDED_QUERY_CREATE,
            description="Create an evidence-grounded answer in the exact authorized scope.",
        ),
        PermissionDefinition(
            permission_id=CONVERSATION_READ,
            description="Read owned operational conversations in the exact authorized scope.",
        ),
        PermissionDefinition(
            permission_id=CONVERSATION_CREATE,
            description="Create one target-bound operational conversation.",
        ),
        PermissionDefinition(
            permission_id=CONVERSATION_TURN_APPEND,
            description="Append one governed decision-support turn to an owned conversation.",
        ),
        PermissionDefinition(
            permission_id=GRAPH_STORAGE_IMPACT_READ,
            description="Read bounded storage dependency impact in the exact graph scope.",
        ),
        PermissionDefinition(
            permission_id=HEALTH_CHECK_OVERVIEW_READ,
            description="Read governed health-check definitions, schedules, and recent runs.",
        ),
        PermissionDefinition(
            permission_id=HEALTH_CHECK_RUN_CREATE,
            description="Run an exact allowlisted C1 read-only health check.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_DEFINITION_READ,
            description="Read immutable code-owned workflow definitions.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PLAN_CREATE,
            description="Create a durable non-executable workflow run plan.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PLAN_CANCEL,
            description="Cancel an exact-scope non-executable workflow run plan.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PLAN_READ,
            description="Read exact-scope non-executable workflow run plans.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_READ,
            description="Read minimized immutable workflow transport compatibility admissions.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_TRANSPORT_PROFILE_READ,
            description="Read minimized immutable deployment transport profile snapshots.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_READ,
            description="Read minimized immutable deployment transport route snapshots.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_READ,
            description=(
                "Read minimized immutable deployment transport credential-assignment snapshots."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_READ,
            description="Read minimized immutable workflow physical transport route bindings.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ,
            description=(
                "Read minimized immutable workflow physical transport credential-assignment "
                "bindings."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND,
            description=(
                "Bind one exact immutable physical route to one credential-assignment snapshot."
            ),
        ),
        PermissionDefinition(
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_READ
            ),
            description=(
                "Read minimized immutable workflow physical transport credential-assignment "
                "freshness admissions."
            ),
        ),
        PermissionDefinition(
            permission_id=(WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_READ),
            description=(
                "Read minimized immutable workflow physical transport credential-access "
                "authorization leases."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_READ,
            description=(
                "Read minimized immutable workflow physical transport protected credential "
                "materialization outcomes."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ,
            description=(
                "Read minimized immutable workflow physical transport target-context bindings."
            ),
        ),
        PermissionDefinition(
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_READ
            ),
            description=(
                "Read minimized immutable workflow protected transport target-context access "
                "authorization leases."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_READ,
            description=(
                "Read minimized immutable workflow protected transport target-context artifact "
                "opening outcomes."
            ),
        ),
        PermissionDefinition(
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_CONSUMER_BINDING_READ
            ),
            description=(
                "Read minimized immutable workflow protected transport target-context capsule "
                "consumer bindings."
            ),
        ),
        PermissionDefinition(
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_READ
            ),
            description=(
                "Read minimized immutable workflow protected transport target-context capsule "
                "handoff authorization leases."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_READ,
            description=(
                "Read minimized immutable workflow protected transport target-context capsule "
                "handoff outcomes."
            ),
        ),
        PermissionDefinition(
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_READ
            ),
            description=(
                "Read minimized immutable target-context capsule opening authorization leases."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_READ,
            description=(
                "Read minimized immutable protected resident-context access authorizations."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_READ,
            description=(
                "Read minimized immutable protected resident-context access consumption outcomes."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_READ,
            description="Read minimized immutable target-context capsule opening outcomes.",
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_READ,
            description=(
                "Read minimized immutable workflow physical transport route freshness admissions."
            ),
        ),
        PermissionDefinition(
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_READ
            ),
            description=(
                "Read minimized immutable workflow physical transport endpoint resolution "
                "authorization leases."
            ),
        ),
        PermissionDefinition(
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_READ,
            description=(
                "Read minimized immutable workflow physical transport protected endpoint "
                "materialization outcomes."
            ),
        ),
        PermissionDefinition(
            permission_id=INVESTIGATION_CREATE,
            description="Create an evidence-grounded investigation in the exact storage scope.",
        ),
        PermissionDefinition(
            permission_id=RCA_CREATE,
            description=(
                "Create a provisional evidence-grounded RCA case in the exact storage scope."
            ),
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_CREATE,
            description="Create a governed recommendation from an exact authorized RCA case.",
        ),
        PermissionDefinition(
            permission_id=APPROVAL_REQUEST_CREATE,
            description="Create an immutable approval packet from an exact recommendation.",
        ),
        PermissionDefinition(
            permission_id=APPROVAL_REQUEST_READ,
            description="Read an exact-scope immutable approval packet.",
        ),
        PermissionDefinition(
            permission_id=APPROVAL_REQUEST_DECIDE,
            description="Record a separated human decision on an exact approval packet.",
        ),
        PermissionDefinition(
            permission_id=REPORT_CREATE,
            description="Create a governed report and non-dispatching ITSM handoff draft.",
        ),
        PermissionDefinition(
            permission_id=REPORT_READ,
            description="Read an exact-scope immutable governed technical report.",
        ),
        PermissionDefinition(
            permission_id=ITSM_HANDOFF_REVIEW_READ,
            description="Read an exact-scope immutable ITSM handoff human review.",
        ),
        PermissionDefinition(
            permission_id=ITSM_HANDOFF_REVIEW_DECIDE,
            description="Record a separated human decision on an exact ITSM handoff draft.",
        ),
        PermissionDefinition(
            permission_id=SECURITY_EXPORT_OVERVIEW_READ,
            description="Read exact-scope governed Syslog and SIEM export health.",
        ),
        PermissionDefinition(
            permission_id=SECURITY_EXPORT_TEST_CREATE,
            description="Dispatch an explicit synthetic security event over TLS.",
        ),
        PermissionDefinition(
            permission_id=RELEASE_PREFLIGHT_READ,
            description="Read one bounded release and host preflight report without mutation.",
        ),
        PermissionDefinition(
            permission_id=DEPLOYMENT_CONFIGURATION_PREVIEW,
            description="Preview one exact-scope deployment configuration without mutation.",
        ),
        PermissionDefinition(
            permission_id=BOOTSTRAP_PLAN_READ,
            description="Read one exact-input bootstrap plan without executing it.",
        ),
        PermissionDefinition(
            permission_id=BOOTSTRAP_STATE_READ,
            description="Read exact-scope bootstrap checkpoint and lease metadata.",
        ),
        PermissionDefinition(
            permission_id=BOOTSTRAP_STATE_MANAGE,
            description="Coordinate bootstrap metadata without executing a phase.",
        ),
        PermissionDefinition(
            permission_id=BOOTSTRAP_INVALIDATION_PREVIEW,
            description="Preview checkpoint invalidation caused by exact bootstrap input drift.",
        ),
        PermissionDefinition(
            permission_id=SUPPORT_BUNDLE_PREVIEW,
            description="Preview one bounded local support bundle without collecting host files.",
        ),
        PermissionDefinition(
            permission_id=SUPPORT_BUNDLE_EXPORT,
            description="Create one confirmed local support bundle from an exact safe preview.",
        ),
        PermissionDefinition(
            permission_id=BACKUP_LOGICAL_PREVIEW,
            description="Preview one bounded Atlas-owned logical backup.",
        ),
        PermissionDefinition(
            permission_id=BACKUP_LOGICAL_CREATE,
            description="Create one confirmed local logical backup from an exact preview.",
        ),
        PermissionDefinition(
            permission_id=BACKUP_LOGICAL_RESTORE_VALIDATE,
            description="Validate one logical backup in an isolated ephemeral target.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_READINESS_PREVIEW,
            description="Preview exact upgrade readiness without changing active state.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_ROLLBACK_SIMULATE,
            description="Run one confirmed isolated upgrade and rollback simulation.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_CHANGE_REVIEW_PREVIEW,
            description="Preview one exact evidence-bound upgrade change review packet.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_CHANGE_REVIEW_CREATE,
            description="Create one confirmed local upgrade change review packet.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_HUMAN_REVIEW_CREATE,
            description="Create one exact-packet multi-stage human review request.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_HUMAN_REVIEW_READ,
            description="Read one exact-scope upgrade human review request.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_HUMAN_REVIEW_DECIDE,
            description="Record one eligible human decision for an exact review stage.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_COMPLETION_RECEIPT_CREATE,
            description="Create one non-executable receipt for a completed exact human review.",
        ),
        PermissionDefinition(
            permission_id=UPGRADE_COMPLETION_RECEIPT_READ,
            description="Read one exact-scope non-executable human review completion receipt.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_PROJECT_CREATE,
            description="Analyze one approved OpenAPI source in the quarantined MCP Builder.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_PROJECT_READ,
            description="Read one owned secret-free MCP Builder source-analysis project.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_DESIGN_CREATE,
            description="Confirm one exact-source MCP Builder design without generation authority.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_DESIGN_READ,
            description="Read one exact-scope secret-free MCP Builder design checkpoint.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_GENERATION_CREATE,
            description="Create one exact-design quarantined MCP Builder scaffold.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_GENERATION_READ,
            description="Inspect one exact-scope quarantined MCP Builder scaffold.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_VALIDATION_CREATE,
            description="Statically validate one exact quarantined MCP Builder scaffold.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_VALIDATION_READ,
            description="Read one exact-scope MCP Builder static validation report.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_DOMAIN_REVIEW_CREATE,
            description="Record one human domain review for an exact validated scaffold.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_DOMAIN_REVIEW_READ,
            description="Read one exact-scope MCP Builder human domain review.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_SECURITY_REVIEW_CREATE,
            description="Record one independent security review for an accepted domain review.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_SECURITY_REVIEW_READ,
            description="Read one exact-scope MCP Builder independent security review.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_LAB_VALIDATION_CREATE,
            description="Run one exact-scaffold isolated synthetic MCP Builder lab validation.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_LAB_VALIDATION_READ,
            description="Read one exact-scope MCP Builder isolated lab validation.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_CREATE,
            description="Create one unsigned quarantined MCP Builder candidate handoff.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_READ,
            description="Read one exact-scope MCP Builder candidate handoff.",
        ),
        PermissionDefinition(
            permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD,
            description="Download one integrity-verified quarantined candidate archive.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_ACQUIRE,
            description="Acquire one exact Builder candidate into connector quarantine.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_ACQUISITION_READ,
            description="Read one exact-scope immutable connector package acquisition receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_VALIDATION_CREATE,
            description="Validate manifest and schemas for one exact acquired connector package.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_VALIDATION_READ,
            description="Read one exact-scope immutable connector package validation report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_CREATE,
            description="Inventory exact content and dependency declarations for one package.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_READ,
            description="Read one immutable connector package supply-chain inventory.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_CREATE,
            description="Scan one exact package inventory for secrets and prohibited content.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_READ,
            description="Read one immutable connector package content-policy scan.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_CREATE,
            description="Validate configuration and capability schema semantics for one package.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_READ,
            description="Read one immutable connector package schema semantics report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_CREATE,
            description="Compare declared connector authority to bounded implementation behavior.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_READ,
            description="Read one immutable connector package authority behavior report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_CREATE,
            description="Analyze bounded connector source and dependency declaration hygiene.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_READ,
            description="Read one immutable connector package static dependency report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_CREATE,
            description="Analyze represented connector dependencies against trusted advisories.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_READ,
            description="Read one immutable connector package vulnerability report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_MALWARE_ANALYSIS_CREATE,
            description="Analyze exact connector package content against trusted definitions.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_MALWARE_ANALYSIS_READ,
            description="Read one immutable connector package malware report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_LICENSE_ANALYSIS_CREATE,
            description="Analyze represented package licenses against trusted policy.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_LICENSE_ANALYSIS_READ,
            description="Read one immutable connector package license policy report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_CONTRACT_VALIDATION_CREATE,
            description="Validate exact connector package contract consistency statically.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_CONTRACT_VALIDATION_READ,
            description="Read one immutable connector package contract validation report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_RUNNER_VALIDATION_CREATE,
            description="Run exact connector package in the disconnected synthetic runner.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_RUNNER_VALIDATION_READ,
            description="Read one immutable connector package runner validation report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_LAB_SELF_TEST_CREATE,
            description="Run an exact connector package under an approved read-only lab plan.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_LAB_SELF_TEST_READ,
            description="Read one immutable connector package lab self-test report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_FINAL_VALIDATION_CREATE,
            description="Create one exact-lineage connector final-validation report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_FINAL_VALIDATION_READ,
            description="Read one immutable connector package final-validation report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_APPROVAL_CREATE,
            description="Create one exact-final-validation connector approval request.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_APPROVAL_READ,
            description="Read one immutable connector package approval record.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_APPROVAL_DECIDE,
            description="Record one separated human connector package approval decision.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PUBLISHER_ATTESTATION_CREATE,
            description="Independently verify one exact connector publisher claim.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PUBLISHER_ATTESTATION_READ,
            description="Read one immutable connector publisher attestation report.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_SIGNING_CREATE,
            description="Request one policy-governed exact connector package signature.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_SIGNING_READ,
            description="Read one immutable minimized connector package signing receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_REGISTRY_PUBLICATION_CREATE,
            description="Publish one exact signed connector package to the governed registry.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_REGISTRY_PUBLICATION_READ,
            description="Read one immutable minimized connector registry publication receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_REGISTRATION_CREATE,
            description="Register one exact published connector package without installing it.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_REGISTRATION_READ,
            description="Read one immutable minimized connector package registration record.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_INSTALLATION_CREATE,
            description="Install one exact registered connector package without enabling it.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_PACKAGE_INSTALLATION_READ,
            description="Read one immutable minimized connector package installation receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INSTANCE_CREATE,
            description="Create one disabled unconfigured connector instance identity.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INSTANCE_READ,
            description="Read minimized connector instance lifecycle records.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INSTANCE_RETIRE,
            description=(
                "Retire one disabled unconfigured connector instance with history preserved."
            ),
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_APPROVAL_CREATE,
            description="Submit one exact eligible connector upgrade plan for human approval.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_APPROVAL_READ,
            description="Read one minimized connector upgrade approval request.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_APPROVAL_DECIDE,
            description="Record one independent decision for an exact connector upgrade plan.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_CREATE,
            description="Revalidate one approved connector upgrade without issuing a handoff.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_READ,
            description="Read one minimized connector upgrade approval revalidation receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_HANDOFF_READINESS_READ,
            description="Assess connector upgrade handoff readiness without issuing an artifact.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_CREATE,
            description="Create one non-executable connector upgrade evidence receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_VERIFY,
            description="Verify one non-executable connector upgrade evidence receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_CREATE,
            description="Authenticate one non-executable connector upgrade evidence receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_VERIFY,
            description="Verify one signed connector upgrade evidence receipt.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_SIGNING_KEY_TRUST_INVENTORY_READ,
            description="Read scoped connector upgrade signing-key trust metadata.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_CREATE,
            description="Run one bounded connector upgrade signing-provider diagnostic.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_READ,
            description="Read the latest scoped signing-provider conformance evidence.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_READINESS_READ,
            description="Read scoped production signing-provider onboarding readiness.",
        ),
        PermissionDefinition(
            permission_id=(
                CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_POLICY_PROVENANCE_DIAGNOSTIC_READ
            ),
            description="Read scoped signing-provider onboarding-policy provenance diagnostics.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_CHANGE_CONTEXT_CREATE,
            description="Create one connector upgrade ITSM/change-context draft without dispatch.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_UPGRADE_CHANGE_CONTEXT_READ,
            description="Read one minimized connector upgrade change-context draft.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_TARGET_CONFIGURATION_CREATE,
            description="Bind a disabled connector instance to governed target configuration.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_TARGET_CONFIGURATION_READ,
            description="Read one minimized immutable target configuration binding.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE,
            description="Assign one governed credential profile without resolving a secret.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_CREDENTIAL_ASSIGNMENT_READ,
            description="Read one minimized immutable connector credential assignment.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_CONFIGURATION_VALIDATION_CREATE,
            description="Verify one signed bounded connector configuration evidence set.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_CONFIGURATION_VALIDATION_READ,
            description="Read one minimized immutable connector configuration validation.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_CAPABILITY_ENABLEMENT_CREATE,
            description="Enable one exact signed C0/C1 connector capability profile.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_CAPABILITY_ENABLEMENT_READ,
            description="Read one minimized immutable connector capability enablement.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_RUNTIME_TRUST_CREATE,
            description="Grant one exact signed connector runtime boundary trust record.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_RUNTIME_TRUST_READ,
            description="Read one minimized immutable connector runtime trust grant.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_SECRET_BROKERAGE_CREATE,
            description="Authorize exact governed future connector secret brokerage.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_SECRET_BROKERAGE_READ,
            description="Read one minimized immutable secret brokerage authorization.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_RUNTIME_ACTIVATION_CREATE,
            description="Activate one exact governed connector runtime boundary.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_RUNTIME_ACTIVATION_READ,
            description="Read one minimized immutable connector runtime activation.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_TARGET_SESSION_CREATE,
            description="Verify one governed bounded connector target session.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_TARGET_SESSION_READ,
            description="Read one minimized immutable target session verification.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INVOCATION_AUTHORIZATION_CREATE,
            description="Authorize one bounded governed connector capability invocation.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INVOCATION_AUTHORIZATION_READ,
            description="Read one minimized immutable connector invocation authorization.",
        ),
        PermissionDefinition(
            permission_id=STORAGE_HEALTH_READ,
            description="Read governed storage health evidence through a connector capability.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_BOUNDED_INVOCATION_CREATE,
            description="Consume authorization and invoke one bounded connector capability.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_BOUNDED_INVOCATION_READ,
            description="Read one minimized immutable bounded connector invocation.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INVOCATION_EVIDENCE_CREATE,
            description="Persist one governed connector invocation evidence package.",
        ),
        PermissionDefinition(
            permission_id=CONNECTOR_INVOCATION_EVIDENCE_READ,
            description="Read minimized connector invocation evidence metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
            description="Create one governed non-retrievable operational evidence draft.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_EVIDENCE_DRAFT_READ,
            description="Read minimized operational evidence knowledge draft metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
            description="Create one governed operational knowledge review request.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
            description="Read minimized operational knowledge review request metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
            description="Request policy-controlled domain and security reviewer assignment.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
            description="Read minimized operational knowledge reviewer assignment metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE,
            description="Request an exact-assignee protected inspection lease.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
            description="Read minimized protected inspection lease metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE,
            description="Present one bounded exact-assignee operational knowledge snapshot.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
            description="Replay one exact protected snapshot during its active lease.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_REVIEW_FINDING_CREATE,
            description="Record one immutable track-specific operational knowledge finding packet.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_REVIEW_FINDING_READ,
            description="Read minimized operational knowledge finding metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_FINDING_PRESENTATION_CREATE,
            description="Present one exact sealed operational knowledge finding packet.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_FINDING_PRESENTATION_READ,
            description="Replay one exact finding packet during its active inspection lease.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
            description="Record one immutable exact-assignee track review decision.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
            description="Read minimized track review decision metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE,
            description="Create one governed corrected draft and review generation.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
            description="Read minimized correction and resubmission metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_FINAL_RESOLUTION_CREATE,
            description="Record one governed final knowledge resolution.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_FINAL_RESOLUTION_READ,
            description="Read minimized final knowledge resolution metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PUBLICATION_PREPARATION_CREATE,
            description="Create one governed metadata-only publication preparation.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PUBLICATION_PREPARATION_READ,
            description="Read minimized publication preparation metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE,
            description="Create one governed protected source materialization.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
            description="Read minimized protected source materialization metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE,
            description="Create one governed deterministic protected chunk set.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
            description="Read minimized deterministic protected chunk-set metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_EMBEDDING_GENERATION_CREATE,
            description="Create one governed protected knowledge embedding set.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_EMBEDDING_GENERATION_READ,
            description="Read minimized protected knowledge embedding-set metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_INDEX_STAGING_CREATE,
            description="Stage and validate one governed protected knowledge index projection.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_INDEX_STAGING_READ,
            description="Read minimized protected knowledge index-staging metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
            description="Atomically publish one governed protected retrieval index.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
            description="Read minimized protected retrieval-publication metadata.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE,
            description="Run one governed policy-filtered protected knowledge retrieval.",
        ),
        PermissionDefinition(
            permission_id=KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
            description="Read one current authorized protected evidence package.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_MODEL_CONTEXT_CREATE,
            description="Assemble one governed protected model context without model invocation.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_MODEL_CONTEXT_READ,
            description="Read minimized protected model-context assembly metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_MODEL_INVOCATION_CREATE,
            description="Invoke one governed model over an exact protected context.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_MODEL_INVOCATION_READ,
            description="Read minimized protected model-invocation metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
            description="Adjudicate one exact protected model draft without presentation.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_DRAFT_ADJUDICATION_READ,
            description="Read minimized protected draft-adjudication metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_ANSWER_PRESENTATION_CREATE,
            description="Present one eligible protected answer without operational authority.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_ANSWER_PRESENTATION_READ,
            description="Read one exact protected answer presentation.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
            description=(
                "Generate one protected grounded candidate set without recommendation authority."
            ),
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
            description="Read minimized protected recommendation-candidate metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
            description="Enrich one protected candidate set with bounded graph impact context.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_CANDIDATE_IMPACT_READ,
            description="Read minimized protected candidate-impact metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE,
            description=(
                "Complete protected candidate risk, duration, interruption, and recovery evidence."
            ),
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
            description="Read minimized protected candidate risk-recovery metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE,
            description="Adjudicate one exact protected completed recommendation candidate set.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ,
            description="Read minimized protected recommendation adjudication metadata.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE,
            description="Present one exact protected recommendation adjudication safely.",
        ),
        PermissionDefinition(
            permission_id=AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ,
            description="Read a protected inert recommendation presentation.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_PROMOTION_CREATE,
            description="Promote one exact protected presentation into a recommendation draft.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_PROMOTION_READ,
            description="Read a minimized promoted recommendation draft.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_READINESS_CREATE,
            description="Assess one exact recommendation draft for human review readiness.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_READINESS_READ,
            description="Read a minimized recommendation review-readiness assessment.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_REVIEW_REQUEST_CREATE,
            description="Request policy-owned human review for one exact ready recommendation.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_REVIEW_REQUEST_READ,
            description="Read a minimized recommendation human-review request.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
            description="Request policy-controlled recommendation reviewer assignment.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
            description="Read minimized recommendation reviewer assignment metadata.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
            description="Request an exact-assignee recommendation inspection lease.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
            description="Read minimized recommendation inspection lease metadata.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
            description="Present exact-assignee protected recommendation content.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
            description="Read an existing protected recommendation presentation.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
            description="Record exact-assignee recommendation review findings.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
            description="Read minimized recommendation review finding metadata.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_FINDING_PRESENTATION_CREATE,
            description="Present sealed recommendation review findings to the exact assignee.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_FINDING_PRESENTATION_READ,
            description="Read an existing protected recommendation finding presentation.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE,
            description="Record one exact-assignee recommendation track decision.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
            description="Read minimized recommendation track decision metadata.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE,
            description="Create one governed corrected recommendation version.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
            description="Read minimized recommendation correction metadata.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_FINAL_DISPOSITION_CREATE,
            description="Record one governed final recommendation disposition.",
        ),
        PermissionDefinition(
            permission_id=RECOMMENDATION_FINAL_DISPOSITION_READ,
            description="Read minimized final recommendation disposition metadata.",
        ),
    )
    role = RoleDefinition(
        role_id=DEVELOPMENT_ROLE_ID,
        version=1,
        permissions=frozenset(
            {
                IDENTITY_SELF_READ,
                SESSION_SELF_READ,
                SESSION_SELF_REVOKE,
                API_CREDENTIAL_SELF_CREATE,
                API_CREDENTIAL_SELF_READ,
                API_CREDENTIAL_SELF_REVOKE,
                STORAGE_OVERVIEW_READ,
                INVENTORY_DEVICE_READ,
                INVENTORY_DEVICE_CREATE,
                INVENTORY_DEVICE_RETIRE,
                ITSM_INTEGRATION_READ,
                ITSM_INTEGRATION_CREATE,
                ITSM_INTEGRATION_RETIRE,
                ITSM_SANDBOX_CONFORMANCE_READ,
                ITSM_SANDBOX_CONFORMANCE_CREATE,
                ITSM_SANDBOX_ONBOARDING_READ,
                AI_GROUNDED_QUERY_CREATE,
                CONVERSATION_READ,
                CONVERSATION_CREATE,
                CONVERSATION_TURN_APPEND,
                GRAPH_STORAGE_IMPACT_READ,
                HEALTH_CHECK_OVERVIEW_READ,
                HEALTH_CHECK_RUN_CREATE,
                WORKFLOW_DEFINITION_READ,
                WORKFLOW_PLAN_CREATE,
                WORKFLOW_PLAN_CANCEL,
                WORKFLOW_PLAN_READ,
                WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_READ,
                WORKFLOW_TRANSPORT_PROFILE_READ,
                WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_READ,
                WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_CONSUMER_BINDING_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_READ,
                WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_READ,
                WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_READ,
                WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_READ,
                INVESTIGATION_CREATE,
                RCA_CREATE,
                RECOMMENDATION_CREATE,
                APPROVAL_REQUEST_CREATE,
                APPROVAL_REQUEST_READ,
                APPROVAL_REQUEST_DECIDE,
                REPORT_CREATE,
                REPORT_READ,
                ITSM_HANDOFF_REVIEW_READ,
                ITSM_HANDOFF_REVIEW_DECIDE,
                SECURITY_EXPORT_OVERVIEW_READ,
                SECURITY_EXPORT_TEST_CREATE,
                RELEASE_PREFLIGHT_READ,
                DEPLOYMENT_CONFIGURATION_PREVIEW,
                BOOTSTRAP_PLAN_READ,
                BOOTSTRAP_STATE_READ,
                BOOTSTRAP_STATE_MANAGE,
                BOOTSTRAP_INVALIDATION_PREVIEW,
                SUPPORT_BUNDLE_PREVIEW,
                SUPPORT_BUNDLE_EXPORT,
                BACKUP_LOGICAL_PREVIEW,
                BACKUP_LOGICAL_CREATE,
                BACKUP_LOGICAL_RESTORE_VALIDATE,
                UPGRADE_READINESS_PREVIEW,
                UPGRADE_ROLLBACK_SIMULATE,
                UPGRADE_CHANGE_REVIEW_PREVIEW,
                UPGRADE_CHANGE_REVIEW_CREATE,
                UPGRADE_HUMAN_REVIEW_CREATE,
                UPGRADE_HUMAN_REVIEW_READ,
                UPGRADE_HUMAN_REVIEW_DECIDE,
                UPGRADE_COMPLETION_RECEIPT_CREATE,
                UPGRADE_COMPLETION_RECEIPT_READ,
                MCP_BUILDER_PROJECT_CREATE,
                MCP_BUILDER_PROJECT_READ,
                MCP_BUILDER_DESIGN_CREATE,
                MCP_BUILDER_DESIGN_READ,
                MCP_BUILDER_GENERATION_CREATE,
                MCP_BUILDER_GENERATION_READ,
                MCP_BUILDER_VALIDATION_CREATE,
                MCP_BUILDER_VALIDATION_READ,
                MCP_BUILDER_DOMAIN_REVIEW_CREATE,
                MCP_BUILDER_DOMAIN_REVIEW_READ,
                MCP_BUILDER_SECURITY_REVIEW_CREATE,
                MCP_BUILDER_SECURITY_REVIEW_READ,
                MCP_BUILDER_LAB_VALIDATION_CREATE,
                MCP_BUILDER_LAB_VALIDATION_READ,
                MCP_BUILDER_CANDIDATE_HANDOFF_CREATE,
                MCP_BUILDER_CANDIDATE_HANDOFF_READ,
                MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD,
                CONNECTOR_PACKAGE_ACQUIRE,
                CONNECTOR_PACKAGE_ACQUISITION_READ,
                CONNECTOR_PACKAGE_VALIDATION_CREATE,
                CONNECTOR_PACKAGE_VALIDATION_READ,
                CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_CREATE,
                CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_READ,
                CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_CREATE,
                CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_READ,
                CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_CREATE,
                CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_READ,
                CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_CREATE,
                CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_READ,
                CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_CREATE,
                CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_READ,
                CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_CREATE,
                CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_READ,
                CONNECTOR_PACKAGE_MALWARE_ANALYSIS_CREATE,
                CONNECTOR_PACKAGE_MALWARE_ANALYSIS_READ,
                CONNECTOR_PACKAGE_LICENSE_ANALYSIS_CREATE,
                CONNECTOR_PACKAGE_LICENSE_ANALYSIS_READ,
                CONNECTOR_PACKAGE_CONTRACT_VALIDATION_CREATE,
                CONNECTOR_PACKAGE_CONTRACT_VALIDATION_READ,
                CONNECTOR_PACKAGE_RUNNER_VALIDATION_CREATE,
                CONNECTOR_PACKAGE_RUNNER_VALIDATION_READ,
                CONNECTOR_PACKAGE_LAB_SELF_TEST_CREATE,
                CONNECTOR_PACKAGE_LAB_SELF_TEST_READ,
                CONNECTOR_PACKAGE_FINAL_VALIDATION_CREATE,
                CONNECTOR_PACKAGE_FINAL_VALIDATION_READ,
                CONNECTOR_PACKAGE_APPROVAL_CREATE,
                CONNECTOR_PACKAGE_APPROVAL_READ,
                CONNECTOR_PACKAGE_APPROVAL_DECIDE,
                CONNECTOR_PUBLISHER_ATTESTATION_CREATE,
                CONNECTOR_PUBLISHER_ATTESTATION_READ,
                CONNECTOR_PACKAGE_SIGNING_CREATE,
                CONNECTOR_PACKAGE_SIGNING_READ,
                CONNECTOR_REGISTRY_PUBLICATION_CREATE,
                CONNECTOR_REGISTRY_PUBLICATION_READ,
                CONNECTOR_PACKAGE_REGISTRATION_CREATE,
                CONNECTOR_PACKAGE_REGISTRATION_READ,
                CONNECTOR_PACKAGE_INSTALLATION_CREATE,
                CONNECTOR_PACKAGE_INSTALLATION_READ,
                CONNECTOR_INSTANCE_CREATE,
                CONNECTOR_INSTANCE_READ,
                CONNECTOR_INSTANCE_RETIRE,
                CONNECTOR_UPGRADE_APPROVAL_CREATE,
                CONNECTOR_UPGRADE_APPROVAL_READ,
                CONNECTOR_UPGRADE_APPROVAL_DECIDE,
                CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_CREATE,
                CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_READ,
                CONNECTOR_UPGRADE_HANDOFF_READINESS_READ,
                CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_CREATE,
                CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_VERIFY,
                CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_CREATE,
                CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_VERIFY,
                CONNECTOR_UPGRADE_SIGNING_KEY_TRUST_INVENTORY_READ,
                CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_CREATE,
                CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_READ,
                CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_READINESS_READ,
                CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_POLICY_PROVENANCE_DIAGNOSTIC_READ,
                CONNECTOR_UPGRADE_CHANGE_CONTEXT_CREATE,
                CONNECTOR_UPGRADE_CHANGE_CONTEXT_READ,
                CONNECTOR_TARGET_CONFIGURATION_CREATE,
                CONNECTOR_TARGET_CONFIGURATION_READ,
                CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE,
                CONNECTOR_CREDENTIAL_ASSIGNMENT_READ,
                CONNECTOR_CONFIGURATION_VALIDATION_CREATE,
                CONNECTOR_CONFIGURATION_VALIDATION_READ,
                CONNECTOR_CAPABILITY_ENABLEMENT_CREATE,
                CONNECTOR_CAPABILITY_ENABLEMENT_READ,
                CONNECTOR_RUNTIME_TRUST_CREATE,
                CONNECTOR_RUNTIME_TRUST_READ,
                CONNECTOR_SECRET_BROKERAGE_CREATE,
                CONNECTOR_SECRET_BROKERAGE_READ,
                CONNECTOR_RUNTIME_ACTIVATION_CREATE,
                CONNECTOR_RUNTIME_ACTIVATION_READ,
                CONNECTOR_TARGET_SESSION_CREATE,
                CONNECTOR_TARGET_SESSION_READ,
                CONNECTOR_INVOCATION_AUTHORIZATION_CREATE,
                CONNECTOR_INVOCATION_AUTHORIZATION_READ,
                STORAGE_HEALTH_READ,
                CONNECTOR_BOUNDED_INVOCATION_CREATE,
                CONNECTOR_BOUNDED_INVOCATION_READ,
                CONNECTOR_INVOCATION_EVIDENCE_CREATE,
                CONNECTOR_INVOCATION_EVIDENCE_READ,
                KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
                KNOWLEDGE_EVIDENCE_DRAFT_READ,
                KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
                KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
                KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
                KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
                KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE,
                KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
                KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE,
                KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
                KNOWLEDGE_REVIEW_FINDING_CREATE,
                KNOWLEDGE_REVIEW_FINDING_READ,
                KNOWLEDGE_FINDING_PRESENTATION_CREATE,
                KNOWLEDGE_FINDING_PRESENTATION_READ,
                KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
                KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
                KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE,
                KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
                KNOWLEDGE_FINAL_RESOLUTION_CREATE,
                KNOWLEDGE_FINAL_RESOLUTION_READ,
                KNOWLEDGE_PUBLICATION_PREPARATION_CREATE,
                KNOWLEDGE_PUBLICATION_PREPARATION_READ,
                KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE,
                KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
                KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE,
                KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
                KNOWLEDGE_EMBEDDING_GENERATION_CREATE,
                KNOWLEDGE_EMBEDDING_GENERATION_READ,
                KNOWLEDGE_INDEX_STAGING_CREATE,
                KNOWLEDGE_INDEX_STAGING_READ,
                KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
                KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
                KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE,
                KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
                AI_PROTECTED_MODEL_CONTEXT_CREATE,
                AI_PROTECTED_MODEL_CONTEXT_READ,
                AI_PROTECTED_MODEL_INVOCATION_CREATE,
                AI_PROTECTED_MODEL_INVOCATION_READ,
                AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
                AI_PROTECTED_DRAFT_ADJUDICATION_READ,
                AI_PROTECTED_ANSWER_PRESENTATION_CREATE,
                AI_PROTECTED_ANSWER_PRESENTATION_READ,
                AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
                AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
                AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
                AI_PROTECTED_CANDIDATE_IMPACT_READ,
                AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE,
                AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
                AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE,
                AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ,
                AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE,
                AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ,
                RECOMMENDATION_PROMOTION_CREATE,
                RECOMMENDATION_PROMOTION_READ,
                RECOMMENDATION_READINESS_CREATE,
                RECOMMENDATION_READINESS_READ,
                RECOMMENDATION_REVIEW_REQUEST_CREATE,
                RECOMMENDATION_REVIEW_REQUEST_READ,
                RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
                RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
                RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
                RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
                RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
                RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
                RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
                RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
                RECOMMENDATION_FINDING_PRESENTATION_CREATE,
                RECOMMENDATION_FINDING_PRESENTATION_READ,
                RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE,
                RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
                RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE,
                RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
                RECOMMENDATION_FINAL_DISPOSITION_CREATE,
                RECOMMENDATION_FINAL_DISPOSITION_READ,
            }
        ),
    )
    assignments: tuple[RoleAssignment, ...] = ()

    if (
        settings.development_identity_enabled
        and DEVELOPMENT_ROLE_ID in settings.development_role_ids
    ):
        assignments = (
            RoleAssignment(
                assignment_id="assignment.development.operator",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=current_identity_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.session-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=session_self_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C0_INFORMATIONAL,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.session-revoke",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=session_self_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.api-credential-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=api_credential_self_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C0_INFORMATIONAL,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.api-credential-governance",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=api_credential_self_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.storage-overview",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=storage_overview_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.inventory-device-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=inventory_device_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C0_INFORMATIONAL,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.inventory-device-manage",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=inventory_device_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.itsm-integration-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=itsm_integration_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.itsm-integration-manage",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=itsm_integration_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.release-preflight",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=release_preflight_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.deployment-configuration",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=deployment_configuration_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.bootstrap-plan",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=bootstrap_plan_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.bootstrap-state-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=bootstrap_state_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C0_INFORMATIONAL,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.bootstrap-state-manage",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=bootstrap_state_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.bootstrap-invalidation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=bootstrap_invalidation_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.support-bundle-preview",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=support_bundle_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.support-bundle-export",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=support_bundle_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.logical-backup-preview",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=logical_backup_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.logical-backup-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=logical_backup_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.restore-validation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=logical_backup_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-readiness",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_simulation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-simulation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_simulation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-change-review-preview",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_change_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-change-review-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_change_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-human-review-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_human_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-human-review-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_human_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-human-review-decide",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_human_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-completion-receipt-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_completion_receipt_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.upgrade-completion-receipt-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=upgrade_completion_receipt_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.mcp-builder-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=mcp_builder_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.mcp-builder-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=mcp_builder_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-acquire",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_acquisition_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-acquisition-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_acquisition_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-validation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-validation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-supply-chain-inventory-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_supply_chain_inventory_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-supply-chain-inventory-read"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_supply_chain_inventory_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-content-policy-scan-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_content_policy_scan_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-content-policy-scan-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_content_policy_scan_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-schema-semantics-validation-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_schema_semantics_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-schema-semantics-validation-read"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_schema_semantics_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-authority-behavior-validation-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_authority_behavior_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-authority-behavior-validation-read"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_authority_behavior_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-static-dependency-analysis-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_static_dependency_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-static-dependency-analysis-read"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_static_dependency_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-vulnerability-analysis-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_vulnerability_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.connector-package-vulnerability-analysis-read"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_vulnerability_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-malware-analysis-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_malware_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-malware-analysis-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_malware_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-license-analysis-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_license_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-license-analysis-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_license_analysis_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-contract-validation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_contract_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-contract-validation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_contract_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-runner-validation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_runner_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-runner-validation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_runner_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-lab-self-test-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_lab_self_test_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-lab-self-test-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_lab_self_test_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-final-validation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_final_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-final-validation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_final_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-approval-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_approval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-approval-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_approval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-approval-decide",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_approval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-publisher-attestation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_publisher_attestation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-publisher-attestation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_publisher_attestation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-signing-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_signing_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-signing-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_signing_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-registry-publication-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_registry_publication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-registry-publication-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_registry_publication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-registration-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_registration_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-registration-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_registration_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-installation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_installation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-package-installation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_package_installation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-instance-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_instance_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-instance-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_instance_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-upgrade-evidence-receipt",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_instance_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-target-configuration-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_target_configuration_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-target-configuration-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_target_configuration_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-credential-assignment-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_credential_assignment_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-credential-assignment-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_credential_assignment_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-configuration-validation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_configuration_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-configuration-validation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_configuration_validation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-capability-enablement-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_capability_enablement_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-capability-enablement-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_capability_enablement_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-runtime-trust-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_runtime_trust_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-runtime-trust-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_runtime_trust_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-secret-brokerage-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_secret_brokerage_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-secret-brokerage-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_secret_brokerage_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-runtime-activation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_runtime_activation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-runtime-activation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_runtime_activation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-target-session-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_target_session_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-target-session-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_target_session_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=("assignment.development.connector-invocation-authorization-create"),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_invocation_authorization_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=("assignment.development.connector-invocation-authorization-read"),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_invocation_authorization_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.storage-health-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_capability_invocation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-bounded-invocation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_bounded_invocation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-bounded-invocation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_bounded_invocation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-invocation-evidence-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_invocation_evidence_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.connector-invocation-evidence-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=connector_invocation_evidence_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.operational-evidence-knowledge-draft-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_evidence_knowledge_draft_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.operational-evidence-knowledge-draft-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_evidence_knowledge_draft_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.operational-knowledge-review-request-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_review_request_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.operational-knowledge-review-request-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_review_request_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-reviewer-assignment-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_reviewer_assignment_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-reviewer-assignment-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_reviewer_assignment_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-protected-inspection-lease-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_protected_inspection_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-protected-inspection-lease-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_protected_inspection_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-protected-content-presentation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_protected_content_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-review-finding",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_review_finding_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-finding-presentation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_finding_presentation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-track-review-decision",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_track_review_decision_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-correction-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_correction_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-correction-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_correction_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-final-resolution-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_final_resolution_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-final-resolution-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_final_resolution_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-publication-preparation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_publication_preparation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-publication-preparation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_publication_preparation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-source-materialization-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_source_materialization_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-source-materialization-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_source_materialization_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-deterministic-chunking-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_deterministic_chunking_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-deterministic-chunking-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_deterministic_chunking_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-embedding-generation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_embedding_generation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-embedding-generation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_embedding_generation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-index-staging-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_index_staging_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-index-staging-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_index_staging_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-retrieval-publication-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_retrieval_publication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-retrieval-publication-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_retrieval_publication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-protected-retrieval-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_protected_retrieval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.knowledge-protected-retrieval-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=operational_knowledge_protected_retrieval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-model-context-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_model_context_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-model-context-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_model_context_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-model-invocation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_model_invocation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-model-invocation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_model_invocation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-draft-adjudication-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_draft_adjudication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-draft-adjudication-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_draft_adjudication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-answer-presentation-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_answer_presentation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-answer-presentation-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_answer_presentation_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.ai-protected-recommendation-candidate-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_recommendation_candidate_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=("assignment.development.ai-protected-recommendation-candidate-read"),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_recommendation_candidate_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-candidate-impact-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_candidate_impact_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-protected-candidate-impact-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_candidate_impact_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.ai-protected-candidate-risk-recovery-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_candidate_risk_recovery_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=("assignment.development.ai-protected-candidate-risk-recovery-read"),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_candidate_risk_recovery_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.ai-protected-recommendation-adjudication-create"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_recommendation_adjudication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.ai-protected-recommendation-adjudication-read"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_protected_recommendation_adjudication_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.mcp-builder-design-create",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=mcp_builder_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.mcp-builder-design-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=mcp_builder_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.ai-grounded-query",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=ai_grounded_query_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.conversation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=conversation_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.graph-storage-impact",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=graph_storage_impact_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.health-check",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=health_check_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.workflow-definitions",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C0_INFORMATIONAL,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.workflow-plans",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.workflow-transport-profiles",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_transport_profile_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.workflow-transport-compatibility-admissions",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_transport_compatibility_admission_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.workflow-transport-route-snapshots",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_transport_route_snapshot_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.workflow-transport-credential-assignment-snapshots"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_transport_credential_assignment_snapshot_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=("assignment.development.workflow-physical-transport-route-bindings"),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_route_binding_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-credential-assignment-bindings"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_credential_assignment_binding_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-capsule-handoffs"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_target_context_capsule_handoff_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-capsule-handoff-"
                    "authorization-leases"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=(
                    workflow_physical_transport_target_context_capsule_handoff_authorization_lease_scope(
                        settings.development_organization_id,
                        settings.environment,
                    )
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-capsule-opening-"
                    "authorization-leases"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=(
                    workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope(
                        settings.development_organization_id,
                        settings.environment,
                    )
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-capsule-openings"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_target_context_capsule_opening_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-artifact-openings"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_target_context_artifact_opening_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-capsule-consumer-bindings"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_target_context_capsule_consumer_binding_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-credential-assignment-freshness-admissions"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=(
                    workflow_physical_transport_credential_assignment_freshness_admission_scope(
                        settings.development_organization_id,
                        settings.environment,
                    )
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-credential-access-authorization-leases"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=(
                    workflow_physical_transport_credential_access_authorization_lease_scope(
                        settings.development_organization_id,
                        settings.environment,
                    )
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.workflow-physical-transport-route-freshness-admissions"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_route_freshness_admission_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-endpoint-resolution-authorization-leases"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=(
                    workflow_physical_transport_endpoint_resolution_authorization_lease_scope(
                        settings.development_organization_id,
                        settings.environment,
                    )
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.workflow-physical-transport-credential-materializations"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_credential_materialization_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.workflow-physical-transport-target-context-bindings"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_target_context_binding_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development."
                    "workflow-physical-transport-target-context-access-authorization-leases"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=(
                    workflow_physical_transport_target_context_access_authorization_lease_scope(
                        settings.development_organization_id,
                        settings.environment,
                    )
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id=(
                    "assignment.development.workflow-physical-transport-endpoint-materializations"
                ),
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=workflow_physical_transport_endpoint_materialization_scope(
                    settings.development_organization_id,
                    settings.environment,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.investigation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=investigation_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.rca",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=rca_scope(settings.development_organization_id, settings.environment),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.recommendation",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=recommendation_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.approval-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=approval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C0_INFORMATIONAL,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.approval-governance",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=approval_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.report",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=report_scope(settings.development_organization_id, settings.environment),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.report-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=report_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.itsm-handoff-review-read",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=itsm_handoff_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.itsm-handoff-review-decide",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=itsm_handoff_review_scope(
                    settings.development_organization_id,
                    settings.environment,
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
            RoleAssignment(
                assignment_id="assignment.development.security-export",
                version=1,
                subject_id=settings.development_subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=security_export_scope(
                    settings.development_organization_id, settings.environment
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
        )

    return AuthorizationService(
        permissions=permissions,
        roles=(
            role,
            security_administrator_role_definition(include_workload_identity=True),
            security_auditor_role_definition(),
            itsm_reviewer_role_definition(),
        ),
        assignments=assignments,
        audit_sink=audit_sink,
    )
