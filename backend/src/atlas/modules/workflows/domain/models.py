from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

NO_EXECUTION_SAFETY_NOTICE = (
    "Planning only. This record cannot dispatch workers, invoke connectors, create approvals, "
    "mutate ITSM, execute runbooks, or change infrastructure."
)


def canonical_digest(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical payload must contain finite JSON values") from exc
    return sha256(encoded).hexdigest()


def _require_text(value: str, *, name: str, maximum: int) -> None:
    if value != value.strip() or not value or len(value) > maximum:
        raise ValueError(f"{name} must contain 1 to {maximum} normalized characters")


def _require_identifier(value: str, *, name: str) -> None:
    _require_text(value, name=name, maximum=240)
    if any(character.isspace() for character in value):
        raise ValueError(f"{name} must not contain whitespace")


def _require_digest(value: str, *, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


class WorkflowCapabilityClass(StrEnum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"


class WorkflowStepKind(StrEnum):
    EVIDENCE_QUERY = "evidence_query"
    HEALTH_ASSESSMENT = "health_assessment"
    REPORT_GENERATION = "report_generation"


class WorkflowPlanState(StrEnum):
    PLANNED = "planned"
    CANCELLED = "cancelled"


class WorkflowPlanStepState(StrEnum):
    NOT_STARTED = "not_started"


@dataclass(frozen=True, slots=True)
class WorkflowScope:
    organization_id: str
    environment_id: str
    site_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.organization_id, name="organization_id")
        _require_identifier(self.environment_id, name="environment_id")
        _require_identifier(self.site_id, name="site_id")

    def canonical_value(self) -> dict[str, str]:
        return {
            "environment_id": self.environment_id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
        }


@dataclass(frozen=True, slots=True)
class WorkflowStepDefinition:
    step_id: str
    ordinal: int
    title: str
    kind: WorkflowStepKind
    capability_class: WorkflowCapabilityClass
    timeout_seconds: int
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.step_id, name="step_id")
        _require_text(self.title, name="step title", maximum=120)
        if self.ordinal < 1:
            raise ValueError("step ordinal must be positive")
        if not isinstance(self.kind, WorkflowStepKind):
            raise ValueError("unsupported workflow step kind")
        if not isinstance(self.capability_class, WorkflowCapabilityClass):
            raise ValueError("workflow steps are limited to C0-C2 capabilities")
        if not 1 <= self.timeout_seconds <= 3600:
            raise ValueError("step timeout must be between 1 and 3600 seconds")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("step dependencies must be unique")
        for dependency in self.depends_on:
            _require_identifier(dependency, name="step dependency")
        if self.step_id in self.depends_on:
            raise ValueError("a workflow step cannot depend on itself")

    def canonical_value(self) -> dict[str, object]:
        return {
            "capability_class": self.capability_class.value,
            "depends_on": self.depends_on,
            "kind": self.kind.value,
            "ordinal": self.ordinal,
            "step_id": self.step_id,
            "timeout_seconds": self.timeout_seconds,
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    definition_id: str
    version: int
    title: str
    purpose: str
    input_schema_version: str
    steps: tuple[WorkflowStepDefinition, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.definition_id, name="definition_id")
        if self.version < 1:
            raise ValueError("definition version must be positive")
        _require_text(self.title, name="definition title", maximum=120)
        _require_text(self.purpose, name="definition purpose", maximum=500)
        _require_identifier(self.input_schema_version, name="input_schema_version")
        if not 1 <= len(self.steps) <= 50:
            raise ValueError("workflow definitions require between 1 and 50 steps")
        step_ids = tuple(step.step_id for step in self.steps)
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("workflow step identifiers must be unique")
        if tuple(step.ordinal for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("workflow steps must have stable contiguous order")
        known = set(step_ids)
        if any(dependency not in known for step in self.steps for dependency in step.depends_on):
            raise ValueError("workflow definition contains a missing dependency")
        self._validate_acyclic()
        ordinal_by_id = {step.step_id: step.ordinal for step in self.steps}
        if any(
            ordinal_by_id[dependency] >= step.ordinal
            for step in self.steps
            for dependency in step.depends_on
        ):
            raise ValueError("workflow steps must follow dependency order")

    @property
    def definition_digest(self) -> str:
        return canonical_digest(self.canonical_value())

    def canonical_value(self) -> dict[str, object]:
        return {
            "definition_id": self.definition_id,
            "input_schema_version": self.input_schema_version,
            "purpose": self.purpose,
            "steps": [step.canonical_value() for step in self.steps],
            "title": self.title,
            "version": self.version,
        }

    def _validate_acyclic(self) -> None:
        dependencies = {step.step_id: step.depends_on for step in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("workflow definition contains a dependency cycle")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in dependencies:
            visit(step_id)


@dataclass(frozen=True, slots=True)
class WorkflowDefinitionRegistry:
    definitions: tuple[WorkflowDefinition, ...]

    def __post_init__(self) -> None:
        identities = tuple(
            (definition.definition_id, definition.version) for definition in self.definitions
        )
        if not self.definitions or len(identities) != len(set(identities)):
            raise ValueError("workflow definition versions must be unique")
        active_ids = tuple(definition.definition_id for definition in self.definitions)
        if len(active_ids) != len(set(active_ids)):
            raise ValueError(
                "the code-owned registry may expose only one active version per workflow"
            )

    def list_active(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(sorted(self.definitions, key=lambda item: item.definition_id))

    def get(self, definition_id: str, version: int) -> WorkflowDefinition | None:
        return next(
            (
                definition
                for definition in self.definitions
                if definition.definition_id == definition_id and definition.version == version
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class WorkflowPlanAuthority:
    worker_dispatch_authorized: bool = False
    connector_invocation_authorized: bool = False
    approval_creation_authorized: bool = False
    signal_delivery_authorized: bool = False
    retry_authorized: bool = False
    itsm_mutation_authorized: bool = False
    runbook_execution_authorized: bool = False
    infrastructure_change_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("workflow plans cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "approval_creation_authorized": self.approval_creation_authorized,
            "connector_invocation_authorized": self.connector_invocation_authorized,
            "infrastructure_change_authorized": self.infrastructure_change_authorized,
            "itsm_mutation_authorized": self.itsm_mutation_authorized,
            "retry_authorized": self.retry_authorized,
            "runbook_execution_authorized": self.runbook_execution_authorized,
            "signal_delivery_authorized": self.signal_delivery_authorized,
            "worker_dispatch_authorized": self.worker_dispatch_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowPlanStep:
    step_id: str
    ordinal: int
    kind: WorkflowStepKind
    capability_class: WorkflowCapabilityClass
    state: WorkflowPlanStepState = WorkflowPlanStepState.NOT_STARTED

    def __post_init__(self) -> None:
        _require_identifier(self.step_id, name="plan step_id")
        if self.ordinal < 1:
            raise ValueError("plan step ordinal must be positive")
        if not isinstance(self.kind, WorkflowStepKind):
            raise ValueError("plan contains an unsupported step kind")
        if not isinstance(self.capability_class, WorkflowCapabilityClass):
            raise ValueError("plan contains an unsupported capability class")
        if self.state is not WorkflowPlanStepState.NOT_STARTED:
            raise ValueError("new workflow plan steps must remain not_started")

    def canonical_value(self) -> dict[str, object]:
        return {
            "capability_class": self.capability_class.value,
            "kind": self.kind.value,
            "ordinal": self.ordinal,
            "state": self.state.value,
            "step_id": self.step_id,
        }


@dataclass(frozen=True, slots=True)
class WorkflowPlanTransition:
    transition_id: str
    prior_state: WorkflowPlanState
    new_state: WorkflowPlanState
    actor_subject_id: str
    scope: WorkflowScope
    target_id: str
    target_type: str
    reason: str
    reason_digest: str
    correlation_id: str
    occurred_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.transition_id, name="transition_id")
        if self.prior_state is not WorkflowPlanState.PLANNED:
            raise ValueError("workflow cancellation must start from planned")
        if self.new_state is not WorkflowPlanState.CANCELLED:
            raise ValueError("workflow cancellation must end in cancelled")
        _require_identifier(self.actor_subject_id, name="transition actor_subject_id")
        _require_identifier(self.target_id, name="transition target_id")
        if self.target_type != "storage":
            raise ValueError("workflow cancellation supports only storage targets")
        _require_text(self.reason, name="cancellation reason", maximum=500)
        if self.reason != " ".join(self.reason.split()):
            raise ValueError("cancellation reason must be normalized")
        _require_digest(self.reason_digest, name="cancellation reason_digest")
        if self.reason_digest != canonical_digest({"reason": self.reason}):
            raise ValueError("workflow cancellation reason digest mismatch")
        _require_identifier(self.correlation_id, name="transition correlation_id")
        if self.occurred_at.tzinfo is None:
            raise ValueError("workflow transition occurred_at must be timezone-aware")
        _require_digest(self.canonical_digest, name="transition canonical_digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow transition canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "actor_subject_id": self.actor_subject_id,
            "correlation_id": self.correlation_id,
            "new_state": self.new_state.value,
            "occurred_at": self.occurred_at.isoformat(),
            "prior_state": self.prior_state.value,
            "reason": self.reason,
            "reason_digest": self.reason_digest,
            "scope": self.scope.canonical_value(),
            "target_id": self.target_id,
            "target_type": self.target_type,
            "transition_id": self.transition_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowRunPlan:
    plan_id: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScope
    target_id: str
    target_type: str
    canonical_input_digest: str
    creator_subject_id: str
    created_at: datetime
    state: WorkflowPlanState
    steps: tuple[WorkflowPlanStep, ...]
    durable: bool
    authority: WorkflowPlanAuthority
    safety_notice: str
    canonical_digest: str
    transition_history: tuple[WorkflowPlanTransition, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.plan_id, name="plan_id")
        _require_identifier(self.definition_id, name="definition_id")
        if self.definition_version < 1:
            raise ValueError("definition_version must be positive")
        _require_digest(self.definition_digest, name="definition_digest")
        _require_identifier(self.target_id, name="target_id")
        if self.target_type != "storage":
            raise ValueError("this workflow planning slice supports only storage targets")
        _require_digest(self.canonical_input_digest, name="canonical_input_digest")
        _require_identifier(self.creator_subject_id, name="creator_subject_id")
        if self.created_at.tzinfo is None:
            raise ValueError("plan created_at must be timezone-aware")
        if not isinstance(self.state, WorkflowPlanState):
            raise ValueError("workflow run plan state is unsupported")
        if not self.steps:
            raise ValueError("workflow run plans require steps")
        if tuple(step.ordinal for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("workflow plan steps must preserve definition order")
        if len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError("workflow plan step identifiers must be unique")
        if self.safety_notice != NO_EXECUTION_SAFETY_NOTICE:
            raise ValueError("workflow plan must preserve the no-execution boundary")
        self._validate_transition_history()
        expected = canonical_digest(self.digest_payload())
        if self.canonical_digest != expected:
            raise ValueError("workflow plan canonical digest mismatch")

    def digest_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "authority": self.authority.canonical_value(),
            "canonical_input_digest": self.canonical_input_digest,
            "created_at": self.created_at.isoformat(),
            "creator_subject_id": self.creator_subject_id,
            "definition_digest": self.definition_digest,
            "definition_id": self.definition_id,
            "definition_version": self.definition_version,
            "durable": self.durable,
            "plan_id": self.plan_id,
            "safety_notice": self.safety_notice,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "steps": [step.canonical_value() for step in self.steps],
            "target_id": self.target_id,
            "target_type": self.target_type,
        }
        # Preserve the IMP-184 digest contract for plans with no lifecycle history.
        if self.transition_history:
            payload["transition_history"] = [
                transition.canonical_value() for transition in self.transition_history
            ]
        return payload

    def _validate_transition_history(self) -> None:
        if self.state is WorkflowPlanState.PLANNED:
            if self.transition_history:
                raise ValueError("planned workflow plans cannot contain transition history")
            return
        if self.state is not WorkflowPlanState.CANCELLED or len(self.transition_history) != 1:
            raise ValueError("cancelled workflow plans require one cancellation transition")
        transition = self.transition_history[0]
        if (
            transition.prior_state is not WorkflowPlanState.PLANNED
            or transition.new_state is not WorkflowPlanState.CANCELLED
            or transition.scope != self.scope
            or transition.target_id != self.target_id
            or transition.target_type != self.target_type
            or transition.occurred_at < self.created_at
        ):
            raise ValueError("workflow cancellation transition binding mismatch")
        if any(step.state is not WorkflowPlanStepState.NOT_STARTED for step in self.steps):
            raise ValueError("cancelled workflow plan steps must remain not_started")


def code_owned_workflow_registry() -> WorkflowDefinitionRegistry:
    definitions = (
        WorkflowDefinition(
            definition_id="workflow.evidence-grounded-query",
            version=1,
            title="Evidence-grounded query",
            purpose="Plan bounded evidence retrieval and read-only evidence assessment.",
            input_schema_version="workflow-input.v1",
            steps=(
                WorkflowStepDefinition(
                    step_id="query-authorized-evidence",
                    ordinal=1,
                    title="Query authorized evidence",
                    kind=WorkflowStepKind.EVIDENCE_QUERY,
                    capability_class=WorkflowCapabilityClass.C1,
                    timeout_seconds=60,
                ),
                WorkflowStepDefinition(
                    step_id="assess-evidence-health",
                    ordinal=2,
                    title="Assess evidence health",
                    kind=WorkflowStepKind.HEALTH_ASSESSMENT,
                    capability_class=WorkflowCapabilityClass.C2,
                    timeout_seconds=120,
                    depends_on=("query-authorized-evidence",),
                ),
            ),
        ),
        WorkflowDefinition(
            definition_id="workflow.scheduled-health-assessment",
            version=1,
            title="Scheduled health assessment",
            purpose="Plan a read-only health evidence query and deterministic assessment.",
            input_schema_version="workflow-input.v1",
            steps=(
                WorkflowStepDefinition(
                    step_id="query-health-evidence",
                    ordinal=1,
                    title="Query health evidence",
                    kind=WorkflowStepKind.EVIDENCE_QUERY,
                    capability_class=WorkflowCapabilityClass.C1,
                    timeout_seconds=90,
                ),
                WorkflowStepDefinition(
                    step_id="assess-target-health",
                    ordinal=2,
                    title="Assess target health",
                    kind=WorkflowStepKind.HEALTH_ASSESSMENT,
                    capability_class=WorkflowCapabilityClass.C2,
                    timeout_seconds=180,
                    depends_on=("query-health-evidence",),
                ),
            ),
        ),
        WorkflowDefinition(
            definition_id="workflow.technical-report-generation",
            version=1,
            title="Technical report generation",
            purpose="Plan authorized evidence collection and non-mutating report generation.",
            input_schema_version="workflow-input.v1",
            steps=(
                WorkflowStepDefinition(
                    step_id="query-report-evidence",
                    ordinal=1,
                    title="Query report evidence",
                    kind=WorkflowStepKind.EVIDENCE_QUERY,
                    capability_class=WorkflowCapabilityClass.C1,
                    timeout_seconds=90,
                ),
                WorkflowStepDefinition(
                    step_id="generate-technical-report",
                    ordinal=2,
                    title="Generate technical report",
                    kind=WorkflowStepKind.REPORT_GENERATION,
                    capability_class=WorkflowCapabilityClass.C0,
                    timeout_seconds=180,
                    depends_on=("query-report-evidence",),
                ),
            ),
        ),
    )
    return WorkflowDefinitionRegistry(definitions)
