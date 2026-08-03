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
STORAGE_OVERVIEW_READ = "storage.overview.read"
AI_GROUNDED_QUERY_CREATE = "ai.grounded-query.create"
GRAPH_STORAGE_IMPACT_READ = "graph.storage-impact.read"
HEALTH_CHECK_OVERVIEW_READ = "health-check.overview.read"
HEALTH_CHECK_RUN_CREATE = "health-check.run.create"
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


def build_development_authorization_service(
    settings: Settings, audit_sink: AuditSink
) -> AuthorizationService:
    permissions = (
        PermissionDefinition(
            permission_id=IDENTITY_SELF_READ,
            description="Read the authenticated subject's own normalized identity context.",
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
    )
    role = RoleDefinition(
        role_id=DEVELOPMENT_ROLE_ID,
        version=1,
        permissions=frozenset(
            {
                IDENTITY_SELF_READ,
                STORAGE_OVERVIEW_READ,
                AI_GROUNDED_QUERY_CREATE,
                GRAPH_STORAGE_IMPACT_READ,
                HEALTH_CHECK_OVERVIEW_READ,
                HEALTH_CHECK_RUN_CREATE,
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
        )

    return AuthorizationService(
        permissions=permissions,
        roles=(role,),
        assignments=assignments,
        audit_sink=audit_sink,
    )
