from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    AuthorizationRequest,
    CapabilityClass,
    DecisionOutcome,
    PermissionDefinition,
    ResourceScope,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def subject() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.test.operator",
        display_name="Test Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.test.local",
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
        authenticated_at=NOW,
        organization_id="organization.test",
        role_ids=("role.test.viewer",),
    )


def scope(*, resource_id: str = "resource.inventory.one") -> ResourceScope:
    return ResourceScope(
        organization_id="organization.test",
        environment_id="environment.test",
        site_id="site.local",
        domain_id="domain.storage",
        resource_id=resource_id,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


def service(
    audit_sink: CollectingAuditSink,
    *,
    expires_at: datetime | None = None,
) -> AuthorizationService:
    return AuthorizationService(
        permissions=(
            PermissionDefinition(
                permission_id="inventory.read",
                description="Read normalized inventory.",
            ),
        ),
        roles=(
            RoleDefinition(
                role_id="role.test.viewer",
                version=2,
                permissions=frozenset({"inventory.read"}),
            ),
        ),
        assignments=(
            RoleAssignment(
                assignment_id="assignment.test.viewer",
                version=3,
                subject_id="subject.test.operator",
                role_id="role.test.viewer",
                scope=scope(),
                valid_from=NOW - timedelta(hours=1),
                expires_at=expires_at,
            ),
        ),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_exact_permission_role_assignment_and_scope_are_required() -> None:
    audit_sink = CollectingAuditSink()
    decision = await service(audit_sink).evaluate(
        AuthorizationRequest(
            subject=subject(),
            permission_id="inventory.read",
            resource_type="resource.inventory.item",
            scope=scope(),
            correlation_id="cor_authorization_test",
            requested_at=NOW,
        )
    )

    assert decision.outcome is DecisionOutcome.ALLOWED
    assert decision.role_references == ("role.test.viewer:v2",)
    assert decision.assignment_references == ("assignment.test.viewer:v3",)
    assert audit_sink.records[0].event_type == "atlas.authorization.access.allowed"
    assert audit_sink.records[0].correlation_id == "cor_authorization_test"


@pytest.mark.asyncio
async def test_resource_scope_mismatch_is_denied_without_partial_inheritance() -> None:
    audit_sink = CollectingAuditSink()
    decision = await service(audit_sink).evaluate(
        AuthorizationRequest(
            subject=subject(),
            permission_id="inventory.read",
            resource_type="resource.inventory.item",
            scope=scope(resource_id="resource.inventory.two"),
            correlation_id="cor_scope_test",
            requested_at=NOW,
        )
    )

    assert decision.outcome is DecisionOutcome.DENIED
    assert decision.reason_code == "no_matching_assignment"
    assert decision.role_references == ()
    assert decision.assignment_references == ()
    assert audit_sink.records[0].outcome == "denied"


@pytest.mark.asyncio
async def test_expired_assignment_is_denied() -> None:
    audit_sink = CollectingAuditSink()
    decision = await service(audit_sink, expires_at=NOW - timedelta(minutes=1)).evaluate(
        AuthorizationRequest(
            subject=subject(),
            permission_id="inventory.read",
            resource_type="resource.inventory.item",
            scope=scope(),
            correlation_id="cor_expired_test",
            requested_at=NOW,
        )
    )

    assert decision.outcome is DecisionOutcome.DENIED
    assert decision.reason_code == "assignment_inactive"


def test_role_cannot_reference_permission_outside_registry() -> None:
    with pytest.raises(ValueError, match="outside the registry"):
        AuthorizationService(
            permissions=(),
            roles=(
                RoleDefinition(
                    role_id="role.test.invalid",
                    version=1,
                    permissions=frozenset({"inventory.read"}),
                ),
            ),
            assignments=(),
            audit_sink=CollectingAuditSink(),
        )
