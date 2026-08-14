from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.orchestration_ports import (
    WorkflowOrchestrationLeaseRepository,
)
from atlas.modules.workflows.application.ports import WorkflowPlanRepository
from atlas.modules.workflows.application.publication_lease_ports import (
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireStatus,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationStatus,
    WorkflowOutboxPublicationLeaseRepository,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowOutboxPublicationLeaseState,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowScope,
    canonical_digest,
)

WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE = "audience.workflow-outbox-publisher"


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublisherContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    credential_audience: str
    scope: WorkflowScope
    authorized_target_ids: frozenset[str]
    correlation_id: str
    decision_id: str
    requested_at: datetime

    def __post_init__(self) -> None:
        identifiers = (
            self.subject_id,
            self.actor_type,
            self.authentication_method,
            self.credential_audience,
            self.correlation_id,
            self.decision_id,
        )
        if any(not value or value != value.strip() or len(value) > 240 for value in identifiers):
            raise ValueError("workflow outbox publisher context contains an invalid identifier")
        if any(
            not target_id.strip() or len(target_id) > 240
            for target_id in self.authorized_target_ids
        ):
            raise ValueError("workflow outbox publisher context contains an invalid target")
        if self.requested_at.tzinfo is None:
            raise ValueError("workflow outbox publisher requested_at must be timezone-aware")


class WorkflowOutboxPublicationLeaseService:
    """Coordinates provider-neutral publication ownership without publication authority."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        orchestration_lease_repository: WorkflowOrchestrationLeaseRepository,
        publication_lease_repository: WorkflowOutboxPublicationLeaseRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._plan_repository = plan_repository
        self._orchestration_lease_repository = orchestration_lease_repository
        self._publication_lease_repository = publication_lease_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._publication_lease_repository.durable

    @property
    def repository(self) -> WorkflowOutboxPublicationLeaseRepository:
        return self._publication_lease_repository

    async def acquire(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        lease_seconds: int,
        idempotency_key: str,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowOutboxPublicationLease:
        await self._require_publisher(context, operation="acquire")
        try:
            normalized_outbox_id = self._identifier(outbox_entry_id, name="outbox_entry_id")
            normalized_outbox_digest = self._digest(outbox_entry_digest, name="outbox_entry_digest")
            normalized_key = self._idempotency_key(idempotency_key)
            self._lease_seconds(lease_seconds)
        except WorkflowOutboxPublicationLeaseError as exc:
            await self._deny(context, operation="acquire", result_code=exc.code)
            raise

        outbox, orchestration_lease = await self._require_current_evidence(
            outbox_entry_id=normalized_outbox_id,
            outbox_entry_digest=normalized_outbox_digest,
            context=context,
            operation="acquire",
            idempotency_key=normalized_key,
        )
        fingerprint = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "lease_seconds": lease_seconds,
                "operation": "workflow.outbox-publication-lease.acquire",
                "orchestration_fencing_token": orchestration_lease.fencing_token,
                "orchestration_lease_digest": orchestration_lease.canonical_digest,
                "orchestration_lease_id": orchestration_lease.lease_id,
                "outbox_entry_digest": outbox.canonical_digest,
                "outbox_entry_id": outbox.outbox_entry_id,
                "publisher_subject_id": context.subject_id,
                "scope": outbox.scope.canonical_value(),
                "target_id": outbox.target_id,
                "target_type": outbox.target_type,
            }
        )
        prior = await self._publication_lease_repository.get_publication_lease_acquire_request(
            scope=context.scope,
            publisher_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    operation="acquire",
                    result_code="workflow_outbox_publication_lease_idempotency_conflict",
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    lease=prior.lease,
                )
                raise WorkflowOutboxPublicationLeaseError(
                    "workflow_outbox_publication_lease_idempotency_conflict",
                    "The idempotency key was already used for a different acquisition.",
                )
            self._validate_lease_binding(prior.lease, outbox, orchestration_lease, context)
            await self._success(
                context,
                operation="acquire.replayed",
                result_code="workflow_outbox_publication_lease_acquisition_replayed",
                idempotency_key=normalized_key,
                outbox=outbox,
                lease=prior.lease,
            )
            return prior.lease

        current = await self._publication_lease_repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox.outbox_entry_id
        )
        if (
            current is not None
            and current.effective_state(requested_at=context.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
        ):
            await self._deny(
                context,
                operation="acquire",
                result_code="workflow_outbox_publication_lease_contended",
                idempotency_key=normalized_key,
                outbox=outbox,
                lease=current,
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_contended",
                "The outbox entry already has an active publication lease.",
            )
        publication_fencing_token = 1 if current is None else current.publication_fencing_token + 1
        candidate = self._build_lease(
            outbox=outbox,
            orchestration_lease=orchestration_lease,
            context=context,
            lease_seconds=lease_seconds,
            idempotency_key=normalized_key,
            fingerprint=fingerprint,
            publication_fencing_token=publication_fencing_token,
        )
        result = await self._publication_lease_repository.acquire_publication_lease(
            WorkflowOutboxPublicationLeaseAcquireRequest(
                expected_outbox_entry_digest=outbox.canonical_digest,
                expected_orchestration_lease_id=orchestration_lease.lease_id,
                expected_orchestration_lease_digest=orchestration_lease.canonical_digest,
                expected_orchestration_fencing_token=orchestration_lease.fencing_token,
                candidate=candidate,
                requested_at=context.requested_at,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                expected_current_lease_digest=(
                    None if current is None else current.canonical_digest
                ),
                expected_current_publication_fencing_token=(
                    None if current is None else current.publication_fencing_token
                ),
            )
        )
        if result.status in {
            WorkflowOutboxPublicationLeaseAcquireStatus.ACQUIRED,
            WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY,
        }:
            if result.lease is None:
                raise WorkflowOutboxPublicationLeaseError(
                    "workflow_outbox_publication_lease_repository_contract_violation",
                    "The repository returned an incomplete acquisition result.",
                )
            self._validate_lease_binding(result.lease, outbox, orchestration_lease, context)
            replayed = result.status is WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY
            await self._success(
                context,
                operation="acquire.replayed" if replayed else "acquired",
                result_code=(
                    "workflow_outbox_publication_lease_acquisition_replayed"
                    if replayed
                    else "workflow_outbox_publication_lease_acquired"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                lease=result.lease,
            )
            return result.lease
        code, detail = self._acquire_failure(result.status)
        await self._deny(
            context,
            operation="acquire",
            result_code=code,
            idempotency_key=normalized_key,
            outbox=outbox,
            lease=result.lease,
        )
        raise WorkflowOutboxPublicationLeaseError(code, detail)

    async def heartbeat(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        lease_seconds: int,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowOutboxPublicationLease:
        self._lease_seconds(lease_seconds)
        return await self._mutate(
            operation="heartbeat",
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=publication_lease_digest,
            publication_fencing_token=publication_fencing_token,
            lease_seconds=lease_seconds,
            context=context,
        )

    async def release(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowOutboxPublicationLease:
        return await self._mutate(
            operation="release",
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=publication_lease_digest,
            publication_fencing_token=publication_fencing_token,
            lease_seconds=None,
            context=context,
        )

    async def _mutate(
        self,
        *,
        operation: str,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        lease_seconds: int | None,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowOutboxPublicationLease:
        await self._require_publisher(context, operation=operation)
        try:
            normalized_outbox_id = self._identifier(outbox_entry_id, name="outbox_entry_id")
            normalized_outbox_digest = self._digest(outbox_entry_digest, name="outbox_entry_digest")
            normalized_lease_id = self._identifier(
                publication_lease_id, name="publication_lease_id"
            )
            normalized_lease_digest = self._digest(
                publication_lease_digest, name="publication_lease_digest"
            )
            if publication_fencing_token < 1:
                raise WorkflowOutboxPublicationLeaseError(
                    "workflow_outbox_publication_lease_conflict",
                    "The publication fencing token is invalid.",
                )
        except WorkflowOutboxPublicationLeaseError as exc:
            await self._deny(context, operation=operation, result_code=exc.code)
            raise
        outbox, orchestration_lease = await self._require_current_evidence(
            outbox_entry_id=normalized_outbox_id,
            outbox_entry_digest=normalized_outbox_digest,
            context=context,
            operation=operation,
        )
        current = await self._publication_lease_repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox.outbox_entry_id
        )
        if (
            current is None
            or not self._matches_expected_lease(
                current,
                publication_lease_id=normalized_lease_id,
                publication_lease_digest=normalized_lease_digest,
                publication_fencing_token=publication_fencing_token,
                context=context,
            )
            or current.effective_state(requested_at=context.requested_at)
            is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            or not self._matches_orchestration(current, orchestration_lease)
        ):
            code = (
                "workflow_outbox_publication_lease_not_found"
                if current is None
                else "workflow_outbox_publication_lease_conflict"
            )
            await self._deny(
                context,
                operation=operation,
                result_code=code,
                outbox=outbox,
                lease=current,
            )
            raise WorkflowOutboxPublicationLeaseError(
                code, "The publication lease is unavailable, stale, or no longer active."
            )
        updated = self._updated_lease(
            current=current,
            last_heartbeat_at=(
                context.requested_at if operation == "heartbeat" else current.last_heartbeat_at
            ),
            expires_at=(
                context.requested_at + timedelta(seconds=lease_seconds)
                if lease_seconds is not None
                else current.expires_at
            ),
            state=(
                WorkflowOutboxPublicationLeaseState.ACTIVE
                if operation == "heartbeat"
                else WorkflowOutboxPublicationLeaseState.RELEASED
            ),
        )
        request = WorkflowOutboxPublicationLeaseMutationRequest(
            expected_outbox_entry_digest=outbox.canonical_digest,
            expected_orchestration_lease_id=orchestration_lease.lease_id,
            expected_orchestration_lease_digest=orchestration_lease.canonical_digest,
            expected_orchestration_fencing_token=orchestration_lease.fencing_token,
            expected_publication_lease_id=current.publication_lease_id,
            expected_publication_lease_digest=current.canonical_digest,
            expected_publication_fencing_token=current.publication_fencing_token,
            publisher_subject_id=context.subject_id,
            requested_at=context.requested_at,
            updated_lease=updated,
        )
        result = (
            await self._publication_lease_repository.heartbeat_publication_lease(request)
            if operation == "heartbeat"
            else await self._publication_lease_repository.release_publication_lease(request)
        )
        if (
            result.status is WorkflowOutboxPublicationLeaseMutationStatus.UPDATED
            and result.lease is not None
        ):
            self._validate_lease_binding(result.lease, outbox, orchestration_lease, context)
            await self._success(
                context,
                operation=operation,
                result_code=(
                    "workflow_outbox_publication_lease_heartbeated"
                    if operation == "heartbeat"
                    else "workflow_outbox_publication_lease_released"
                ),
                outbox=outbox,
                lease=result.lease,
            )
            return result.lease
        code = (
            "workflow_outbox_publication_lease_not_found"
            if result.status is WorkflowOutboxPublicationLeaseMutationStatus.NOT_FOUND
            else "workflow_outbox_publication_lease_evidence_conflict"
            if result.status is WorkflowOutboxPublicationLeaseMutationStatus.EVIDENCE_CONFLICT
            else "workflow_outbox_publication_lease_conflict"
        )
        await self._deny(
            context,
            operation=operation,
            result_code=code,
            outbox=outbox,
            lease=result.lease,
        )
        raise WorkflowOutboxPublicationLeaseError(code, "The publication lease mutation failed.")

    async def _require_current_evidence(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        context: WorkflowOutboxPublisherContext,
        operation: str,
        idempotency_key: str | None = None,
    ) -> tuple[WorkflowDispatchOutboxEntry, WorkflowOrchestrationLease]:
        outbox = await self._publication_lease_repository.get_outbox_entry_by_id(
            outbox_entry_id=outbox_entry_id
        )
        if (
            outbox is None
            or outbox.scope != context.scope
            or outbox.target_id not in context.authorized_target_ids
            or outbox.target_type != "storage"
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_outbox_publication_entry_not_found",
                idempotency_key=idempotency_key,
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_entry_not_found",
                "The workflow outbox entry is unavailable.",
            )
        if (
            outbox.canonical_digest != outbox_entry_digest
            or outbox.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
            or any(outbox.authority.canonical_value().values())
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_outbox_publication_evidence_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_evidence_conflict",
                "The workflow outbox entry changed or is not pending publication.",
            )
        plan = await self._plan_repository.get_by_id(plan_id=outbox.plan_id)
        if (
            plan is None
            or plan.scope != outbox.scope
            or plan.target_id != outbox.target_id
            or plan.target_type != outbox.target_type
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_outbox_publication_plan_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_plan_not_found", "The workflow plan is unavailable."
            )
        if (
            plan.state is not WorkflowPlanState.PLANNED
            or plan.canonical_digest != outbox.plan_digest
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_outbox_publication_plan_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_plan_conflict",
                "The workflow plan is terminal or its digest changed.",
            )
        orchestration_lease = await self._orchestration_lease_repository.get_lease_by_plan_id(
            plan_id=outbox.plan_id
        )
        if (
            orchestration_lease is None
            or orchestration_lease.lease_id != outbox.lease_id
            or orchestration_lease.canonical_digest != outbox.lease_digest
            or orchestration_lease.fencing_token != outbox.fencing_token
            or orchestration_lease.scope != outbox.scope
            or orchestration_lease.target_id != outbox.target_id
            or orchestration_lease.target_type != outbox.target_type
            or orchestration_lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_outbox_publication_orchestration_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_orchestration_lease_conflict",
                "The exact active orchestration lease is unavailable.",
            )
        return outbox, orchestration_lease

    @staticmethod
    def _build_lease(
        *,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        context: WorkflowOutboxPublisherContext,
        lease_seconds: int,
        idempotency_key: str,
        fingerprint: str,
        publication_fencing_token: int,
    ) -> WorkflowOutboxPublicationLease:
        publication_lease_id = (
            "workflow-outbox-publication-lease."
            + sha256(
                (
                    f"{outbox.outbox_entry_id}:{context.subject_id}:{idempotency_key}:{fingerprint}"
                ).encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "publication_lease_id": publication_lease_id,
            "outbox_entry_id": outbox.outbox_entry_id,
            "outbox_entry_digest": outbox.canonical_digest,
            "dispatch_intent_id": outbox.dispatch_intent_id,
            "dispatch_intent_digest": outbox.dispatch_intent_digest,
            "plan_id": outbox.plan_id,
            "plan_digest": outbox.plan_digest,
            "run_id": outbox.run_id,
            "run_digest": outbox.run_digest,
            "step_run_id": outbox.step_run_id,
            "step_run_digest": outbox.step_run_digest,
            "step_id": outbox.step_id,
            "attempt_id": outbox.attempt_id,
            "attempt_digest": outbox.attempt_digest,
            "attempt_number": outbox.attempt_number,
            "scope": outbox.scope,
            "target_id": outbox.target_id,
            "target_type": outbox.target_type,
            "orchestration_lease_id": orchestration_lease.lease_id,
            "orchestration_lease_digest": orchestration_lease.canonical_digest,
            "orchestration_fencing_token": orchestration_lease.fencing_token,
            "publisher_subject_id": context.subject_id,
            "acquired_at": context.requested_at,
            "last_heartbeat_at": context.requested_at,
            "expires_at": context.requested_at + timedelta(seconds=lease_seconds),
            "publication_fencing_token": publication_fencing_token,
            "state": WorkflowOutboxPublicationLeaseState.ACTIVE,
            "authority": WorkflowPlanAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (WorkflowScope, WorkflowPlanAuthority))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowOutboxPublicationLeaseState)
            else value
            for key, value in values.items()
        }
        return WorkflowOutboxPublicationLease(
            **cast(Any, values),
            canonical_digest=canonical_digest(digest_payload),
        )

    @staticmethod
    def _updated_lease(
        *,
        current: WorkflowOutboxPublicationLease,
        last_heartbeat_at: datetime,
        expires_at: datetime,
        state: WorkflowOutboxPublicationLeaseState,
    ) -> WorkflowOutboxPublicationLease:
        values = {
            name: getattr(current, name)
            for name in current.__dataclass_fields__
            if name != "canonical_digest"
        }
        values.update(
            last_heartbeat_at=last_heartbeat_at,
            expires_at=expires_at,
            state=state,
        )
        digest_payload = current.digest_payload()
        digest_payload.update(
            last_heartbeat_at=last_heartbeat_at.isoformat(),
            expires_at=expires_at.isoformat(),
            state=state.value,
        )
        return WorkflowOutboxPublicationLease(
            **cast(Any, values),
            canonical_digest=canonical_digest(digest_payload),
        )

    @classmethod
    def _validate_lease_binding(
        cls,
        lease: WorkflowOutboxPublicationLease,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        if (
            not cls._matches_lineage(lease, outbox)
            or not cls._matches_orchestration(lease, orchestration_lease)
            or lease.publisher_subject_id != context.subject_id
            or lease.scope != context.scope
            or lease.target_id not in context.authorized_target_ids
            or lease.grants_publication_authority
            or lease.grants_delivery_authority
            or lease.grants_dispatch_authority
            or lease.grants_execution_authority
            or any(lease.authority.canonical_value().values())
        ):
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_scope_violation",
                "The repository returned an incorrectly bound publication lease.",
            )

    @staticmethod
    def _matches_lineage(
        lease: WorkflowOutboxPublicationLease, outbox: WorkflowDispatchOutboxEntry
    ) -> bool:
        return (
            lease.outbox_entry_id,
            lease.outbox_entry_digest,
            lease.dispatch_intent_id,
            lease.dispatch_intent_digest,
            lease.plan_id,
            lease.plan_digest,
            lease.run_id,
            lease.run_digest,
            lease.step_run_id,
            lease.step_run_digest,
            lease.step_id,
            lease.attempt_id,
            lease.attempt_digest,
            lease.attempt_number,
            lease.scope,
            lease.target_id,
            lease.target_type,
        ) == (
            outbox.outbox_entry_id,
            outbox.canonical_digest,
            outbox.dispatch_intent_id,
            outbox.dispatch_intent_digest,
            outbox.plan_id,
            outbox.plan_digest,
            outbox.run_id,
            outbox.run_digest,
            outbox.step_run_id,
            outbox.step_run_digest,
            outbox.step_id,
            outbox.attempt_id,
            outbox.attempt_digest,
            outbox.attempt_number,
            outbox.scope,
            outbox.target_id,
            outbox.target_type,
        )

    @staticmethod
    def _matches_orchestration(
        lease: WorkflowOutboxPublicationLease,
        orchestration_lease: WorkflowOrchestrationLease,
    ) -> bool:
        return (
            lease.orchestration_lease_id == orchestration_lease.lease_id
            and lease.orchestration_lease_digest == orchestration_lease.canonical_digest
            and lease.orchestration_fencing_token == orchestration_lease.fencing_token
        )

    @staticmethod
    def _matches_expected_lease(
        lease: WorkflowOutboxPublicationLease,
        *,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        context: WorkflowOutboxPublisherContext,
    ) -> bool:
        return (
            lease.publication_lease_id == publication_lease_id
            and lease.canonical_digest == publication_lease_digest
            and lease.publication_fencing_token == publication_fencing_token
            and lease.publisher_subject_id == context.subject_id
            and lease.scope == context.scope
            and lease.target_id in context.authorized_target_ids
        )

    async def _require_publisher(
        self, context: WorkflowOutboxPublisherContext, *, operation: str
    ) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_outbox_publisher_identity_required",
            )
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publisher_identity_required",
                "A workflow outbox publisher workload identity is required.",
            )

    @staticmethod
    def _identifier(value: str, *, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(char.isspace() for char in normalized):
            raise WorkflowOutboxPublicationLeaseError(
                f"workflow_outbox_publication_lease_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, name="idempotency_key")
        if not 8 <= len(normalized) <= 200:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_idempotency_key_invalid",
                "Idempotency key must contain 8 to 200 characters.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, *, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowOutboxPublicationLeaseError(
                f"workflow_outbox_publication_lease_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value

    @staticmethod
    def _lease_seconds(value: int) -> None:
        if not 30 <= value <= 300:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_duration_invalid",
                "Publication lease duration must be between 30 and 300 seconds.",
            )

    @staticmethod
    def _acquire_failure(
        status: WorkflowOutboxPublicationLeaseAcquireStatus,
    ) -> tuple[str, str]:
        if status is WorkflowOutboxPublicationLeaseAcquireStatus.IDEMPOTENCY_CONFLICT:
            return (
                "workflow_outbox_publication_lease_idempotency_conflict",
                "The idempotency key was already used for a different acquisition.",
            )
        if status is WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED:
            return (
                "workflow_outbox_publication_lease_contended",
                "The outbox entry already has an active publication lease.",
            )
        return (
            "workflow_outbox_publication_lease_evidence_conflict",
            "The outbox or orchestration lease evidence changed.",
        )

    async def _success(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        operation: str,
        result_code: str,
        outbox: WorkflowDispatchOutboxEntry,
        lease: WorkflowOutboxPublicationLease,
        idempotency_key: str | None = None,
    ) -> None:
        await self._audit(
            context,
            event_type=f"atlas.workflow.outbox-publication-lease.{operation}",
            outcome="succeeded",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            lease=lease,
        )

    async def _deny(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        operation: str,
        result_code: str,
        idempotency_key: str | None = None,
        outbox: WorkflowDispatchOutboxEntry | None = None,
        lease: WorkflowOutboxPublicationLease | None = None,
    ) -> None:
        await self._audit(
            context,
            event_type=f"atlas.workflow.outbox-publication-lease.{operation}.denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            lease=lease,
        )

    async def _audit(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        event_type: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        outbox: WorkflowDispatchOutboxEntry | None,
        lease: WorkflowOutboxPublicationLease | None,
    ) -> None:
        metadata: list[tuple[str, str]] = [
            ("publication_authority", "false"),
            ("delivery_authority", "false"),
            ("dispatch_authority", "false"),
            ("execution_authority", "false"),
        ]
        if outbox is not None:
            metadata.extend(
                (
                    ("outbox_entry_id", outbox.outbox_entry_id),
                    ("outbox_entry_digest", outbox.canonical_digest),
                    ("dispatch_intent_id", outbox.dispatch_intent_id),
                    ("plan_id", outbox.plan_id),
                    ("run_id", outbox.run_id),
                    ("step_run_id", outbox.step_run_id),
                    ("attempt_id", outbox.attempt_id),
                )
            )
        if lease is not None:
            metadata.extend(
                (
                    ("publication_lease_id", lease.publication_lease_id),
                    ("publication_lease_digest", lease.canonical_digest),
                    (
                        "publication_fencing_token",
                        str(lease.publication_fencing_token),
                    ),
                    ("publication_lease_state", lease.state.value),
                    ("orchestration_lease_id", lease.orchestration_lease_id),
                    ("orchestration_lease_digest", lease.orchestration_lease_digest),
                    (
                        "orchestration_fencing_token",
                        str(lease.orchestration_fencing_token),
                    ),
                )
            )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-workflow-outbox-control",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.outbox-publication-lease.mutate",
                resource_type="resource.workflow-outbox-publication-lease",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-outbox-publication-lease",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=tuple(metadata),
            )
        )


__all__ = [
    "WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE",
    "WorkflowOutboxPublicationLeaseService",
    "WorkflowOutboxPublisherContext",
]
