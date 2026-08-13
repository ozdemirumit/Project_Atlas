from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.ports import (
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationStatus,
    WorkflowPlanMutationStatus,
    WorkflowPlanningError,
    WorkflowPlanRepository,
)
from atlas.modules.workflows.domain import (
    NO_EXECUTION_SAFETY_NOTICE,
    WorkflowDefinition,
    WorkflowDefinitionRegistry,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowPlanStep,
    WorkflowPlanTransition,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
)


@dataclass(frozen=True, slots=True)
class WorkflowAccessContext:
    subject_id: str
    role_ids: frozenset[str]
    actor_type: str
    authentication_method: str
    assurance_level: str
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
            self.assurance_level,
            self.correlation_id,
            self.decision_id,
        )
        if any(not value or value != value.strip() or len(value) > 240 for value in identifiers):
            raise ValueError("workflow access context contains an invalid identifier")
        if not self.role_ids:
            raise ValueError("workflow access context requires an authorized role")
        if any(not role_id.strip() or len(role_id) > 240 for role_id in self.role_ids):
            raise ValueError("workflow access context contains an invalid role")
        if any(
            not target_id.strip() or len(target_id) > 240
            for target_id in self.authorized_target_ids
        ):
            raise ValueError("workflow access context contains an invalid target")
        if self.requested_at.tzinfo is None:
            raise ValueError("workflow requested_at must be timezone-aware")


class WorkflowPlanningService:
    def __init__(
        self,
        *,
        registry: WorkflowDefinitionRegistry,
        repository: WorkflowPlanRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def repository(self) -> WorkflowPlanRepository:
        return self._repository

    async def close(self) -> None:
        await self._repository.close()

    async def list_definitions(
        self, *, context: WorkflowAccessContext
    ) -> tuple[WorkflowDefinition, ...]:
        self._require_human(context)
        definitions = self._registry.list_active()
        await self._audit(
            context,
            event_type="atlas.workflow.definition.list.read",
            permission_id="workflow.definition.read",
            outcome="succeeded",
            result_code="workflow_definitions_returned",
            metadata=(("result_count", str(len(definitions))),),
        )
        return definitions

    async def create_plan(
        self,
        *,
        definition_id: str,
        definition_version: int,
        target_id: str,
        inputs: Mapping[str, object],
        idempotency_key: str,
        context: WorkflowAccessContext,
    ) -> WorkflowRunPlan:
        self._require_human(context)
        normalized_definition_id = self._identifier(definition_id, name="definition_id")
        normalized_target_id = self._identifier(target_id, name="target_id")
        normalized_key = self._idempotency_key(idempotency_key)
        if definition_version < 1:
            raise WorkflowPlanningError(
                "workflow_definition_invalid", "The workflow definition version is invalid."
            )
        definition = self._registry.get(normalized_definition_id, definition_version)
        if definition is None:
            await self._audit_denial(
                context,
                result_code="workflow_definition_unavailable",
                idempotency_key=normalized_key,
            )
            raise WorkflowPlanningError(
                "workflow_definition_unavailable",
                "The requested workflow definition is unavailable.",
            )
        if normalized_target_id not in context.authorized_target_ids:
            await self._audit_denial(
                context,
                result_code="workflow_target_unavailable",
                idempotency_key=normalized_key,
            )
            raise WorkflowPlanningError(
                "workflow_target_unavailable", "The requested storage target is unavailable."
            )
        input_digest = self._input_digest(inputs)
        fingerprint = canonical_digest(
            {
                "canonical_input_digest": input_digest,
                "creator_subject_id": context.subject_id,
                "definition_digest": definition.definition_digest,
                "definition_id": definition.definition_id,
                "definition_version": definition.version,
                "operation": "workflow.plan.create",
                "scope": context.scope.canonical_value(),
                "target_id": normalized_target_id,
                "target_type": "storage",
            }
        )
        prior = await self._repository.get_create_request(
            scope=context.scope,
            creator_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._audit_denial(
                    context,
                    result_code="workflow_idempotency_conflict",
                    idempotency_key=normalized_key,
                )
                raise WorkflowPlanningError(
                    "workflow_idempotency_conflict",
                    "The idempotency key was already used for a different plan.",
                )
            self._validate_visible(prior.plan, context)
            await self._audit(
                context,
                event_type="atlas.workflow.plan.create.replayed",
                permission_id="workflow.plan.create",
                outcome="succeeded",
                result_code="workflow_plan_replayed",
                idempotency_key=normalized_key,
                plan=prior.plan,
            )
            return prior.plan

        plan = self._build_plan(
            definition=definition,
            target_id=normalized_target_id,
            input_digest=input_digest,
            context=context,
            idempotency_key=normalized_key,
            fingerprint=fingerprint,
        )
        # A failed audit must leave no plan behind, including in durable repositories.
        await self._audit(
            context,
            event_type="atlas.workflow.plan.create.authorized",
            permission_id="workflow.plan.create",
            outcome="succeeded",
            result_code="workflow_plan_authorized",
            idempotency_key=normalized_key,
            plan=plan,
        )
        result = await self._repository.create(
            plan,
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
        )
        if result.status in {WorkflowPlanMutationStatus.CREATED, WorkflowPlanMutationStatus.REPLAY}:
            if result.plan is None:
                raise WorkflowPlanningError(
                    "workflow_repository_contract_violation",
                    "The workflow repository returned an incomplete mutation result.",
                )
            self._validate_visible(result.plan, context)
            return result.plan
        raise WorkflowPlanningError(
            "workflow_idempotency_conflict",
            "The idempotency key was concurrently used for a different plan.",
        )

    async def list_plans(
        self, *, context: WorkflowAccessContext, limit: int = 50
    ) -> tuple[WorkflowRunPlan, ...]:
        self._require_human(context)
        if not 1 <= limit <= 100:
            raise WorkflowPlanningError(
                "workflow_plan_limit_invalid", "Workflow plan limit must be between 1 and 100."
            )
        plans = await self._repository.list_scoped(
            scope=context.scope,
            authorized_target_ids=context.authorized_target_ids,
            limit=limit,
        )
        if any(not self._is_visible(plan, context) for plan in plans):
            raise WorkflowPlanningError(
                "workflow_repository_scope_violation",
                "The workflow repository returned data outside the authorized scope.",
            )
        await self._audit(
            context,
            event_type="atlas.workflow.plan.list.read",
            permission_id="workflow.plan.read",
            outcome="succeeded",
            result_code="workflow_plans_returned",
            metadata=(("result_count", str(len(plans))),),
        )
        return plans

    async def cancel_plan(
        self,
        *,
        plan_id: str,
        reason: str,
        acknowledge_no_external_undo: bool,
        idempotency_key: str,
        context: WorkflowAccessContext,
    ) -> WorkflowRunPlan:
        self._require_human(context)
        normalized_plan_id = self._identifier(plan_id, name="plan_id")
        normalized_reason = self._cancellation_reason(reason)
        normalized_key = self._idempotency_key(idempotency_key)
        if acknowledge_no_external_undo is not True:
            raise WorkflowPlanningError(
                "workflow_cancellation_acknowledgement_required",
                "Cancellation requires acknowledgement that it cannot undo external work.",
            )
        current = await self._repository.get_by_id(plan_id=normalized_plan_id)
        if current is None or not self._is_visible(current, context):
            await self._audit_cancellation_denial(
                context,
                result_code="workflow_plan_not_found",
                idempotency_key=normalized_key,
            )
            raise WorkflowPlanningError(
                "workflow_plan_not_found", "The requested workflow plan is unavailable."
            )
        fingerprint = canonical_digest(
            {
                "acknowledge_no_external_undo": True,
                "actor_subject_id": context.subject_id,
                "operation": "workflow.plan.cancel",
                "plan_id": current.plan_id,
                "reason": normalized_reason,
                "scope": context.scope.canonical_value(),
                "target_id": current.target_id,
                "target_type": current.target_type,
            }
        )
        prior = await self._repository.get_cancellation_request(
            scope=context.scope,
            actor_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._audit_cancellation_denial(
                    context,
                    result_code="workflow_cancellation_idempotency_conflict",
                    idempotency_key=normalized_key,
                    plan=current,
                )
                raise WorkflowPlanningError(
                    "workflow_cancellation_idempotency_conflict",
                    "The idempotency key was already used for a different cancellation.",
                )
            self._validate_visible(prior.plan, context)
            await self._audit(
                context,
                event_type="atlas.workflow.plan.cancel.replayed",
                permission_id="workflow.plan.cancel",
                outcome="succeeded",
                result_code="workflow_plan_cancellation_replayed",
                idempotency_key=normalized_key,
                plan=prior.plan,
            )
            return prior.plan
        if current.state is not WorkflowPlanState.PLANNED:
            await self._audit_cancellation_denial(
                context,
                result_code="workflow_plan_not_cancellable",
                idempotency_key=normalized_key,
                plan=current,
            )
            raise WorkflowPlanningError(
                "workflow_plan_not_cancellable", "The workflow plan is already terminal."
            )
        cancelled = self._build_cancelled_plan(
            current=current,
            reason=normalized_reason,
            idempotency_key=normalized_key,
            fingerprint=fingerprint,
            context=context,
        )
        result = await self._repository.cancel(
            WorkflowPlanCancellationRequest(
                expected_plan_digest=current.canonical_digest,
                cancelled_plan=cancelled,
                actor_subject_id=context.subject_id,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if result.status in {
            WorkflowPlanCancellationStatus.CANCELLED,
            WorkflowPlanCancellationStatus.REPLAY,
        }:
            if result.plan is None:
                raise WorkflowPlanningError(
                    "workflow_repository_contract_violation",
                    "The workflow repository returned an incomplete cancellation result.",
                )
            self._validate_visible(result.plan, context)
            await self._audit(
                context,
                event_type=(
                    "atlas.workflow.plan.cancel.replayed"
                    if result.status is WorkflowPlanCancellationStatus.REPLAY
                    else "atlas.workflow.plan.cancelled"
                ),
                permission_id="workflow.plan.cancel",
                outcome="succeeded",
                result_code=(
                    "workflow_plan_cancellation_replayed"
                    if result.status is WorkflowPlanCancellationStatus.REPLAY
                    else "workflow_plan_cancelled"
                ),
                idempotency_key=normalized_key,
                plan=result.plan,
                metadata=(("reason_digest", result.plan.transition_history[-1].reason_digest),),
            )
            return result.plan
        if result.status is WorkflowPlanCancellationStatus.IDEMPOTENCY_CONFLICT:
            code = "workflow_cancellation_idempotency_conflict"
            detail = "The idempotency key was already used for a different cancellation."
        elif result.status is WorkflowPlanCancellationStatus.STATE_CONFLICT:
            code = "workflow_cancellation_state_conflict"
            detail = "The workflow plan changed; reload it before cancelling."
        else:
            code = "workflow_plan_not_found"
            detail = "The requested workflow plan is unavailable."
        await self._audit_cancellation_denial(
            context,
            result_code=code,
            idempotency_key=normalized_key,
            plan=result.plan,
        )
        raise WorkflowPlanningError(code, detail)

    async def get_plan(self, *, plan_id: str, context: WorkflowAccessContext) -> WorkflowRunPlan:
        self._require_human(context)
        normalized_plan_id = self._identifier(plan_id, name="plan_id")
        plan = await self._repository.get_by_id(plan_id=normalized_plan_id)
        if plan is None or not self._is_visible(plan, context):
            await self._audit_denial(context, result_code="workflow_plan_not_found")
            raise WorkflowPlanningError(
                "workflow_plan_not_found", "The requested workflow plan is unavailable."
            )
        await self._audit(
            context,
            event_type="atlas.workflow.plan.read",
            permission_id="workflow.plan.read",
            outcome="succeeded",
            result_code="workflow_plan_returned",
            plan=plan,
        )
        return plan

    def _build_plan(
        self,
        *,
        definition: WorkflowDefinition,
        target_id: str,
        input_digest: str,
        context: WorkflowAccessContext,
        idempotency_key: str,
        fingerprint: str,
    ) -> WorkflowRunPlan:
        identity_seed = ":".join(
            (
                context.scope.organization_id,
                context.scope.environment_id,
                context.scope.site_id,
                context.subject_id,
                idempotency_key,
                fingerprint,
            )
        )
        plan_id = f"workflow-plan.{sha256(identity_seed.encode()).hexdigest()[:24]}"
        steps = tuple(
            WorkflowPlanStep(
                step_id=step.step_id,
                ordinal=step.ordinal,
                kind=step.kind,
                capability_class=step.capability_class,
            )
            for step in definition.steps
        )
        authority = WorkflowPlanAuthority()
        payload = {
            "authority": authority.canonical_value(),
            "canonical_input_digest": input_digest,
            "created_at": context.requested_at.isoformat(),
            "creator_subject_id": context.subject_id,
            "definition_digest": definition.definition_digest,
            "definition_id": definition.definition_id,
            "definition_version": definition.version,
            "durable": self._repository.durable,
            "plan_id": plan_id,
            "safety_notice": NO_EXECUTION_SAFETY_NOTICE,
            "scope": context.scope.canonical_value(),
            "state": WorkflowPlanState.PLANNED.value,
            "steps": [step.canonical_value() for step in steps],
            "target_id": target_id,
            "target_type": "storage",
        }
        return WorkflowRunPlan(
            plan_id=plan_id,
            definition_id=definition.definition_id,
            definition_version=definition.version,
            definition_digest=definition.definition_digest,
            scope=context.scope,
            target_id=target_id,
            target_type="storage",
            canonical_input_digest=input_digest,
            creator_subject_id=context.subject_id,
            created_at=context.requested_at,
            state=WorkflowPlanState.PLANNED,
            steps=steps,
            durable=self._repository.durable,
            authority=authority,
            safety_notice=NO_EXECUTION_SAFETY_NOTICE,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _build_cancelled_plan(
        *,
        current: WorkflowRunPlan,
        reason: str,
        idempotency_key: str,
        fingerprint: str,
        context: WorkflowAccessContext,
    ) -> WorkflowRunPlan:
        transition_id = (
            "workflow-transition."
            + sha256(
                f"{current.plan_id}:{context.subject_id}:{idempotency_key}:{fingerprint}".encode()
            ).hexdigest()[:24]
        )
        reason_digest = canonical_digest({"reason": reason})
        transition_payload = {
            "actor_subject_id": context.subject_id,
            "correlation_id": context.correlation_id,
            "new_state": WorkflowPlanState.CANCELLED.value,
            "occurred_at": context.requested_at.isoformat(),
            "prior_state": WorkflowPlanState.PLANNED.value,
            "reason": reason,
            "reason_digest": reason_digest,
            "scope": current.scope.canonical_value(),
            "target_id": current.target_id,
            "target_type": current.target_type,
            "transition_id": transition_id,
        }
        transition = WorkflowPlanTransition(
            transition_id=transition_id,
            prior_state=WorkflowPlanState.PLANNED,
            new_state=WorkflowPlanState.CANCELLED,
            actor_subject_id=context.subject_id,
            scope=current.scope,
            target_id=current.target_id,
            target_type=current.target_type,
            reason=reason,
            reason_digest=reason_digest,
            correlation_id=context.correlation_id,
            occurred_at=context.requested_at,
            canonical_digest=canonical_digest(transition_payload),
        )
        history = (*current.transition_history, transition)
        payload = current.digest_payload()
        payload["state"] = WorkflowPlanState.CANCELLED.value
        payload["transition_history"] = [item.canonical_value() for item in history]
        return replace(
            current,
            state=WorkflowPlanState.CANCELLED,
            transition_history=history,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _input_digest(inputs: Mapping[str, object]) -> str:
        if not isinstance(inputs, Mapping):
            raise WorkflowPlanningError(
                "workflow_inputs_invalid", "Workflow inputs must be a JSON object."
            )
        try:
            serialized = json.dumps(
                dict(inputs),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_inputs_invalid", "Workflow inputs must contain finite JSON values."
            ) from exc
        if len(serialized.encode()) > 16_384:
            raise WorkflowPlanningError(
                "workflow_inputs_too_large", "Workflow inputs exceed the planning limit."
            )
        return sha256(serialized.encode()).hexdigest()

    @staticmethod
    def _identifier(value: str, *, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(char.isspace() for char in normalized):
            raise WorkflowPlanningError(f"workflow_{name}_invalid", f"{name} is invalid.")
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, name="idempotency_key")
        if not 8 <= len(normalized) <= 200:
            raise WorkflowPlanningError(
                "workflow_idempotency_key_invalid",
                "Idempotency key must contain 8 to 200 characters.",
            )
        return normalized

    @staticmethod
    def _cancellation_reason(value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or len(normalized) > 500:
            raise WorkflowPlanningError(
                "workflow_cancellation_reason_invalid",
                "Cancellation reason must contain 1 to 500 normalized characters.",
            )
        return normalized

    @staticmethod
    def _require_human(context: WorkflowAccessContext) -> None:
        if context.actor_type != "human":
            raise WorkflowPlanningError(
                "workflow_human_required", "Workflow planning requires a human actor."
            )

    @staticmethod
    def _is_visible(plan: WorkflowRunPlan, context: WorkflowAccessContext) -> bool:
        return (
            plan.scope == context.scope
            and plan.target_type == "storage"
            and plan.target_id in context.authorized_target_ids
        )

    @classmethod
    def _validate_visible(cls, plan: WorkflowRunPlan, context: WorkflowAccessContext) -> None:
        if not cls._is_visible(plan, context):
            raise WorkflowPlanningError(
                "workflow_plan_not_found", "The requested workflow plan is unavailable."
            )

    async def _audit_denial(
        self,
        context: WorkflowAccessContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
    ) -> None:
        await self._audit(
            context,
            event_type="atlas.workflow.plan.denied",
            permission_id="workflow.plan.create",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
        )

    async def _audit_cancellation_denial(
        self,
        context: WorkflowAccessContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        plan: WorkflowRunPlan | None = None,
    ) -> None:
        await self._audit(
            context,
            event_type="atlas.workflow.plan.cancel.denied",
            permission_id="workflow.plan.cancel",
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            plan=plan,
        )

    async def _audit(
        self,
        context: WorkflowAccessContext,
        *,
        event_type: str,
        permission_id: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None = None,
        plan: WorkflowRunPlan | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> None:
        target_metadata = list(metadata)
        if plan is not None:
            target_metadata.extend(
                (
                    ("plan_id", plan.plan_id),
                    ("plan_digest", plan.canonical_digest),
                    ("definition_id", plan.definition_id),
                    ("definition_version", str(plan.definition_version)),
                    ("definition_digest", plan.definition_digest),
                    ("target_id", plan.target_id),
                    ("durable", str(plan.durable).lower()),
                )
            )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id=permission_id,
                resource_type="resource.workflow-plan",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-plan",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=tuple(target_metadata),
            )
        )
