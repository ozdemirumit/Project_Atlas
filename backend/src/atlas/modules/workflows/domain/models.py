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


class WorkflowOrchestrationLeaseState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class WorkflowOrchestrationLeaseEffectiveState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"


class WorkflowExecutionRunState(StrEnum):
    CREATED = "created"


class WorkflowExecutionStepRunState(StrEnum):
    NOT_STARTED = "not_started"


class WorkflowExecutionAttemptState(StrEnum):
    CREATED = "created"


class WorkflowDispatchIntentState(StrEnum):
    STAGED = "staged"


class WorkflowDispatchOutboxState(StrEnum):
    PENDING_PUBLICATION = "pending_publication"


class WorkflowOutboxPublicationLeaseState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class WorkflowOutboxPublicationLeaseEffectiveState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"


class WorkflowDispatchEventEnvelopeState(StrEnum):
    PREPARED = "prepared"


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
class WorkflowOrchestrationLease:
    """Fenced ownership record that deliberately grants no execution authority."""

    lease_id: str
    plan_id: str
    plan_digest: str
    scope: WorkflowScope
    target_id: str
    target_type: str
    worker_subject_id: str
    acquired_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime
    fencing_token: int
    state: WorkflowOrchestrationLeaseState
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.lease_id, name="lease_id")
        _require_identifier(self.plan_id, name="lease plan_id")
        _require_digest(self.plan_digest, name="lease plan_digest")
        _require_identifier(self.target_id, name="lease target_id")
        if self.target_type != "storage":
            raise ValueError("workflow orchestration leases support only storage targets")
        _require_identifier(self.worker_subject_id, name="lease worker_subject_id")
        if any(
            timestamp.tzinfo is None
            for timestamp in (self.acquired_at, self.last_heartbeat_at, self.expires_at)
        ):
            raise ValueError("workflow orchestration lease timestamps must be timezone-aware")
        if self.last_heartbeat_at < self.acquired_at:
            raise ValueError("lease heartbeat cannot precede acquisition")
        if self.expires_at <= self.last_heartbeat_at:
            raise ValueError("lease expiry must follow the latest heartbeat")
        if self.fencing_token < 1:
            raise ValueError("lease fencing_token must be at least one")
        if not isinstance(self.state, WorkflowOrchestrationLeaseState):
            raise ValueError("workflow orchestration lease state is unsupported")
        _require_digest(self.canonical_digest, name="lease canonical_digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow orchestration lease canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "fencing_token": self.fencing_token,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat(),
            "lease_id": self.lease_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "worker_subject_id": self.worker_subject_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, requested_at: datetime
    ) -> WorkflowOrchestrationLeaseEffectiveState:
        if requested_at.tzinfo is None:
            raise ValueError("lease effective-state time must be timezone-aware")
        if self.state is WorkflowOrchestrationLeaseState.RELEASED:
            return WorkflowOrchestrationLeaseEffectiveState.RELEASED
        if requested_at >= self.expires_at:
            return WorkflowOrchestrationLeaseEffectiveState.EXPIRED
        return WorkflowOrchestrationLeaseEffectiveState.ACTIVE

    @property
    def grants_execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowExecutionStepRun:
    """Immutable logical step identity created before attempts or dispatch exist."""

    step_run_id: str
    run_id: str
    step_id: str
    ordinal: int
    kind: WorkflowStepKind
    capability_class: WorkflowCapabilityClass
    timeout_seconds: int
    depends_on: tuple[str, ...]
    state: WorkflowExecutionStepRunState
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.step_run_id, name="step_run_id")
        _require_identifier(self.run_id, name="step run_id")
        _require_identifier(self.step_id, name="step run step_id")
        if self.ordinal < 1:
            raise ValueError("step run ordinal must be positive")
        if not isinstance(self.kind, WorkflowStepKind):
            raise ValueError("step run kind is unsupported")
        if not isinstance(self.capability_class, WorkflowCapabilityClass):
            raise ValueError("step run capability class is unsupported")
        if not 1 <= self.timeout_seconds <= 3600:
            raise ValueError("step run timeout must be between 1 and 3600 seconds")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("step run dependencies must be unique")
        for dependency in self.depends_on:
            _require_identifier(dependency, name="step run dependency")
        if self.step_id in self.depends_on:
            raise ValueError("step run cannot depend on itself")
        if self.state is not WorkflowExecutionStepRunState.NOT_STARTED:
            raise ValueError("materialized step runs must remain not_started")
        _require_digest(self.canonical_digest, name="step run canonical_digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("step run canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "capability_class": self.capability_class.value,
            "depends_on": list(self.depends_on),
            "kind": self.kind.value,
            "ordinal": self.ordinal,
            "run_id": self.run_id,
            "state": self.state.value,
            "step_id": self.step_id,
            "step_run_id": self.step_run_id,
            "timeout_seconds": self.timeout_seconds,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowExecutionRun:
    """Durable run graph that deliberately grants no attempt or dispatch authority."""

    run_id: str
    plan_id: str
    plan_digest: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScope
    target_id: str
    target_type: str
    lease_id: str
    lease_digest: str
    fencing_token: int
    materialized_by_subject_id: str
    created_at: datetime
    state: WorkflowExecutionRunState
    step_runs: tuple[WorkflowExecutionStepRun, ...]
    authority: WorkflowPlanAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.run_id, name="execution run_id")
        _require_identifier(self.plan_id, name="execution run plan_id")
        _require_digest(self.plan_digest, name="execution run plan_digest")
        _require_identifier(self.definition_id, name="execution run definition_id")
        if self.definition_version < 1:
            raise ValueError("execution run definition_version must be positive")
        _require_digest(self.definition_digest, name="execution run definition_digest")
        _require_identifier(self.target_id, name="execution run target_id")
        if self.target_type != "storage":
            raise ValueError("workflow execution runs support only storage targets")
        _require_identifier(self.lease_id, name="execution run lease_id")
        _require_digest(self.lease_digest, name="execution run lease_digest")
        if self.fencing_token < 1:
            raise ValueError("execution run fencing_token must be at least one")
        _require_identifier(
            self.materialized_by_subject_id,
            name="execution run materialized_by_subject_id",
        )
        if self.created_at.tzinfo is None:
            raise ValueError("execution run created_at must be timezone-aware")
        if self.state is not WorkflowExecutionRunState.CREATED:
            raise ValueError("materialized workflow execution runs must remain created")
        if not self.step_runs:
            raise ValueError("workflow execution runs require step runs")
        if tuple(step.ordinal for step in self.step_runs) != tuple(
            range(1, len(self.step_runs) + 1)
        ):
            raise ValueError("workflow execution step runs must preserve definition order")
        if len({step.step_id for step in self.step_runs}) != len(self.step_runs):
            raise ValueError("workflow execution step identifiers must be unique")
        available: set[str] = set()
        for step in self.step_runs:
            if step.run_id != self.run_id or any(
                dependency not in available for dependency in step.depends_on
            ):
                raise ValueError("workflow execution step binding is invalid")
            available.add(step.step_id)
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow execution runs cannot grant operational authority")
        _require_digest(self.canonical_digest, name="execution run canonical_digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow execution run canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "authority": self.authority.canonical_value(),
            "created_at": self.created_at.isoformat(),
            "definition_digest": self.definition_digest,
            "definition_id": self.definition_id,
            "definition_version": self.definition_version,
            "fencing_token": self.fencing_token,
            "lease_digest": self.lease_digest,
            "lease_id": self.lease_id,
            "materialized_by_subject_id": self.materialized_by_subject_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "step_runs": [step.canonical_value() for step in self.step_runs],
            "target_id": self.target_id,
            "target_type": self.target_type,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowExecutionAttempt:
    """Durable pre-dispatch attempt identity with no execution authority."""

    attempt_id: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_number: int
    plan_id: str
    plan_digest: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScope
    target_id: str
    target_type: str
    lease_id: str
    lease_digest: str
    fencing_token: int
    materialized_by_subject_id: str
    created_at: datetime
    state: WorkflowExecutionAttemptState
    authority: WorkflowPlanAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.attempt_id, "attempt_id"),
            (self.run_id, "attempt run_id"),
            (self.step_run_id, "attempt step_run_id"),
            (self.step_id, "attempt step_id"),
            (self.plan_id, "attempt plan_id"),
            (self.definition_id, "attempt definition_id"),
            (self.target_id, "attempt target_id"),
            (self.lease_id, "attempt lease_id"),
            (self.materialized_by_subject_id, "attempt materialized_by_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.run_digest, "attempt run_digest"),
            (self.step_run_digest, "attempt step_run_digest"),
            (self.plan_digest, "attempt plan_digest"),
            (self.definition_digest, "attempt definition_digest"),
            (self.lease_digest, "attempt lease_digest"),
            (self.canonical_digest, "attempt canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.attempt_number != 1:
            raise ValueError("pre-dispatch attempt number must be one")
        if self.definition_version < 1:
            raise ValueError("attempt definition_version must be positive")
        if self.target_type != "storage":
            raise ValueError("workflow execution attempts support only storage targets")
        if self.fencing_token < 1:
            raise ValueError("attempt fencing_token must be at least one")
        if self.created_at.tzinfo is None:
            raise ValueError("attempt created_at must be timezone-aware")
        if self.state is not WorkflowExecutionAttemptState.CREATED:
            raise ValueError("pre-dispatch attempts must remain created")
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow execution attempts cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow execution attempt canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "created_at": self.created_at.isoformat(),
            "definition_digest": self.definition_digest,
            "definition_id": self.definition_id,
            "definition_version": self.definition_version,
            "fencing_token": self.fencing_token,
            "lease_digest": self.lease_digest,
            "lease_id": self.lease_id,
            "materialized_by_subject_id": self.materialized_by_subject_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "step_id": self.step_id,
            "step_run_digest": self.step_run_digest,
            "step_run_id": self.step_run_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowDispatchIntent:
    """Durable dispatch staging evidence that grants no delivery or execution authority."""

    dispatch_intent_id: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: int
    scope: WorkflowScope
    target_id: str
    target_type: str
    lease_id: str
    lease_digest: str
    fencing_token: int
    worker_subject_id: str
    staged_at: datetime
    state: WorkflowDispatchIntentState
    authority: WorkflowPlanAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.dispatch_intent_id, "dispatch intent id"),
            (self.plan_id, "dispatch intent plan_id"),
            (self.run_id, "dispatch intent run_id"),
            (self.step_run_id, "dispatch intent step_run_id"),
            (self.step_id, "dispatch intent step_id"),
            (self.attempt_id, "dispatch intent attempt_id"),
            (self.target_id, "dispatch intent target_id"),
            (self.lease_id, "dispatch intent lease_id"),
            (self.worker_subject_id, "dispatch intent worker_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.plan_digest, "dispatch intent plan_digest"),
            (self.run_digest, "dispatch intent run_digest"),
            (self.step_run_digest, "dispatch intent step_run_digest"),
            (self.attempt_digest, "dispatch intent attempt_digest"),
            (self.lease_digest, "dispatch intent lease_digest"),
            (self.canonical_digest, "dispatch intent canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.attempt_number != 1:
            raise ValueError("dispatch intents support only attempt number one")
        if self.target_type != "storage":
            raise ValueError("workflow dispatch intents support only storage targets")
        if self.fencing_token < 1:
            raise ValueError("dispatch intent fencing_token must be at least one")
        if self.staged_at.tzinfo is None:
            raise ValueError("dispatch intent staged_at must be timezone-aware")
        if self.state is not WorkflowDispatchIntentState.STAGED:
            raise ValueError("workflow dispatch intents must remain staged")
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow dispatch intents cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow dispatch intent canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "dispatch_intent_id": self.dispatch_intent_id,
            "fencing_token": self.fencing_token,
            "lease_digest": self.lease_digest,
            "lease_id": self.lease_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "scope": self.scope.canonical_value(),
            "staged_at": self.staged_at.isoformat(),
            "state": self.state.value,
            "step_id": self.step_id,
            "step_run_digest": self.step_run_digest,
            "step_run_id": self.step_run_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "worker_subject_id": self.worker_subject_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_publication_authority(self) -> bool:
        return False

    @property
    def grants_delivery_authority(self) -> bool:
        return False

    @property
    def grants_dispatch_authority(self) -> bool:
        return False

    @property
    def grants_execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowDispatchOutboxEntry:
    """Provider-neutral admission evidence that cannot publish or deliver work."""

    outbox_entry_id: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: int
    scope: WorkflowScope
    target_id: str
    target_type: str
    lease_id: str
    lease_digest: str
    fencing_token: int
    worker_subject_id: str
    admitted_at: datetime
    state: WorkflowDispatchOutboxState
    authority: WorkflowPlanAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.outbox_entry_id, "dispatch outbox entry id"),
            (self.dispatch_intent_id, "dispatch outbox dispatch_intent_id"),
            (self.plan_id, "dispatch outbox plan_id"),
            (self.run_id, "dispatch outbox run_id"),
            (self.step_run_id, "dispatch outbox step_run_id"),
            (self.step_id, "dispatch outbox step_id"),
            (self.attempt_id, "dispatch outbox attempt_id"),
            (self.target_id, "dispatch outbox target_id"),
            (self.lease_id, "dispatch outbox lease_id"),
            (self.worker_subject_id, "dispatch outbox worker_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.dispatch_intent_digest, "dispatch outbox dispatch_intent_digest"),
            (self.plan_digest, "dispatch outbox plan_digest"),
            (self.run_digest, "dispatch outbox run_digest"),
            (self.step_run_digest, "dispatch outbox step_run_digest"),
            (self.attempt_digest, "dispatch outbox attempt_digest"),
            (self.lease_digest, "dispatch outbox lease_digest"),
            (self.canonical_digest, "dispatch outbox canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.attempt_number != 1:
            raise ValueError("dispatch outbox entries support only attempt number one")
        if self.target_type != "storage":
            raise ValueError("workflow dispatch outbox entries support only storage targets")
        if self.fencing_token < 1:
            raise ValueError("dispatch outbox fencing_token must be at least one")
        if self.admitted_at.tzinfo is None:
            raise ValueError("dispatch outbox admitted_at must be timezone-aware")
        if self.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION:
            raise ValueError("workflow dispatch outbox entries must remain pending_publication")
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow dispatch outbox entries cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow dispatch outbox canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admitted_at": self.admitted_at.isoformat(),
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "dispatch_intent_digest": self.dispatch_intent_digest,
            "dispatch_intent_id": self.dispatch_intent_id,
            "fencing_token": self.fencing_token,
            "lease_digest": self.lease_digest,
            "lease_id": self.lease_id,
            "outbox_entry_id": self.outbox_entry_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "step_id": self.step_id,
            "step_run_digest": self.step_run_digest,
            "step_run_id": self.step_run_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "worker_subject_id": self.worker_subject_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_publication_authority(self) -> bool:
        return False

    @property
    def grants_delivery_authority(self) -> bool:
        return False

    @property
    def grants_dispatch_authority(self) -> bool:
        return False

    @property
    def grants_execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublicationLease:
    """Fenced outbox ownership evidence that grants no operational authority."""

    publication_lease_id: str
    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: int
    scope: WorkflowScope
    target_id: str
    target_type: str
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int
    publisher_subject_id: str
    acquired_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime
    publication_fencing_token: int
    state: WorkflowOutboxPublicationLeaseState
    authority: WorkflowPlanAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.publication_lease_id, "publication lease id"),
            (self.outbox_entry_id, "publication lease outbox_entry_id"),
            (self.dispatch_intent_id, "publication lease dispatch_intent_id"),
            (self.plan_id, "publication lease plan_id"),
            (self.run_id, "publication lease run_id"),
            (self.step_run_id, "publication lease step_run_id"),
            (self.step_id, "publication lease step_id"),
            (self.attempt_id, "publication lease attempt_id"),
            (self.target_id, "publication lease target_id"),
            (self.orchestration_lease_id, "publication lease orchestration_lease_id"),
            (self.publisher_subject_id, "publication lease publisher_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.outbox_entry_digest, "publication lease outbox_entry_digest"),
            (self.dispatch_intent_digest, "publication lease dispatch_intent_digest"),
            (self.plan_digest, "publication lease plan_digest"),
            (self.run_digest, "publication lease run_digest"),
            (self.step_run_digest, "publication lease step_run_digest"),
            (self.attempt_digest, "publication lease attempt_digest"),
            (
                self.orchestration_lease_digest,
                "publication lease orchestration_lease_digest",
            ),
            (self.canonical_digest, "publication lease canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.attempt_number != 1:
            raise ValueError("publication leases support only attempt number one")
        if self.target_type != "storage":
            raise ValueError("workflow publication leases support only storage targets")
        if self.orchestration_fencing_token < 1:
            raise ValueError("orchestration_fencing_token must be at least one")
        if self.publication_fencing_token < 1:
            raise ValueError("publication_fencing_token must be at least one")
        if any(
            timestamp.tzinfo is None
            for timestamp in (self.acquired_at, self.last_heartbeat_at, self.expires_at)
        ):
            raise ValueError("publication lease timestamps must be timezone-aware")
        if self.last_heartbeat_at < self.acquired_at:
            raise ValueError("publication lease heartbeat cannot precede acquisition")
        if self.expires_at <= self.last_heartbeat_at:
            raise ValueError("publication lease expiry must follow the latest heartbeat")
        if not isinstance(self.state, WorkflowOutboxPublicationLeaseState):
            raise ValueError("workflow publication lease state is unsupported")
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow publication leases cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow publication lease canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "acquired_at": self.acquired_at.isoformat(),
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "dispatch_intent_digest": self.dispatch_intent_digest,
            "dispatch_intent_id": self.dispatch_intent_id,
            "expires_at": self.expires_at.isoformat(),
            "last_heartbeat_at": self.last_heartbeat_at.isoformat(),
            "orchestration_fencing_token": self.orchestration_fencing_token,
            "orchestration_lease_digest": self.orchestration_lease_digest,
            "orchestration_lease_id": self.orchestration_lease_id,
            "outbox_entry_digest": self.outbox_entry_digest,
            "outbox_entry_id": self.outbox_entry_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "publication_fencing_token": self.publication_fencing_token,
            "publication_lease_id": self.publication_lease_id,
            "publisher_subject_id": self.publisher_subject_id,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "step_id": self.step_id,
            "step_run_digest": self.step_run_digest,
            "step_run_id": self.step_run_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, requested_at: datetime
    ) -> WorkflowOutboxPublicationLeaseEffectiveState:
        if requested_at.tzinfo is None:
            raise ValueError("publication lease effective-state time must be timezone-aware")
        if self.state is WorkflowOutboxPublicationLeaseState.RELEASED:
            return WorkflowOutboxPublicationLeaseEffectiveState.RELEASED
        if requested_at >= self.expires_at:
            return WorkflowOutboxPublicationLeaseEffectiveState.EXPIRED
        return WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE

    @property
    def grants_publication_authority(self) -> bool:
        return False

    @property
    def grants_delivery_authority(self) -> bool:
        return False

    @property
    def grants_dispatch_authority(self) -> bool:
        return False

    @property
    def grants_execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEventAuthority:
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("workflow dispatch event envelopes cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "execution_authorized": self.execution_authorized,
            "publication_authorized": self.publication_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEventPayload:
    """Minimized provider-neutral lineage carried by a workflow dispatch event."""

    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: int
    scope: WorkflowScope
    target_id: str
    target_type: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.outbox_entry_id, "event payload outbox_entry_id"),
            (self.dispatch_intent_id, "event payload dispatch_intent_id"),
            (self.plan_id, "event payload plan_id"),
            (self.run_id, "event payload run_id"),
            (self.step_run_id, "event payload step_run_id"),
            (self.step_id, "event payload step_id"),
            (self.attempt_id, "event payload attempt_id"),
            (self.target_id, "event payload target_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.outbox_entry_digest, "event payload outbox_entry_digest"),
            (self.dispatch_intent_digest, "event payload dispatch_intent_digest"),
            (self.plan_digest, "event payload plan_digest"),
            (self.run_digest, "event payload run_digest"),
            (self.step_run_digest, "event payload step_run_digest"),
            (self.attempt_digest, "event payload attempt_digest"),
        ):
            _require_digest(value, name=name)
        if self.attempt_number != 1:
            raise ValueError("workflow dispatch event payloads support only attempt number one")
        if self.target_type != "storage":
            raise ValueError("workflow dispatch event payloads support only storage targets")

    def canonical_value(self) -> dict[str, object]:
        return {
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "dispatch_intent_digest": self.dispatch_intent_digest,
            "dispatch_intent_id": self.dispatch_intent_id,
            "outbox_entry_digest": self.outbox_entry_digest,
            "outbox_entry_id": self.outbox_entry_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "scope": self.scope.canonical_value(),
            "step_id": self.step_id,
            "step_run_digest": self.step_run_digest,
            "step_run_id": self.step_run_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEventEnvelope:
    """Canonical event evidence that deliberately has no transport authority."""

    event_id: str
    event_type: str
    event_version: str
    occurred_at: datetime
    recorded_at: datetime
    producer: str
    producer_version: str
    subject_type: str
    subject_id: str
    organization_id: str
    environment_id: str
    correlation_id: str
    causation_id: str
    workflow_id: str
    data_classification: str
    schema_uri: str
    payload: WorkflowDispatchEventPayload
    extensions: tuple[tuple[str, str], ...]
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int
    publisher_subject_id: str
    prepared_at: datetime
    state: WorkflowDispatchEventEnvelopeState
    authority: WorkflowDispatchEventAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.event_id, "dispatch event id"),
            (self.producer, "dispatch event producer"),
            (self.producer_version, "dispatch event producer_version"),
            (self.subject_id, "dispatch event subject_id"),
            (self.organization_id, "dispatch event organization_id"),
            (self.environment_id, "dispatch event environment_id"),
            (self.correlation_id, "dispatch event correlation_id"),
            (self.causation_id, "dispatch event causation_id"),
            (self.workflow_id, "dispatch event workflow_id"),
            (self.orchestration_lease_id, "dispatch event orchestration_lease_id"),
            (self.publication_lease_id, "dispatch event publication_lease_id"),
            (self.publisher_subject_id, "dispatch event publisher_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.orchestration_lease_digest, "dispatch event orchestration_lease_digest"),
            (self.publication_lease_digest, "dispatch event publication_lease_digest"),
            (self.canonical_digest, "dispatch event canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.event_type != "WorkflowStepDispatchRequested":
            raise ValueError("workflow dispatch event type is unsupported")
        if self.event_version != "1.0":
            raise ValueError("workflow dispatch event version is unsupported")
        if self.subject_type != "workflow-execution-attempt":
            raise ValueError("workflow dispatch event subject type is unsupported")
        if self.data_classification != "internal":
            raise ValueError("workflow dispatch event classification must be internal")
        if self.schema_uri != "urn:project-atlas:event:workflow-step-dispatch-requested:1.0":
            raise ValueError("workflow dispatch event schema URI is unsupported")
        if self.extensions:
            raise ValueError("workflow dispatch event extensions must remain empty")
        if any(
            timestamp.tzinfo is None
            for timestamp in (self.occurred_at, self.recorded_at, self.prepared_at)
        ):
            raise ValueError("workflow dispatch event timestamps must be timezone-aware")
        if self.recorded_at != self.prepared_at or self.recorded_at < self.occurred_at:
            raise ValueError("workflow dispatch event recording time is invalid")
        if self.subject_id != self.payload.attempt_id:
            raise ValueError("workflow dispatch event subject does not match its attempt")
        if (
            self.organization_id != self.payload.scope.organization_id
            or self.environment_id != self.payload.scope.environment_id
            or self.correlation_id != self.payload.run_id
            or self.causation_id != self.payload.dispatch_intent_id
            or self.workflow_id != self.payload.run_id
        ):
            raise ValueError("workflow dispatch event context does not match its payload")
        if self.orchestration_fencing_token < 1 or self.publication_fencing_token < 1:
            raise ValueError("workflow dispatch event fencing tokens must be at least one")
        if self.state is not WorkflowDispatchEventEnvelopeState.PREPARED:
            raise ValueError("workflow dispatch event envelopes must remain prepared")
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow dispatch event envelopes cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow dispatch event envelope canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "authority": self.authority.canonical_value(),
            "causation_id": self.causation_id,
            "correlation_id": self.correlation_id,
            "data_classification": self.data_classification,
            "environment_id": self.environment_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "extensions": {},
            "occurred_at": self.occurred_at.isoformat(),
            "orchestration_fencing_token": self.orchestration_fencing_token,
            "orchestration_lease_digest": self.orchestration_lease_digest,
            "orchestration_lease_id": self.orchestration_lease_id,
            "organization_id": self.organization_id,
            "payload": self.payload.canonical_value(),
            "prepared_at": self.prepared_at.isoformat(),
            "producer": self.producer,
            "producer_version": self.producer_version,
            "publication_fencing_token": self.publication_fencing_token,
            "publication_lease_digest": self.publication_lease_digest,
            "publication_lease_id": self.publication_lease_id,
            "publisher_subject_id": self.publisher_subject_id,
            "recorded_at": self.recorded_at.isoformat(),
            "schema_uri": self.schema_uri,
            "state": self.state.value,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "workflow_id": self.workflow_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_publication_authority(self) -> bool:
        return False

    @property
    def grants_delivery_authority(self) -> bool:
        return False

    @property
    def grants_dispatch_authority(self) -> bool:
        return False

    @property
    def grants_execution_authority(self) -> bool:
        return False


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
