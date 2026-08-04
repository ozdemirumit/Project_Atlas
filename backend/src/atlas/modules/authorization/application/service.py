from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.domain.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    DecisionOutcome,
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import CredentialGrant


class AuthorizationService:
    def __init__(
        self,
        *,
        permissions: Sequence[PermissionDefinition],
        roles: Sequence[RoleDefinition],
        assignments: Sequence[RoleAssignment],
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._permissions = {item.permission_id: item for item in permissions}
        self._roles = {item.role_id: item for item in roles}
        self._assignments = tuple(assignments)
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

        if len(self._permissions) != len(permissions):
            raise ValueError("permission identifiers must be unique")
        if len(self._roles) != len(roles):
            raise ValueError("role identifiers must be unique")
        unknown_permissions = {
            permission
            for role in roles
            for permission in role.permissions
            if permission not in self._permissions
        }
        if unknown_permissions:
            raise ValueError("roles contain permissions outside the registry")
        if any(assignment.role_id not in self._roles for assignment in assignments):
            raise ValueError("assignments contain roles outside the registry")

    async def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        decided_at = self._clock()
        outcome = DecisionOutcome.DENIED
        reason_code = "no_matching_assignment"
        matched_roles: list[RoleDefinition] = []
        matched_assignments: list[RoleAssignment] = []

        if request.permission_id not in self._permissions:
            reason_code = "permission_not_registered"
        elif request.subject.organization_id != request.scope.organization_id:
            reason_code = "organization_scope_mismatch"
        elif (
            request.subject.credential_grants is not None
            and CredentialGrant(
                permission_id=request.permission_id,
                scope_reference=request.scope.reference,
            )
            not in request.subject.credential_grants
        ):
            reason_code = "credential_scope_denied"
        else:
            scoped_assignments = [
                assignment
                for assignment in self._assignments
                if assignment.subject_id == request.subject.subject_id
                and assignment.role_id in request.subject.role_ids
                and assignment.scope == request.scope
            ]
            if scoped_assignments and not any(
                assignment.is_active(decided_at) for assignment in scoped_assignments
            ):
                reason_code = "assignment_inactive"
            for assignment in self._assignments:
                role = self._roles.get(assignment.role_id)
                if (
                    assignment.subject_id != request.subject.subject_id
                    or assignment.role_id not in request.subject.role_ids
                    or role is None
                    or assignment.scope != request.scope
                    or not assignment.is_active(decided_at)
                    or request.permission_id not in role.permissions
                ):
                    continue
                matched_assignments.append(assignment)
                matched_roles.append(role)

            if matched_assignments:
                outcome = DecisionOutcome.ALLOWED
                reason_code = "permission_granted"

        decision = AuthorizationDecision(
            decision_id=f"dec_{uuid4().hex}",
            decided_at=decided_at,
            outcome=outcome,
            reason_code=reason_code,
            permission_id=request.permission_id,
            scope_reference=request.scope.reference,
            subject_id=request.subject.subject_id,
            role_references=tuple(role.version_reference for role in matched_roles),
            assignment_references=tuple(
                assignment.version_reference for assignment in matched_assignments
            ),
            correlation_id=request.correlation_id,
        )
        await self._audit_decision(request, decision)
        return decision

    async def _audit_decision(
        self, request: AuthorizationRequest, decision: AuthorizationDecision
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.authorization.access.{decision.outcome.value}",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=decision.decided_at,
                correlation_id=decision.correlation_id,
                subject_id=request.subject.subject_id,
                actor_type=request.subject.kind.value,
                authentication_method=request.subject.authentication_method.value,
                assurance_level=request.subject.assurance_level.value,
                permission_id=request.permission_id,
                resource_type=request.resource_type,
                scope_reference=request.scope.reference,
                decision_id=decision.decision_id,
                outcome=decision.outcome.value,
                result_code=decision.reason_code,
                target_subject_id=request.target_subject_id,
                reason=request.reason,
                idempotency_key=request.idempotency_key,
                target_metadata=request.target_metadata,
            )
        )
