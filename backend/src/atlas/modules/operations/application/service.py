"""docs/050_API.md SS15/SS19/SS20: `OperationResourceService`, the application service that makes
`operations.domain.models.OperationResource` reachable.

`create()` always persists a real `QUEUED` resource; the caller (the one real consumer today is
`atlas.api.routes.document_knowledge`'s `index-operations` route) is responsible for actually
performing the long-running work and reporting back through `mark_running()` /
`mark_succeeded()` / `mark_failed()` / `mark_partial()`. Those transition methods do not
independently re-authorize the acting subject -- they are invoked by the same background task that
already carries the actor authorized at `create()` time, not by a new inbound request. `get()` and
`cancel()` are the two methods a *new* inbound request reaches, so both independently re-authorize
the base permission and, when the acting subject does not own the operation, the elevated
cross-subject permission -- mirroring `conversations/application/service.py`'s `_is_owned` check,
extended with the "or holds the elevated cross-subject permission" branch the way
`itsm/application/attachments.py`'s `classification_ceiling()` extends ownership-free reads.

`cancel()` is a real, explicit, idempotent command per SS20: cancelling an already-cancelled
operation succeeds without altering its recorded reason (SS18's idempotency principle), while
cancelling an operation that has already reached a different terminal state is a real conflict.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.operations.application.ports import (
    OperationResourceError,
    OperationResourcePermissionAuthorizer,
    OperationResourceRepository,
)
from atlas.modules.operations.domain.models import OperationResource, OperationState

_OPERATION_RESOURCE_READ = "operations.resources.read"
_OPERATION_RESOURCE_CANCEL = "operations.resources.cancel"

_RESOURCE_TYPE = "resource.operations.resources"


class OperationResourceService:
    def __init__(
        self,
        *,
        repository: OperationResourceRepository,
        permission_authorizer: OperationResourcePermissionAuthorizer,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._permission_authorizer = permission_authorizer
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> OperationResourceRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_type: str,
        input_artifact_reference: str,
        correlation_id: str,
        workflow_run_reference: str | None = None,
        deadline_at: datetime | None = None,
        expires_at: datetime | None = None,
        progress_summary: str = "Queued for processing.",
        current_step: str = "queued",
        required_human_task_reference: str | None = None,
    ) -> OperationResource:
        now = self._clock()
        seed = sha256(
            f"{organization_id}:{environment_id}:{operation_type}:{actor.subject_id}:"
            f"{now.isoformat()}:{uuid4().hex}".encode()
        ).hexdigest()
        try:
            resource = OperationResource(
                operation_id=f"operation.{seed[:24]}",
                operation_type=operation_type,
                owner_subject_id=actor.subject_id,
                organization_id=organization_id,
                environment_id=environment_id,
                state=OperationState.QUEUED,
                progress_summary=progress_summary,
                created_at=now,
                started_at=None,
                updated_at=now,
                deadline_at=deadline_at,
                expires_at=expires_at,
                input_artifact_reference=input_artifact_reference,
                workflow_run_reference=workflow_run_reference,
                correlation_id=correlation_id,
                current_step=current_step,
                result_reference=None,
                partial_result_reference=None,
                error_reference=None,
                evidence_references=(),
                cancellation_eligible=True,
                cancellation_reason=None,
                required_human_task_reference=required_human_task_reference,
            )
        except ValueError as error:
            raise OperationResourceError("operation_resource_invalid", str(error)) from error
        if not await self._repository.add(resource):
            raise OperationResourceError("operation_resource_persistence_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            resource=resource,
            result_code="operation_resource_created",
        )
        return resource

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_id: str,
        correlation_id: str,
    ) -> OperationResource:
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_OPERATION_RESOURCE_READ,
            correlation_id=correlation_id,
        )
        resource = await self._repository.get(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource is None:
            raise OperationResourceError("operation_resource_not_found")
        if resource.owner_subject_id != actor.subject_id and not (
            await self._permission_authorizer.cross_subject_access_allowed(
                actor=actor,
                organization_id=organization_id,
                environment_id=environment_id,
                correlation_id=correlation_id,
            )
        ):
            await self._audit_denied(
                actor=actor,
                correlation_id=correlation_id,
                operation_id=operation_id,
                result_code="operation_resource_not_found",
            )
            raise OperationResourceError("operation_resource_not_found")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            resource=resource,
            result_code="operation_resource_read",
        )
        return resource

    async def cancel(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_id: str,
        reason: str,
        correlation_id: str,
    ) -> OperationResource:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_OPERATION_RESOURCE_CANCEL,
            correlation_id=correlation_id,
        )
        if not reason.strip():
            raise OperationResourceError("operation_resource_cancellation_reason_required")
        resource = await self._repository.get(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource is None:
            raise OperationResourceError("operation_resource_not_found")
        if resource.owner_subject_id != actor.subject_id and not (
            await self._permission_authorizer.cross_subject_access_allowed(
                actor=actor,
                organization_id=organization_id,
                environment_id=environment_id,
                correlation_id=correlation_id,
            )
        ):
            await self._audit_denied(
                actor=actor,
                correlation_id=correlation_id,
                operation_id=operation_id,
                result_code="operation_resource_not_found",
            )
            raise OperationResourceError("operation_resource_not_found")

        if resource.state is OperationState.CANCELLED:
            # SS18/SS20: repeated cancellation of an already-cancelled operation is a real
            # success, not an error -- the original recorded reason is never overwritten.
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                resource=resource,
                result_code="operation_resource_cancellation_idempotent",
            )
            return resource
        if resource.is_terminal:
            raise OperationResourceError("operation_resource_already_terminal")
        if not resource.cancellation_eligible:
            raise OperationResourceError("operation_resource_not_cancellable")

        now = self._clock()
        updated = replace(
            resource,
            state=OperationState.CANCELLED,
            updated_at=now,
            current_step="cancelled",
            progress_summary="Cancelled by request.",
            result_reference=None,
            partial_result_reference=None,
            error_reference=None,
            cancellation_eligible=False,
            cancellation_reason=reason.strip(),
        )
        if not await self._repository.update(expected=resource, replacement=updated):
            raise OperationResourceError("operation_resource_transition_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            resource=updated,
            result_code="operation_resource_cancelled",
        )
        return updated

    async def mark_running(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_id: str,
        current_step: str,
        progress_summary: str | None = None,
        correlation_id: str,
    ) -> OperationResource:
        resource = await self._require(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource.state not in (OperationState.QUEUED, OperationState.WAITING):
            raise OperationResourceError("operation_resource_transition_invalid")
        now = self._clock()
        updated = replace(
            resource,
            state=OperationState.RUNNING,
            started_at=resource.started_at or now,
            updated_at=now,
            current_step=current_step,
            progress_summary=progress_summary or resource.progress_summary,
        )
        return await self._transition(resource, updated, actor=actor, correlation_id=correlation_id)

    async def mark_succeeded(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_id: str,
        result_reference: str,
        evidence_references: tuple[str, ...] = (),
        correlation_id: str,
    ) -> OperationResource:
        resource = await self._require(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource.is_terminal:
            raise OperationResourceError("operation_resource_already_terminal")
        now = self._clock()
        updated = replace(
            resource,
            state=OperationState.SUCCEEDED,
            started_at=resource.started_at or now,
            updated_at=now,
            current_step="completed",
            progress_summary="Completed successfully.",
            result_reference=result_reference,
            evidence_references=evidence_references,
            cancellation_eligible=False,
        )
        return await self._transition(resource, updated, actor=actor, correlation_id=correlation_id)

    async def mark_failed(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_id: str,
        error_reference: str,
        correlation_id: str,
    ) -> OperationResource:
        resource = await self._require(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource.is_terminal:
            raise OperationResourceError("operation_resource_already_terminal")
        now = self._clock()
        updated = replace(
            resource,
            state=OperationState.FAILED,
            started_at=resource.started_at or now,
            updated_at=now,
            current_step="failed",
            progress_summary="Failed with a real error.",
            error_reference=error_reference,
            cancellation_eligible=False,
        )
        return await self._transition(resource, updated, actor=actor, correlation_id=correlation_id)

    async def mark_partial(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        operation_id: str,
        partial_result_reference: str,
        evidence_references: tuple[str, ...] = (),
        correlation_id: str,
    ) -> OperationResource:
        resource = await self._require(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource.is_terminal:
            raise OperationResourceError("operation_resource_already_terminal")
        now = self._clock()
        updated = replace(
            resource,
            state=OperationState.PARTIAL,
            started_at=resource.started_at or now,
            updated_at=now,
            current_step="partially completed",
            progress_summary="Completed with a real partial result.",
            partial_result_reference=partial_result_reference,
            evidence_references=evidence_references,
        )
        return await self._transition(resource, updated, actor=actor, correlation_id=correlation_id)

    async def close(self) -> None:
        await self._repository.close()

    async def _require(
        self, *, operation_id: str, organization_id: str, environment_id: str
    ) -> OperationResource:
        resource = await self._repository.get(
            operation_id=operation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if resource is None:
            raise OperationResourceError("operation_resource_not_found")
        return resource

    async def _transition(
        self,
        expected: OperationResource,
        replacement: OperationResource,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationResource:
        if not await self._repository.update(expected=expected, replacement=replacement):
            raise OperationResourceError("operation_resource_transition_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            resource=replacement,
            result_code=f"operation_resource_{replacement.state.value}",
        )
        return replacement

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise OperationResourceError("operation_resource_human_required")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        resource: OperationResource,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.operations.resource",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=None,
                resource_type=_RESOURCE_TYPE,
                scope_reference=resource.operation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(("state", resource.state.value),),
            )
        )

    async def _audit_denied(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        operation_id: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.operations.resource",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=None,
                resource_type=_RESOURCE_TYPE,
                scope_reference=operation_id,
                decision_id=None,
                outcome="denied",
                result_code=result_code,
                target_metadata=(),
            )
        )
