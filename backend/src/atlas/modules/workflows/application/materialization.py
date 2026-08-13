from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.materialization_ports import (
    WorkflowRunMaterializationError,
    WorkflowRunMaterializationRepository,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationStatus,
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
    WorkflowDefinition,
    WorkflowDefinitionRegistry,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRun,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowRunPlan,
    canonical_digest,
)


class WorkflowRunMaterializationService:
    """Materializes immutable run identities without creating attempts or dispatching work."""

    def __init__(
        self,
        *,
        registry: WorkflowDefinitionRegistry,
        plan_repository: WorkflowPlanRepository,
        lease_repository: WorkflowOrchestrationLeaseRepository,
        run_repository: WorkflowRunMaterializationRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._registry = registry
        self._plan_repository = plan_repository
        self._lease_repository = lease_repository
        self._run_repository = run_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._run_repository.durable

    @property
    def repository(self) -> WorkflowRunMaterializationRepository:
        return self._run_repository

    async def materialize(
        self,
        *,
        plan_id: str,
        plan_digest: str,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        idempotency_key: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowExecutionRun:
        if not self._is_worker(context):
            await self._audit_denied(
                context, "workflow_worker_identity_required", idempotency_key or "invalid"
            )
            raise WorkflowRunMaterializationError(
                "workflow_worker_identity_required", "A workflow worker identity is required."
            )
        plan_id = self._identifier(plan_id, "plan_id")
        plan_digest = self._digest(plan_digest, "plan_digest")
        lease_id = self._identifier(lease_id, "lease_id")
        lease_digest = self._digest(lease_digest, "lease_digest")
        idempotency_key = self._idempotency_key(idempotency_key)
        if fencing_token < 1:
            raise WorkflowRunMaterializationError(
                "workflow_run_fencing_token_invalid", "The fencing token is invalid."
            )
        plan = await self._plan_repository.get_by_id(plan_id=plan_id)
        if (
            plan is None
            or plan.scope != context.scope
            or plan.target_id not in context.authorized_target_ids
            or plan.target_type != "storage"
        ):
            await self._audit_denied(context, "workflow_run_plan_not_found", idempotency_key)
            raise WorkflowRunMaterializationError(
                "workflow_run_plan_not_found", "The workflow plan is unavailable."
            )
        if plan.state is not WorkflowPlanState.PLANNED or plan.canonical_digest != plan_digest:
            await self._audit_denied(context, "workflow_run_plan_conflict", idempotency_key)
            raise WorkflowRunMaterializationError(
                "workflow_run_plan_conflict", "The workflow plan is terminal or changed."
            )
        definition = self._registry.get(plan.definition_id, plan.definition_version)
        if definition is None or definition.definition_digest != plan.definition_digest:
            await self._audit_denied(context, "workflow_run_definition_conflict", idempotency_key)
            raise WorkflowRunMaterializationError(
                "workflow_run_definition_conflict", "The workflow definition is unavailable."
            )
        lease = await self._lease_repository.get_lease_by_plan_id(plan_id=plan.plan_id)
        if (
            lease is None
            or lease.lease_id != lease_id
            or lease.canonical_digest != lease_digest
            or lease.fencing_token != fencing_token
            or lease.plan_digest != plan.canonical_digest
            or lease.scope != plan.scope
            or lease.target_id != plan.target_id
            or lease.target_type != plan.target_type
            or lease.worker_subject_id != context.subject_id
            or lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            or lease.grants_execution_authority
        ):
            await self._audit_denied(context, "workflow_run_lease_conflict", idempotency_key)
            raise WorkflowRunMaterializationError(
                "workflow_run_lease_conflict", "The workflow orchestration lease is unavailable."
            )
        fingerprint = canonical_digest(
            {
                "definition_digest": definition.definition_digest,
                "fencing_token": fencing_token,
                "lease_digest": lease_digest,
                "lease_id": lease_id,
                "operation": "workflow.run.materialize",
                "plan_digest": plan.canonical_digest,
                "plan_id": plan.plan_id,
                "scope": plan.scope.canonical_value(),
                "target_id": plan.target_id,
                "worker_subject_id": context.subject_id,
            }
        )
        prior = await self._run_repository.get_run_materialization_request(
            scope=context.scope,
            worker_subject_id=context.subject_id,
            idempotency_key=idempotency_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._audit_denied(
                    context, "workflow_run_idempotency_conflict", idempotency_key
                )
                raise WorkflowRunMaterializationError(
                    "workflow_run_idempotency_conflict",
                    "The idempotency key was used for a different materialization.",
                )
            self._validate_run(prior.run, plan.canonical_digest, lease_digest, context)
            await self._audit_replayed(context, prior.run, idempotency_key)
            return prior.run
        run = self._build_run(
            definition=definition,
            plan=plan,
            lease_id=lease_id,
            lease_digest=lease_digest,
            fencing_token=fencing_token,
            fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            context=context,
        )
        # Required audit is recorded before any durable state is written.
        await self._audit_authorized(context, run, idempotency_key)
        try:
            result = await self._run_repository.materialize_run(
                WorkflowRunMaterializationRequest(
                    candidate=run,
                    expected_plan_digest=plan.canonical_digest,
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
            await self._audit_denied(context, "workflow_run_repository_failure", idempotency_key)
            raise
        if (
            result.status
            in {
                WorkflowRunMaterializationStatus.CREATED,
                WorkflowRunMaterializationStatus.REPLAY,
            }
            and result.run is not None
        ):
            self._validate_run(result.run, plan.canonical_digest, lease_digest, context)
            return result.run
        code = (
            "workflow_run_idempotency_conflict"
            if result.status is WorkflowRunMaterializationStatus.IDEMPOTENCY_CONFLICT
            else "workflow_run_state_conflict"
        )
        await self._audit_denied(context, code, idempotency_key)
        raise WorkflowRunMaterializationError(code, "Workflow run materialization was rejected.")

    async def get_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        return await self._run_repository.get_materialized_run_by_plan_id(plan_id=plan_id)

    @staticmethod
    def _build_run(
        *,
        definition: WorkflowDefinition,
        plan: WorkflowRunPlan,
        lease_id: str,
        lease_digest: str,
        fencing_token: int,
        fingerprint: str,
        idempotency_key: str,
        context: WorkflowWorkerContext,
    ) -> WorkflowExecutionRun:
        run_id = (
            "workflow-run."
            + sha256(f"{plan.plan_id}:{idempotency_key}:{fingerprint}".encode()).hexdigest()[:24]
        )
        step_runs: list[WorkflowExecutionStepRun] = []
        for step in definition.steps:
            step_run_id = (
                "workflow-step-run."
                + sha256(f"{run_id}:{step.step_id}:{step.ordinal}".encode()).hexdigest()[:24]
            )
            step_payload = {
                "capability_class": step.capability_class.value,
                "depends_on": list(step.depends_on),
                "kind": step.kind.value,
                "ordinal": step.ordinal,
                "run_id": run_id,
                "state": WorkflowExecutionStepRunState.NOT_STARTED.value,
                "step_id": step.step_id,
                "step_run_id": step_run_id,
                "timeout_seconds": step.timeout_seconds,
            }
            step_runs.append(
                WorkflowExecutionStepRun(
                    step_run_id=step_run_id,
                    run_id=run_id,
                    step_id=step.step_id,
                    ordinal=step.ordinal,
                    kind=step.kind,
                    capability_class=step.capability_class,
                    timeout_seconds=step.timeout_seconds,
                    depends_on=step.depends_on,
                    state=WorkflowExecutionStepRunState.NOT_STARTED,
                    canonical_digest=canonical_digest(step_payload),
                )
            )
        authority = WorkflowPlanAuthority()
        payload = {
            "authority": authority.canonical_value(),
            "created_at": context.requested_at.isoformat(),
            "definition_digest": definition.definition_digest,
            "definition_id": definition.definition_id,
            "definition_version": definition.version,
            "fencing_token": fencing_token,
            "lease_digest": lease_digest,
            "lease_id": lease_id,
            "materialized_by_subject_id": context.subject_id,
            "plan_digest": plan.canonical_digest,
            "plan_id": plan.plan_id,
            "run_id": run_id,
            "scope": plan.scope.canonical_value(),
            "state": WorkflowExecutionRunState.CREATED.value,
            "step_runs": [step.canonical_value() for step in step_runs],
            "target_id": plan.target_id,
            "target_type": plan.target_type,
        }
        return WorkflowExecutionRun(
            run_id=run_id,
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            definition_id=definition.definition_id,
            definition_version=definition.version,
            definition_digest=definition.definition_digest,
            scope=plan.scope,
            target_id=plan.target_id,
            target_type=plan.target_type,
            lease_id=lease_id,
            lease_digest=lease_digest,
            fencing_token=fencing_token,
            materialized_by_subject_id=context.subject_id,
            created_at=context.requested_at,
            state=WorkflowExecutionRunState.CREATED,
            step_runs=tuple(step_runs),
            authority=authority,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _validate_run(
        run: WorkflowExecutionRun,
        plan_digest: str,
        lease_digest: str,
        context: WorkflowWorkerContext,
    ) -> None:
        if (
            run.plan_digest != plan_digest
            or run.lease_digest != lease_digest
            or run.scope != context.scope
            or run.target_id not in context.authorized_target_ids
            or run.materialized_by_subject_id != context.subject_id
            or run.state is not WorkflowExecutionRunState.CREATED
            or any(
                step.state is not WorkflowExecutionStepRunState.NOT_STARTED
                for step in run.step_runs
            )
            or any(run.authority.canonical_value().values())
            or run.grants_execution_authority
        ):
            raise WorkflowRunMaterializationError(
                "workflow_run_repository_scope_violation",
                "The run repository returned an incorrectly bound record.",
            )

    @staticmethod
    def _is_worker(context: WorkflowWorkerContext) -> bool:
        return (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_WORKER_AUDIENCE
        ) is False

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(char.isspace() for char in normalized):
            raise WorkflowRunMaterializationError(
                f"workflow_run_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowRunMaterializationError(
                "workflow_run_idempotency_key_invalid", "The idempotency key is invalid."
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowRunMaterializationError(
                f"workflow_run_{name}_invalid", f"{name} must be a SHA-256 digest."
            )
        return value

    async def _audit_authorized(
        self, context: WorkflowWorkerContext, run: WorkflowExecutionRun, key: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.workflow.run.materialization.authorized",
                schema_version="1.0",
                producer="project-atlas-worker-control",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.run.materialize",
                resource_type="resource.workflow-run",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-run",
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code="workflow_run_materialization_authorized",
                idempotency_key=key,
                target_metadata=(
                    ("run_id", run.run_id),
                    ("plan_id", run.plan_id),
                    ("plan_digest", run.plan_digest),
                    ("lease_id", run.lease_id),
                    ("lease_digest", run.lease_digest),
                    ("fencing_token", str(run.fencing_token)),
                    ("execution_authority", "false"),
                ),
            )
        )

    async def _audit_replayed(
        self, context: WorkflowWorkerContext, run: WorkflowExecutionRun, key: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.workflow.run.materialization.replayed",
                schema_version="1.0",
                producer="project-atlas-worker-control",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.run.materialize",
                resource_type="resource.workflow-run",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-run",
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code="workflow_run_materialization_replayed",
                idempotency_key=key,
                target_metadata=(
                    ("run_id", run.run_id),
                    ("plan_id", run.plan_id),
                    ("execution_authority", "false"),
                ),
            )
        )

    async def _audit_denied(self, context: WorkflowWorkerContext, code: str, key: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.workflow.run.materialization.denied",
                schema_version="1.0",
                producer="project-atlas-worker-control",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.run.materialize",
                resource_type="resource.workflow-run",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-run",
                    )
                ),
                decision_id=context.decision_id,
                outcome="denied",
                result_code=code,
                idempotency_key=key,
                target_metadata=(("execution_authority", "false"),),
            )
        )


__all__ = ["WorkflowRunMaterializationService"]
