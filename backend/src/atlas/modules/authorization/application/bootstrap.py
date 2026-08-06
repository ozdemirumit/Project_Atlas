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
AI_GROUNDED_QUERY_CREATE = "ai.grounded-query.create"
GRAPH_STORAGE_IMPACT_READ = "graph.storage-impact.read"
HEALTH_CHECK_OVERVIEW_READ = "health-check.overview.read"
HEALTH_CHECK_RUN_CREATE = "health-check.run.create"
INVESTIGATION_CREATE = "investigation.create"
RCA_CREATE = "rca.create"
RECOMMENDATION_CREATE = "recommendation.create"
APPROVAL_REQUEST_CREATE = "approval.request.create"
APPROVAL_REQUEST_READ = "approval.request.read"
APPROVAL_REQUEST_DECIDE = "approval.request.decide"
REPORT_CREATE = "report.create"
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
CONNECTOR_TARGET_CONFIGURATION_CREATE = "connectors.target-configuration-bindings.create"
CONNECTOR_TARGET_CONFIGURATION_READ = "connectors.target-configuration-bindings.read"
CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE = "connectors.credential-assignments.create"
CONNECTOR_CREDENTIAL_ASSIGNMENT_READ = "connectors.credential-assignments.read"
DEVELOPMENT_ROLE_ID = "role.development.operator"
SECURITY_ADMINISTRATOR_ROLE_ID = "role.security-administrator"
SECURITY_AUDITOR_ROLE_ID = "role.security-auditor"


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


def ai_grounded_query_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.ai",
        resource_id="resource.ai.grounded-query.synthetic",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
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


def report_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.report",
        resource_id="resource.report.storage.synthetic",
        capability_class=CapabilityClass.C0_INFORMATIONAL,
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
            description="Read one immutable minimized connector instance record.",
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
                AI_GROUNDED_QUERY_CREATE,
                GRAPH_STORAGE_IMPACT_READ,
                HEALTH_CHECK_OVERVIEW_READ,
                HEALTH_CHECK_RUN_CREATE,
                INVESTIGATION_CREATE,
                RCA_CREATE,
                RECOMMENDATION_CREATE,
                APPROVAL_REQUEST_CREATE,
                APPROVAL_REQUEST_READ,
                APPROVAL_REQUEST_DECIDE,
                REPORT_CREATE,
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
                CONNECTOR_TARGET_CONFIGURATION_CREATE,
                CONNECTOR_TARGET_CONFIGURATION_READ,
                CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE,
                CONNECTOR_CREDENTIAL_ASSIGNMENT_READ,
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
        ),
        assignments=assignments,
        audit_sink=audit_sink,
    )
