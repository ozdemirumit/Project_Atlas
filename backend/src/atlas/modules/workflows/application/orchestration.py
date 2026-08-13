from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.orchestration_ports import (
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireStatus,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationStatus,
    WorkflowOrchestrationLeaseError,
    WorkflowOrchestrationLeaseRepository,
)
from atlas.modules.workflows.application.ports import WorkflowPlanRepository
from atlas.modules.workflows.domain import (
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOrchestrationLeaseState,
    WorkflowPlanState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
)

WORKFLOW_WORKER_AUDIENCE = "audience.workflow-worker"


@dataclass(frozen=True, slots=True)
class WorkflowWorkerContext:
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
            raise ValueError("workflow worker context contains an invalid identifier")
        if any(
            not target_id.strip() or len(target_id) > 240
            for target_id in self.authorized_target_ids
        ):
            raise ValueError("workflow worker context contains an invalid target")
        if self.requested_at.tzinfo is None:
            raise ValueError("workflow worker requested_at must be timezone-aware")


class WorkflowOrchestrationLeaseService:
    """Coordinates fenced ownership without granting or exercising execution authority."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        lease_repository: WorkflowOrchestrationLeaseRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._plan_repository = plan_repository
        self._lease_repository = lease_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._lease_repository.durable

    @property
    def repository(self) -> WorkflowOrchestrationLeaseRepository:
        return self._lease_repository

    async def acquire(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        lease_seconds: int,
        idempotency_key: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowOrchestrationLease:
        await self._require_worker(context, operation="acquire")
        normalized_plan_id = self._identifier(plan_id, name="plan_id")
        normalized_digest = self._digest(plan_digest, name="plan_digest")
        normalized_key = self._idempotency_key(idempotency_key)
        self._lease_seconds(lease_seconds)
        plan = await self._require_exact_planned_plan(
            plan_id=normalized_plan_id,
            plan_digest=normalized_digest,
            context=context,
            idempotency_key=normalized_key,
            operation="acquire",
        )
        fingerprint = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "lease_seconds": lease_seconds,
                "operation": "workflow.orchestration-lease.acquire",
                "plan_digest": plan.canonical_digest,
                "plan_id": plan.plan_id,
                "scope": plan.scope.canonical_value(),
                "target_id": plan.target_id,
                "target_type": plan.target_type,
                "worker_subject_id": context.subject_id,
            }
        )
        prior = await self._lease_repository.get_lease_acquire_request(
            scope=context.scope,
            worker_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    operation="acquire",
                    result_code="workflow_lease_idempotency_conflict",
                    idempotency_key=normalized_key,
                    plan=plan,
                    lease=prior.lease,
                )
                raise WorkflowOrchestrationLeaseError(
                    "workflow_lease_idempotency_conflict",
                    "The idempotency key was already used for a different lease acquisition.",
                )
            self._validate_lease_binding(prior.lease, plan, context)
            await self._success(
                context,
                operation="acquire.replayed",
                result_code="workflow_lease_acquisition_replayed",
                idempotency_key=normalized_key,
                plan=plan,
                lease=prior.lease,
            )
            return prior.lease

        current = await self._lease_repository.get_lease_by_plan_id(plan_id=plan.plan_id)
        if (
            current is not None
            and current.effective_state(requested_at=context.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            await self._deny(
                context,
                operation="acquire",
                result_code="workflow_lease_contended",
                idempotency_key=normalized_key,
                plan=plan,
                lease=current,
            )
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_contended", "The workflow plan already has an active lease."
            )
        fencing_token = 1 if current is None else current.fencing_token + 1
        lease = self._build_lease(
            plan=plan,
            context=context,
            lease_seconds=lease_seconds,
            idempotency_key=normalized_key,
            fingerprint=fingerprint,
            fencing_token=fencing_token,
        )
        result = await self._lease_repository.acquire_lease(
            WorkflowLeaseAcquireRequest(
                expected_plan_digest=plan.canonical_digest,
                candidate=lease,
                requested_at=context.requested_at,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                expected_current_lease_digest=(
                    None if current is None else current.canonical_digest
                ),
                expected_current_fencing_token=(None if current is None else current.fencing_token),
            )
        )
        if result.status in {
            WorkflowLeaseAcquireStatus.ACQUIRED,
            WorkflowLeaseAcquireStatus.REPLAY,
        }:
            if result.lease is None:
                raise WorkflowOrchestrationLeaseError(
                    "workflow_lease_repository_contract_violation",
                    "The lease repository returned an incomplete acquisition result.",
                )
            self._validate_lease_binding(result.lease, plan, context)
            await self._success(
                context,
                operation=(
                    "acquire.replayed"
                    if result.status is WorkflowLeaseAcquireStatus.REPLAY
                    else "acquired"
                ),
                result_code=(
                    "workflow_lease_acquisition_replayed"
                    if result.status is WorkflowLeaseAcquireStatus.REPLAY
                    else "workflow_lease_acquired"
                ),
                idempotency_key=normalized_key,
                plan=plan,
                lease=result.lease,
            )
            return result.lease
        code, detail = self._acquire_failure(result.status)
        await self._deny(
            context,
            operation="acquire",
            result_code=code,
            idempotency_key=normalized_key,
            plan=plan,
            lease=result.lease,
        )
        raise WorkflowOrchestrationLeaseError(code, detail)

    async def heartbeat(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        lease_seconds: int,
        context: WorkflowWorkerContext,
    ) -> WorkflowOrchestrationLease:
        self._lease_seconds(lease_seconds)
        return await self._mutate(
            operation="heartbeat",
            plan_id=plan_id,
            plan_digest=plan_digest,
            lease_id=lease_id,
            lease_digest=lease_digest,
            fencing_token=fencing_token,
            context=context,
            lease_seconds=lease_seconds,
        )

    async def release(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        context: WorkflowWorkerContext,
    ) -> WorkflowOrchestrationLease:
        return await self._mutate(
            operation="release",
            plan_id=plan_id,
            plan_digest=plan_digest,
            lease_id=lease_id,
            lease_digest=lease_digest,
            fencing_token=fencing_token,
            context=context,
            lease_seconds=None,
        )

    async def _mutate(
        self,
        *,
        operation: str,
        plan_id: str,
        plan_digest: str,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        context: WorkflowWorkerContext,
        lease_seconds: int | None,
    ) -> WorkflowOrchestrationLease:
        await self._require_worker(context, operation=operation)
        normalized_plan_id = self._identifier(plan_id, name="plan_id")
        normalized_plan_digest = self._digest(plan_digest, name="plan_digest")
        normalized_lease_id = self._identifier(lease_id, name="lease_id")
        normalized_lease_digest = self._digest(lease_digest, name="lease_digest")
        if fencing_token < 1:
            await self._deny(context, operation=operation, result_code="workflow_lease_conflict")
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_conflict", "The workflow lease fencing token is invalid."
            )
        plan = await self._require_exact_planned_plan(
            plan_id=normalized_plan_id,
            plan_digest=normalized_plan_digest,
            context=context,
            idempotency_key=None,
            operation=operation,
        )
        current = await self._lease_repository.get_lease_by_plan_id(plan_id=plan.plan_id)
        if current is None:
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_lease_not_found",
                plan=plan,
            )
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_not_found", "The workflow lease is unavailable."
            )
        if (
            not self._matches_expected_lease(
                current,
                lease_id=normalized_lease_id,
                lease_digest=normalized_lease_digest,
                fencing_token=fencing_token,
                context=context,
            )
            or current.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_lease_conflict",
                plan=plan,
                lease=current,
            )
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_conflict", "The workflow lease is stale or no longer active."
            )
        if operation == "heartbeat":
            assert lease_seconds is not None
            updated = self._updated_lease(
                current=current,
                last_heartbeat_at=context.requested_at,
                expires_at=context.requested_at + timedelta(seconds=lease_seconds),
                state=WorkflowOrchestrationLeaseState.ACTIVE,
            )
        else:
            updated = self._updated_lease(
                current=current,
                last_heartbeat_at=current.last_heartbeat_at,
                expires_at=current.expires_at,
                state=WorkflowOrchestrationLeaseState.RELEASED,
            )
        request = WorkflowLeaseMutationRequest(
            expected_plan_digest=plan.canonical_digest,
            expected_lease_id=current.lease_id,
            expected_lease_digest=current.canonical_digest,
            expected_fencing_token=current.fencing_token,
            worker_subject_id=context.subject_id,
            requested_at=context.requested_at,
            updated_lease=updated,
        )
        result = (
            await self._lease_repository.heartbeat_lease(request)
            if operation == "heartbeat"
            else await self._lease_repository.release_lease(request)
        )
        if result.status is WorkflowLeaseMutationStatus.UPDATED and result.lease is not None:
            self._validate_lease_binding(result.lease, plan, context)
            result_code = (
                "workflow_lease_heartbeated"
                if operation == "heartbeat"
                else "workflow_lease_released"
            )
            await self._success(
                context,
                operation=operation,
                result_code=result_code,
                plan=plan,
                lease=result.lease,
            )
            return result.lease
        code = (
            "workflow_lease_plan_conflict"
            if result.status is WorkflowLeaseMutationStatus.PLAN_CONFLICT
            else "workflow_lease_not_found"
            if result.status is WorkflowLeaseMutationStatus.NOT_FOUND
            else "workflow_lease_conflict"
        )
        await self._deny(
            context,
            operation=operation,
            result_code=code,
            plan=plan,
            lease=result.lease,
        )
        raise WorkflowOrchestrationLeaseError(code, "The workflow lease mutation was rejected.")

    async def _require_exact_planned_plan(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        context: WorkflowWorkerContext,
        idempotency_key: str | None,
        operation: str,
    ) -> WorkflowRunPlan:
        plan = await self._plan_repository.get_by_id(plan_id=plan_id)
        if (
            plan is None
            or plan.scope != context.scope
            or plan.target_type != "storage"
            or plan.target_id not in context.authorized_target_ids
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_lease_plan_not_found",
                idempotency_key=idempotency_key,
            )
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_plan_not_found", "The workflow plan is unavailable."
            )
        if plan.state is not WorkflowPlanState.PLANNED or plan.canonical_digest != plan_digest:
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_lease_plan_conflict",
                idempotency_key=idempotency_key,
                plan=plan,
            )
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_plan_conflict",
                "The workflow plan is terminal or its digest changed.",
            )
        return plan

    @staticmethod
    def _build_lease(
        *,
        plan: WorkflowRunPlan,
        context: WorkflowWorkerContext,
        lease_seconds: int,
        idempotency_key: str,
        fingerprint: str,
        fencing_token: int,
    ) -> WorkflowOrchestrationLease:
        lease_id = (
            "workflow-lease."
            + sha256(
                f"{plan.plan_id}:{context.subject_id}:{idempotency_key}:{fingerprint}".encode()
            ).hexdigest()[:24]
        )
        payload = {
            "acquired_at": context.requested_at.isoformat(),
            "expires_at": (context.requested_at + timedelta(seconds=lease_seconds)).isoformat(),
            "fencing_token": fencing_token,
            "last_heartbeat_at": context.requested_at.isoformat(),
            "lease_id": lease_id,
            "plan_digest": plan.canonical_digest,
            "plan_id": plan.plan_id,
            "scope": plan.scope.canonical_value(),
            "state": WorkflowOrchestrationLeaseState.ACTIVE.value,
            "target_id": plan.target_id,
            "target_type": plan.target_type,
            "worker_subject_id": context.subject_id,
        }
        return WorkflowOrchestrationLease(
            lease_id=lease_id,
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            scope=plan.scope,
            target_id=plan.target_id,
            target_type=plan.target_type,
            worker_subject_id=context.subject_id,
            acquired_at=context.requested_at,
            last_heartbeat_at=context.requested_at,
            expires_at=context.requested_at + timedelta(seconds=lease_seconds),
            fencing_token=fencing_token,
            state=WorkflowOrchestrationLeaseState.ACTIVE,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _updated_lease(
        *,
        current: WorkflowOrchestrationLease,
        last_heartbeat_at: datetime,
        expires_at: datetime,
        state: WorkflowOrchestrationLeaseState,
    ) -> WorkflowOrchestrationLease:
        payload = current.digest_payload()
        payload.update(
            {
                "expires_at": expires_at.isoformat(),
                "last_heartbeat_at": last_heartbeat_at.isoformat(),
                "state": state.value,
            }
        )
        return WorkflowOrchestrationLease(
            lease_id=current.lease_id,
            plan_id=current.plan_id,
            plan_digest=current.plan_digest,
            scope=current.scope,
            target_id=current.target_id,
            target_type=current.target_type,
            worker_subject_id=current.worker_subject_id,
            acquired_at=current.acquired_at,
            last_heartbeat_at=last_heartbeat_at,
            expires_at=expires_at,
            fencing_token=current.fencing_token,
            state=state,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _validate_lease_binding(
        lease: WorkflowOrchestrationLease,
        plan: WorkflowRunPlan,
        context: WorkflowWorkerContext,
    ) -> None:
        if (
            lease.plan_id != plan.plan_id
            or lease.plan_digest != plan.canonical_digest
            or lease.scope != plan.scope
            or lease.target_id != plan.target_id
            or lease.target_type != plan.target_type
            or lease.worker_subject_id != context.subject_id
            or lease.grants_execution_authority
        ):
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_repository_scope_violation",
                "The lease repository returned an incorrectly bound lease.",
            )

    @staticmethod
    def _matches_expected_lease(
        lease: WorkflowOrchestrationLease,
        *,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        context: WorkflowWorkerContext,
    ) -> bool:
        return (
            lease.lease_id == lease_id
            and lease.canonical_digest == lease_digest
            and lease.fencing_token == fencing_token
            and lease.worker_subject_id == context.subject_id
            and lease.scope == context.scope
            and lease.target_id in context.authorized_target_ids
        )

    async def _require_worker(self, context: WorkflowWorkerContext, *, operation: str) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_WORKER_AUDIENCE
        ):
            await self._deny(
                context,
                operation=operation,
                result_code="workflow_worker_identity_required",
            )
            raise WorkflowOrchestrationLeaseError(
                "workflow_worker_identity_required",
                "A workflow worker workload identity is required.",
            )

    @staticmethod
    def _identifier(value: str, *, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(char.isspace() for char in normalized):
            raise WorkflowOrchestrationLeaseError(
                f"workflow_lease_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, name="idempotency_key")
        if not 8 <= len(normalized) <= 200:
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_idempotency_key_invalid",
                "Idempotency key must contain 8 to 200 characters.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, *, name: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise WorkflowOrchestrationLeaseError(
                f"workflow_lease_{name}_invalid", f"{name} must be a SHA-256 digest."
            )
        return value

    @staticmethod
    def _lease_seconds(value: int) -> None:
        if not 30 <= value <= 300:
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_duration_invalid",
                "Workflow lease duration must be between 30 and 300 seconds.",
            )

    @staticmethod
    def _acquire_failure(status: WorkflowLeaseAcquireStatus) -> tuple[str, str]:
        if status is WorkflowLeaseAcquireStatus.IDEMPOTENCY_CONFLICT:
            return (
                "workflow_lease_idempotency_conflict",
                "The idempotency key was already used for a different acquisition.",
            )
        if status is WorkflowLeaseAcquireStatus.CONTENDED:
            return "workflow_lease_contended", "The workflow plan already has an active lease."
        return "workflow_lease_plan_conflict", "The workflow plan or lease changed."

    async def _success(
        self,
        context: WorkflowWorkerContext,
        *,
        operation: str,
        result_code: str,
        plan: WorkflowRunPlan,
        lease: WorkflowOrchestrationLease,
        idempotency_key: str | None = None,
    ) -> None:
        await self._audit(
            context,
            event_type=f"atlas.workflow.orchestration-lease.{operation}",
            outcome="succeeded",
            result_code=result_code,
            idempotency_key=idempotency_key,
            plan=plan,
            lease=lease,
        )

    async def _deny(
        self,
        context: WorkflowWorkerContext,
        *,
        operation: str,
        result_code: str,
        idempotency_key: str | None = None,
        plan: WorkflowRunPlan | None = None,
        lease: WorkflowOrchestrationLease | None = None,
    ) -> None:
        await self._audit(
            context,
            event_type=f"atlas.workflow.orchestration-lease.{operation}.denied",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            plan=plan,
            lease=lease,
        )

    async def _audit(
        self,
        context: WorkflowWorkerContext,
        *,
        event_type: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        plan: WorkflowRunPlan | None,
        lease: WorkflowOrchestrationLease | None,
    ) -> None:
        metadata: list[tuple[str, str]] = [("execution_authority", "false")]
        if plan is not None:
            metadata.extend((("plan_id", plan.plan_id), ("plan_digest", plan.canonical_digest)))
        if lease is not None:
            metadata.extend(
                (
                    ("lease_id", lease.lease_id),
                    ("lease_digest", lease.canonical_digest),
                    ("fencing_token", str(lease.fencing_token)),
                    ("lease_state", lease.state.value),
                )
            )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-worker-control",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.orchestration-lease.mutate",
                resource_type="resource.workflow-orchestration-lease",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-orchestration-lease",
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
    "WORKFLOW_WORKER_AUDIENCE",
    "WorkflowOrchestrationLeaseService",
    "WorkflowWorkerContext",
]
