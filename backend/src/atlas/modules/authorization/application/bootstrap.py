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


def build_development_authorization_service(
    settings: Settings, audit_sink: AuditSink
) -> AuthorizationService:
    permissions = (
        PermissionDefinition(
            permission_id=IDENTITY_SELF_READ,
            description="Read the authenticated subject's own normalized identity context.",
        ),
    )
    role = RoleDefinition(
        role_id=DEVELOPMENT_ROLE_ID,
        version=1,
        permissions=frozenset({IDENTITY_SELF_READ}),
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
        )

    return AuthorizationService(
        permissions=permissions,
        roles=(role,),
        assignments=assignments,
        audit_sink=audit_sink,
    )
