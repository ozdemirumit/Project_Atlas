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

IDENTITY_SELF_READ = "identity.self.read"
SESSION_SELF_READ = "identity.session.self.read"
SESSION_SELF_REVOKE = "identity.session.self.revoke"
STORAGE_OVERVIEW_READ = "storage.overview.read"
AI_GROUNDED_QUERY_CREATE = "ai.grounded-query.create"
GRAPH_STORAGE_IMPACT_READ = "graph.storage-impact.read"
HEALTH_CHECK_OVERVIEW_READ = "health-check.overview.read"
HEALTH_CHECK_RUN_CREATE = "health-check.run.create"
INVESTIGATION_CREATE = "investigation.create"
RCA_CREATE = "rca.create"
RECOMMENDATION_CREATE = "recommendation.create"
REPORT_CREATE = "report.create"
SECURITY_EXPORT_OVERVIEW_READ = "security-export.overview.read"
SECURITY_EXPORT_TEST_CREATE = "security-export.test.create"
DEVELOPMENT_ROLE_ID = "role.development.operator"


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


def storage_overview_scope(organization_id: str, environment: str) -> ResourceScope:
    return ResourceScope(
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        domain_id="domain.storage",
        resource_id="resource.storage.lab-overview",
        capability_class=CapabilityClass.C1_READ_ONLY,
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


def build_development_authorization_service(
    settings: Settings, audit_sink: AuditSink
) -> AuthorizationService:
    permissions = (
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
    )
    role = RoleDefinition(
        role_id=DEVELOPMENT_ROLE_ID,
        version=1,
        permissions=frozenset(
            {
                IDENTITY_SELF_READ,
                SESSION_SELF_READ,
                SESSION_SELF_REVOKE,
                STORAGE_OVERVIEW_READ,
                AI_GROUNDED_QUERY_CREATE,
                GRAPH_STORAGE_IMPACT_READ,
                HEALTH_CHECK_OVERVIEW_READ,
                HEALTH_CHECK_RUN_CREATE,
                INVESTIGATION_CREATE,
                RCA_CREATE,
                RECOMMENDATION_CREATE,
                REPORT_CREATE,
                SECURITY_EXPORT_OVERVIEW_READ,
                SECURITY_EXPORT_TEST_CREATE,
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
        roles=(role,),
        assignments=assignments,
        audit_sink=audit_sink,
    )
