from __future__ import annotations

from hashlib import sha256
from typing import NoReturn
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.attempt_ports import (
    WorkflowAttemptMaterializationRepository,
)
from atlas.modules.workflows.application.dispatch_intent_ports import (
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingRepository,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingStatus,
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
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
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


class WorkflowDispatchIntentStagingService:
    """Stages immutable dispatch evidence without publishing or delivering work."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        lease_repository: WorkflowOrchestrationLeaseRepository,
        run_repository: WorkflowRunMaterializationRepository,
        attempt_repository: WorkflowAttemptMaterializationRepository,
        dispatch_intent_repository: WorkflowDispatchIntentStagingRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._plan_repository = plan_repository
        self._lease_repository = lease_repository
        self._run_repository = run_repository
        self._attempt_repository = attempt_repository
        self._dispatch_intent_repository = dispatch_intent_repository
        self._audit_sink = audit_sink

    @property
    def repository(self) -> WorkflowDispatchIntentStagingRepository:
        return self._dispatch_intent_repository

    @property
    def durable(self) -> bool:
        return self._dispatch_intent_repository.durable

    async def stage(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        run_id: str,
        run_digest: str,
        step_run_id: str,
        step_run_digest: str,
        attempt_id: str,
        attempt_digest: str,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        idempotency_key: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowDispatchIntent:
        if not self._is_worker(context):
            await self._audit(context, "workflow_dispatch_intent_worker_required", idempotency_key)
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_worker_required",
                "A workflow worker identity is required.",
            )
        plan_id = self._identifier(plan_id, "plan_id")
        run_id = self._identifier(run_id, "run_id")
        step_run_id = self._identifier(step_run_id, "step_run_id")
        attempt_id = self._identifier(attempt_id, "attempt_id")
        lease_id = self._identifier(lease_id, "lease_id")
        plan_digest = self._digest(plan_digest, "plan_digest")
        run_digest = self._digest(run_digest, "run_digest")
        step_run_digest = self._digest(step_run_digest, "step_run_digest")
        attempt_digest = self._digest(attempt_digest, "attempt_digest")
        lease_digest = self._digest(lease_digest, "lease_digest")
        idempotency_key = self._idempotency_key(idempotency_key)
        if fencing_token < 1:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_fencing_token_invalid",
                "The fencing token is invalid.",
            )

        plan = await self._plan_repository.get_by_id(plan_id=plan_id)
        if (
            plan is None
            or plan.scope != context.scope
            or plan.target_id not in context.authorized_target_ids
            or plan.target_type != "storage"
        ):
            await self._deny(context, "workflow_dispatch_intent_plan_not_found", idempotency_key)
        if plan.state is not WorkflowPlanState.PLANNED or plan.canonical_digest != plan_digest:
            await self._deny(context, "workflow_dispatch_intent_plan_conflict", idempotency_key)

        run = await self._run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if not self._run_matches(run, plan.canonical_digest, run_id, run_digest, context):
            await self._deny(context, "workflow_dispatch_intent_run_conflict", idempotency_key)
        assert run is not None
        step = next((item for item in run.step_runs if item.step_run_id == step_run_id), None)
        if (
            step is None
            or step.canonical_digest != step_run_digest
            or step.state is not WorkflowExecutionStepRunState.NOT_STARTED
        ):
            await self._deny(context, "workflow_dispatch_intent_step_ineligible", idempotency_key)
        assert step is not None

        attempts = await self._attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
        attempt = next((item for item in attempts if item.attempt_id == attempt_id), None)
        if not self._attempt_matches(
            attempt,
            attempt_digest=attempt_digest,
            run=run,
            step=step,
            context=context,
        ):
            await self._deny(
                context, "workflow_dispatch_intent_attempt_ineligible", idempotency_key
            )
        assert attempt is not None

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
            or attempt.lease_id != lease.lease_id
            or attempt.fencing_token != lease.fencing_token
            or lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            or lease.grants_execution_authority
        ):
            await self._deny(context, "workflow_dispatch_intent_lease_conflict", idempotency_key)

        fingerprint = canonical_digest(
            {
                "attempt_digest": attempt.canonical_digest,
                "attempt_id": attempt.attempt_id,
                "fencing_token": fencing_token,
                "lease_digest": lease_digest,
                "lease_id": lease_id,
                "operation": "workflow.dispatch-intent.stage",
                "plan_digest": plan.canonical_digest,
                "plan_id": plan.plan_id,
                "run_digest": run.canonical_digest,
                "run_id": run.run_id,
                "scope": run.scope.canonical_value(),
                "step_run_digest": step.canonical_digest,
                "step_run_id": step.step_run_id,
                "target_id": run.target_id,
                "target_type": run.target_type,
                "worker_subject_id": context.subject_id,
            }
        )
        prior = await self._dispatch_intent_repository.get_dispatch_intent_staging_request(
            scope=context.scope,
            worker_subject_id=context.subject_id,
            idempotency_key=idempotency_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context, "workflow_dispatch_intent_idempotency_conflict", idempotency_key
                )
            self._validate_dispatch_intent(
                prior.dispatch_intent, attempt, run, step, lease_digest, context
            )
            await self._audit(
                context,
                "workflow_dispatch_intent_staging_replayed",
                idempotency_key,
                prior.dispatch_intent,
            )
            return prior.dispatch_intent

        dispatch_intent = self._build_dispatch_intent(attempt, run, step, lease_digest, context)
        await self._audit(
            context,
            "workflow_dispatch_intent_staged",
            idempotency_key,
            dispatch_intent,
        )
        try:
            result = await self._dispatch_intent_repository.stage_dispatch_intent(
                WorkflowDispatchIntentStagingRequest(
                    candidate=dispatch_intent,
                    expected_plan_digest=plan.canonical_digest,
                    expected_run_digest=run.canonical_digest,
                    expected_step_run_digest=step.canonical_digest,
                    expected_attempt_digest=attempt.canonical_digest,
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
            await self._audit(
                context, "workflow_dispatch_intent_repository_failure", idempotency_key
            )
            raise
        if (
            result.status
            in {
                WorkflowDispatchIntentStagingStatus.STAGED,
                WorkflowDispatchIntentStagingStatus.REPLAY,
            }
            and result.dispatch_intent is not None
        ):
            self._validate_dispatch_intent(
                result.dispatch_intent, attempt, run, step, lease_digest, context
            )
            return result.dispatch_intent
        code = (
            "workflow_dispatch_intent_idempotency_conflict"
            if result.status is WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
            else "workflow_dispatch_intent_state_conflict"
        )
        await self._audit(context, code, idempotency_key)
        raise WorkflowDispatchIntentStagingError(code, "Dispatch intent staging was rejected.")

    @staticmethod
    def _build_dispatch_intent(
        attempt: WorkflowExecutionAttempt,
        run: WorkflowExecutionRun,
        step: WorkflowExecutionStepRun,
        lease_digest: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowDispatchIntent:
        dispatch_intent_id = (
            "workflow-dispatch-intent."
            + sha256(f"{attempt.attempt_id}:staged".encode()).hexdigest()[:24]
        )
        authority = WorkflowPlanAuthority()
        payload = {
            "attempt_digest": attempt.canonical_digest,
            "attempt_id": attempt.attempt_id,
            "attempt_number": attempt.attempt_number,
            "authority": authority.canonical_value(),
            "dispatch_intent_id": dispatch_intent_id,
            "fencing_token": run.fencing_token,
            "lease_digest": lease_digest,
            "lease_id": run.lease_id,
            "plan_digest": run.plan_digest,
            "plan_id": run.plan_id,
            "run_digest": run.canonical_digest,
            "run_id": run.run_id,
            "scope": run.scope.canonical_value(),
            "staged_at": context.requested_at.isoformat(),
            "state": WorkflowDispatchIntentState.STAGED.value,
            "step_id": step.step_id,
            "step_run_digest": step.canonical_digest,
            "step_run_id": step.step_run_id,
            "target_id": run.target_id,
            "target_type": run.target_type,
            "worker_subject_id": context.subject_id,
        }
        return WorkflowDispatchIntent(
            dispatch_intent_id=dispatch_intent_id,
            plan_id=run.plan_id,
            plan_digest=run.plan_digest,
            run_id=run.run_id,
            run_digest=run.canonical_digest,
            step_run_id=step.step_run_id,
            step_run_digest=step.canonical_digest,
            step_id=step.step_id,
            attempt_id=attempt.attempt_id,
            attempt_digest=attempt.canonical_digest,
            attempt_number=attempt.attempt_number,
            scope=run.scope,
            target_id=run.target_id,
            target_type=run.target_type,
            lease_id=run.lease_id,
            lease_digest=lease_digest,
            fencing_token=run.fencing_token,
            worker_subject_id=context.subject_id,
            staged_at=context.requested_at,
            state=WorkflowDispatchIntentState.STAGED,
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
    def _attempt_matches(
        attempt: WorkflowExecutionAttempt | None,
        *,
        attempt_digest: str,
        run: WorkflowExecutionRun,
        step: WorkflowExecutionStepRun,
        context: WorkflowWorkerContext,
    ) -> bool:
        return bool(
            attempt is not None
            and attempt.canonical_digest == attempt_digest
            and attempt.run_id == run.run_id
            and attempt.run_digest == run.canonical_digest
            and attempt.step_run_id == step.step_run_id
            and attempt.step_run_digest == step.canonical_digest
            and attempt.plan_id == run.plan_id
            and attempt.plan_digest == run.plan_digest
            and attempt.scope == context.scope
            and attempt.target_id in context.authorized_target_ids
            and attempt.target_type == run.target_type
            and attempt.attempt_number == 1
            and attempt.state is WorkflowExecutionAttemptState.CREATED
            and not any(attempt.authority.canonical_value().values())
            and not attempt.grants_execution_authority
        )

    @staticmethod
    def _validate_dispatch_intent(
        dispatch_intent: WorkflowDispatchIntent,
        attempt: WorkflowExecutionAttempt,
        run: WorkflowExecutionRun,
        step: WorkflowExecutionStepRun,
        lease_digest: str,
        context: WorkflowWorkerContext,
    ) -> None:
        if (
            dispatch_intent.plan_id != run.plan_id
            or dispatch_intent.plan_digest != run.plan_digest
            or dispatch_intent.run_id != run.run_id
            or dispatch_intent.run_digest != run.canonical_digest
            or dispatch_intent.step_run_id != step.step_run_id
            or dispatch_intent.step_run_digest != step.canonical_digest
            or dispatch_intent.step_id != step.step_id
            or dispatch_intent.attempt_id != attempt.attempt_id
            or dispatch_intent.attempt_digest != attempt.canonical_digest
            or dispatch_intent.attempt_number != attempt.attempt_number
            or dispatch_intent.scope != context.scope
            or dispatch_intent.target_id not in context.authorized_target_ids
            or dispatch_intent.target_type != run.target_type
            or dispatch_intent.lease_id != run.lease_id
            or dispatch_intent.lease_digest != lease_digest
            or dispatch_intent.fencing_token != run.fencing_token
            or dispatch_intent.worker_subject_id != context.subject_id
            or dispatch_intent.state is not WorkflowDispatchIntentState.STAGED
            or any(dispatch_intent.authority.canonical_value().values())
            or dispatch_intent.grants_publication_authority
            or dispatch_intent.grants_delivery_authority
            or dispatch_intent.grants_dispatch_authority
            or dispatch_intent.grants_execution_authority
        ):
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_scope_violation",
                "The dispatch intent repository returned an incorrectly bound record.",
            )

    async def _deny(self, context: WorkflowWorkerContext, code: str, key: str) -> NoReturn:
        await self._audit(context, code, key)
        raise WorkflowDispatchIntentStagingError(code, "The workflow resource is unavailable.")

    async def _audit(
        self,
        context: WorkflowWorkerContext,
        code: str,
        key: str,
        dispatch_intent: WorkflowDispatchIntent | None = None,
    ) -> None:
        success = code.endswith("staged") or code.endswith("replayed")
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.dispatch-intent.staging.succeeded"
                    if success
                    else "atlas.workflow.dispatch-intent.staging.denied"
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
                permission_id="workflow.dispatch-intent.stage",
                resource_type="resource.workflow-dispatch-intent",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-dispatch-intent",
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded" if success else "denied",
                result_code=code,
                idempotency_key=key,
                target_metadata=(
                    (
                        "dispatch_intent_id",
                        "none" if dispatch_intent is None else dispatch_intent.dispatch_intent_id,
                    ),
                    ("broker_publication", "false"),
                    ("queue_delivery", "false"),
                    ("worker_dispatch_authority", "false"),
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
            raise WorkflowDispatchIntentStagingError(
                f"workflow_dispatch_intent_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowDispatchIntentStagingError(
                f"workflow_dispatch_intent_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = ["WorkflowDispatchIntentStagingService"]
