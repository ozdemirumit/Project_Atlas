"""Self-service durable role-assignment grants for the three LOCAL-reachable tiers (admin,
operator, monitor). Closes the gap where `AuthorizationService` could only ever authorize
subjects hand-written into a static, code-level list built once at startup (docs/031_RBAC.md
Sec.11/26) -- see `atlas.modules.authorization.application.service.AuthorizationService`'s
additive `dynamic_assignments` lookup path for the read side of this.

The self-escalation guard is the route layer, not this service: only `role.local-administrator`
(and, for dev/test continuity, the development role) carries `RBAC_ROLE_ASSIGNMENT_CREATE`, so
only an actor already holding that permission can ever reach `grant()` at all -- the same pattern
every other privileged action in this codebase uses (a `Depends(authorize_...)` route dependency),
not a second check duplicated here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.application.bootstrap import (
    DEVELOPMENT_ROLE_ID,
    LOCAL_ADMINISTRATOR_ROLE_ID,
    LOCAL_MONITOR_ROLE_ID,
    LOCAL_OPERATOR_ROLE_ID,
)
from atlas.modules.authorization.application.role_assignment_ports import (
    RoleAssignmentRepository,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

_GRANTABLE_ROLE_IDS = (LOCAL_ADMINISTRATOR_ROLE_ID, LOCAL_OPERATOR_ROLE_ID, LOCAL_MONITOR_ROLE_ID)


class RoleAssignmentGrantError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RoleAssignmentGrantService:
    def __init__(
        self,
        *,
        repository: RoleAssignmentRepository,
        authorization_service: AuthorizationService,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._authorization_service = authorization_service
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def grant(
        self,
        *,
        actor: AuthenticatedSubject,
        subject_id: str,
        role_id: str,
        correlation_id: str,
    ) -> tuple[RoleAssignment, ...]:
        if actor.kind is not SubjectKind.HUMAN:
            raise RoleAssignmentGrantError("role_assignment_grant_human_required")
        if role_id not in _GRANTABLE_ROLE_IDS:
            raise RoleAssignmentGrantError("role_assignment_grant_role_not_grantable")
        scopes = self._authorization_service.static_role_scopes(DEVELOPMENT_ROLE_ID)
        if not scopes:
            raise RoleAssignmentGrantError("role_assignment_grant_no_scopes_available")
        now = self._clock()
        created: list[RoleAssignment] = []
        for scope in scopes:
            assignment = RoleAssignment(
                assignment_id=f"assignment.{uuid4().hex}",
                version=1,
                subject_id=subject_id,
                role_id=role_id,
                scope=scope,
                valid_from=now,
            )
            if await self._repository.create(assignment):
                created.append(assignment)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            subject_id=subject_id,
            role_id=role_id,
            result_code="role_assignment_granted",
        )
        return tuple(created)

    async def list_active(
        self, *, actor: AuthenticatedSubject, subject_id: str
    ) -> tuple[RoleAssignment, ...]:
        del actor
        return await self._repository.list_active_for_subject(
            subject_id=subject_id, at=self._clock()
        )

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        subject_id: str,
        role_id: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.authorization.role-assignment.granted",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="authorization.role-assignments.create",
                resource_type="resource.authorization.role-assignments",
                scope_reference=role_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_subject_id=subject_id,
            )
        )
