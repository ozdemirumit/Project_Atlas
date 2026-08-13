from __future__ import annotations

from hashlib import sha256
from typing import NoReturn
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.attempt_ports import (
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationRepository,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationStatus,
)
from atlas.modules.workflows.application.materialization_ports import (
    WorkflowRunMaterializationRepository,
)
from atlas.modules.workflows.application.orchestration import (
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowWorkerContext,
)
from atlas.modules.workflows.application.orchestration_ports import (
    WorkflowOrchestrationLeaseRepository,
)
from atlas.modules.workflows.application.ports import WorkflowPlanRepository
from atlas.modules.workflows.domain import (
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRun,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    canonical_digest,
)


class WorkflowAttemptMaterializationService:
    """Creates a durable attempt identity without queue or dispatch authority."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        lease_repository: WorkflowOrchestrationLeaseRepository,
        run_repository: WorkflowRunMaterializationRepository,
        attempt_repository: WorkflowAttemptMaterializationRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._plan_repository = plan_repository
        self._lease_repository = lease_repository
        self._run_repository = run_repository
        self._attempt_repository = attempt_repository
        self._audit_sink = audit_sink

    @property
    def repository(self) -> WorkflowAttemptMaterializationRepository:
        return self._attempt_repository

    @property
    def durable(self) -> bool:
        return self._attempt_repository.durable

    async def materialize(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        run_id: str,
        run_digest: str,
        step_run_id: str,
        step_run_digest: str,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        idempotency_key: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowExecutionAttempt:
        if not self._is_worker(context):
            await self._audit(context, "workflow_attempt_worker_required", idempotency_key)
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_worker_required", "A workflow worker identity is required."
            )
        plan_id = self._identifier(plan_id, "plan_id")
        run_id = self._identifier(run_id, "run_id")
        step_run_id = self._identifier(step_run_id, "step_run_id")
        lease_id = self._identifier(lease_id, "lease_id")
        plan_digest = self._digest(plan_digest, "plan_digest")
        run_digest = self._digest(run_digest, "run_digest")
        step_run_digest = self._digest(step_run_digest, "step_run_digest")
        lease_digest = self._digest(lease_digest, "lease_digest")
        idempotency_key = self._idempotency_key(idempotency_key)
        if fencing_token < 1:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_fencing_token_invalid", "The fencing token is invalid."
            )

        plan = await self._plan_repository.get_by_id(plan_id=plan_id)
        if (
            plan is None
            or plan.scope != context.scope
            or plan.target_id not in context.authorized_target_ids
            or plan.target_type != "storage"
        ):
            await self._deny(context, "workflow_attempt_plan_not_found", idempotency_key)
        if plan.state is not WorkflowPlanState.PLANNED or plan.canonical_digest != plan_digest:
            await self._deny(context, "workflow_attempt_plan_conflict", idempotency_key)

        run = await self._run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if not self._run_matches(run, plan.canonical_digest, run_id, run_digest, context):
            await self._deny(context, "workflow_attempt_run_conflict", idempotency_key)
        assert run is not None
        step = next((item for item in run.step_runs if item.step_run_id == step_run_id), None)
        if (
            step is None
            or step.canonical_digest != step_run_digest
            or step.state is not WorkflowExecutionStepRunState.NOT_STARTED
            or step.depends_on
        ):
            await self._deny(context, "workflow_attempt_step_ineligible", idempotency_key)
        assert step is not None

        lease = await self._lease_repository.get_lease_by_plan_id(plan_id=plan.plan_id)
        if (
            lease is None
            or lease.lease_id != lease_id
            or lease.canonical_digest != lease_digest
            or lease.fencing_token != fencing_token
            or lease.plan_digest != plan.canonical_digest
            or lease.scope != run.scope
            or lease.target_id != run.target_id
            or lease.target_type != run.target_type
            or lease.worker_subject_id != context.subject_id
            or run.lease_id != lease.lease_id
            or run.fencing_token != lease.fencing_token
            or lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            or lease.grants_execution_authority
        ):
            await self._deny(context, "workflow_attempt_lease_conflict", idempotency_key)

        fingerprint = canonical_digest(
            {
                "fencing_token": fencing_token,
                "lease_digest": lease_digest,
                "lease_id": lease_id,
                "operation": "workflow.attempt.materialize",
                "plan_digest": plan.canonical_digest,
                "plan_id": plan.plan_id,
                "run_digest": run.canonical_digest,
                "run_id": run.run_id,
                "scope": run.scope.canonical_value(),
                "step_run_digest": step.canonical_digest,
                "step_run_id": step.step_run_id,
                "worker_subject_id": context.subject_id,
            }
        )
        prior = await self._attempt_repository.get_attempt_materialization_request(
            scope=context.scope,
            worker_subject_id=context.subject_id,
            idempotency_key=idempotency_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(context, "workflow_attempt_idempotency_conflict", idempotency_key)
            self._validate_attempt(prior.attempt, run, step, lease_digest, context)
            await self._audit(
                context,
                "workflow_attempt_materialization_replayed",
                idempotency_key,
                prior.attempt,
            )
            return prior.attempt

        attempt = self._build_attempt(run, step, lease_digest, context)
        await self._audit(
            context, "workflow_attempt_materialization_authorized", idempotency_key, attempt
        )
        try:
            result = await self._attempt_repository.materialize_attempt(
                WorkflowAttemptMaterializationRequest(
                    candidate=attempt,
                    expected_plan_digest=plan.canonical_digest,
                    expected_run_digest=run.canonical_digest,
                    expected_step_run_digest=step.canonical_digest,
                    expected_lease_id=lease_id,
                    expected_lease_digest=lease_digest,
                    expected_fencing_token=fencing_token,
                    worker_subject_id=context.subject_id,
                    requested_at=context.requested_at,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                )
            )
        except Exception:
            await self._audit(context, "workflow_attempt_repository_failure", idempotency_key)
            raise
        if (
            result.status
            in {
                WorkflowAttemptMaterializationStatus.CREATED,
                WorkflowAttemptMaterializationStatus.REPLAY,
            }
            and result.attempt is not None
        ):
            self._validate_attempt(result.attempt, run, step, lease_digest, context)
            return result.attempt
        code = (
            "workflow_attempt_idempotency_conflict"
            if result.status is WorkflowAttemptMaterializationStatus.IDEMPOTENCY_CONFLICT
            else "workflow_attempt_state_conflict"
        )
        await self._audit(context, code, idempotency_key)
        raise WorkflowAttemptMaterializationError(code, "Attempt materialization was rejected.")

    @staticmethod
    def _build_attempt(
        run: WorkflowExecutionRun,
        step: WorkflowExecutionStepRun,
        lease_digest: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowExecutionAttempt:
        attempt_id = (
            "workflow-attempt."
            + sha256(f"{run.run_id}:{step.step_run_id}:1".encode()).hexdigest()[:24]
        )
        authority = WorkflowPlanAuthority()
        payload = {
            "attempt_id": attempt_id,
            "attempt_number": 1,
            "authority": authority.canonical_value(),
            "created_at": context.requested_at.isoformat(),
            "definition_digest": run.definition_digest,
            "definition_id": run.definition_id,
            "definition_version": run.definition_version,
            "fencing_token": run.fencing_token,
            "lease_digest": lease_digest,
            "lease_id": run.lease_id,
            "materialized_by_subject_id": context.subject_id,
            "plan_digest": run.plan_digest,
            "plan_id": run.plan_id,
            "run_digest": run.canonical_digest,
            "run_id": run.run_id,
            "scope": run.scope.canonical_value(),
            "state": WorkflowExecutionAttemptState.CREATED.value,
            "step_id": step.step_id,
            "step_run_digest": step.canonical_digest,
            "step_run_id": step.step_run_id,
            "target_id": run.target_id,
            "target_type": run.target_type,
        }
        return WorkflowExecutionAttempt(
            attempt_id=attempt_id,
            run_id=run.run_id,
            run_digest=run.canonical_digest,
            step_run_id=step.step_run_id,
            step_run_digest=step.canonical_digest,
            step_id=step.step_id,
            attempt_number=1,
            plan_id=run.plan_id,
            plan_digest=run.plan_digest,
            definition_id=run.definition_id,
            definition_version=run.definition_version,
            definition_digest=run.definition_digest,
            scope=run.scope,
            target_id=run.target_id,
            target_type=run.target_type,
            lease_id=run.lease_id,
            lease_digest=lease_digest,
            fencing_token=run.fencing_token,
            materialized_by_subject_id=context.subject_id,
            created_at=context.requested_at,
            state=WorkflowExecutionAttemptState.CREATED,
            authority=authority,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _run_matches(
        run: WorkflowExecutionRun | None,
        plan_digest: str,
        run_id: str,
        run_digest: str,
        context: WorkflowWorkerContext,
    ) -> bool:
        return bool(
            run is not None
            and run.run_id == run_id
            and run.canonical_digest == run_digest
            and run.plan_digest == plan_digest
            and run.scope == context.scope
            and run.target_id in context.authorized_target_ids
            and run.state is WorkflowExecutionRunState.CREATED
            and not run.grants_execution_authority
        )

    @staticmethod
    def _validate_attempt(
        attempt: WorkflowExecutionAttempt,
        run: WorkflowExecutionRun,
        step: WorkflowExecutionStepRun,
        lease_digest: str,
        context: WorkflowWorkerContext,
    ) -> None:
        if (
            attempt.run_id != run.run_id
            or attempt.run_digest != run.canonical_digest
            or attempt.step_run_id != step.step_run_id
            or attempt.step_run_digest != step.canonical_digest
            or attempt.plan_id != run.plan_id
            or attempt.plan_digest != run.plan_digest
            or attempt.scope != context.scope
            or attempt.target_id not in context.authorized_target_ids
            or attempt.lease_id != run.lease_id
            or attempt.lease_digest != lease_digest
            or attempt.fencing_token != run.fencing_token
            or attempt.materialized_by_subject_id != context.subject_id
            or attempt.attempt_number != 1
            or attempt.state is not WorkflowExecutionAttemptState.CREATED
            or any(attempt.authority.canonical_value().values())
            or attempt.grants_execution_authority
        ):
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_repository_scope_violation",
                "The attempt repository returned an incorrectly bound record.",
            )

    async def _deny(self, context: WorkflowWorkerContext, code: str, key: str) -> NoReturn:
        await self._audit(context, code, key)
        raise WorkflowAttemptMaterializationError(code, "The workflow resource is unavailable.")

    async def _audit(
        self,
        context: WorkflowWorkerContext,
        code: str,
        key: str,
        attempt: WorkflowExecutionAttempt | None = None,
    ) -> None:
        success = code.endswith("authorized") or code.endswith("replayed")
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.attempt.materialization.succeeded"
                    if success
                    else "atlas.workflow.attempt.materialization.denied"
                ),
                schema_version="1.0",
                producer="project-atlas-worker-control",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.attempt.materialize",
                resource_type="resource.workflow-attempt",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-attempt",
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded" if success else "denied",
                result_code=code,
                idempotency_key=key,
                target_metadata=(
                    ("attempt_id", "none" if attempt is None else attempt.attempt_id),
                    ("dispatch_authority", "false"),
                    ("execution_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _is_worker(context: WorkflowWorkerContext) -> bool:
        return (
            context.actor_type == "service"
            and context.authentication_method == "workload_token"
            and context.credential_audience == WORKFLOW_WORKER_AUDIENCE
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(char.isspace() for char in normalized):
            raise WorkflowAttemptMaterializationError(
                f"workflow_attempt_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_idempotency_key_invalid", "The idempotency key is invalid."
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowAttemptMaterializationError(
                f"workflow_attempt_{name}_invalid", f"{name} must be a SHA-256 digest."
            )
        return value


__all__ = ["WorkflowAttemptMaterializationService"]
