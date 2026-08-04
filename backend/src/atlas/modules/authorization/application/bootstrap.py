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
