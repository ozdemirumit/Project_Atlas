from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol, cast

NO_EXECUTION_SAFETY_NOTICE = (
    "Planning only. This record cannot dispatch workers, invoke connectors, create approvals, "
    "mutate ITSM, execute runbooks, or change infrastructure."
)


def canonical_digest(payload: object) -> str:
    return sha256(canonical_json_bytes(payload)).hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    """Serialize finite JSON deterministically as UTF-8 bytes."""
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical payload must contain finite JSON values") from exc


def canonical_json_byte_count(payload: object) -> int:
    """Return canonical JSON's UTF-8 size without retaining a serialized artifact."""
    return len(canonical_json_bytes(payload))


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


class WorkflowEventTransportAdmissionState(StrEnum):
    ADMITTED = "admitted"


class WorkflowEventByteArtifactState(StrEnum):
    MATERIALIZED = "materialized"


class WorkflowEventLogicalChannelBindingState(StrEnum):
    BOUND = "bound"


class EventPhysicalTransportProfileSnapshotState(StrEnum):
    SNAPSHOTTED = "snapshotted"


class WorkflowEventTransportCompatibilityAdmissionState(StrEnum):
    ADMITTED = "admitted"


class EventPhysicalTransportRouteSnapshotState(StrEnum):
    SNAPSHOTTED = "snapshotted"


class EventPhysicalTransportCredentialAssignmentSnapshotState(StrEnum):
    SNAPSHOTTED = "snapshotted"


class WorkflowEventPhysicalTransportRouteBindingState(StrEnum):
    BOUND = "bound"


class WorkflowEventPhysicalTransportCredentialAssignmentBindingState(StrEnum):
    BOUND = "bound"


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState(StrEnum):
    ADMITTED_CURRENT = "admitted_current"


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionState(StrEnum):
    ADMITTED_CURRENT = "admitted_current"


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class WorkflowEventPhysicalTransportEndpointMaterializationAttemptState(StrEnum):
    MATERIALIZATION_STARTED = "materialization_started"


class WorkflowEventPhysicalTransportEndpointMaterializationResultState(StrEnum):
    MATERIALIZED_PROTECTED = "materialized_protected"
    MATERIALIZATION_FAILED = "materialization_failed"


class WorkflowEventPhysicalTransportEndpointMaterializationFailureClass(StrEnum):
    SEALED_LINEAGE_REJECTED = "sealed_lineage_rejected"
    ENDPOINT_SET_INVALID = "endpoint_set_invalid"
    POLICY_LIMIT_EXCEEDED = "policy_limit_exceeded"
    DEADLINE_EXPIRED = "deadline_expired"
    PROTECTED_ARTIFACT_REVOKED = "protected_artifact_revoked"


class WorkflowEventPhysicalTransportCredentialMaterializationAttemptState(StrEnum):
    MATERIALIZATION_STARTED = "materialization_started"


class WorkflowEventPhysicalTransportCredentialMaterializationResultState(StrEnum):
    MATERIALIZED_PROTECTED = "materialized_protected"
    MATERIALIZATION_FAILED = "materialization_failed"


class WorkflowEventPhysicalTransportTargetContextBindingState(StrEnum):
    BOUND = "bound"


class WorkflowEventPhysicalTransportTargetContextBindingEffectiveState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class WorkflowProtectedArtifactKind(StrEnum):
    ENDPOINT = "endpoint"
    CREDENTIAL = "credential"


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptState(StrEnum):
    OPENING_STARTED = "opening_started"


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState(StrEnum):
    OPENED_PROTECTED = "opened_protected"
    OPENING_FAILED = "opening_failed"


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass(StrEnum):
    DEADLINE_EXPIRED = "deadline_expired"
    ENDPOINT_SOURCE_INVALID = "endpoint_source_invalid"
    CREDENTIAL_SOURCE_INVALID = "credential_source_invalid"
    PAIR_INTEGRITY_INVALID = "pair_integrity_invalid"
    TRUSTED_OPENER_REJECTED = "trusted_opener_rejected"


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState(StrEnum):
    BOUND = "bound"


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState(
    StrEnum
):
    ACTIVE = "active"
    EXPIRED = "expired"


class WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptState(StrEnum):
    STARTED = "started"


class WorkflowProtectedTransportTargetContextCapsuleHandoffResultState(StrEnum):
    HANDED_OFF_SEALED = "handed_off_sealed"
    HANDOFF_FAILED = "handoff_failed"


class WorkflowProtectedTransportTargetContextCapsuleHandoffFailureClass(StrEnum):
    CAPSULE_NOT_HANDOFF_ELIGIBLE = "capsule_not_handoff_eligible"
    CONSUMER_BOUNDARY_REJECTED = "consumer_boundary_rejected"
    SEALED_HANDOFF_REJECTED = "sealed_handoff_rejected"
    DEADLINE_EXPIRED = "deadline_expired"


class WorkflowEventPhysicalTransportCredentialMaterializationFailureClass(StrEnum):
    SEALED_LINEAGE_REJECTED = "sealed_lineage_rejected"
    CREDENTIAL_SOURCE_INVALID = "credential_source_invalid"
    POLICY_LIMIT_EXCEEDED = "policy_limit_exceeded"
    DEADLINE_EXPIRED = "deadline_expired"
    PROTECTED_ARTIFACT_REVOKED = "protected_artifact_revoked"


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
class WorkflowEventTransportAdmissionPolicy:
    """Immutable provider-neutral eligibility policy owned by Atlas code."""

    policy_id: str
    policy_version: str
    allowed_event_types: tuple[str, ...]
    allowed_event_versions: tuple[str, ...]
    allowed_schema_uris: tuple[str, ...]
    allowed_data_classifications: tuple[str, ...]
    representation_name: str
    encoding: str
    maximum_canonical_byte_count: int
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="transport admission policy_id")
        _require_identifier(self.policy_version, name="transport admission policy_version")
        for values, name in (
            (self.allowed_event_types, "allowed event types"),
            (self.allowed_event_versions, "allowed event versions"),
            (self.allowed_schema_uris, "allowed schema URIs"),
            (self.allowed_data_classifications, "allowed data classifications"),
        ):
            if not values or tuple(sorted(set(values))) != values:
                raise ValueError(f"transport admission {name} must be unique and sorted")
            for value in values:
                _require_text(value, name=f"transport admission {name}", maximum=240)
        if self.representation_name != "canonical-json":
            raise ValueError("transport admission representation must be canonical-json")
        if self.encoding != "utf-8":
            raise ValueError("transport admission encoding must be utf-8")
        if not 1 <= self.maximum_canonical_byte_count <= 1_048_576:
            raise ValueError("transport admission canonical byte limit is invalid")
        _require_digest(self.canonical_digest, name="transport admission policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport admission policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "allowed_data_classifications": list(self.allowed_data_classifications),
            "allowed_event_types": list(self.allowed_event_types),
            "allowed_event_versions": list(self.allowed_event_versions),
            "allowed_schema_uris": list(self.allowed_schema_uris),
            "encoding": self.encoding,
            "maximum_canonical_byte_count": self.maximum_canonical_byte_count,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "representation_name": self.representation_name,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_transport_admission_policy() -> WorkflowEventTransportAdmissionPolicy:
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-transport-admission",
        "policy_version": "1.0",
        "allowed_event_types": ("WorkflowStepDispatchRequested",),
        "allowed_event_versions": ("1.0",),
        "allowed_schema_uris": ("urn:project-atlas:event:workflow-step-dispatch-requested:1.0",),
        "allowed_data_classifications": ("internal",),
        "representation_name": "canonical-json",
        "encoding": "utf-8",
        "maximum_canonical_byte_count": 65_536,
    }
    digest_payload = {
        key: list(value) if isinstance(value, tuple) else value for key, value in values.items()
    }
    return WorkflowEventTransportAdmissionPolicy(
        policy_id="policy.workflow-event-transport-admission",
        policy_version="1.0",
        allowed_event_types=("WorkflowStepDispatchRequested",),
        allowed_event_versions=("1.0",),
        allowed_schema_uris=("urn:project-atlas:event:workflow-step-dispatch-requested:1.0",),
        allowed_data_classifications=("internal",),
        representation_name="canonical-json",
        encoding="utf-8",
        maximum_canonical_byte_count=65_536,
        canonical_digest=canonical_digest(digest_payload),
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportAdmissionAuthority:
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError(
                "workflow event transport admission cannot grant operational authority"
            )

    def canonical_value(self) -> dict[str, bool]:
        return {
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "execution_authorized": self.execution_authorized,
            "publication_authorized": self.publication_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportAdmission:
    """Immutable policy admission evidence with no transport authority."""

    admission_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    event_id: str
    event_digest: str
    event_type: str
    event_version: str
    schema_uri: str
    data_classification: str
    representation_name: str
    encoding: str
    canonical_byte_count: int
    maximum_canonical_byte_count: int
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
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int
    publisher_subject_id: str
    admitted_at: datetime
    state: WorkflowEventTransportAdmissionState
    authority: WorkflowEventTransportAdmissionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.admission_id, "transport admission id"),
            (self.policy_id, "transport admission policy_id"),
            (self.policy_version, "transport admission policy_version"),
            (self.event_id, "transport admission event_id"),
            (self.outbox_entry_id, "transport admission outbox_entry_id"),
            (self.dispatch_intent_id, "transport admission dispatch_intent_id"),
            (self.plan_id, "transport admission plan_id"),
            (self.run_id, "transport admission run_id"),
            (self.step_run_id, "transport admission step_run_id"),
            (self.step_id, "transport admission step_id"),
            (self.attempt_id, "transport admission attempt_id"),
            (self.target_id, "transport admission target_id"),
            (self.orchestration_lease_id, "transport admission orchestration_lease_id"),
            (self.publication_lease_id, "transport admission publication_lease_id"),
            (self.publisher_subject_id, "transport admission publisher_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.policy_digest, "transport admission policy_digest"),
            (self.event_digest, "transport admission event_digest"),
            (self.outbox_entry_digest, "transport admission outbox_entry_digest"),
            (self.dispatch_intent_digest, "transport admission dispatch_intent_digest"),
            (self.plan_digest, "transport admission plan_digest"),
            (self.run_digest, "transport admission run_digest"),
            (self.step_run_digest, "transport admission step_run_digest"),
            (self.attempt_digest, "transport admission attempt_digest"),
            (self.orchestration_lease_digest, "transport admission orchestration_lease_digest"),
            (self.publication_lease_digest, "transport admission publication_lease_digest"),
            (self.canonical_digest, "transport admission canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.representation_name != "canonical-json" or self.encoding != "utf-8":
            raise ValueError("workflow event transport admission representation is invalid")
        if not 1 <= self.canonical_byte_count <= self.maximum_canonical_byte_count:
            raise ValueError("workflow event transport admission canonical byte count is invalid")
        if self.attempt_number != 1 or self.target_type != "storage":
            raise ValueError("workflow event transport admission lineage is unsupported")
        if self.orchestration_fencing_token < 1 or self.publication_fencing_token < 1:
            raise ValueError("workflow event transport admission fencing tokens are invalid")
        if self.admitted_at.tzinfo is None:
            raise ValueError("workflow event transport admission time must be timezone-aware")
        if self.state is not WorkflowEventTransportAdmissionState.ADMITTED:
            raise ValueError("workflow event transport admission must remain admitted")
        if any(self.authority.canonical_value().values()):
            raise ValueError(
                "workflow event transport admission cannot grant operational authority"
            )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow event transport admission canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admission_id": self.admission_id,
            "admitted_at": self.admitted_at.isoformat(),
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "canonical_byte_count": self.canonical_byte_count,
            "data_classification": self.data_classification,
            "dispatch_intent_digest": self.dispatch_intent_digest,
            "dispatch_intent_id": self.dispatch_intent_id,
            "encoding": self.encoding,
            "event_digest": self.event_digest,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "maximum_canonical_byte_count": self.maximum_canonical_byte_count,
            "orchestration_fencing_token": self.orchestration_fencing_token,
            "orchestration_lease_digest": self.orchestration_lease_digest,
            "orchestration_lease_id": self.orchestration_lease_id,
            "outbox_entry_digest": self.outbox_entry_digest,
            "outbox_entry_id": self.outbox_entry_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "publication_fencing_token": self.publication_fencing_token,
            "publication_lease_digest": self.publication_lease_digest,
            "publication_lease_id": self.publication_lease_id,
            "publisher_subject_id": self.publisher_subject_id,
            "representation_name": self.representation_name,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "schema_uri": self.schema_uri,
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
class WorkflowEventByteArtifactAuthority:
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("workflow event byte artifacts cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "execution_authorized": self.execution_authorized,
            "publication_authorized": self.publication_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventByteArtifact:
    """Immutable canonical bytes whose public evidence never exposes their content."""

    artifact_id: str
    admission_id: str
    admission_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    event_id: str
    event_digest: str
    event_type: str
    event_version: str
    schema_uri: str
    data_classification: str
    representation_name: str
    encoding: str
    canonical_bytes: bytes
    canonical_byte_count: int
    content_sha256: str
    maximum_canonical_byte_count: int
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
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int
    publisher_subject_id: str
    materialized_at: datetime
    state: WorkflowEventByteArtifactState
    authority: WorkflowEventByteArtifactAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.artifact_id, "byte artifact id"),
            (self.admission_id, "byte artifact admission_id"),
            (self.policy_id, "byte artifact policy_id"),
            (self.policy_version, "byte artifact policy_version"),
            (self.event_id, "byte artifact event_id"),
            (self.outbox_entry_id, "byte artifact outbox_entry_id"),
            (self.dispatch_intent_id, "byte artifact dispatch_intent_id"),
            (self.plan_id, "byte artifact plan_id"),
            (self.run_id, "byte artifact run_id"),
            (self.step_run_id, "byte artifact step_run_id"),
            (self.step_id, "byte artifact step_id"),
            (self.attempt_id, "byte artifact attempt_id"),
            (self.target_id, "byte artifact target_id"),
            (self.orchestration_lease_id, "byte artifact orchestration_lease_id"),
            (self.publication_lease_id, "byte artifact publication_lease_id"),
            (self.publisher_subject_id, "byte artifact publisher_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.admission_digest, "byte artifact admission_digest"),
            (self.policy_digest, "byte artifact policy_digest"),
            (self.event_digest, "byte artifact event_digest"),
            (self.content_sha256, "byte artifact content_sha256"),
            (self.outbox_entry_digest, "byte artifact outbox_entry_digest"),
            (self.dispatch_intent_digest, "byte artifact dispatch_intent_digest"),
            (self.plan_digest, "byte artifact plan_digest"),
            (self.run_digest, "byte artifact run_digest"),
            (self.step_run_digest, "byte artifact step_run_digest"),
            (self.attempt_digest, "byte artifact attempt_digest"),
            (self.orchestration_lease_digest, "byte artifact orchestration_lease_digest"),
            (self.publication_lease_digest, "byte artifact publication_lease_digest"),
            (self.canonical_digest, "byte artifact canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.event_type != "WorkflowStepDispatchRequested" or self.event_version != "1.0":
            raise ValueError("workflow event byte artifact event contract is unsupported")
        if self.schema_uri != "urn:project-atlas:event:workflow-step-dispatch-requested:1.0":
            raise ValueError("workflow event byte artifact schema URI is unsupported")
        if self.data_classification != "internal":
            raise ValueError("workflow event byte artifact classification must be internal")
        if self.representation_name != "canonical-json" or self.encoding != "utf-8":
            raise ValueError("workflow event byte artifact representation is invalid")
        if not isinstance(self.canonical_bytes, bytes) or not self.canonical_bytes:
            raise ValueError("workflow event byte artifact requires immutable canonical bytes")
        try:
            decoded_value = json.loads(self.canonical_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("workflow event byte artifact bytes are not valid UTF-8 JSON") from exc
        if (
            not isinstance(decoded_value, dict)
            or canonical_json_bytes(decoded_value) != self.canonical_bytes
        ):
            raise ValueError("workflow event byte artifact bytes are not canonical JSON")
        if self.canonical_byte_count != len(self.canonical_bytes):
            raise ValueError("workflow event byte artifact byte count mismatch")
        if not 1 <= self.canonical_byte_count <= self.maximum_canonical_byte_count:
            raise ValueError("workflow event byte artifact canonical byte count is invalid")
        if self.content_sha256 != sha256(self.canonical_bytes).hexdigest():
            raise ValueError("workflow event byte artifact content digest mismatch")
        if self.attempt_number != 1 or self.target_type != "storage":
            raise ValueError("workflow event byte artifact lineage is unsupported")
        if self.orchestration_fencing_token < 1 or self.publication_fencing_token < 1:
            raise ValueError("workflow event byte artifact fencing tokens are invalid")
        if self.materialized_at.tzinfo is None:
            raise ValueError("workflow event byte artifact time must be timezone-aware")
        if self.state is not WorkflowEventByteArtifactState.MATERIALIZED:
            raise ValueError("workflow event byte artifacts must remain materialized")
        if any(self.authority.canonical_value().values()):
            raise ValueError("workflow event byte artifacts cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("workflow event byte artifact canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admission_digest": self.admission_digest,
            "admission_id": self.admission_id,
            "artifact_id": self.artifact_id,
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "canonical_byte_count": self.canonical_byte_count,
            "content_sha256": self.content_sha256,
            "data_classification": self.data_classification,
            "dispatch_intent_digest": self.dispatch_intent_digest,
            "dispatch_intent_id": self.dispatch_intent_id,
            "encoding": self.encoding,
            "event_digest": self.event_digest,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "materialized_at": self.materialized_at.isoformat(),
            "maximum_canonical_byte_count": self.maximum_canonical_byte_count,
            "orchestration_fencing_token": self.orchestration_fencing_token,
            "orchestration_lease_digest": self.orchestration_lease_digest,
            "orchestration_lease_id": self.orchestration_lease_id,
            "outbox_entry_digest": self.outbox_entry_digest,
            "outbox_entry_id": self.outbox_entry_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "publication_fencing_token": self.publication_fencing_token,
            "publication_lease_digest": self.publication_lease_digest,
            "publication_lease_id": self.publication_lease_id,
            "publisher_subject_id": self.publisher_subject_id,
            "representation_name": self.representation_name,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "schema_uri": self.schema_uri,
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
class WorkflowEventLogicalChannelPolicy:
    """Code-owned logical event contract independent of physical transport."""

    policy_id: str
    policy_version: str
    logical_channel_id: str
    logical_channel_version: str
    allowed_event_types: tuple[str, ...]
    allowed_event_versions: tuple[str, ...]
    allowed_schema_uris: tuple[str, ...]
    allowed_data_classifications: tuple[str, ...]
    representation_name: str
    encoding: str
    delivery_semantics: str
    durability_required: bool
    ordering_key_kind: str
    retention_class: str
    maximum_canonical_byte_count: int
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.policy_id, "logical channel policy_id"),
            (self.policy_version, "logical channel policy_version"),
            (self.logical_channel_id, "logical channel id"),
            (self.logical_channel_version, "logical channel version"),
        ):
            _require_identifier(value, name=name)
        for values, name in (
            (self.allowed_event_types, "allowed event types"),
            (self.allowed_event_versions, "allowed event versions"),
            (self.allowed_schema_uris, "allowed schema URIs"),
            (self.allowed_data_classifications, "allowed data classifications"),
        ):
            if not values or tuple(sorted(set(values))) != values:
                raise ValueError(f"logical channel {name} must be unique and sorted")
            for value in values:
                _require_text(value, name=f"logical channel {name}", maximum=240)
        if self.representation_name != "canonical-json" or self.encoding != "utf-8":
            raise ValueError("logical channel representation is unsupported")
        if self.delivery_semantics != "at-least-once":
            raise ValueError("logical channel delivery semantics are unsupported")
        if self.durability_required is not True:
            raise ValueError("logical channel must require durable delivery")
        if self.ordering_key_kind != "workflow-run":
            raise ValueError("logical channel ordering key kind is unsupported")
        if self.retention_class != "workflow-operational":
            raise ValueError("logical channel retention class is unsupported")
        if self.maximum_canonical_byte_count != 65_536:
            raise ValueError("logical channel canonical byte limit is unsupported")
        _require_digest(self.canonical_digest, name="logical channel policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("logical channel policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "allowed_data_classifications": list(self.allowed_data_classifications),
            "allowed_event_types": list(self.allowed_event_types),
            "allowed_event_versions": list(self.allowed_event_versions),
            "allowed_schema_uris": list(self.allowed_schema_uris),
            "delivery_semantics": self.delivery_semantics,
            "durability_required": self.durability_required,
            "encoding": self.encoding,
            "logical_channel_id": self.logical_channel_id,
            "logical_channel_version": self.logical_channel_version,
            "maximum_canonical_byte_count": self.maximum_canonical_byte_count,
            "ordering_key_kind": self.ordering_key_kind,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "representation_name": self.representation_name,
            "retention_class": self.retention_class,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_logical_channel_policy() -> WorkflowEventLogicalChannelPolicy:
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-logical-channel",
        "policy_version": "1.0",
        "logical_channel_id": "channel.workflow-dispatch.internal",
        "logical_channel_version": "1.0",
        "allowed_event_types": ("WorkflowStepDispatchRequested",),
        "allowed_event_versions": ("1.0",),
        "allowed_schema_uris": ("urn:project-atlas:event:workflow-step-dispatch-requested:1.0",),
        "allowed_data_classifications": ("internal",),
        "representation_name": "canonical-json",
        "encoding": "utf-8",
        "delivery_semantics": "at-least-once",
        "durability_required": True,
        "ordering_key_kind": "workflow-run",
        "retention_class": "workflow-operational",
        "maximum_canonical_byte_count": 65_536,
    }
    digest_payload = {
        key: list(value) if isinstance(value, tuple) else value for key, value in values.items()
    }
    return WorkflowEventLogicalChannelPolicy(
        policy_id="policy.workflow-event-logical-channel",
        policy_version="1.0",
        logical_channel_id="channel.workflow-dispatch.internal",
        logical_channel_version="1.0",
        allowed_event_types=("WorkflowStepDispatchRequested",),
        allowed_event_versions=("1.0",),
        allowed_schema_uris=("urn:project-atlas:event:workflow-step-dispatch-requested:1.0",),
        allowed_data_classifications=("internal",),
        representation_name="canonical-json",
        encoding="utf-8",
        delivery_semantics="at-least-once",
        durability_required=True,
        ordering_key_kind="workflow-run",
        retention_class="workflow-operational",
        maximum_canonical_byte_count=65_536,
        canonical_digest=canonical_digest(digest_payload),
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventLogicalChannelBindingAuthority:
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("logical channel bindings cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "execution_authorized": self.execution_authorized,
            "publication_authorized": self.publication_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventLogicalChannelBinding:
    """Immutable logical channel evidence that grants no transport authority."""

    binding_id: str
    artifact_id: str
    artifact_digest: str
    content_sha256: str
    canonical_byte_count: int
    admission_id: str
    admission_digest: str
    event_id: str
    event_digest: str
    event_type: str
    event_version: str
    schema_uri: str
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
    policy_id: str
    policy_version: str
    policy_digest: str
    logical_channel_id: str
    logical_channel_version: str
    data_classification: str
    representation_name: str
    encoding: str
    delivery_semantics: str
    durability_required: bool
    ordering_key_kind: str
    ordering_key_value: str
    retention_class: str
    maximum_canonical_byte_count: int
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int
    publisher_subject_id: str
    bound_at: datetime
    state: WorkflowEventLogicalChannelBindingState
    authority: WorkflowEventLogicalChannelBindingAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.binding_id, "logical channel binding id"),
            (self.artifact_id, "logical channel artifact_id"),
            (self.admission_id, "logical channel admission_id"),
            (self.event_id, "logical channel event_id"),
            (self.outbox_entry_id, "logical channel outbox_entry_id"),
            (self.dispatch_intent_id, "logical channel dispatch_intent_id"),
            (self.plan_id, "logical channel plan_id"),
            (self.run_id, "logical channel run_id"),
            (self.step_run_id, "logical channel step_run_id"),
            (self.step_id, "logical channel step_id"),
            (self.attempt_id, "logical channel attempt_id"),
            (self.target_id, "logical channel target_id"),
            (self.policy_id, "logical channel policy_id"),
            (self.policy_version, "logical channel policy_version"),
            (self.logical_channel_id, "logical channel id"),
            (self.logical_channel_version, "logical channel version"),
            (self.ordering_key_value, "logical channel ordering_key_value"),
            (self.orchestration_lease_id, "logical channel orchestration_lease_id"),
            (self.publication_lease_id, "logical channel publication_lease_id"),
            (self.publisher_subject_id, "logical channel publisher_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.artifact_digest, "logical channel artifact_digest"),
            (self.content_sha256, "logical channel content_sha256"),
            (self.admission_digest, "logical channel admission_digest"),
            (self.event_digest, "logical channel event_digest"),
            (self.outbox_entry_digest, "logical channel outbox_entry_digest"),
            (self.dispatch_intent_digest, "logical channel dispatch_intent_digest"),
            (self.plan_digest, "logical channel plan_digest"),
            (self.run_digest, "logical channel run_digest"),
            (self.step_run_digest, "logical channel step_run_digest"),
            (self.attempt_digest, "logical channel attempt_digest"),
            (self.policy_digest, "logical channel policy_digest"),
            (self.orchestration_lease_digest, "logical channel orchestration_lease_digest"),
            (self.publication_lease_digest, "logical channel publication_lease_digest"),
            (self.canonical_digest, "logical channel canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.event_type != "WorkflowStepDispatchRequested" or self.event_version != "1.0":
            raise ValueError("logical channel event contract is unsupported")
        if self.schema_uri != "urn:project-atlas:event:workflow-step-dispatch-requested:1.0":
            raise ValueError("logical channel schema URI is unsupported")
        if self.data_classification != "internal":
            raise ValueError("logical channel classification must be internal")
        if self.representation_name != "canonical-json" or self.encoding != "utf-8":
            raise ValueError("logical channel representation is unsupported")
        if self.delivery_semantics != "at-least-once" or self.durability_required is not True:
            raise ValueError("logical channel delivery contract is unsupported")
        if self.ordering_key_kind != "workflow-run" or self.ordering_key_value != self.run_id:
            raise ValueError("logical channel ordering must use the exact workflow run")
        if self.retention_class != "workflow-operational":
            raise ValueError("logical channel retention class is unsupported")
        if not 1 <= self.canonical_byte_count <= self.maximum_canonical_byte_count == 65_536:
            raise ValueError("logical channel canonical byte count is invalid")
        if self.attempt_number != 1 or self.target_type != "storage":
            raise ValueError("logical channel lineage is unsupported")
        if self.orchestration_fencing_token < 1 or self.publication_fencing_token < 1:
            raise ValueError("logical channel fencing tokens are invalid")
        if self.bound_at.tzinfo is None:
            raise ValueError("logical channel binding time must be timezone-aware")
        if self.state is not WorkflowEventLogicalChannelBindingState.BOUND:
            raise ValueError("logical channel bindings must remain bound")
        if any(self.authority.canonical_value().values()):
            raise ValueError("logical channel bindings cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("logical channel binding canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admission_digest": self.admission_digest,
            "admission_id": self.admission_id,
            "artifact_digest": self.artifact_digest,
            "artifact_id": self.artifact_id,
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "authority": self.authority.canonical_value(),
            "binding_id": self.binding_id,
            "bound_at": self.bound_at.isoformat(),
            "canonical_byte_count": self.canonical_byte_count,
            "content_sha256": self.content_sha256,
            "data_classification": self.data_classification,
            "delivery_semantics": self.delivery_semantics,
            "dispatch_intent_digest": self.dispatch_intent_digest,
            "dispatch_intent_id": self.dispatch_intent_id,
            "durability_required": self.durability_required,
            "encoding": self.encoding,
            "event_digest": self.event_digest,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "logical_channel_id": self.logical_channel_id,
            "logical_channel_version": self.logical_channel_version,
            "maximum_canonical_byte_count": self.maximum_canonical_byte_count,
            "orchestration_fencing_token": self.orchestration_fencing_token,
            "orchestration_lease_digest": self.orchestration_lease_digest,
            "orchestration_lease_id": self.orchestration_lease_id,
            "ordering_key_kind": self.ordering_key_kind,
            "ordering_key_value": self.ordering_key_value,
            "outbox_entry_digest": self.outbox_entry_digest,
            "outbox_entry_id": self.outbox_entry_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "publication_fencing_token": self.publication_fencing_token,
            "publication_lease_digest": self.publication_lease_digest,
            "publication_lease_id": self.publication_lease_id,
            "publisher_subject_id": self.publisher_subject_id,
            "representation_name": self.representation_name,
            "retention_class": self.retention_class,
            "run_digest": self.run_digest,
            "run_id": self.run_id,
            "schema_uri": self.schema_uri,
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


_ALLOWED_DEPLOYMENT_PROFILES = frozenset(
    {"developer", "lab", "enterprise-test", "production", "offline"}
)
_ALLOWED_TRANSPORT_IMPLEMENTATIONS = frozenset(
    {"transport.apache-kafka", "transport.nats-jetstream", "transport.rabbitmq"}
)
_ALLOWED_EVENT_CONTRACTS = frozenset(
    {
        "WorkflowStepDispatchRequested|1.0|"
        "urn:project-atlas:event:workflow-step-dispatch-requested:1.0"
    }
)
_ALLOWED_CLASSIFICATIONS = frozenset({"internal"})
_ALLOWED_REPRESENTATIONS = frozenset({"canonical-json"})
_ALLOWED_ENCODINGS = frozenset({"utf-8"})
_ALLOWED_DELIVERY_SEMANTICS = frozenset({"at-least-once"})
_ALLOWED_ORDERING_KEY_KINDS = frozenset({"workflow-run"})
_ALLOWED_RETENTION_CLASSES = frozenset({"workflow-operational"})
_ALLOWED_TRANSPORT_ROUTE_KINDS = frozenset({"message-broker"})
_ALLOWED_TRANSPORT_TLS_MINIMUM_VERSIONS = frozenset({"1.2", "1.3"})
_ALLOWED_TRANSPORT_PROXY_MODES = frozenset({"prohibited", "deployment-managed"})
_ALLOWED_TRANSPORT_AUTHENTICATION_MECHANISM_CLASSES = frozenset({"mutual-tls", "workload-token"})
_ALLOWED_TRANSPORT_PRINCIPAL_CLASSES = frozenset({"service-workload"})


def _require_allowlisted_values(
    values: tuple[str, ...], *, name: str, allowed: frozenset[str]
) -> None:
    if not values or values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must be non-empty, sorted, and unique")
    if not set(values).issubset(allowed):
        raise ValueError(f"{name} contains an unsupported value")


class _EventTransportCapabilities(Protocol):
    @property
    def supported_event_contracts(self) -> tuple[str, ...]: ...

    @property
    def supported_classifications(self) -> tuple[str, ...]: ...

    @property
    def supported_representations(self) -> tuple[str, ...]: ...

    @property
    def supported_encodings(self) -> tuple[str, ...]: ...

    @property
    def supported_delivery_semantics(self) -> tuple[str, ...]: ...

    @property
    def supported_ordering_key_kinds(self) -> tuple[str, ...]: ...

    @property
    def supported_retention_classes(self) -> tuple[str, ...]: ...


def _validate_event_transport_capabilities(value: _EventTransportCapabilities) -> None:
    for values, name, allowed in (
        (value.supported_event_contracts, "supported_event_contracts", _ALLOWED_EVENT_CONTRACTS),
        (
            value.supported_classifications,
            "supported_classifications",
            _ALLOWED_CLASSIFICATIONS,
        ),
        (
            value.supported_representations,
            "supported_representations",
            _ALLOWED_REPRESENTATIONS,
        ),
        (value.supported_encodings, "supported_encodings", _ALLOWED_ENCODINGS),
        (
            value.supported_delivery_semantics,
            "supported_delivery_semantics",
            _ALLOWED_DELIVERY_SEMANTICS,
        ),
        (
            value.supported_ordering_key_kinds,
            "supported_ordering_key_kinds",
            _ALLOWED_ORDERING_KEY_KINDS,
        ),
        (
            value.supported_retention_classes,
            "supported_retention_classes",
            _ALLOWED_RETENTION_CLASSES,
        ),
    ):
        _require_allowlisted_values(values, name=name, allowed=allowed)


@dataclass(frozen=True, slots=True)
class EventPhysicalTransportProfileSnapshotAuthority:
    route_selection_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("transport profile snapshots cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "execution_authorized": self.execution_authorized,
            "publication_authorized": self.publication_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class DeploymentEventTransportProfile:
    """Server-owned, active deployment manifest from which snapshots are captured."""

    transport_profile_id: str
    transport_profile_revision: str
    deployment_release_id: str
    deployment_profile: str
    scope: WorkflowScope
    transport_resource_id: str
    transport_resource_digest: str
    transport_implementation_id: str
    transport_implementation_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    adapter_contract_digest: str
    supported_event_contracts: tuple[str, ...]
    supported_classifications: tuple[str, ...]
    supported_representations: tuple[str, ...]
    supported_encodings: tuple[str, ...]
    supported_delivery_semantics: tuple[str, ...]
    durable_delivery_supported: bool
    supported_ordering_key_kinds: tuple[str, ...]
    supported_retention_classes: tuple[str, ...]
    maximum_message_byte_count: int
    transport_encryption_required: bool
    restricted_network_supported: bool
    active: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.transport_profile_id, "transport_profile_id"),
            (self.transport_profile_revision, "transport_profile_revision"),
            (self.deployment_release_id, "deployment_release_id"),
            (self.transport_resource_id, "transport_resource_id"),
            (self.transport_implementation_id, "transport_implementation_id"),
            (self.transport_implementation_version, "transport_implementation_version"),
            (self.adapter_contract_id, "adapter_contract_id"),
            (self.adapter_contract_version, "adapter_contract_version"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.transport_resource_digest, "transport_resource_digest"),
            (self.adapter_contract_digest, "adapter_contract_digest"),
            (self.canonical_digest, "transport profile canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.deployment_profile not in _ALLOWED_DEPLOYMENT_PROFILES:
            raise ValueError("deployment_profile is unsupported")
        if self.transport_implementation_id not in _ALLOWED_TRANSPORT_IMPLEMENTATIONS:
            raise ValueError("transport_implementation_id is unsupported")
        _validate_event_transport_capabilities(self)
        if not 1 <= self.maximum_message_byte_count <= 16_777_216:
            raise ValueError("maximum_message_byte_count is outside the supported range")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport profile canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "active": self.active,
            "adapter_contract_digest": self.adapter_contract_digest,
            "adapter_contract_id": self.adapter_contract_id,
            "adapter_contract_version": self.adapter_contract_version,
            "deployment_profile": self.deployment_profile,
            "deployment_release_id": self.deployment_release_id,
            "durable_delivery_supported": self.durable_delivery_supported,
            "maximum_message_byte_count": self.maximum_message_byte_count,
            "restricted_network_supported": self.restricted_network_supported,
            "scope": self.scope.canonical_value(),
            "supported_classifications": self.supported_classifications,
            "supported_delivery_semantics": self.supported_delivery_semantics,
            "supported_encodings": self.supported_encodings,
            "supported_event_contracts": self.supported_event_contracts,
            "supported_ordering_key_kinds": self.supported_ordering_key_kinds,
            "supported_representations": self.supported_representations,
            "supported_retention_classes": self.supported_retention_classes,
            "transport_encryption_required": self.transport_encryption_required,
            "transport_implementation_id": self.transport_implementation_id,
            "transport_implementation_version": self.transport_implementation_version,
            "transport_profile_id": self.transport_profile_id,
            "transport_profile_revision": self.transport_profile_revision,
            "transport_resource_digest": self.transport_resource_digest,
            "transport_resource_id": self.transport_resource_id,
        }


@dataclass(frozen=True, slots=True)
class EventPhysicalTransportProfileSnapshot:
    """Immutable deployment capability evidence with no route or operation authority."""

    snapshot_id: str
    transport_profile_id: str
    transport_profile_revision: str
    source_profile_digest: str
    deployment_release_id: str
    deployment_profile: str
    scope: WorkflowScope
    transport_resource_id: str
    transport_resource_digest: str
    transport_implementation_id: str
    transport_implementation_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    adapter_contract_digest: str
    supported_event_contracts: tuple[str, ...]
    supported_classifications: tuple[str, ...]
    supported_representations: tuple[str, ...]
    supported_encodings: tuple[str, ...]
    supported_delivery_semantics: tuple[str, ...]
    durable_delivery_supported: bool
    supported_ordering_key_kinds: tuple[str, ...]
    supported_retention_classes: tuple[str, ...]
    maximum_message_byte_count: int
    transport_encryption_required: bool
    restricted_network_supported: bool
    snapshotter_subject_id: str
    captured_at: datetime
    state: EventPhysicalTransportProfileSnapshotState
    authority: EventPhysicalTransportProfileSnapshotAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.snapshot_id, "snapshot_id"),
            (self.transport_profile_id, "transport_profile_id"),
            (self.transport_profile_revision, "transport_profile_revision"),
            (self.deployment_release_id, "deployment_release_id"),
            (self.transport_resource_id, "transport_resource_id"),
            (self.transport_implementation_id, "transport_implementation_id"),
            (self.transport_implementation_version, "transport_implementation_version"),
            (self.adapter_contract_id, "adapter_contract_id"),
            (self.adapter_contract_version, "adapter_contract_version"),
            (self.snapshotter_subject_id, "snapshotter_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.source_profile_digest, "source_profile_digest"),
            (self.transport_resource_digest, "transport_resource_digest"),
            (self.adapter_contract_digest, "adapter_contract_digest"),
            (self.canonical_digest, "snapshot canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.deployment_profile not in _ALLOWED_DEPLOYMENT_PROFILES:
            raise ValueError("deployment_profile is unsupported")
        if self.transport_implementation_id not in _ALLOWED_TRANSPORT_IMPLEMENTATIONS:
            raise ValueError("transport_implementation_id is unsupported")
        _validate_event_transport_capabilities(self)
        if not 1 <= self.maximum_message_byte_count <= 16_777_216:
            raise ValueError("maximum_message_byte_count is outside the supported range")
        if self.captured_at.tzinfo is None:
            raise ValueError("snapshot capture time must be timezone-aware")
        if self.state is not EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED:
            raise ValueError("transport profile snapshots must remain snapshotted")
        if any(self.authority.canonical_value().values()):
            raise ValueError("transport profile snapshots cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport profile snapshot canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "adapter_contract_digest": self.adapter_contract_digest,
            "adapter_contract_id": self.adapter_contract_id,
            "adapter_contract_version": self.adapter_contract_version,
            "authority": self.authority.canonical_value(),
            "captured_at": self.captured_at.isoformat(),
            "deployment_profile": self.deployment_profile,
            "deployment_release_id": self.deployment_release_id,
            "durable_delivery_supported": self.durable_delivery_supported,
            "maximum_message_byte_count": self.maximum_message_byte_count,
            "restricted_network_supported": self.restricted_network_supported,
            "scope": self.scope.canonical_value(),
            "snapshot_id": self.snapshot_id,
            "snapshotter_subject_id": self.snapshotter_subject_id,
            "source_profile_digest": self.source_profile_digest,
            "state": self.state.value,
            "supported_classifications": self.supported_classifications,
            "supported_delivery_semantics": self.supported_delivery_semantics,
            "supported_encodings": self.supported_encodings,
            "supported_event_contracts": self.supported_event_contracts,
            "supported_ordering_key_kinds": self.supported_ordering_key_kinds,
            "supported_representations": self.supported_representations,
            "supported_retention_classes": self.supported_retention_classes,
            "transport_encryption_required": self.transport_encryption_required,
            "transport_implementation_id": self.transport_implementation_id,
            "transport_implementation_version": self.transport_implementation_version,
            "transport_profile_id": self.transport_profile_id,
            "transport_profile_revision": self.transport_profile_revision,
            "transport_resource_digest": self.transport_resource_digest,
            "transport_resource_id": self.transport_resource_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

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


def _validate_transport_route_security_requirements(
    value: DeploymentEventTransportRoute | EventPhysicalTransportRouteSnapshot,
) -> None:
    if value.route_kind not in _ALLOWED_TRANSPORT_ROUTE_KINDS:
        raise ValueError("transport route kind is unsupported")
    if value.minimum_tls_version not in _ALLOWED_TRANSPORT_TLS_MINIMUM_VERSIONS:
        raise ValueError("transport route minimum TLS version is unsupported")
    if value.server_authentication_required is not True:
        raise ValueError("transport route must require server authentication")
    if value.plaintext_fallback_prohibited is not True:
        raise ValueError("transport route must prohibit plaintext fallback")
    if value.restricted_network_enforced is not True:
        raise ValueError("transport route must enforce a restricted network")
    if value.public_egress_prohibited is not True:
        raise ValueError("transport route must prohibit public egress")
    if value.proxy_mode not in _ALLOWED_TRANSPORT_PROXY_MODES:
        raise ValueError("transport route proxy mode is unsupported")
    if (
        value.authentication_mechanism_class
        not in _ALLOWED_TRANSPORT_AUTHENTICATION_MECHANISM_CLASSES
    ):
        raise ValueError("transport route authentication mechanism class is unsupported")
    if value.principal_class not in _ALLOWED_TRANSPORT_PRINCIPAL_CLASSES:
        raise ValueError("transport route principal class is unsupported")


@dataclass(frozen=True, slots=True)
class DeploymentEventTransportRoute:
    """Server-owned deployment route descriptor with no resolved endpoint or credential."""

    route_id: str
    route_revision: str
    route_set_id: str
    route_set_revision: str
    selection_epoch_id: str
    selection_epoch_revision: str
    deployment_release_id: str
    deployment_profile: str
    scope: WorkflowScope
    transport_profile_id: str
    transport_profile_revision: str
    transport_resource_id: str
    transport_resource_digest: str
    transport_implementation_id: str
    transport_implementation_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    adapter_contract_digest: str
    route_kind: str
    endpoint_set_id: str
    endpoint_set_revision: str
    destination_id: str
    destination_revision: str
    routing_contract_id: str
    routing_contract_revision: str
    private_route_descriptor_commitment: str
    transport_security_policy_id: str
    transport_security_policy_version: str
    transport_security_policy_digest: str
    minimum_tls_version: str
    server_authentication_required: bool
    client_authentication_required: bool
    plaintext_fallback_prohibited: bool
    network_policy_id: str
    network_policy_version: str
    network_policy_digest: str
    source_zone_class: str
    destination_zone_class: str
    restricted_network_enforced: bool
    public_egress_prohibited: bool
    proxy_mode: str
    credential_requirement_profile_id: str
    credential_requirement_profile_version: str
    credential_requirement_profile_digest: str
    authentication_mechanism_class: str
    principal_class: str
    active: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.route_id, "route_id"),
            (self.route_revision, "route_revision"),
            (self.route_set_id, "route_set_id"),
            (self.route_set_revision, "route_set_revision"),
            (self.selection_epoch_id, "selection_epoch_id"),
            (self.selection_epoch_revision, "selection_epoch_revision"),
            (self.deployment_release_id, "deployment_release_id"),
            (self.transport_profile_id, "transport_profile_id"),
            (self.transport_profile_revision, "transport_profile_revision"),
            (self.transport_resource_id, "transport_resource_id"),
            (self.transport_implementation_id, "transport_implementation_id"),
            (self.transport_implementation_version, "transport_implementation_version"),
            (self.adapter_contract_id, "adapter_contract_id"),
            (self.adapter_contract_version, "adapter_contract_version"),
            (self.endpoint_set_id, "endpoint_set_id"),
            (self.endpoint_set_revision, "endpoint_set_revision"),
            (self.destination_id, "destination_id"),
            (self.destination_revision, "destination_revision"),
            (self.routing_contract_id, "routing_contract_id"),
            (self.routing_contract_revision, "routing_contract_revision"),
            (self.transport_security_policy_id, "transport_security_policy_id"),
            (self.transport_security_policy_version, "transport_security_policy_version"),
            (self.network_policy_id, "network_policy_id"),
            (self.network_policy_version, "network_policy_version"),
            (self.source_zone_class, "source_zone_class"),
            (self.destination_zone_class, "destination_zone_class"),
            (self.credential_requirement_profile_id, "credential_requirement_profile_id"),
            (
                self.credential_requirement_profile_version,
                "credential_requirement_profile_version",
            ),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.transport_resource_digest, "transport_resource_digest"),
            (self.adapter_contract_digest, "adapter_contract_digest"),
            (
                self.private_route_descriptor_commitment,
                "private_route_descriptor_commitment",
            ),
            (self.transport_security_policy_digest, "transport_security_policy_digest"),
            (self.network_policy_digest, "network_policy_digest"),
            (
                self.credential_requirement_profile_digest,
                "credential_requirement_profile_digest",
            ),
            (self.canonical_digest, "transport route canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.deployment_profile not in _ALLOWED_DEPLOYMENT_PROFILES:
            raise ValueError("deployment_profile is unsupported")
        if self.transport_implementation_id not in _ALLOWED_TRANSPORT_IMPLEMENTATIONS:
            raise ValueError("transport_implementation_id is unsupported")
        _validate_transport_route_security_requirements(self)
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport route canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "active": self.active,
            "adapter_contract_digest": self.adapter_contract_digest,
            "adapter_contract_id": self.adapter_contract_id,
            "adapter_contract_version": self.adapter_contract_version,
            "authentication_mechanism_class": self.authentication_mechanism_class,
            "client_authentication_required": self.client_authentication_required,
            "credential_requirement_profile_digest": (self.credential_requirement_profile_digest),
            "credential_requirement_profile_id": self.credential_requirement_profile_id,
            "credential_requirement_profile_version": self.credential_requirement_profile_version,
            "deployment_profile": self.deployment_profile,
            "deployment_release_id": self.deployment_release_id,
            "destination_id": self.destination_id,
            "destination_revision": self.destination_revision,
            "destination_zone_class": self.destination_zone_class,
            "endpoint_set_id": self.endpoint_set_id,
            "endpoint_set_revision": self.endpoint_set_revision,
            "minimum_tls_version": self.minimum_tls_version,
            "network_policy_digest": self.network_policy_digest,
            "network_policy_id": self.network_policy_id,
            "network_policy_version": self.network_policy_version,
            "plaintext_fallback_prohibited": self.plaintext_fallback_prohibited,
            "principal_class": self.principal_class,
            "proxy_mode": self.proxy_mode,
            "public_egress_prohibited": self.public_egress_prohibited,
            "restricted_network_enforced": self.restricted_network_enforced,
            "route_id": self.route_id,
            "route_kind": self.route_kind,
            "route_revision": self.route_revision,
            "route_set_id": self.route_set_id,
            "route_set_revision": self.route_set_revision,
            "routing_contract_id": self.routing_contract_id,
            "routing_contract_revision": self.routing_contract_revision,
            "selection_epoch_id": self.selection_epoch_id,
            "selection_epoch_revision": self.selection_epoch_revision,
            "scope": self.scope.canonical_value(),
            "server_authentication_required": self.server_authentication_required,
            "source_zone_class": self.source_zone_class,
            "transport_implementation_id": self.transport_implementation_id,
            "transport_implementation_version": self.transport_implementation_version,
            "transport_profile_id": self.transport_profile_id,
            "transport_profile_revision": self.transport_profile_revision,
            "transport_resource_digest": self.transport_resource_digest,
            "transport_resource_id": self.transport_resource_id,
            "transport_security_policy_digest": self.transport_security_policy_digest,
            "transport_security_policy_id": self.transport_security_policy_id,
            "transport_security_policy_version": self.transport_security_policy_version,
            "private_route_descriptor_commitment": self.private_route_descriptor_commitment,
        }


@dataclass(frozen=True, slots=True)
class EventPhysicalTransportRouteSnapshotAuthority:
    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_access_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("transport route snapshots cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "network_access_authorized": self.network_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class EventPhysicalTransportRouteSnapshot:
    """Immutable opaque route evidence without resolution or operational authority."""

    snapshot_id: str
    route_id: str
    route_revision: str
    route_set_id: str
    route_set_revision: str
    selection_epoch_id: str
    selection_epoch_revision: str
    source_route_digest: str
    deployment_release_id: str
    deployment_profile: str
    scope: WorkflowScope
    transport_profile_id: str
    transport_profile_revision: str
    transport_resource_id: str
    transport_resource_digest: str
    transport_implementation_id: str
    transport_implementation_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    adapter_contract_digest: str
    route_kind: str
    endpoint_set_id: str
    endpoint_set_revision: str
    destination_id: str
    destination_revision: str
    routing_contract_id: str
    routing_contract_revision: str
    private_route_descriptor_commitment: str
    transport_security_policy_id: str
    transport_security_policy_version: str
    transport_security_policy_digest: str
    minimum_tls_version: str
    server_authentication_required: bool
    client_authentication_required: bool
    plaintext_fallback_prohibited: bool
    network_policy_id: str
    network_policy_version: str
    network_policy_digest: str
    source_zone_class: str
    destination_zone_class: str
    restricted_network_enforced: bool
    public_egress_prohibited: bool
    proxy_mode: str
    credential_requirement_profile_id: str
    credential_requirement_profile_version: str
    credential_requirement_profile_digest: str
    authentication_mechanism_class: str
    principal_class: str
    snapshotter_subject_id: str
    captured_at: datetime
    state: EventPhysicalTransportRouteSnapshotState
    authority: EventPhysicalTransportRouteSnapshotAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.snapshot_id, "route snapshot_id"),
            (self.route_id, "route_id"),
            (self.route_revision, "route_revision"),
            (self.route_set_id, "route_set_id"),
            (self.route_set_revision, "route_set_revision"),
            (self.selection_epoch_id, "selection_epoch_id"),
            (self.selection_epoch_revision, "selection_epoch_revision"),
            (self.deployment_release_id, "deployment_release_id"),
            (self.transport_profile_id, "transport_profile_id"),
            (self.transport_profile_revision, "transport_profile_revision"),
            (self.transport_resource_id, "transport_resource_id"),
            (self.transport_implementation_id, "transport_implementation_id"),
            (self.transport_implementation_version, "transport_implementation_version"),
            (self.adapter_contract_id, "adapter_contract_id"),
            (self.adapter_contract_version, "adapter_contract_version"),
            (self.endpoint_set_id, "endpoint_set_id"),
            (self.endpoint_set_revision, "endpoint_set_revision"),
            (self.destination_id, "destination_id"),
            (self.destination_revision, "destination_revision"),
            (self.routing_contract_id, "routing_contract_id"),
            (self.routing_contract_revision, "routing_contract_revision"),
            (self.transport_security_policy_id, "transport_security_policy_id"),
            (self.transport_security_policy_version, "transport_security_policy_version"),
            (self.network_policy_id, "network_policy_id"),
            (self.network_policy_version, "network_policy_version"),
            (self.source_zone_class, "source_zone_class"),
            (self.destination_zone_class, "destination_zone_class"),
            (self.credential_requirement_profile_id, "credential_requirement_profile_id"),
            (
                self.credential_requirement_profile_version,
                "credential_requirement_profile_version",
            ),
            (self.snapshotter_subject_id, "route snapshotter_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.source_route_digest, "source_route_digest"),
            (self.transport_resource_digest, "transport_resource_digest"),
            (self.adapter_contract_digest, "adapter_contract_digest"),
            (
                self.private_route_descriptor_commitment,
                "private_route_descriptor_commitment",
            ),
            (self.transport_security_policy_digest, "transport_security_policy_digest"),
            (self.network_policy_digest, "network_policy_digest"),
            (
                self.credential_requirement_profile_digest,
                "credential_requirement_profile_digest",
            ),
            (self.canonical_digest, "route snapshot canonical_digest"),
        ):
            _require_digest(value, name=name)
        if self.deployment_profile not in _ALLOWED_DEPLOYMENT_PROFILES:
            raise ValueError("deployment_profile is unsupported")
        if self.transport_implementation_id not in _ALLOWED_TRANSPORT_IMPLEMENTATIONS:
            raise ValueError("transport_implementation_id is unsupported")
        _validate_transport_route_security_requirements(self)
        if self.captured_at.tzinfo is None:
            raise ValueError("route snapshot capture time must be timezone-aware")
        if self.state is not EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED:
            raise ValueError("transport route snapshots must remain snapshotted")
        if any(self.authority.canonical_value().values()):
            raise ValueError("transport route snapshots cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport route snapshot canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "adapter_contract_digest": self.adapter_contract_digest,
            "adapter_contract_id": self.adapter_contract_id,
            "adapter_contract_version": self.adapter_contract_version,
            "authentication_mechanism_class": self.authentication_mechanism_class,
            "authority": self.authority.canonical_value(),
            "captured_at": self.captured_at.isoformat(),
            "client_authentication_required": self.client_authentication_required,
            "credential_requirement_profile_digest": (self.credential_requirement_profile_digest),
            "credential_requirement_profile_id": self.credential_requirement_profile_id,
            "credential_requirement_profile_version": self.credential_requirement_profile_version,
            "deployment_profile": self.deployment_profile,
            "deployment_release_id": self.deployment_release_id,
            "destination_id": self.destination_id,
            "destination_revision": self.destination_revision,
            "destination_zone_class": self.destination_zone_class,
            "endpoint_set_id": self.endpoint_set_id,
            "endpoint_set_revision": self.endpoint_set_revision,
            "minimum_tls_version": self.minimum_tls_version,
            "network_policy_digest": self.network_policy_digest,
            "network_policy_id": self.network_policy_id,
            "network_policy_version": self.network_policy_version,
            "plaintext_fallback_prohibited": self.plaintext_fallback_prohibited,
            "principal_class": self.principal_class,
            "proxy_mode": self.proxy_mode,
            "public_egress_prohibited": self.public_egress_prohibited,
            "restricted_network_enforced": self.restricted_network_enforced,
            "route_id": self.route_id,
            "route_kind": self.route_kind,
            "route_revision": self.route_revision,
            "route_set_id": self.route_set_id,
            "route_set_revision": self.route_set_revision,
            "routing_contract_id": self.routing_contract_id,
            "routing_contract_revision": self.routing_contract_revision,
            "selection_epoch_id": self.selection_epoch_id,
            "selection_epoch_revision": self.selection_epoch_revision,
            "scope": self.scope.canonical_value(),
            "server_authentication_required": self.server_authentication_required,
            "source_zone_class": self.source_zone_class,
            "snapshot_id": self.snapshot_id,
            "snapshotter_subject_id": self.snapshotter_subject_id,
            "source_route_digest": self.source_route_digest,
            "state": self.state.value,
            "transport_implementation_id": self.transport_implementation_id,
            "transport_implementation_version": self.transport_implementation_version,
            "transport_profile_id": self.transport_profile_id,
            "transport_profile_revision": self.transport_profile_revision,
            "transport_resource_digest": self.transport_resource_digest,
            "transport_resource_id": self.transport_resource_id,
            "transport_security_policy_digest": self.transport_security_policy_digest,
            "transport_security_policy_id": self.transport_security_policy_id,
            "transport_security_policy_version": self.transport_security_policy_version,
            "private_route_descriptor_commitment": self.private_route_descriptor_commitment,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return False

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

    @property
    def grants_route_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

    @property
    def grants_network_access_authority(self) -> bool:
        return False

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return False

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
class DeploymentPhysicalTransportCredentialAssignment:
    """Deployment-owned credential metadata without secret material or a secret locator."""

    assignment_id: str
    assignment_revision: str
    scope: WorkflowScope
    route_id: str
    route_revision: str
    source_route_digest: str
    credential_requirement_profile_id: str
    credential_requirement_profile_version: str
    credential_requirement_profile_digest: str
    credential_profile_id: str
    credential_profile_version: str
    credential_profile_digest: str
    authentication_mechanism_class: str
    principal_class: str
    privilege_class: str
    target_scope_commitment: str
    credential_generation: int
    rotation_epoch: int
    activated_at: datetime
    expires_at: datetime
    revoked: bool
    active: bool
    broker_policy_id: str
    broker_policy_version: str
    broker_policy_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.assignment_id, "credential assignment_id"),
            (self.assignment_revision, "credential assignment_revision"),
            (self.route_id, "credential assignment route_id"),
            (self.route_revision, "credential assignment route_revision"),
            (
                self.credential_requirement_profile_id,
                "credential assignment requirement profile_id",
            ),
            (
                self.credential_requirement_profile_version,
                "credential assignment requirement profile_version",
            ),
            (self.credential_profile_id, "credential assignment profile_id"),
            (self.credential_profile_version, "credential assignment profile_version"),
            (self.broker_policy_id, "credential assignment broker policy_id"),
            (self.broker_policy_version, "credential assignment broker policy_version"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.source_route_digest, "credential assignment source_route_digest"),
            (
                self.credential_requirement_profile_digest,
                "credential assignment requirement profile_digest",
            ),
            (self.credential_profile_digest, "credential assignment profile_digest"),
            (self.target_scope_commitment, "credential assignment target scope commitment"),
            (self.broker_policy_digest, "credential assignment broker policy_digest"),
            (self.canonical_digest, "credential assignment canonical_digest"),
        ):
            _require_digest(value, name=name)
        if (
            self.authentication_mechanism_class
            not in _ALLOWED_TRANSPORT_AUTHENTICATION_MECHANISM_CLASSES
        ):
            raise ValueError("credential assignment authentication mechanism is unsupported")
        if self.principal_class not in _ALLOWED_TRANSPORT_PRINCIPAL_CLASSES:
            raise ValueError("credential assignment principal class is unsupported")
        if self.privilege_class != "read-only":
            raise ValueError("credential assignment must be least privilege")
        if self.credential_generation < 1 or self.rotation_epoch < 1:
            raise ValueError("credential assignment generation and rotation epoch must be positive")
        if self.activated_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("credential assignment lifecycle times must be timezone-aware")
        if self.expires_at <= self.activated_at:
            raise ValueError("credential assignment expiry must follow activation")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential assignment canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "activated_at": self.activated_at.isoformat(),
            "active": self.active,
            "assignment_id": self.assignment_id,
            "assignment_revision": self.assignment_revision,
            "authentication_mechanism_class": self.authentication_mechanism_class,
            "broker_policy_digest": self.broker_policy_digest,
            "broker_policy_id": self.broker_policy_id,
            "broker_policy_version": self.broker_policy_version,
            "credential_generation": self.credential_generation,
            "credential_profile_digest": self.credential_profile_digest,
            "credential_profile_id": self.credential_profile_id,
            "credential_profile_version": self.credential_profile_version,
            "credential_requirement_profile_digest": (self.credential_requirement_profile_digest),
            "credential_requirement_profile_id": self.credential_requirement_profile_id,
            "credential_requirement_profile_version": (self.credential_requirement_profile_version),
            "expires_at": self.expires_at.isoformat(),
            "principal_class": self.principal_class,
            "privilege_class": self.privilege_class,
            "revoked": self.revoked,
            "rotation_epoch": self.rotation_epoch,
            "route_id": self.route_id,
            "route_revision": self.route_revision,
            "scope": self.scope.canonical_value(),
            "source_route_digest": self.source_route_digest,
            "target_scope_commitment": self.target_scope_commitment,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def select_deployment_physical_transport_credential_assignment_head(
    assignments: tuple[DeploymentPhysicalTransportCredentialAssignment, ...],
) -> DeploymentPhysicalTransportCredentialAssignment | None:
    if not assignments:
        return None
    assignment_ids = {assignment.assignment_id for assignment in assignments}
    if len(assignment_ids) != 1:
        raise ValueError("credential assignment head candidates must share one assignment id")
    ranks = [
        (assignment.rotation_epoch, assignment.credential_generation) for assignment in assignments
    ]
    if len(ranks) != len(set(ranks)):
        raise ValueError("credential assignment head generation is ambiguous")
    return max(
        assignments,
        key=lambda assignment: (assignment.rotation_epoch, assignment.credential_generation),
    )


@dataclass(frozen=True, slots=True)
class EventPhysicalTransportCredentialAssignmentSnapshotAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("credential assignment snapshots cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
        }


@dataclass(frozen=True, slots=True)
class EventPhysicalTransportCredentialAssignmentSnapshot:
    """Historical assignment evidence without workflow binding or credential access."""

    snapshot_id: str
    assignment_id: str
    assignment_revision: str
    source_assignment_digest: str
    scope: WorkflowScope
    route_snapshot_id: str
    route_id: str
    route_revision: str
    source_route_digest: str
    credential_requirement_profile_id: str
    credential_requirement_profile_version: str
    credential_requirement_profile_digest: str
    credential_profile_id: str
    credential_profile_version: str
    credential_profile_digest: str
    authentication_mechanism_class: str
    principal_class: str
    privilege_class: str
    target_scope_commitment: str
    credential_generation: int
    rotation_epoch: int
    activated_at: datetime
    expires_at: datetime
    source_non_revoked: bool
    broker_policy_id: str
    broker_policy_version: str
    broker_policy_digest: str
    snapshotter_subject_id: str
    captured_at: datetime
    state: EventPhysicalTransportCredentialAssignmentSnapshotState
    authority: EventPhysicalTransportCredentialAssignmentSnapshotAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.snapshot_id, "credential assignment snapshot_id"),
            (self.assignment_id, "credential assignment snapshot assignment_id"),
            (self.assignment_revision, "credential assignment snapshot assignment_revision"),
            (self.route_snapshot_id, "credential assignment snapshot route_snapshot_id"),
            (self.route_id, "credential assignment snapshot route_id"),
            (self.route_revision, "credential assignment snapshot route_revision"),
            (
                self.credential_requirement_profile_id,
                "credential assignment snapshot requirement profile_id",
            ),
            (
                self.credential_requirement_profile_version,
                "credential assignment snapshot requirement profile_version",
            ),
            (self.credential_profile_id, "credential assignment snapshot profile_id"),
            (self.credential_profile_version, "credential assignment snapshot profile_version"),
            (self.broker_policy_id, "credential assignment snapshot broker policy_id"),
            (self.broker_policy_version, "credential assignment snapshot broker policy_version"),
            (self.snapshotter_subject_id, "credential assignment snapshotter_subject_id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.source_assignment_digest, "credential assignment snapshot source digest"),
            (self.source_route_digest, "credential assignment snapshot route digest"),
            (
                self.credential_requirement_profile_digest,
                "credential assignment snapshot requirement profile digest",
            ),
            (self.credential_profile_digest, "credential assignment snapshot profile digest"),
            (self.target_scope_commitment, "credential assignment snapshot target commitment"),
            (self.broker_policy_digest, "credential assignment snapshot broker policy digest"),
            (self.canonical_digest, "credential assignment snapshot canonical digest"),
        ):
            _require_digest(value, name=name)
        if (
            self.authentication_mechanism_class
            not in _ALLOWED_TRANSPORT_AUTHENTICATION_MECHANISM_CLASSES
        ):
            raise ValueError("credential assignment snapshot mechanism is unsupported")
        if self.principal_class not in _ALLOWED_TRANSPORT_PRINCIPAL_CLASSES:
            raise ValueError("credential assignment snapshot principal is unsupported")
        if self.privilege_class != "read-only":
            raise ValueError("credential assignment snapshot must remain least privilege")
        if self.credential_generation < 1 or self.rotation_epoch < 1:
            raise ValueError("credential assignment snapshot epochs must be positive")
        if (
            self.activated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.captured_at.tzinfo is None
        ):
            raise ValueError("credential assignment snapshot times must be timezone-aware")
        if not self.activated_at <= self.captured_at < self.expires_at:
            raise ValueError("credential assignment snapshot must be captured while active")
        if self.source_non_revoked is not True:
            raise ValueError("credential assignment snapshot source must be non-revoked")
        if self.state is not EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED:
            raise ValueError("credential assignment snapshots must remain snapshotted")
        if any(self.authority.canonical_value().values()):
            raise ValueError("credential assignment snapshots cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential assignment snapshot canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "activated_at": self.activated_at.isoformat(),
            "assignment_id": self.assignment_id,
            "assignment_revision": self.assignment_revision,
            "authentication_mechanism_class": self.authentication_mechanism_class,
            "authority": self.authority.canonical_value(),
            "broker_policy_digest": self.broker_policy_digest,
            "broker_policy_id": self.broker_policy_id,
            "broker_policy_version": self.broker_policy_version,
            "captured_at": self.captured_at.isoformat(),
            "credential_generation": self.credential_generation,
            "credential_profile_digest": self.credential_profile_digest,
            "credential_profile_id": self.credential_profile_id,
            "credential_profile_version": self.credential_profile_version,
            "credential_requirement_profile_digest": (self.credential_requirement_profile_digest),
            "credential_requirement_profile_id": self.credential_requirement_profile_id,
            "credential_requirement_profile_version": (self.credential_requirement_profile_version),
            "expires_at": self.expires_at.isoformat(),
            "principal_class": self.principal_class,
            "privilege_class": self.privilege_class,
            "rotation_epoch": self.rotation_epoch,
            "route_id": self.route_id,
            "route_revision": self.route_revision,
            "route_snapshot_id": self.route_snapshot_id,
            "scope": self.scope.canonical_value(),
            "snapshot_id": self.snapshot_id,
            "snapshotter_subject_id": self.snapshotter_subject_id,
            "source_assignment_digest": self.source_assignment_digest,
            "source_non_revoked": self.source_non_revoked,
            "source_route_digest": self.source_route_digest,
            "state": self.state.value,
            "target_scope_commitment": self.target_scope_commitment,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

    @property
    def grants_network_access_authority(self) -> bool:
        return False

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return False

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
class WorkflowEventTransportCompatibilityPolicy:
    """Code-owned comparison contract that grants no physical transport authority."""

    policy_id: str
    policy_version: str
    event_type: str
    event_version: str
    schema_uri: str
    data_classification: str
    representation_name: str
    encoding: str
    delivery_semantics: str
    durability_required: bool
    ordering_key_kind: str
    retention_class: str
    maximum_logical_byte_count: int
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="transport compatibility policy_id")
        _require_identifier(self.policy_version, name="transport compatibility policy_version")
        if self.event_type != "WorkflowStepDispatchRequested" or self.event_version != "1.0":
            raise ValueError("transport compatibility event contract is unsupported")
        if self.schema_uri != "urn:project-atlas:event:workflow-step-dispatch-requested:1.0":
            raise ValueError("transport compatibility schema URI is unsupported")
        if self.data_classification != "internal":
            raise ValueError("transport compatibility classification is unsupported")
        if self.representation_name != "canonical-json" or self.encoding != "utf-8":
            raise ValueError("transport compatibility representation is unsupported")
        if self.delivery_semantics != "at-least-once" or self.durability_required is not True:
            raise ValueError("transport compatibility delivery contract is unsupported")
        if self.ordering_key_kind != "workflow-run":
            raise ValueError("transport compatibility ordering contract is unsupported")
        if self.retention_class != "workflow-operational":
            raise ValueError("transport compatibility retention contract is unsupported")
        if self.maximum_logical_byte_count != 65_536:
            raise ValueError("transport compatibility logical byte limit is unsupported")
        _require_digest(self.canonical_digest, name="transport compatibility policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport compatibility policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "data_classification": self.data_classification,
            "delivery_semantics": self.delivery_semantics,
            "durability_required": self.durability_required,
            "encoding": self.encoding,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "maximum_logical_byte_count": self.maximum_logical_byte_count,
            "ordering_key_kind": self.ordering_key_kind,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "representation_name": self.representation_name,
            "retention_class": self.retention_class,
            "schema_uri": self.schema_uri,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_transport_compatibility_policy() -> (
    WorkflowEventTransportCompatibilityPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-transport-compatibility",
        "policy_version": "1.0",
        "event_type": "WorkflowStepDispatchRequested",
        "event_version": "1.0",
        "schema_uri": "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        "data_classification": "internal",
        "representation_name": "canonical-json",
        "encoding": "utf-8",
        "delivery_semantics": "at-least-once",
        "durability_required": True,
        "ordering_key_kind": "workflow-run",
        "retention_class": "workflow-operational",
        "maximum_logical_byte_count": 65_536,
    }
    return WorkflowEventTransportCompatibilityPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportCompatibilityAdmissionAuthority:
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_access_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError(
                "transport compatibility admissions cannot grant operational authority"
            )

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "execution_authorized": self.execution_authorized,
            "publication_authorized": self.publication_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportCompatibilityAdmission:
    """Immutable proof that two exact declared contracts match under one policy."""

    compatibility_admission_id: str
    logical_channel_binding_id: str
    logical_channel_binding_digest: str
    transport_profile_snapshot_id: str
    transport_profile_snapshot_digest: str
    transport_profile_id: str
    transport_profile_revision: str
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    event_type: str
    event_version: str
    schema_uri: str
    data_classification: str
    representation_name: str
    encoding: str
    delivery_semantics: str
    durability_required: bool
    ordering_key_kind: str
    retention_class: str
    logical_maximum_byte_count: int
    artifact_byte_count: int
    profile_maximum_message_byte_count: int
    admitter_subject_id: str
    admitted_at: datetime
    state: WorkflowEventTransportCompatibilityAdmissionState
    authority: WorkflowEventTransportCompatibilityAdmissionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.compatibility_admission_id, "transport compatibility admission id"),
            (self.logical_channel_binding_id, "logical channel binding id"),
            (self.transport_profile_snapshot_id, "transport profile snapshot id"),
            (self.transport_profile_id, "transport profile id"),
            (self.transport_profile_revision, "transport profile revision"),
            (self.policy_id, "transport compatibility policy id"),
            (self.policy_version, "transport compatibility policy version"),
            (self.admitter_subject_id, "transport compatibility admitter subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.logical_channel_binding_digest, "logical channel binding digest"),
            (self.transport_profile_snapshot_digest, "transport profile snapshot digest"),
            (self.policy_digest, "transport compatibility policy digest"),
            (self.canonical_digest, "transport compatibility admission digest"),
        ):
            _require_digest(value, name=name)
        if self.event_type != "WorkflowStepDispatchRequested" or self.event_version != "1.0":
            raise ValueError("transport compatibility event contract is unsupported")
        if self.schema_uri != "urn:project-atlas:event:workflow-step-dispatch-requested:1.0":
            raise ValueError("transport compatibility schema URI is unsupported")
        if self.data_classification != "internal":
            raise ValueError("transport compatibility classification is unsupported")
        if self.representation_name != "canonical-json" or self.encoding != "utf-8":
            raise ValueError("transport compatibility representation is unsupported")
        if self.delivery_semantics != "at-least-once" or self.durability_required is not True:
            raise ValueError("transport compatibility delivery contract is unsupported")
        if self.ordering_key_kind != "workflow-run":
            raise ValueError("transport compatibility ordering contract is unsupported")
        if self.retention_class != "workflow-operational":
            raise ValueError("transport compatibility retention contract is unsupported")
        if not 1 <= self.artifact_byte_count <= self.logical_maximum_byte_count == 65_536:
            raise ValueError("transport compatibility logical byte evidence is invalid")
        if self.profile_maximum_message_byte_count < self.logical_maximum_byte_count:
            raise ValueError("transport compatibility profile byte evidence is insufficient")
        if self.admitted_at.tzinfo is None:
            raise ValueError("transport compatibility admission time must be timezone-aware")
        if self.state is not WorkflowEventTransportCompatibilityAdmissionState.ADMITTED:
            raise ValueError("transport compatibility admissions must remain admitted")
        if any(self.authority.canonical_value().values()):
            raise ValueError(
                "transport compatibility admissions cannot grant operational authority"
            )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport compatibility admission canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admitted_at": self.admitted_at.isoformat(),
            "admitter_subject_id": self.admitter_subject_id,
            "artifact_byte_count": self.artifact_byte_count,
            "authority": self.authority.canonical_value(),
            "compatibility_admission_id": self.compatibility_admission_id,
            "data_classification": self.data_classification,
            "delivery_semantics": self.delivery_semantics,
            "durability_required": self.durability_required,
            "encoding": self.encoding,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "logical_channel_binding_digest": self.logical_channel_binding_digest,
            "logical_channel_binding_id": self.logical_channel_binding_id,
            "logical_maximum_byte_count": self.logical_maximum_byte_count,
            "ordering_key_kind": self.ordering_key_kind,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "profile_maximum_message_byte_count": self.profile_maximum_message_byte_count,
            "representation_name": self.representation_name,
            "retention_class": self.retention_class,
            "schema_uri": self.schema_uri,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "transport_profile_id": self.transport_profile_id,
            "transport_profile_revision": self.transport_profile_revision,
            "transport_profile_snapshot_digest": self.transport_profile_snapshot_digest,
            "transport_profile_snapshot_id": self.transport_profile_snapshot_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

    @property
    def grants_route_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

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
class WorkflowEventPhysicalTransportRouteBindingPolicy:
    """Code-owned requirements for binding an admitted event to one physical route."""

    policy_id: str
    policy_version: str
    minimum_tls_version: str
    server_authentication_required: bool
    plaintext_fallback_prohibited: bool
    restricted_network_required: bool
    public_egress_prohibited: bool
    allowed_proxy_modes: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="physical route binding policy_id")
        _require_identifier(self.policy_version, name="physical route binding policy_version")
        if self.minimum_tls_version != "1.3":
            raise ValueError("physical route binding policy must require TLS 1.3")
        if self.server_authentication_required is not True:
            raise ValueError("physical route binding policy must require server authentication")
        if self.plaintext_fallback_prohibited is not True:
            raise ValueError("physical route binding policy must prohibit plaintext fallback")
        if self.restricted_network_required is not True:
            raise ValueError("physical route binding policy must require a restricted network")
        if self.public_egress_prohibited is not True:
            raise ValueError("physical route binding policy must prohibit public egress")
        if self.allowed_proxy_modes != ("deployment-managed", "prohibited"):
            raise ValueError("physical route binding policy proxy modes are unsupported")
        _require_digest(self.canonical_digest, name="physical route binding policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("physical route binding policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "allowed_proxy_modes": self.allowed_proxy_modes,
            "minimum_tls_version": self.minimum_tls_version,
            "plaintext_fallback_prohibited": self.plaintext_fallback_prohibited,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "public_egress_prohibited": self.public_egress_prohibited,
            "restricted_network_required": self.restricted_network_required,
            "server_authentication_required": self.server_authentication_required,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_route_binding_policy() -> (
    WorkflowEventPhysicalTransportRouteBindingPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-route-binding",
        "policy_version": "1.0",
        "minimum_tls_version": "1.3",
        "server_authentication_required": True,
        "plaintext_fallback_prohibited": True,
        "restricted_network_required": True,
        "public_egress_prohibited": True,
        "allowed_proxy_modes": ("deployment-managed", "prohibited"),
    }
    return WorkflowEventPhysicalTransportRouteBindingPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteBindingAuthority:
    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_access_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("physical route bindings cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "network_access_authorized": self.network_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteBinding:
    """Immutable evidence joining one admitted logical event to one physical route."""

    binding_id: str
    logical_channel_binding_id: str
    logical_channel_binding_digest: str
    transport_compatibility_admission_id: str
    transport_compatibility_admission_digest: str
    transport_profile_snapshot_id: str
    transport_profile_snapshot_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    binder_subject_id: str
    bound_at: datetime
    state: WorkflowEventPhysicalTransportRouteBindingState
    authority: WorkflowEventPhysicalTransportRouteBindingAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.binding_id, "physical route binding id"),
            (self.logical_channel_binding_id, "logical channel binding id"),
            (
                self.transport_compatibility_admission_id,
                "transport compatibility admission id",
            ),
            (self.transport_profile_snapshot_id, "transport profile snapshot id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.policy_id, "physical route binding policy id"),
            (self.policy_version, "physical route binding policy version"),
            (self.binder_subject_id, "physical route binder subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.logical_channel_binding_digest, "logical channel binding digest"),
            (
                self.transport_compatibility_admission_digest,
                "transport compatibility admission digest",
            ),
            (self.transport_profile_snapshot_digest, "transport profile snapshot digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.policy_digest, "physical route binding policy digest"),
            (self.canonical_digest, "physical route binding canonical digest"),
        ):
            _require_digest(value, name=name)
        if self.bound_at.tzinfo is None:
            raise ValueError("physical route binding time must be timezone-aware")
        if self.state is not WorkflowEventPhysicalTransportRouteBindingState.BOUND:
            raise ValueError("physical route bindings must remain bound")
        if any(self.authority.canonical_value().values()):
            raise ValueError("physical route bindings cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("physical route binding canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "authority": self.authority.canonical_value(),
            "binder_subject_id": self.binder_subject_id,
            "binding_id": self.binding_id,
            "bound_at": self.bound_at.isoformat(),
            "logical_channel_binding_digest": self.logical_channel_binding_digest,
            "logical_channel_binding_id": self.logical_channel_binding_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "transport_compatibility_admission_digest": (
                self.transport_compatibility_admission_digest
            ),
            "transport_compatibility_admission_id": self.transport_compatibility_admission_id,
            "transport_profile_snapshot_digest": self.transport_profile_snapshot_digest,
            "transport_profile_snapshot_id": self.transport_profile_snapshot_id,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return False

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

    @property
    def grants_route_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

    @property
    def grants_network_access_authority(self) -> bool:
        return False

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return False

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
class WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy:
    """Code-owned compatibility rules for immutable credential-assignment binding."""

    policy_id: str
    policy_version: str
    exact_route_snapshot_required: bool
    exact_credential_requirement_required: bool
    exact_authentication_mechanism_required: bool
    exact_principal_class_required: bool
    required_privilege_class: str
    positive_credential_generation_required: bool
    positive_rotation_epoch_required: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(
            self.policy_id,
            name="physical transport credential assignment binding policy_id",
        )
        _require_identifier(
            self.policy_version,
            name="physical transport credential assignment binding policy_version",
        )
        required_flags = (
            self.exact_route_snapshot_required,
            self.exact_credential_requirement_required,
            self.exact_authentication_mechanism_required,
            self.exact_principal_class_required,
            self.positive_credential_generation_required,
            self.positive_rotation_epoch_required,
        )
        if not all(value is True for value in required_flags):
            raise ValueError("physical transport credential assignment binding policy is unsafe")
        if self.required_privilege_class != "read-only":
            raise ValueError(
                "physical transport credential assignment binding policy must require read-only"
            )
        _require_digest(
            self.canonical_digest,
            name="physical transport credential assignment binding policy digest",
        )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError(
                "physical transport credential assignment binding policy digest mismatch"
            )

    def digest_payload(self) -> dict[str, object]:
        return {
            "exact_authentication_mechanism_required": (
                self.exact_authentication_mechanism_required
            ),
            "exact_credential_requirement_required": (self.exact_credential_requirement_required),
            "exact_principal_class_required": self.exact_principal_class_required,
            "exact_route_snapshot_required": self.exact_route_snapshot_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "positive_credential_generation_required": (
                self.positive_credential_generation_required
            ),
            "positive_rotation_epoch_required": self.positive_rotation_epoch_required,
            "required_privilege_class": self.required_privilege_class,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_credential_assignment_binding_policy() -> (
    WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy
):
    values: dict[str, object] = {
        "policy_id": ("policy.workflow-event-physical-transport-credential-assignment-binding"),
        "policy_version": "1.0",
        "exact_route_snapshot_required": True,
        "exact_credential_requirement_required": True,
        "exact_authentication_mechanism_required": True,
        "exact_principal_class_required": True,
        "required_privilege_class": "read-only",
        "positive_credential_generation_required": True,
        "positive_rotation_epoch_required": True,
    }
    return WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError(
                "physical transport credential assignment bindings cannot grant authority"
            )

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": (self.protected_artifact_access_authorized),
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAssignmentBinding:
    """Immutable historical selection without credential or network authority."""

    binding_id: str
    physical_transport_route_binding_id: str
    physical_transport_route_binding_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    binder_subject_id: str
    bound_at: datetime
    state: WorkflowEventPhysicalTransportCredentialAssignmentBindingState
    authority: WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.binding_id, "credential assignment binding id"),
            (self.physical_transport_route_binding_id, "physical route binding id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.credential_assignment_snapshot_id, "credential assignment snapshot id"),
            (self.policy_id, "credential assignment binding policy id"),
            (self.policy_version, "credential assignment binding policy version"),
            (self.binder_subject_id, "credential assignment binder subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (
                self.physical_transport_route_binding_digest,
                "physical route binding digest",
            ),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (
                self.credential_assignment_snapshot_digest,
                "credential assignment snapshot digest",
            ),
            (self.policy_digest, "credential assignment binding policy digest"),
            (self.canonical_digest, "credential assignment binding canonical digest"),
        ):
            _require_digest(value, name=name)
        if self.bound_at.tzinfo is None:
            raise ValueError("credential assignment binding time must be timezone-aware")
        if self.state is not WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND:
            raise ValueError("credential assignment bindings must remain bound")
        if any(self.authority.canonical_value().values()):
            raise ValueError("credential assignment bindings cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential assignment binding canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "authority": self.authority.canonical_value(),
            "binder_subject_id": self.binder_subject_id,
            "binding_id": self.binding_id,
            "bound_at": self.bound_at.isoformat(),
            "credential_assignment_snapshot_digest": (self.credential_assignment_snapshot_digest),
            "credential_assignment_snapshot_id": self.credential_assignment_snapshot_id,
            "physical_transport_route_binding_digest": (
                self.physical_transport_route_binding_digest
            ),
            "physical_transport_route_binding_id": self.physical_transport_route_binding_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return False

    @property
    def grants_protected_artifact_access_authority(self) -> bool:
        return False

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

    @property
    def grants_route_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_selection_authority(self) -> bool:
        return False

    @property
    def grants_credential_assignment_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

    @property
    def grants_credential_brokerage_authority(self) -> bool:
        return False

    @property
    def grants_credential_resolution_authority(self) -> bool:
        return False

    @property
    def grants_credential_delivery_authority(self) -> bool:
        return False

    @property
    def grants_network_access_authority(self) -> bool:
        return False

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return False

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

    @property
    def grants_infrastructure_mutation_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessPolicy:
    """Code-owned requirements for a bounded assignment-head admission."""

    policy_id: str
    policy_version: str
    validity_window_seconds: int
    unique_current_head_required: bool
    monotonic_rotation_rank_required: bool
    active_assignment_required: bool
    non_revoked_assignment_required: bool
    assignment_expiry_bound_required: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="credential assignment freshness policy id")
        _require_identifier(
            self.policy_version,
            name="credential assignment freshness policy version",
        )
        if self.validity_window_seconds != 60:
            raise ValueError("credential assignment freshness validity window must be 60 seconds")
        if not all(
            value is True
            for value in (
                self.unique_current_head_required,
                self.monotonic_rotation_rank_required,
                self.active_assignment_required,
                self.non_revoked_assignment_required,
                self.assignment_expiry_bound_required,
            )
        ):
            raise ValueError("credential assignment freshness policy is unsafe")
        _require_digest(
            self.canonical_digest,
            name="credential assignment freshness policy digest",
        )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential assignment freshness policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "active_assignment_required": self.active_assignment_required,
            "assignment_expiry_bound_required": self.assignment_expiry_bound_required,
            "monotonic_rotation_rank_required": self.monotonic_rotation_rank_required,
            "non_revoked_assignment_required": self.non_revoked_assignment_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "unique_current_head_required": self.unique_current_head_required,
            "validity_window_seconds": self.validity_window_seconds,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy() -> (
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessPolicy
):
    values: dict[str, object] = {
        "policy_id": ("policy.workflow-event-physical-transport-credential-assignment-freshness"),
        "policy_version": "1.0",
        "validity_window_seconds": 60,
        "unique_current_head_required": True,
        "monotonic_rotation_rank_required": True,
        "active_assignment_required": True,
        "non_revoked_assignment_required": True,
        "assignment_expiry_bound_required": True,
    }
    return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(value is not False for value in self.canonical_value().values()):
            raise ValueError("credential assignment freshness admissions cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": (self.protected_artifact_access_authorized),
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
    """Bounded current-assignment evidence without credential access authority."""

    freshness_admission_id: str
    physical_transport_credential_assignment_binding_id: str
    physical_transport_credential_assignment_binding_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    assignment_id: str
    assignment_revision: str
    source_assignment_digest: str
    credential_generation: int
    rotation_epoch: int
    assignment_activated_at: datetime
    assignment_expires_at: datetime
    assignment_active: bool
    assignment_non_revoked: bool
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    admitter_subject_id: str
    evaluated_at: datetime
    valid_until: datetime
    state: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState
    authority: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.freshness_admission_id, "credential assignment freshness admission id"),
            (
                self.physical_transport_credential_assignment_binding_id,
                "credential assignment binding id",
            ),
            (self.credential_assignment_snapshot_id, "credential assignment snapshot id"),
            (self.assignment_id, "credential assignment id"),
            (self.assignment_revision, "credential assignment revision"),
            (self.policy_id, "credential assignment freshness policy id"),
            (self.policy_version, "credential assignment freshness policy version"),
            (self.admitter_subject_id, "credential assignment freshness admitter subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (
                self.physical_transport_credential_assignment_binding_digest,
                "credential assignment binding digest",
            ),
            (
                self.credential_assignment_snapshot_digest,
                "credential assignment snapshot digest",
            ),
            (self.source_assignment_digest, "credential assignment source digest"),
            (self.policy_digest, "credential assignment freshness policy digest"),
            (self.canonical_digest, "credential assignment freshness admission digest"),
        ):
            _require_digest(value, name=name)
        if self.credential_generation < 1 or self.rotation_epoch < 1:
            raise ValueError("credential assignment freshness rank must be positive")
        if (
            self.assignment_activated_at.tzinfo is None
            or self.assignment_expires_at.tzinfo is None
            or self.evaluated_at.tzinfo is None
            or self.valid_until.tzinfo is None
        ):
            raise ValueError("credential assignment freshness times must be timezone-aware")
        if not self.assignment_activated_at <= self.evaluated_at < self.assignment_expires_at:
            raise ValueError("credential assignment must be active at freshness evaluation")
        if self.valid_until - self.evaluated_at > timedelta(seconds=60):
            raise ValueError("credential assignment freshness validity exceeds policy maximum")
        if not self.evaluated_at < self.valid_until <= self.assignment_expires_at:
            raise ValueError("credential assignment freshness validity is outside assignment life")
        if self.assignment_active is not True or self.assignment_non_revoked is not True:
            raise ValueError("credential assignment freshness source state is inadmissible")
        if self.state.value != "admitted_current":
            raise ValueError("credential assignment freshness must remain admitted_current")
        if any(self.authority.canonical_value().values()):
            raise ValueError("credential assignment freshness cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential assignment freshness admission digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admitter_subject_id": self.admitter_subject_id,
            "assignment_activated_at": self.assignment_activated_at.isoformat(),
            "assignment_active": self.assignment_active,
            "assignment_expires_at": self.assignment_expires_at.isoformat(),
            "assignment_id": self.assignment_id,
            "assignment_non_revoked": self.assignment_non_revoked,
            "assignment_revision": self.assignment_revision,
            "authority": self.authority.canonical_value(),
            "credential_assignment_snapshot_digest": (self.credential_assignment_snapshot_digest),
            "credential_assignment_snapshot_id": self.credential_assignment_snapshot_id,
            "credential_generation": self.credential_generation,
            "evaluated_at": self.evaluated_at.isoformat(),
            "freshness_admission_id": self.freshness_admission_id,
            "physical_transport_credential_assignment_binding_digest": (
                self.physical_transport_credential_assignment_binding_digest
            ),
            "physical_transport_credential_assignment_binding_id": (
                self.physical_transport_credential_assignment_binding_id
            ),
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "rotation_epoch": self.rotation_epoch,
            "scope": self.scope.canonical_value(),
            "source_assignment_digest": self.source_assignment_digest,
            "state": self.state.value,
            "valid_until": self.valid_until.isoformat(),
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return False

    @property
    def grants_protected_artifact_access_authority(self) -> bool:
        return False

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

    @property
    def grants_route_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_selection_authority(self) -> bool:
        return False

    @property
    def grants_credential_assignment_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

    @property
    def grants_credential_brokerage_authority(self) -> bool:
        return False

    @property
    def grants_credential_resolution_authority(self) -> bool:
        return False

    @property
    def grants_credential_delivery_authority(self) -> bool:
        return False

    @property
    def grants_network_access_authority(self) -> bool:
        return False

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return False

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

    @property
    def grants_infrastructure_mutation_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAccessAuthorizationPolicy:
    """Code-owned requirements for one bounded credential-access authorization."""

    policy_id: str
    policy_version: str
    validity_window_seconds: int
    full_freshness_window_required: bool
    accessor_subject_bound: bool
    single_use_required: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="credential access authorization policy id")
        _require_identifier(
            self.policy_version,
            name="credential access authorization policy version",
        )
        if self.validity_window_seconds != 15:
            raise ValueError(
                "credential access authorization policy validity window must be 15 seconds"
            )
        if self.full_freshness_window_required is not True:
            raise ValueError(
                "credential access authorization policy must require the full freshness window"
            )
        if self.accessor_subject_bound is not True:
            raise ValueError(
                "credential access authorization policy must bind the accessor subject"
            )
        if self.single_use_required is not True:
            raise ValueError("credential access authorization policy must require single use")
        _require_digest(self.canonical_digest, name="credential access authorization policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential access authorization policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_bound": self.accessor_subject_bound,
            "full_freshness_window_required": self.full_freshness_window_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "single_use_required": self.single_use_required,
            "validity_window_seconds": self.validity_window_seconds,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_credential_access_authorization_policy() -> (
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-credential-access-authorization",
        "policy_version": "1.0",
        "validity_window_seconds": 15,
        "full_freshness_window_required": True,
        "accessor_subject_bound": True,
        "single_use_required": True,
    }
    return WorkflowEventPhysicalTransportCredentialAccessAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = True
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        values = self.canonical_value()
        if values["credential_access_authorized"] is not True or any(
            value is not False
            for name, value in values.items()
            if name != "credential_access_authorized"
        ):
            raise ValueError(
                "credential access authorization leases must grant only credential access"
            )

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
    """Single-use credential-access authority without secret resolution or delivery."""

    authorization_lease_id: str
    freshness_admission_id: str
    freshness_admission_digest: str
    physical_transport_credential_assignment_binding_id: str
    physical_transport_credential_assignment_binding_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    assignment_id: str
    assignment_revision: str
    source_assignment_digest: str
    credential_generation: int
    rotation_epoch: int
    assignment_activated_at: datetime
    assignment_expires_at: datetime
    assignment_active: bool
    assignment_non_revoked: bool
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    accessor_subject_id: str
    issued_at: datetime
    valid_until: datetime
    state: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState
    authority: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.authorization_lease_id, "credential access authorization lease id"),
            (self.freshness_admission_id, "credential assignment freshness admission id"),
            (
                self.physical_transport_credential_assignment_binding_id,
                "credential assignment binding id",
            ),
            (self.credential_assignment_snapshot_id, "credential assignment snapshot id"),
            (self.assignment_id, "credential assignment id"),
            (self.assignment_revision, "credential assignment revision"),
            (self.policy_id, "credential access authorization policy id"),
            (self.policy_version, "credential access authorization policy version"),
            (self.accessor_subject_id, "credential accessor subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.freshness_admission_digest, "credential assignment freshness digest"),
            (
                self.physical_transport_credential_assignment_binding_digest,
                "credential assignment binding digest",
            ),
            (self.credential_assignment_snapshot_digest, "credential assignment snapshot digest"),
            (self.source_assignment_digest, "credential assignment source digest"),
            (self.policy_digest, "credential access authorization policy digest"),
            (self.canonical_digest, "credential access authorization lease digest"),
        ):
            _require_digest(value, name=name)
        if self.credential_generation < 1 or self.rotation_epoch < 1:
            raise ValueError("credential access authorization assignment rank must be positive")
        if any(
            value.tzinfo is None
            for value in (
                self.assignment_activated_at,
                self.assignment_expires_at,
                self.issued_at,
                self.valid_until,
            )
        ):
            raise ValueError("credential access authorization times must be timezone-aware")
        if self.valid_until - self.issued_at != timedelta(seconds=15):
            raise ValueError(
                "credential access authorization lease must have an exact 15-second window"
            )
        if (
            not self.assignment_activated_at
            <= self.issued_at
            < self.valid_until
            <= self.assignment_expires_at
        ):
            raise ValueError("credential access authorization window is outside assignment life")
        if self.assignment_active is not True or self.assignment_non_revoked is not True:
            raise ValueError("credential access authorization source state is inadmissible")
        if (
            self.state
            is not (
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
        ):
            raise ValueError(
                "credential access authorization lease must remain authorized_unconsumed"
            )
        if (
            self.authority
            != WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority()
        ):
            raise ValueError(
                "credential access authorization lease has invalid authority declarations"
            )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential access authorization lease canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_id": self.accessor_subject_id,
            "assignment_activated_at": self.assignment_activated_at.isoformat(),
            "assignment_active": self.assignment_active,
            "assignment_expires_at": self.assignment_expires_at.isoformat(),
            "assignment_id": self.assignment_id,
            "assignment_non_revoked": self.assignment_non_revoked,
            "assignment_revision": self.assignment_revision,
            "authority": self.authority.canonical_value(),
            "authorization_lease_id": self.authorization_lease_id,
            "credential_assignment_snapshot_digest": self.credential_assignment_snapshot_digest,
            "credential_assignment_snapshot_id": self.credential_assignment_snapshot_id,
            "credential_generation": self.credential_generation,
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "issued_at": self.issued_at.isoformat(),
            "physical_transport_credential_assignment_binding_digest": (
                self.physical_transport_credential_assignment_binding_digest
            ),
            "physical_transport_credential_assignment_binding_id": (
                self.physical_transport_credential_assignment_binding_id
            ),
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "rotation_epoch": self.rotation_epoch,
            "scope": self.scope.canonical_value(),
            "source_assignment_digest": self.source_assignment_digest,
            "state": self.state.value,
            "valid_until": self.valid_until.isoformat(),
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, evaluated_at: datetime
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState:
        if evaluated_at.tzinfo is None:
            raise ValueError("credential access authorization evaluation time must be aware")
        if self.issued_at <= evaluated_at < self.valid_until:
            return (
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState
            ).ACTIVE
        return (
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState.EXPIRED
        )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationPolicy:
    """Code-owned protected credential materialization contract."""

    policy_id: str
    policy_version: str
    required_materializer_contract_id: str
    required_materializer_attestor_id: str
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    maximum_artifact_lifetime_seconds: int
    irreversible_consumption_required: bool
    automatic_retry_prohibited: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.policy_id, "credential materialization policy id"),
            (self.policy_version, "credential materialization policy version"),
            (self.required_materializer_contract_id, "credential materializer contract id"),
            (self.required_materializer_attestor_id, "credential materializer attestor id"),
            (self.protected_artifact_schema_id, "protected credential artifact schema id"),
            (
                self.protected_artifact_schema_version,
                "protected credential artifact schema version",
            ),
        ):
            _require_identifier(value, name=name)
        _require_digest(
            self.protected_artifact_profile_digest,
            name="protected credential artifact profile digest",
        )
        _require_digest(self.canonical_digest, name="credential materialization policy digest")
        if not 1 <= self.maximum_artifact_lifetime_seconds <= 15:
            raise ValueError("credential materialization lifetime exceeds lease boundary")
        if (
            self.irreversible_consumption_required is not True
            or self.automatic_retry_prohibited is not True
        ):
            raise ValueError("credential materialization policy is unsafe")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential materialization policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "automatic_retry_prohibited": self.automatic_retry_prohibited,
            "irreversible_consumption_required": self.irreversible_consumption_required,
            "maximum_artifact_lifetime_seconds": self.maximum_artifact_lifetime_seconds,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "protected_artifact_profile_digest": self.protected_artifact_profile_digest,
            "protected_artifact_schema_id": self.protected_artifact_schema_id,
            "protected_artifact_schema_version": self.protected_artifact_schema_version,
            "required_materializer_attestor_id": self.required_materializer_attestor_id,
            "required_materializer_contract_id": self.required_materializer_contract_id,
        }


def code_owned_workflow_event_physical_transport_credential_materialization_policy() -> (
    WorkflowEventPhysicalTransportCredentialMaterializationPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-credential-materialization",
        "policy_version": "1.0",
        "required_materializer_contract_id": (
            "contract.workflow-physical-transport-credential-materializer.v1"
        ),
        "required_materializer_attestor_id": (
            "attestor.workflow-physical-transport-credential-materializer"
        ),
        "protected_artifact_schema_id": "schema.workflow-protected-credential-artifact",
        "protected_artifact_schema_version": "1.0",
        "protected_artifact_profile_digest": canonical_digest(
            {"profile": "workflow-protected-credential-artifact", "version": "1.0"}
        ),
        "maximum_artifact_lifetime_seconds": 15,
        "irreversible_consumption_required": True,
        "automatic_retry_prohibited": True,
    }
    return WorkflowEventPhysicalTransportCredentialMaterializationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(value is not False for value in self.canonical_value().values()):
            raise ValueError("credential materialization evidence cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim:
    claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    freshness_admission_id: str
    freshness_admission_digest: str
    attempt_id: str
    materialization_id: str
    scope: WorkflowScope
    accessor_subject_id: str
    claimed_at: datetime
    request_fingerprint: str
    idempotency_digest: str
    authority: WorkflowEventPhysicalTransportCredentialMaterializationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.claim_id, "credential materialization claim id"),
            (self.authorization_lease_id, "credential access authorization lease id"),
            (self.freshness_admission_id, "credential freshness admission id"),
            (self.attempt_id, "credential materialization attempt id"),
            (self.materialization_id, "credential materialization id"),
            (self.accessor_subject_id, "credential accessor subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.authorization_lease_digest, "credential access authorization lease digest"),
            (self.freshness_admission_digest, "credential freshness admission digest"),
            (self.request_fingerprint, "credential materialization request fingerprint"),
            (self.idempotency_digest, "credential materialization idempotency digest"),
            (self.canonical_digest, "credential materialization claim digest"),
        ):
            _require_digest(value, name=name)
        if self.claimed_at.tzinfo is None:
            raise ValueError("credential materialization claim time must be aware")
        if any(value is not False for value in self.authority.canonical_value().values()):
            raise ValueError("credential materialization claims cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential materialization claim canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_id": self.accessor_subject_id,
            "attempt_id": self.attempt_id,
            "authority": self.authority.canonical_value(),
            "authorization_lease_digest": self.authorization_lease_digest,
            "authorization_lease_id": self.authorization_lease_id,
            "claim_id": self.claim_id,
            "claimed_at": self.claimed_at.isoformat(),
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "idempotency_digest": self.idempotency_digest,
            "materialization_id": self.materialization_id,
            "request_fingerprint": self.request_fingerprint,
            "scope": self.scope.canonical_value(),
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationAttempt:
    attempt_id: str
    materialization_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    freshness_admission_id: str
    freshness_admission_digest: str
    physical_transport_credential_assignment_binding_id: str
    physical_transport_credential_assignment_binding_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    assignment_id: str
    assignment_revision: str
    source_assignment_digest: str
    credential_generation: int
    rotation_epoch: int
    scope: WorkflowScope
    accessor_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    freshness_valid_until: datetime
    lease_valid_until: datetime
    state: WorkflowEventPhysicalTransportCredentialMaterializationAttemptState
    authority: WorkflowEventPhysicalTransportCredentialMaterializationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.attempt_id, "credential materialization attempt id"),
            (self.materialization_id, "credential materialization id"),
            (self.consumption_claim_id, "credential materialization claim id"),
            (self.authorization_lease_id, "credential access authorization lease id"),
            (
                self.physical_transport_credential_assignment_binding_id,
                "credential assignment binding id",
            ),
            (self.credential_assignment_snapshot_id, "credential assignment snapshot id"),
            (self.assignment_id, "credential assignment id"),
            (self.assignment_revision, "credential assignment revision"),
            (self.accessor_subject_id, "credential accessor subject id"),
            (self.policy_id, "credential materialization policy id"),
            (self.policy_version, "credential materialization policy version"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.authorization_lease_digest, "credential access authorization lease digest"),
            (self.freshness_admission_digest, "credential freshness admission digest"),
            (
                self.physical_transport_credential_assignment_binding_digest,
                "credential assignment binding digest",
            ),
            (self.credential_assignment_snapshot_digest, "credential assignment snapshot digest"),
            (self.source_assignment_digest, "credential source assignment digest"),
            (self.policy_digest, "credential materialization policy digest"),
            (self.canonical_digest, "credential materialization attempt digest"),
        ):
            _require_digest(value, name=name)
        if self.credential_generation < 1 or self.rotation_epoch < 1:
            raise ValueError("credential materialization assignment rank must be positive")
        if any(
            value.tzinfo is None
            for value in (self.started_at, self.freshness_valid_until, self.lease_valid_until)
        ):
            raise ValueError("credential materialization attempt times must be aware")
        if not self.started_at < min(self.freshness_valid_until, self.lease_valid_until):
            raise ValueError("credential materialization attempt starts outside validity window")
        if (
            self.state
            is not (
                WorkflowEventPhysicalTransportCredentialMaterializationAttemptState
            ).MATERIALIZATION_STARTED
        ):
            raise ValueError("credential materialization attempt must remain started")
        if any(value is not False for value in self.authority.canonical_value().values()):
            raise ValueError("credential materialization attempts cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential materialization attempt canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_id": self.accessor_subject_id,
            "assignment_id": self.assignment_id,
            "assignment_revision": self.assignment_revision,
            "attempt_id": self.attempt_id,
            "authority": self.authority.canonical_value(),
            "authorization_lease_digest": self.authorization_lease_digest,
            "authorization_lease_id": self.authorization_lease_id,
            "consumption_claim_id": self.consumption_claim_id,
            "credential_assignment_snapshot_digest": self.credential_assignment_snapshot_digest,
            "credential_assignment_snapshot_id": self.credential_assignment_snapshot_id,
            "credential_generation": self.credential_generation,
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "freshness_valid_until": self.freshness_valid_until.isoformat(),
            "lease_valid_until": self.lease_valid_until.isoformat(),
            "materialization_id": self.materialization_id,
            "physical_transport_credential_assignment_binding_digest": (
                self.physical_transport_credential_assignment_binding_digest
            ),
            "physical_transport_credential_assignment_binding_id": (
                self.physical_transport_credential_assignment_binding_id
            ),
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "rotation_epoch": self.rotation_epoch,
            "scope": self.scope.canonical_value(),
            "source_assignment_digest": self.source_assignment_digest,
            "started_at": self.started_at.isoformat(),
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationInstruction:
    materialization_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    assignment_id: str
    assignment_revision: str
    source_assignment_digest: str
    credential_requirement_profile_id: str
    credential_requirement_profile_version: str
    credential_requirement_profile_digest: str
    credential_profile_id: str
    credential_profile_version: str
    credential_profile_digest: str
    authentication_mechanism_class: str
    principal_class: str
    privilege_class: str
    target_scope_commitment: str
    credential_generation: int
    rotation_epoch: int
    broker_policy_id: str
    broker_policy_version: str
    broker_policy_digest: str
    scope: WorkflowScope
    accessor_subject_id: str
    materializer_contract_id: str
    materializer_attestor_id: str
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    started_at: datetime
    lease_valid_until: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.materialization_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.credential_assignment_snapshot_id,
            self.assignment_id,
            self.assignment_revision,
            self.credential_requirement_profile_id,
            self.credential_requirement_profile_version,
            self.credential_profile_id,
            self.credential_profile_version,
            self.broker_policy_id,
            self.broker_policy_version,
            self.accessor_subject_id,
            self.materializer_contract_id,
            self.materializer_attestor_id,
            self.protected_artifact_schema_id,
            self.protected_artifact_schema_version,
        ):
            _require_identifier(value, name="credential materialization instruction identifier")
        for value in (
            self.authorization_lease_digest,
            self.credential_assignment_snapshot_digest,
            self.source_assignment_digest,
            self.credential_requirement_profile_digest,
            self.credential_profile_digest,
            self.target_scope_commitment,
            self.broker_policy_digest,
            self.protected_artifact_profile_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="credential materialization instruction digest")
        if self.credential_generation < 1 or self.rotation_epoch < 1:
            raise ValueError("credential materialization instruction rank must be positive")
        if self.privilege_class != "read-only":
            raise ValueError("credential materialization instruction must remain least privilege")
        if self.started_at.tzinfo is None or self.lease_valid_until.tzinfo is None:
            raise ValueError("credential materialization instruction deadline must be aware")
        if self.started_at >= self.lease_valid_until:
            raise ValueError("credential materialization instruction starts outside lease")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential materialization instruction canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.canonical_value()
                if isinstance(value, WorkflowScope)
                else value
            )
            for name, value in ((field.name, getattr(self, field.name)) for field in fields(self))
            if name != "canonical_digest"
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationReceipt:
    materialization_id: str
    attempt_id: str
    consumption_claim_id: str
    instruction_digest: str
    materializer_contract_id: str
    materializer_id: str
    materializer_version: str
    attested_by: str
    accessor_subject_id: str
    state: WorkflowEventPhysicalTransportCredentialMaterializationResultState
    failure_class: WorkflowEventPhysicalTransportCredentialMaterializationFailureClass | None
    protected_artifact_id: str | None
    protected_artifact_digest: str | None
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    source_assignment_digest: str
    credential_generation: int
    rotation_epoch: int
    materialized_at: datetime | None
    completed_at: datetime
    usable_until: datetime | None
    source_commitment_verified: bool
    encrypted_at_rest: bool
    accessor_bound: bool
    lineage_bound: bool
    raw_credential_returned: bool
    secret_locator_returned: bool
    provider_payload_returned: bool
    network_activity_performed: bool
    process_activity_performed: bool
    protected_artifact_revoked: bool
    cleanup_confirmed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.materialization_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.materializer_contract_id,
            self.materializer_id,
            self.materializer_version,
            self.attested_by,
            self.accessor_subject_id,
            self.protected_artifact_schema_id,
            self.protected_artifact_schema_version,
        ):
            _require_identifier(value, name="credential materialization receipt identifier")
        for value in (
            self.instruction_digest,
            self.protected_artifact_profile_digest,
            self.source_assignment_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="credential materialization receipt digest")
        if self.completed_at.tzinfo is None:
            raise ValueError("credential materialization receipt completion time must be aware")
        if (
            any(
                (
                    self.raw_credential_returned,
                    self.secret_locator_returned,
                    self.provider_payload_returned,
                    self.network_activity_performed,
                    self.process_activity_performed,
                )
            )
            or self.signature_verified is not True
        ):
            raise ValueError("credential materialization receipt reports prohibited exposure")
        if (
            self.state
            is (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED
        ):
            if (
                self.failure_class is not None
                or self.protected_artifact_id is None
                or self.protected_artifact_digest is None
                or self.materialized_at is None
                or self.usable_until is None
                or not self.materialized_at <= self.completed_at < self.usable_until
                or not all(
                    (
                        self.source_commitment_verified,
                        self.encrypted_at_rest,
                        self.accessor_bound,
                        self.lineage_bound,
                        self.cleanup_confirmed,
                    )
                )
                or self.protected_artifact_revoked
            ):
                raise ValueError("successful credential materialization receipt is invalid")
            _require_identifier(self.protected_artifact_id, name="protected credential artifact id")
            _require_digest(
                self.protected_artifact_digest, name="protected credential artifact digest"
            )
        elif (
            self.state
            is not (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZATION_FAILED
            or self.failure_class is None
            or self.protected_artifact_id is not None
            or self.protected_artifact_digest is not None
            or self.materialized_at is not None
            or self.usable_until is not None
            or self.protected_artifact_revoked is not True
            or self.cleanup_confirmed is not True
        ):
            raise ValueError("failed credential materialization receipt is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential materialization receipt canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if isinstance(value, StrEnum)
                else value
            )
            for name, value in ((field.name, getattr(self, field.name)) for field in fields(self))
            if name != "canonical_digest"
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationResult:
    materialization_id: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    freshness_admission_id: str
    freshness_admission_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    assignment_id: str
    assignment_revision: str
    credential_generation: int
    rotation_epoch: int
    scope: WorkflowScope
    accessor_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    materializer_id: str
    materializer_version: str
    materialization_receipt_digest: str
    state: WorkflowEventPhysicalTransportCredentialMaterializationResultState
    failure_class: WorkflowEventPhysicalTransportCredentialMaterializationFailureClass | None
    protected_artifact_id: str | None
    protected_artifact_digest: str | None
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    completed_at: datetime
    usable_until: datetime | None
    protected_artifact_revoked: bool
    cleanup_confirmed: bool
    authority: WorkflowEventPhysicalTransportCredentialMaterializationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.materialization_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.freshness_admission_id,
            self.credential_assignment_snapshot_id,
            self.assignment_id,
            self.assignment_revision,
            self.accessor_subject_id,
            self.policy_id,
            self.policy_version,
            self.materializer_id,
            self.materializer_version,
            self.protected_artifact_schema_id,
            self.protected_artifact_schema_version,
        ):
            _require_identifier(value, name="credential materialization result identifier")
        for value in (
            self.attempt_digest,
            self.consumption_claim_digest,
            self.authorization_lease_digest,
            self.freshness_admission_digest,
            self.credential_assignment_snapshot_digest,
            self.policy_digest,
            self.materialization_receipt_digest,
            self.protected_artifact_profile_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="credential materialization result digest")
        if (
            self.completed_at.tzinfo is None
            or self.credential_generation < 1
            or self.rotation_epoch < 1
        ):
            raise ValueError("credential materialization result metadata is invalid")
        if (
            self.state
            is (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED
        ):
            if (
                self.failure_class is not None
                or self.protected_artifact_id is None
                or self.protected_artifact_digest is None
                or self.usable_until is None
                or not self.completed_at < self.usable_until
                or self.protected_artifact_revoked
                or not self.cleanup_confirmed
            ):
                raise ValueError("successful credential materialization result is invalid")
            _require_identifier(self.protected_artifact_id, name="protected credential artifact id")
            _require_digest(
                self.protected_artifact_digest, name="protected credential artifact digest"
            )
        elif (
            self.state
            is not (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZATION_FAILED
            or self.failure_class is None
            or self.protected_artifact_id is not None
            or self.protected_artifact_digest is not None
            or self.usable_until is not None
            or self.protected_artifact_revoked is not True
            or self.cleanup_confirmed is not True
        ):
            raise ValueError("failed credential materialization result is invalid")
        if any(value is not False for value in self.authority.canonical_value().values()):
            raise ValueError("credential materialization results cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("credential materialization result canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if isinstance(value, StrEnum)
                else value.canonical_value()
                if isinstance(
                    value,
                    (
                        WorkflowScope,
                        WorkflowEventPhysicalTransportCredentialMaterializationAuthority,
                    ),
                )
                else value
            )
            for name, value in ((field.name, getattr(self, field.name)) for field in fields(self))
            if name != "canonical_digest"
        }


@dataclass(frozen=True, slots=True)
class DeploymentEventTransportRouteSelectionHead:
    """Server-owned current route selection evidence without runtime authority."""

    head_id: str
    generation: int
    route_set_id: str
    route_set_revision: str
    selection_epoch_id: str
    selection_epoch_revision: str
    selected_route_id: str
    selected_route_revision: str
    selected_route_digest: str
    fencing_token_digest: str
    selection_active: bool
    selection_eligible: bool
    selection_suspended: bool
    selection_withdrawn: bool
    selection_superseded: bool
    scope: WorkflowScope
    current: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.head_id, "transport route selection head id"),
            (self.route_set_id, "transport route selection head route set id"),
            (self.route_set_revision, "transport route selection head route set revision"),
            (self.selection_epoch_id, "transport route selection head epoch id"),
            (self.selection_epoch_revision, "transport route selection head epoch revision"),
            (self.selected_route_id, "transport route selection head selected route id"),
            (
                self.selected_route_revision,
                "transport route selection head selected route revision",
            ),
        ):
            _require_identifier(value, name=name)
        if self.generation < 1:
            raise ValueError("transport route selection head generation must be positive")
        _require_digest(
            self.selected_route_digest,
            name="transport route selection head selected route digest",
        )
        _require_digest(
            self.fencing_token_digest,
            name="transport route selection head fencing token digest",
        )
        if self.current is not True:
            raise ValueError("transport route selection head must be current")
        if any(
            not isinstance(value, bool)
            for value in (
                self.selection_active,
                self.selection_eligible,
                self.selection_suspended,
                self.selection_withdrawn,
                self.selection_superseded,
            )
        ):
            raise ValueError("transport route selection head state evidence must be boolean")
        _require_digest(
            self.canonical_digest,
            name="transport route selection head canonical digest",
        )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("transport route selection head canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "current": self.current,
            "fencing_token_digest": self.fencing_token_digest,
            "generation": self.generation,
            "head_id": self.head_id,
            "route_set_id": self.route_set_id,
            "route_set_revision": self.route_set_revision,
            "scope": self.scope.canonical_value(),
            "selection_active": self.selection_active,
            "selection_eligible": self.selection_eligible,
            "selection_superseded": self.selection_superseded,
            "selection_suspended": self.selection_suspended,
            "selection_withdrawn": self.selection_withdrawn,
            "selected_route_digest": self.selected_route_digest,
            "selected_route_id": self.selected_route_id,
            "selected_route_revision": self.selected_route_revision,
            "selection_epoch_id": self.selection_epoch_id,
            "selection_epoch_revision": self.selection_epoch_revision,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteFreshnessPolicy:
    """Code-owned requirements for a point-in-time route freshness admission."""

    policy_id: str
    policy_version: str
    validity_window_seconds: int
    unique_current_head_required: bool
    monotonic_generation_required: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="route freshness policy id")
        _require_identifier(self.policy_version, name="route freshness policy version")
        if self.validity_window_seconds != 60:
            raise ValueError("route freshness policy validity window must be 60 seconds")
        if self.unique_current_head_required is not True:
            raise ValueError("route freshness policy must require one unique current head")
        if self.monotonic_generation_required is not True:
            raise ValueError("route freshness policy must require monotonic head generations")
        _require_digest(self.canonical_digest, name="route freshness policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("route freshness policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "monotonic_generation_required": self.monotonic_generation_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "unique_current_head_required": self.unique_current_head_required,
            "validity_window_seconds": self.validity_window_seconds,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_route_freshness_policy() -> (
    WorkflowEventPhysicalTransportRouteFreshnessPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-route-freshness",
        "policy_version": "1.0",
        "validity_window_seconds": 60,
        "unique_current_head_required": True,
        "monotonic_generation_required": True,
    }
    return WorkflowEventPhysicalTransportRouteFreshnessPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority:
    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_access_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("route freshness admissions cannot grant operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "network_access_authorized": self.network_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteFreshnessAdmission:
    """Immutable point-in-time currentness evidence without runtime authority."""

    freshness_admission_id: str
    physical_transport_route_binding_id: str
    physical_transport_route_binding_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    current_selection_head_id: str
    current_selection_head_digest: str
    current_selection_head_generation: int
    current_selection_head_fencing_token_digest: str
    route_set_id: str
    route_set_revision: str
    selection_epoch_id: str
    selection_epoch_revision: str
    selected_route_id: str
    selected_route_revision: str
    selected_route_digest: str
    selection_active: bool
    selection_eligible: bool
    selection_suspended: bool
    selection_withdrawn: bool
    selection_superseded: bool
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    admitter_subject_id: str
    evaluated_at: datetime
    valid_until: datetime
    state: WorkflowEventPhysicalTransportRouteFreshnessAdmissionState
    authority: WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.freshness_admission_id, "route freshness admission id"),
            (self.physical_transport_route_binding_id, "physical route binding id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.current_selection_head_id, "current selection head id"),
            (self.route_set_id, "route freshness route set id"),
            (self.route_set_revision, "route freshness route set revision"),
            (self.selection_epoch_id, "route freshness selection epoch id"),
            (self.selection_epoch_revision, "route freshness selection epoch revision"),
            (self.selected_route_id, "route freshness selected route id"),
            (self.selected_route_revision, "route freshness selected route revision"),
            (self.policy_id, "route freshness policy id"),
            (self.policy_version, "route freshness policy version"),
            (self.admitter_subject_id, "route freshness admitter subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.physical_transport_route_binding_digest, "physical route binding digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.current_selection_head_digest, "current selection head digest"),
            (
                self.current_selection_head_fencing_token_digest,
                "current selection head fencing token digest",
            ),
            (self.selected_route_digest, "selected route digest"),
            (self.policy_digest, "route freshness policy digest"),
            (self.canonical_digest, "route freshness admission canonical digest"),
        ):
            _require_digest(value, name=name)
        if self.current_selection_head_generation < 1:
            raise ValueError("route freshness head generation must be positive")
        if (
            self.selection_active is not True
            or self.selection_eligible is not True
            or self.selection_suspended
            or self.selection_withdrawn
            or self.selection_superseded
        ):
            raise ValueError("route freshness admission selection state is not admissible")
        if self.evaluated_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("route freshness admission times must be timezone-aware")
        if self.valid_until <= self.evaluated_at:
            raise ValueError("route freshness admission must have a positive validity window")
        if (
            self.state
            is not WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
        ):
            raise ValueError("route freshness admissions must remain admitted_current")
        if any(self.authority.canonical_value().values()):
            raise ValueError("route freshness admissions cannot grant operational authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("route freshness admission canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "admitter_subject_id": self.admitter_subject_id,
            "authority": self.authority.canonical_value(),
            "current_selection_head_digest": self.current_selection_head_digest,
            "current_selection_head_fencing_token_digest": (
                self.current_selection_head_fencing_token_digest
            ),
            "current_selection_head_generation": self.current_selection_head_generation,
            "current_selection_head_id": self.current_selection_head_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "freshness_admission_id": self.freshness_admission_id,
            "physical_transport_route_binding_digest": (
                self.physical_transport_route_binding_digest
            ),
            "physical_transport_route_binding_id": self.physical_transport_route_binding_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "route_set_id": self.route_set_id,
            "route_set_revision": self.route_set_revision,
            "scope": self.scope.canonical_value(),
            "selection_active": self.selection_active,
            "selection_eligible": self.selection_eligible,
            "selection_superseded": self.selection_superseded,
            "selection_suspended": self.selection_suspended,
            "selection_withdrawn": self.selection_withdrawn,
            "selected_route_digest": self.selected_route_digest,
            "selected_route_id": self.selected_route_id,
            "selected_route_revision": self.selected_route_revision,
            "selection_epoch_id": self.selection_epoch_id,
            "selection_epoch_revision": self.selection_epoch_revision,
            "state": self.state.value,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
            "valid_until": self.valid_until.isoformat(),
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return False

    @property
    def grants_route_selection_authority(self) -> bool:
        return False

    @property
    def grants_route_binding_authority(self) -> bool:
        return False

    @property
    def grants_credential_access_authority(self) -> bool:
        return False

    @property
    def grants_network_access_authority(self) -> bool:
        return False

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return False

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
class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationPolicy:
    """Code-owned requirements for one bounded endpoint-resolution authorization."""

    policy_id: str
    policy_version: str
    validity_window_seconds: int
    full_freshness_window_required: bool
    resolver_subject_bound: bool
    single_use_required: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="endpoint resolution authorization policy id")
        _require_identifier(
            self.policy_version,
            name="endpoint resolution authorization policy version",
        )
        if self.validity_window_seconds != 15:
            raise ValueError(
                "endpoint resolution authorization policy validity window must be 15 seconds"
            )
        if self.full_freshness_window_required is not True:
            raise ValueError(
                "endpoint resolution authorization policy must require the full freshness window"
            )
        if self.resolver_subject_bound is not True:
            raise ValueError(
                "endpoint resolution authorization policy must bind the resolver subject"
            )
        if self.single_use_required is not True:
            raise ValueError("endpoint resolution authorization policy must require single use")
        _require_digest(
            self.canonical_digest,
            name="endpoint resolution authorization policy digest",
        )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint resolution authorization policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "full_freshness_window_required": self.full_freshness_window_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "resolver_subject_bound": self.resolver_subject_bound,
            "single_use_required": self.single_use_required,
            "validity_window_seconds": self.validity_window_seconds,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy() -> (
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationPolicy
):
    values: dict[str, object] = {
        "policy_id": ("policy.workflow-event-physical-transport-endpoint-resolution-authorization"),
        "policy_version": "1.0",
        "validity_window_seconds": 15,
        "full_freshness_window_required": True,
        "resolver_subject_bound": True,
        "single_use_required": True,
    }
    return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority:
    endpoint_resolution_authorized: bool = True
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_access_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        values = self.canonical_value()
        if values["endpoint_resolution_authorized"] is not True or any(
            value for name, value in values.items() if name != "endpoint_resolution_authorized"
        ):
            raise ValueError(
                "endpoint resolution authorization leases must grant only endpoint resolution"
            )

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "network_access_authorized": self.network_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
    """Single-use resolver authorization without endpoint materialization."""

    authorization_lease_id: str
    freshness_admission_id: str
    freshness_admission_digest: str
    physical_transport_route_binding_id: str
    physical_transport_route_binding_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    current_selection_head_id: str
    current_selection_head_digest: str
    current_selection_head_generation: int
    current_selection_head_fencing_token_digest: str
    route_set_id: str
    route_set_revision: str
    selection_epoch_id: str
    selection_epoch_revision: str
    selected_route_id: str
    selected_route_revision: str
    selected_route_digest: str
    selection_active: bool
    selection_eligible: bool
    selection_suspended: bool
    selection_withdrawn: bool
    selection_superseded: bool
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: WorkflowScope
    resolver_subject_id: str
    issued_at: datetime
    valid_until: datetime
    state: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState
    authority: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.authorization_lease_id, "endpoint resolution authorization lease id"),
            (self.freshness_admission_id, "route freshness admission id"),
            (self.physical_transport_route_binding_id, "physical route binding id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.current_selection_head_id, "current selection head id"),
            (self.route_set_id, "endpoint resolution route set id"),
            (self.route_set_revision, "endpoint resolution route set revision"),
            (self.selection_epoch_id, "endpoint resolution selection epoch id"),
            (self.selection_epoch_revision, "endpoint resolution selection epoch revision"),
            (self.selected_route_id, "endpoint resolution selected route id"),
            (self.selected_route_revision, "endpoint resolution selected route revision"),
            (self.policy_id, "endpoint resolution authorization policy id"),
            (self.policy_version, "endpoint resolution authorization policy version"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.freshness_admission_digest, "route freshness admission digest"),
            (self.physical_transport_route_binding_digest, "physical route binding digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.current_selection_head_digest, "current selection head digest"),
            (
                self.current_selection_head_fencing_token_digest,
                "current selection head fencing token digest",
            ),
            (self.selected_route_digest, "selected route digest"),
            (self.policy_digest, "endpoint resolution authorization policy digest"),
            (self.canonical_digest, "endpoint resolution authorization lease digest"),
        ):
            _require_digest(value, name=name)
        if self.current_selection_head_generation < 1:
            raise ValueError("endpoint resolution authorization head generation must be positive")
        if (
            self.selection_active is not True
            or self.selection_eligible is not True
            or self.selection_suspended
            or self.selection_withdrawn
            or self.selection_superseded
        ):
            raise ValueError("endpoint resolution authorization selection state is not admissible")
        if self.issued_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("endpoint resolution authorization times must be timezone-aware")
        if self.valid_until - self.issued_at != timedelta(seconds=15):
            raise ValueError(
                "endpoint resolution authorization lease must have an exact 15-second window"
            )
        if (
            self.state
            is not (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
        ):
            raise ValueError(
                "endpoint resolution authorization leases must remain authorized_unconsumed"
            )
        if self.authority != (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority()
        ):
            raise ValueError(
                "endpoint resolution authorization lease has invalid authority declarations"
            )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint resolution authorization lease canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "authority": self.authority.canonical_value(),
            "authorization_lease_id": self.authorization_lease_id,
            "current_selection_head_digest": self.current_selection_head_digest,
            "current_selection_head_fencing_token_digest": (
                self.current_selection_head_fencing_token_digest
            ),
            "current_selection_head_generation": self.current_selection_head_generation,
            "current_selection_head_id": self.current_selection_head_id,
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "issued_at": self.issued_at.isoformat(),
            "physical_transport_route_binding_digest": (
                self.physical_transport_route_binding_digest
            ),
            "physical_transport_route_binding_id": self.physical_transport_route_binding_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "resolver_subject_id": self.resolver_subject_id,
            "route_set_id": self.route_set_id,
            "route_set_revision": self.route_set_revision,
            "scope": self.scope.canonical_value(),
            "selection_active": self.selection_active,
            "selection_eligible": self.selection_eligible,
            "selection_superseded": self.selection_superseded,
            "selection_suspended": self.selection_suspended,
            "selection_withdrawn": self.selection_withdrawn,
            "selected_route_digest": self.selected_route_digest,
            "selected_route_id": self.selected_route_id,
            "selected_route_revision": self.selected_route_revision,
            "selection_epoch_id": self.selection_epoch_id,
            "selection_epoch_revision": self.selection_epoch_revision,
            "state": self.state.value,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
            "valid_until": self.valid_until.isoformat(),
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, evaluated_at: datetime
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState:
        if evaluated_at.tzinfo is None:
            raise ValueError("endpoint resolution authorization evaluation time must be aware")
        if evaluated_at < self.valid_until:
            return (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState
            ).ACTIVE
        return (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState.EXPIRED
        )

    @property
    def grants_endpoint_resolution_authority(self) -> bool:
        return self.authority.endpoint_resolution_authorized

    @property
    def grants_route_selection_authority(self) -> bool:
        return self.authority.route_selection_authorized

    @property
    def grants_route_binding_authority(self) -> bool:
        return self.authority.route_binding_authorized

    @property
    def grants_credential_access_authority(self) -> bool:
        return self.authority.credential_access_authorized

    @property
    def grants_network_access_authority(self) -> bool:
        return self.authority.network_access_authorized

    @property
    def grants_readiness_probe_authority(self) -> bool:
        return self.authority.readiness_probe_authorized

    @property
    def grants_publication_authority(self) -> bool:
        return self.authority.publication_authorized

    @property
    def grants_delivery_authority(self) -> bool:
        return self.authority.delivery_authorized

    @property
    def grants_dispatch_authority(self) -> bool:
        return self.authority.dispatch_authorized

    @property
    def grants_execution_authority(self) -> bool:
        return self.authority.execution_authorized


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationPolicy:
    """Code-owned protected endpoint-materialization requirements."""

    policy_id: str
    policy_version: str
    required_materializer_contract_id: str
    required_materializer_attestor_id: str
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    maximum_endpoint_count: int
    raw_endpoint_return_prohibited: bool
    dns_activity_prohibited: bool
    network_activity_prohibited: bool
    credential_access_prohibited: bool
    process_activity_prohibited: bool
    provider_activity_prohibited: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.policy_id, "endpoint materialization policy id"),
            (self.policy_version, "endpoint materialization policy version"),
            (
                self.required_materializer_contract_id,
                "endpoint materializer contract id",
            ),
            (
                self.required_materializer_attestor_id,
                "endpoint materializer attestor id",
            ),
            (self.protected_artifact_schema_id, "protected endpoint artifact schema id"),
            (
                self.protected_artifact_schema_version,
                "protected endpoint artifact schema version",
            ),
        ):
            _require_identifier(value, name=name)
        _require_digest(
            self.protected_artifact_profile_digest,
            name="protected endpoint artifact profile digest",
        )
        if self.maximum_endpoint_count != 64:
            raise ValueError("endpoint materialization policy maximum endpoint count must be 64")
        if not all(
            (
                self.raw_endpoint_return_prohibited,
                self.dns_activity_prohibited,
                self.network_activity_prohibited,
                self.credential_access_prohibited,
                self.process_activity_prohibited,
                self.provider_activity_prohibited,
            )
        ):
            raise ValueError("endpoint materialization policy must prohibit runtime activity")
        _require_digest(self.canonical_digest, name="endpoint materialization policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint materialization policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "credential_access_prohibited": self.credential_access_prohibited,
            "dns_activity_prohibited": self.dns_activity_prohibited,
            "maximum_endpoint_count": self.maximum_endpoint_count,
            "network_activity_prohibited": self.network_activity_prohibited,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "process_activity_prohibited": self.process_activity_prohibited,
            "protected_artifact_profile_digest": self.protected_artifact_profile_digest,
            "protected_artifact_schema_id": self.protected_artifact_schema_id,
            "protected_artifact_schema_version": self.protected_artifact_schema_version,
            "provider_activity_prohibited": self.provider_activity_prohibited,
            "raw_endpoint_return_prohibited": self.raw_endpoint_return_prohibited,
            "required_materializer_attestor_id": self.required_materializer_attestor_id,
            "required_materializer_contract_id": self.required_materializer_contract_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_endpoint_materialization_policy() -> (
    WorkflowEventPhysicalTransportEndpointMaterializationPolicy
):
    protected_artifact_profile_digest = canonical_digest(
        {
            "encryption": "envelope-encryption-required",
            "lineage_binding": "exact",
            "resolver_binding": "exact",
            "schema": "atlas.workflow-protected-endpoint-artifact.v1",
        }
    )
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-endpoint-materialization",
        "policy_version": "1.0",
        "required_materializer_contract_id": (
            "contract.workflow-physical-transport-endpoint-materializer.v1"
        ),
        "required_materializer_attestor_id": (
            "subject.workflow-physical-transport-endpoint-materializer-attestor"
        ),
        "protected_artifact_schema_id": "atlas.workflow-protected-endpoint-artifact",
        "protected_artifact_schema_version": "1.0",
        "protected_artifact_profile_digest": protected_artifact_profile_digest,
        "maximum_endpoint_count": 64,
        "raw_endpoint_return_prohibited": True,
        "dns_activity_prohibited": True,
        "network_activity_prohibited": True,
        "credential_access_prohibited": True,
        "process_activity_prohibited": True,
        "provider_activity_prohibited": True,
    }
    return WorkflowEventPhysicalTransportEndpointMaterializationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationAuthority:
    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_access_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("endpoint materialization evidence cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "network_access_authorized": self.network_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim:
    claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    freshness_admission_id: str
    freshness_admission_digest: str
    attempt_id: str
    materialization_id: str
    scope: WorkflowScope
    resolver_subject_id: str
    claimed_at: datetime
    request_fingerprint: str
    idempotency_digest: str
    authority: WorkflowEventPhysicalTransportEndpointMaterializationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.claim_id, "endpoint materialization claim id"),
            (self.authorization_lease_id, "endpoint authorization lease id"),
            (self.freshness_admission_id, "route freshness admission id"),
            (self.attempt_id, "endpoint materialization attempt id"),
            (self.materialization_id, "endpoint materialization id"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.authorization_lease_digest, "endpoint authorization lease digest"),
            (self.freshness_admission_digest, "route freshness admission digest"),
            (self.request_fingerprint, "endpoint materialization request fingerprint"),
            (self.idempotency_digest, "endpoint materialization idempotency digest"),
            (self.canonical_digest, "endpoint materialization claim digest"),
        ):
            _require_digest(value, name=name)
        if self.claimed_at.tzinfo is None:
            raise ValueError("endpoint materialization claim time must be timezone-aware")
        if any(self.authority.canonical_value().values()):
            raise ValueError("endpoint materialization claims cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint materialization claim canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "authority": self.authority.canonical_value(),
            "authorization_lease_digest": self.authorization_lease_digest,
            "authorization_lease_id": self.authorization_lease_id,
            "claim_id": self.claim_id,
            "claimed_at": self.claimed_at.isoformat(),
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "idempotency_digest": self.idempotency_digest,
            "materialization_id": self.materialization_id,
            "request_fingerprint": self.request_fingerprint,
            "resolver_subject_id": self.resolver_subject_id,
            "scope": self.scope.canonical_value(),
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationAttempt:
    attempt_id: str
    materialization_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    freshness_admission_id: str
    freshness_admission_digest: str
    physical_transport_route_binding_id: str
    physical_transport_route_binding_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    current_selection_head_id: str
    current_selection_head_digest: str
    current_selection_head_generation: int
    current_selection_head_fencing_token_digest: str
    scope: WorkflowScope
    resolver_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    freshness_valid_until: datetime
    lease_valid_until: datetime
    state: WorkflowEventPhysicalTransportEndpointMaterializationAttemptState
    authority: WorkflowEventPhysicalTransportEndpointMaterializationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.attempt_id, "endpoint materialization attempt id"),
            (self.materialization_id, "endpoint materialization id"),
            (self.consumption_claim_id, "endpoint materialization claim id"),
            (self.authorization_lease_id, "endpoint authorization lease id"),
            (self.freshness_admission_id, "route freshness admission id"),
            (self.physical_transport_route_binding_id, "physical route binding id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.current_selection_head_id, "current selection head id"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
            (self.policy_id, "endpoint materialization policy id"),
            (self.policy_version, "endpoint materialization policy version"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.authorization_lease_digest, "endpoint authorization lease digest"),
            (self.freshness_admission_digest, "route freshness admission digest"),
            (self.physical_transport_route_binding_digest, "physical route binding digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.current_selection_head_digest, "current selection head digest"),
            (
                self.current_selection_head_fencing_token_digest,
                "current selection head fencing token digest",
            ),
            (self.policy_digest, "endpoint materialization policy digest"),
            (self.canonical_digest, "endpoint materialization attempt digest"),
        ):
            _require_digest(value, name=name)
        if self.current_selection_head_generation < 1:
            raise ValueError("endpoint materialization head generation must be positive")
        if any(
            value.tzinfo is None
            for value in (self.started_at, self.freshness_valid_until, self.lease_valid_until)
        ):
            raise ValueError("endpoint materialization attempt times must be timezone-aware")
        if not self.started_at < min(self.freshness_valid_until, self.lease_valid_until):
            raise ValueError("endpoint materialization attempt must start inside both windows")
        if (
            self.state
            is not (
                WorkflowEventPhysicalTransportEndpointMaterializationAttemptState
            ).MATERIALIZATION_STARTED
        ):
            raise ValueError("endpoint materialization attempts must remain started")
        if any(self.authority.canonical_value().values()):
            raise ValueError("endpoint materialization attempts cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint materialization attempt canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "authority": self.authority.canonical_value(),
            "authorization_lease_digest": self.authorization_lease_digest,
            "authorization_lease_id": self.authorization_lease_id,
            "consumption_claim_id": self.consumption_claim_id,
            "current_selection_head_digest": self.current_selection_head_digest,
            "current_selection_head_fencing_token_digest": (
                self.current_selection_head_fencing_token_digest
            ),
            "current_selection_head_generation": self.current_selection_head_generation,
            "current_selection_head_id": self.current_selection_head_id,
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "freshness_valid_until": self.freshness_valid_until.isoformat(),
            "lease_valid_until": self.lease_valid_until.isoformat(),
            "materialization_id": self.materialization_id,
            "physical_transport_route_binding_digest": (
                self.physical_transport_route_binding_digest
            ),
            "physical_transport_route_binding_id": self.physical_transport_route_binding_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "resolver_subject_id": self.resolver_subject_id,
            "scope": self.scope.canonical_value(),
            "started_at": self.started_at.isoformat(),
            "state": self.state.value,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationInstruction:
    materialization_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    route_id: str
    route_revision: str
    source_route_digest: str
    endpoint_set_id: str
    endpoint_set_revision: str
    destination_id: str
    destination_revision: str
    routing_contract_id: str
    routing_contract_revision: str
    private_route_descriptor_commitment: str
    scope: WorkflowScope
    resolver_subject_id: str
    materializer_contract_id: str
    materializer_attestor_id: str
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    maximum_endpoint_count: int
    lease_valid_until: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.materialization_id, "endpoint materialization id"),
            (self.attempt_id, "endpoint materialization attempt id"),
            (self.consumption_claim_id, "endpoint materialization claim id"),
            (self.authorization_lease_id, "endpoint authorization lease id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.route_id, "transport route id"),
            (self.route_revision, "transport route revision"),
            (self.endpoint_set_id, "endpoint set id"),
            (self.endpoint_set_revision, "endpoint set revision"),
            (self.destination_id, "destination id"),
            (self.destination_revision, "destination revision"),
            (self.routing_contract_id, "routing contract id"),
            (self.routing_contract_revision, "routing contract revision"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
            (self.materializer_contract_id, "endpoint materializer contract id"),
            (self.materializer_attestor_id, "endpoint materializer attestor id"),
            (self.protected_artifact_schema_id, "protected endpoint artifact schema id"),
            (
                self.protected_artifact_schema_version,
                "protected endpoint artifact schema version",
            ),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.authorization_lease_digest, "endpoint authorization lease digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.source_route_digest, "source route digest"),
            (
                self.private_route_descriptor_commitment,
                "private route descriptor commitment",
            ),
            (self.protected_artifact_profile_digest, "protected endpoint profile digest"),
            (self.canonical_digest, "endpoint materialization instruction digest"),
        ):
            _require_digest(value, name=name)
        if not 1 <= self.maximum_endpoint_count <= 64:
            raise ValueError("endpoint materialization instruction endpoint limit is invalid")
        if self.lease_valid_until.tzinfo is None:
            raise ValueError("endpoint materialization instruction deadline must be aware")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint materialization instruction canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "authorization_lease_digest": self.authorization_lease_digest,
            "authorization_lease_id": self.authorization_lease_id,
            "consumption_claim_id": self.consumption_claim_id,
            "destination_id": self.destination_id,
            "destination_revision": self.destination_revision,
            "endpoint_set_id": self.endpoint_set_id,
            "endpoint_set_revision": self.endpoint_set_revision,
            "lease_valid_until": self.lease_valid_until.isoformat(),
            "materialization_id": self.materialization_id,
            "materializer_attestor_id": self.materializer_attestor_id,
            "materializer_contract_id": self.materializer_contract_id,
            "maximum_endpoint_count": self.maximum_endpoint_count,
            "private_route_descriptor_commitment": (self.private_route_descriptor_commitment),
            "protected_artifact_profile_digest": self.protected_artifact_profile_digest,
            "protected_artifact_schema_id": self.protected_artifact_schema_id,
            "protected_artifact_schema_version": self.protected_artifact_schema_version,
            "resolver_subject_id": self.resolver_subject_id,
            "route_id": self.route_id,
            "route_revision": self.route_revision,
            "routing_contract_id": self.routing_contract_id,
            "routing_contract_revision": self.routing_contract_revision,
            "scope": self.scope.canonical_value(),
            "source_route_digest": self.source_route_digest,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationReceipt:
    materialization_id: str
    attempt_id: str
    consumption_claim_id: str
    instruction_digest: str
    materializer_contract_id: str
    materializer_id: str
    materializer_version: str
    attested_by: str
    resolver_subject_id: str
    state: WorkflowEventPhysicalTransportEndpointMaterializationResultState
    failure_class: WorkflowEventPhysicalTransportEndpointMaterializationFailureClass | None
    protected_artifact_id: str | None
    protected_artifact_digest: str | None
    normalized_endpoint_set_digest: str | None
    endpoint_count: int
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    source_route_digest: str
    private_route_descriptor_commitment: str
    materialized_at: datetime | None
    completed_at: datetime
    usable_until: datetime | None
    commitment_verified: bool
    encrypted_at_rest: bool
    resolver_bound: bool
    lineage_bound: bool
    raw_endpoint_returned: bool
    dns_activity_performed: bool
    network_activity_performed: bool
    credential_access_performed: bool
    process_activity_performed: bool
    provider_activity_performed: bool
    protected_artifact_revoked: bool
    cleanup_confirmed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.materialization_id, "endpoint materialization id"),
            (self.attempt_id, "endpoint materialization attempt id"),
            (self.consumption_claim_id, "endpoint materialization claim id"),
            (self.materializer_contract_id, "endpoint materializer contract id"),
            (self.materializer_id, "endpoint materializer id"),
            (self.materializer_version, "endpoint materializer version"),
            (self.attested_by, "endpoint materializer attestor"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
            (self.protected_artifact_schema_id, "protected endpoint artifact schema id"),
            (
                self.protected_artifact_schema_version,
                "protected endpoint artifact schema version",
            ),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.instruction_digest, "endpoint materialization instruction digest"),
            (self.protected_artifact_profile_digest, "protected endpoint profile digest"),
            (self.source_route_digest, "source route digest"),
            (
                self.private_route_descriptor_commitment,
                "private route descriptor commitment",
            ),
            (self.canonical_digest, "endpoint materialization receipt digest"),
        ):
            _require_digest(value, name=name)
        if self.completed_at.tzinfo is None:
            raise ValueError("endpoint materialization receipt completion time must be aware")
        prohibited_activity = (
            self.raw_endpoint_returned,
            self.dns_activity_performed,
            self.network_activity_performed,
            self.credential_access_performed,
            self.process_activity_performed,
            self.provider_activity_performed,
        )
        if any(prohibited_activity) or not self.signature_verified:
            raise ValueError("endpoint materialization receipt reports prohibited activity")
        if (
            self.state
            is (
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZED_PROTECTED
        ):
            for optional_value, name in (
                (self.protected_artifact_id, "protected endpoint artifact id"),
                (self.protected_artifact_digest, "protected endpoint artifact digest"),
                (self.normalized_endpoint_set_digest, "normalized endpoint set digest"),
            ):
                if optional_value is None:
                    raise ValueError(f"{name} is required for successful materialization")
            assert self.protected_artifact_id is not None
            assert self.protected_artifact_digest is not None
            assert self.normalized_endpoint_set_digest is not None
            _require_identifier(
                self.protected_artifact_id,
                name="protected endpoint artifact id",
            )
            _require_digest(
                self.protected_artifact_digest,
                name="protected endpoint artifact digest",
            )
            _require_digest(
                self.normalized_endpoint_set_digest,
                name="normalized endpoint set digest",
            )
            if (
                self.failure_class is not None
                or self.materialized_at is None
                or self.materialized_at.tzinfo is None
                or self.usable_until is None
                or self.usable_until.tzinfo is None
                or not self.materialized_at <= self.completed_at < self.usable_until
                or self.endpoint_count < 1
                or not all(
                    (
                        self.commitment_verified,
                        self.encrypted_at_rest,
                        self.resolver_bound,
                        self.lineage_bound,
                    )
                )
                or self.protected_artifact_revoked
                or not self.cleanup_confirmed
            ):
                raise ValueError("successful endpoint materialization receipt is invalid")
        else:
            if (
                self.state
                is not (
                    WorkflowEventPhysicalTransportEndpointMaterializationResultState
                ).MATERIALIZATION_FAILED
                or self.failure_class is None
                or any(
                    value is not None
                    for value in (
                        self.protected_artifact_id,
                        self.protected_artifact_digest,
                        self.normalized_endpoint_set_digest,
                        self.materialized_at,
                        self.usable_until,
                    )
                )
                or self.endpoint_count != 0
                or not self.protected_artifact_revoked
                or not self.cleanup_confirmed
            ):
                raise ValueError("failed endpoint materialization receipt is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint materialization receipt canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "attested_by": self.attested_by,
            "cleanup_confirmed": self.cleanup_confirmed,
            "commitment_verified": self.commitment_verified,
            "completed_at": self.completed_at.isoformat(),
            "consumption_claim_id": self.consumption_claim_id,
            "credential_access_performed": self.credential_access_performed,
            "dns_activity_performed": self.dns_activity_performed,
            "encrypted_at_rest": self.encrypted_at_rest,
            "endpoint_count": self.endpoint_count,
            "failure_class": None if self.failure_class is None else self.failure_class.value,
            "instruction_digest": self.instruction_digest,
            "lineage_bound": self.lineage_bound,
            "materialization_id": self.materialization_id,
            "materialized_at": (
                None if self.materialized_at is None else self.materialized_at.isoformat()
            ),
            "materializer_contract_id": self.materializer_contract_id,
            "materializer_id": self.materializer_id,
            "materializer_version": self.materializer_version,
            "network_activity_performed": self.network_activity_performed,
            "normalized_endpoint_set_digest": self.normalized_endpoint_set_digest,
            "private_route_descriptor_commitment": (self.private_route_descriptor_commitment),
            "process_activity_performed": self.process_activity_performed,
            "protected_artifact_digest": self.protected_artifact_digest,
            "protected_artifact_id": self.protected_artifact_id,
            "protected_artifact_profile_digest": self.protected_artifact_profile_digest,
            "protected_artifact_revoked": self.protected_artifact_revoked,
            "protected_artifact_schema_id": self.protected_artifact_schema_id,
            "protected_artifact_schema_version": self.protected_artifact_schema_version,
            "provider_activity_performed": self.provider_activity_performed,
            "raw_endpoint_returned": self.raw_endpoint_returned,
            "resolver_bound": self.resolver_bound,
            "resolver_subject_id": self.resolver_subject_id,
            "signature_verified": self.signature_verified,
            "source_route_digest": self.source_route_digest,
            "state": self.state.value,
            "usable_until": None if self.usable_until is None else self.usable_until.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationResult:
    materialization_id: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    freshness_admission_id: str
    freshness_admission_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    scope: WorkflowScope
    resolver_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    materializer_id: str
    materializer_version: str
    materialization_receipt_digest: str
    state: WorkflowEventPhysicalTransportEndpointMaterializationResultState
    failure_class: WorkflowEventPhysicalTransportEndpointMaterializationFailureClass | None
    protected_artifact_id: str | None
    protected_artifact_digest: str | None
    normalized_endpoint_set_digest: str | None
    endpoint_count: int
    protected_artifact_schema_id: str
    protected_artifact_schema_version: str
    protected_artifact_profile_digest: str
    completed_at: datetime
    usable_until: datetime | None
    protected_artifact_revoked: bool
    cleanup_confirmed: bool
    authority: WorkflowEventPhysicalTransportEndpointMaterializationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.materialization_id, "endpoint materialization id"),
            (self.attempt_id, "endpoint materialization attempt id"),
            (self.consumption_claim_id, "endpoint materialization claim id"),
            (self.authorization_lease_id, "endpoint authorization lease id"),
            (self.freshness_admission_id, "route freshness admission id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
            (self.policy_id, "endpoint materialization policy id"),
            (self.policy_version, "endpoint materialization policy version"),
            (self.materializer_id, "endpoint materializer id"),
            (self.materializer_version, "endpoint materializer version"),
            (self.protected_artifact_schema_id, "protected endpoint artifact schema id"),
            (
                self.protected_artifact_schema_version,
                "protected endpoint artifact schema version",
            ),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.attempt_digest, "endpoint materialization attempt digest"),
            (self.consumption_claim_digest, "endpoint materialization claim digest"),
            (self.authorization_lease_digest, "endpoint authorization lease digest"),
            (self.freshness_admission_digest, "route freshness admission digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.policy_digest, "endpoint materialization policy digest"),
            (self.materialization_receipt_digest, "endpoint materialization receipt digest"),
            (self.protected_artifact_profile_digest, "protected endpoint profile digest"),
            (self.canonical_digest, "endpoint materialization result digest"),
        ):
            _require_digest(value, name=name)
        if self.completed_at.tzinfo is None:
            raise ValueError("endpoint materialization completion time must be timezone-aware")
        if (
            self.state
            is (
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZED_PROTECTED
        ):
            if (
                self.failure_class is not None
                or self.protected_artifact_id is None
                or self.protected_artifact_digest is None
                or self.normalized_endpoint_set_digest is None
                or self.endpoint_count < 1
                or self.usable_until is None
                or self.usable_until.tzinfo is None
                or not self.completed_at < self.usable_until
                or self.protected_artifact_revoked
                or not self.cleanup_confirmed
            ):
                raise ValueError("successful endpoint materialization result is invalid")
            _require_identifier(
                self.protected_artifact_id,
                name="protected endpoint artifact id",
            )
            _require_digest(
                self.protected_artifact_digest,
                name="protected endpoint artifact digest",
            )
            _require_digest(
                self.normalized_endpoint_set_digest,
                name="normalized endpoint set digest",
            )
        elif (
            self.state
            is not (
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZATION_FAILED
            or self.failure_class is None
            or any(
                value is not None
                for value in (
                    self.protected_artifact_id,
                    self.protected_artifact_digest,
                    self.normalized_endpoint_set_digest,
                    self.usable_until,
                )
            )
            or self.endpoint_count != 0
            or not self.protected_artifact_revoked
            or not self.cleanup_confirmed
        ):
            raise ValueError("failed endpoint materialization result is invalid")
        if any(self.authority.canonical_value().values()):
            raise ValueError("endpoint materialization results cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("endpoint materialization result canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "authority": self.authority.canonical_value(),
            "authorization_lease_digest": self.authorization_lease_digest,
            "authorization_lease_id": self.authorization_lease_id,
            "canonical_materialization_receipt_digest": self.materialization_receipt_digest,
            "cleanup_confirmed": self.cleanup_confirmed,
            "completed_at": self.completed_at.isoformat(),
            "consumption_claim_digest": self.consumption_claim_digest,
            "consumption_claim_id": self.consumption_claim_id,
            "endpoint_count": self.endpoint_count,
            "failure_class": None if self.failure_class is None else self.failure_class.value,
            "freshness_admission_digest": self.freshness_admission_digest,
            "freshness_admission_id": self.freshness_admission_id,
            "materialization_id": self.materialization_id,
            "materializer_id": self.materializer_id,
            "materializer_version": self.materializer_version,
            "normalized_endpoint_set_digest": self.normalized_endpoint_set_digest,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "protected_artifact_digest": self.protected_artifact_digest,
            "protected_artifact_id": self.protected_artifact_id,
            "protected_artifact_profile_digest": self.protected_artifact_profile_digest,
            "protected_artifact_revoked": self.protected_artifact_revoked,
            "protected_artifact_schema_id": self.protected_artifact_schema_id,
            "protected_artifact_schema_version": self.protected_artifact_schema_version,
            "resolver_subject_id": self.resolver_subject_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
            "usable_until": None if self.usable_until is None else self.usable_until.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextBindingPolicy:
    """Code-owned requirements for joining protected transport lineages."""

    policy_id: str
    policy_version: str
    target_context_schema_id: str
    target_context_schema_version: str
    successful_endpoint_materialization_required: bool
    successful_credential_materialization_required: bool
    exact_route_lineage_required: bool
    unexpired_overlap_required: bool
    one_binding_per_source_required: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.policy_id, "target context binding policy id"),
            (self.policy_version, "target context binding policy version"),
            (self.target_context_schema_id, "target context schema id"),
            (self.target_context_schema_version, "target context schema version"),
        ):
            _require_identifier(value, name=name)
        if any(
            value is not True
            for value in (
                self.successful_endpoint_materialization_required,
                self.successful_credential_materialization_required,
                self.exact_route_lineage_required,
                self.unexpired_overlap_required,
                self.one_binding_per_source_required,
            )
        ):
            raise ValueError("target context binding policy requirements must remain enabled")
        _require_digest(self.canonical_digest, name="target context binding policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context binding policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "exact_route_lineage_required": self.exact_route_lineage_required,
            "one_binding_per_source_required": self.one_binding_per_source_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "successful_credential_materialization_required": (
                self.successful_credential_materialization_required
            ),
            "successful_endpoint_materialization_required": (
                self.successful_endpoint_materialization_required
            ),
            "target_context_schema_id": self.target_context_schema_id,
            "target_context_schema_version": self.target_context_schema_version,
            "unexpired_overlap_required": self.unexpired_overlap_required,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_target_context_binding_policy() -> (
    WorkflowEventPhysicalTransportTargetContextBindingPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-target-context-binding",
        "policy_version": "1.0",
        "target_context_schema_id": "schema.workflow-physical-transport-target-context",
        "target_context_schema_version": "1.0",
        "successful_endpoint_materialization_required": True,
        "successful_credential_materialization_required": True,
        "exact_route_lineage_required": True,
        "unexpired_overlap_required": True,
        "one_binding_per_source_required": True,
    }
    return WorkflowEventPhysicalTransportTargetContextBindingPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextBindingAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(value is not False for value in self.canonical_value().values()):
            raise ValueError("target context bindings cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextBinding:
    """Immutable endpoint and credential target-context evidence with no authority."""

    binding_id: str
    physical_transport_route_binding_id: str
    physical_transport_route_binding_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    endpoint_materialization_id: str
    endpoint_materialization_digest: str
    physical_transport_credential_assignment_binding_id: str
    physical_transport_credential_assignment_binding_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    credential_materialization_id: str
    credential_materialization_digest: str
    resolver_subject_id: str
    accessor_subject_id: str
    target_context_schema_id: str
    target_context_schema_version: str
    target_context_commitment: str
    scope: WorkflowScope
    binder_subject_id: str
    bound_at: datetime
    joint_usable_until: datetime
    policy_id: str
    policy_version: str
    policy_digest: str
    state: WorkflowEventPhysicalTransportTargetContextBindingState
    authority: WorkflowEventPhysicalTransportTargetContextBindingAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.binding_id, "target context binding id"),
            (self.physical_transport_route_binding_id, "physical route binding id"),
            (self.transport_route_snapshot_id, "transport route snapshot id"),
            (self.endpoint_materialization_id, "endpoint materialization id"),
            (
                self.physical_transport_credential_assignment_binding_id,
                "credential assignment binding id",
            ),
            (self.credential_assignment_snapshot_id, "credential assignment snapshot id"),
            (self.credential_materialization_id, "credential materialization id"),
            (self.resolver_subject_id, "endpoint resolver subject id"),
            (self.accessor_subject_id, "credential accessor subject id"),
            (self.target_context_schema_id, "target context schema id"),
            (self.target_context_schema_version, "target context schema version"),
            (self.binder_subject_id, "target context binder subject id"),
            (self.policy_id, "target context binding policy id"),
            (self.policy_version, "target context binding policy version"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.physical_transport_route_binding_digest, "physical route binding digest"),
            (self.transport_route_snapshot_digest, "transport route snapshot digest"),
            (self.endpoint_materialization_digest, "endpoint materialization digest"),
            (
                self.physical_transport_credential_assignment_binding_digest,
                "credential assignment binding digest",
            ),
            (
                self.credential_assignment_snapshot_digest,
                "credential assignment snapshot digest",
            ),
            (self.credential_materialization_digest, "credential materialization digest"),
            (self.target_context_commitment, "target context commitment"),
            (self.policy_digest, "target context binding policy digest"),
            (self.canonical_digest, "target context binding canonical digest"),
        ):
            _require_digest(value, name=name)
        if self.bound_at.tzinfo is None or self.joint_usable_until.tzinfo is None:
            raise ValueError("target context binding times must be timezone-aware")
        if self.bound_at >= self.joint_usable_until:
            raise ValueError("target context binding requires an unexpired usable overlap")
        if self.state is not WorkflowEventPhysicalTransportTargetContextBindingState.BOUND:
            raise ValueError("target context bindings must remain bound")
        if any(value is not False for value in self.authority.canonical_value().values()):
            raise ValueError("target context bindings cannot grant authority")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context binding canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_id": self.accessor_subject_id,
            "authority": self.authority.canonical_value(),
            "binder_subject_id": self.binder_subject_id,
            "binding_id": self.binding_id,
            "bound_at": self.bound_at.isoformat(),
            "credential_assignment_snapshot_digest": (self.credential_assignment_snapshot_digest),
            "credential_assignment_snapshot_id": self.credential_assignment_snapshot_id,
            "credential_materialization_digest": self.credential_materialization_digest,
            "credential_materialization_id": self.credential_materialization_id,
            "endpoint_materialization_digest": self.endpoint_materialization_digest,
            "endpoint_materialization_id": self.endpoint_materialization_id,
            "joint_usable_until": self.joint_usable_until.isoformat(),
            "physical_transport_credential_assignment_binding_digest": (
                self.physical_transport_credential_assignment_binding_digest
            ),
            "physical_transport_credential_assignment_binding_id": (
                self.physical_transport_credential_assignment_binding_id
            ),
            "physical_transport_route_binding_digest": (
                self.physical_transport_route_binding_digest
            ),
            "physical_transport_route_binding_id": self.physical_transport_route_binding_id,
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "resolver_subject_id": self.resolver_subject_id,
            "scope": self.scope.canonical_value(),
            "state": self.state.value,
            "target_context_commitment": self.target_context_commitment,
            "target_context_schema_id": self.target_context_schema_id,
            "target_context_schema_version": self.target_context_schema_version,
            "transport_route_snapshot_digest": self.transport_route_snapshot_digest,
            "transport_route_snapshot_id": self.transport_route_snapshot_id,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, evaluated_at: datetime
    ) -> WorkflowEventPhysicalTransportTargetContextBindingEffectiveState:
        if evaluated_at.tzinfo is None:
            raise ValueError("target context binding evaluation time must be aware")
        if self.bound_at <= evaluated_at < self.joint_usable_until:
            return WorkflowEventPhysicalTransportTargetContextBindingEffectiveState.ACTIVE
        return WorkflowEventPhysicalTransportTargetContextBindingEffectiveState.EXPIRED


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationPolicy:
    """Code-owned requirements for one bounded protected-artifact access lease."""

    policy_id: str
    policy_version: str
    validity_window_seconds: int
    full_window_required: bool
    accessor_subject_bound: bool
    single_use_required: bool
    renewable_allowed: bool
    transferable_allowed: bool
    endpoint_status_attestation_required: bool
    credential_status_attestation_required: bool
    required_endpoint_status_attestor_id: str
    required_endpoint_status_attestor_version: str
    required_credential_status_attestor_id: str
    required_credential_status_attestor_version: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.policy_id, name="target context access policy id")
        _require_identifier(self.policy_version, name="target context access policy version")
        for value, name in (
            (self.required_endpoint_status_attestor_id, "required endpoint status attestor id"),
            (
                self.required_endpoint_status_attestor_version,
                "required endpoint status attestor version",
            ),
            (
                self.required_credential_status_attestor_id,
                "required credential status attestor id",
            ),
            (
                self.required_credential_status_attestor_version,
                "required credential status attestor version",
            ),
        ):
            _require_identifier(value, name=name)
        if (
            self.required_endpoint_status_attestor_id
            != "attestor.workflow-protected-endpoint-store-status"
            or self.required_endpoint_status_attestor_version != "1.0"
            or self.required_credential_status_attestor_id
            != "attestor.workflow-protected-credential-store-status"
            or self.required_credential_status_attestor_version != "1.0"
        ):
            raise ValueError("target context access policy requires code-owned status attestors")
        if self.validity_window_seconds != 5:
            raise ValueError("target context access policy window must be exactly 5 seconds")
        if any(
            value is not True
            for value in (
                self.full_window_required,
                self.accessor_subject_bound,
                self.single_use_required,
                self.endpoint_status_attestation_required,
                self.credential_status_attestation_required,
            )
        ):
            raise ValueError("target context access policy requirements must remain enabled")
        if self.renewable_allowed is not False or self.transferable_allowed is not False:
            raise ValueError("target context access leases cannot be renewable or transferable")
        _require_digest(self.canonical_digest, name="target context access policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context access policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_bound": self.accessor_subject_bound,
            "credential_status_attestation_required": (self.credential_status_attestation_required),
            "endpoint_status_attestation_required": self.endpoint_status_attestation_required,
            "full_window_required": self.full_window_required,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "required_credential_status_attestor_id": (self.required_credential_status_attestor_id),
            "required_credential_status_attestor_version": (
                self.required_credential_status_attestor_version
            ),
            "required_endpoint_status_attestor_id": self.required_endpoint_status_attestor_id,
            "required_endpoint_status_attestor_version": (
                self.required_endpoint_status_attestor_version
            ),
            "renewable_allowed": self.renewable_allowed,
            "single_use_required": self.single_use_required,
            "transferable_allowed": self.transferable_allowed,
            "validity_window_seconds": self.validity_window_seconds,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def code_owned_workflow_event_physical_transport_target_context_access_authorization_policy() -> (
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationPolicy
):
    values: dict[str, object] = {
        "policy_id": (
            "policy.workflow-event-physical-transport-target-context-access-authorization"
        ),
        "policy_version": "1.0",
        "validity_window_seconds": 5,
        "full_window_required": True,
        "accessor_subject_bound": True,
        "single_use_required": True,
        "renewable_allowed": False,
        "transferable_allowed": False,
        "endpoint_status_attestation_required": True,
        "credential_status_attestation_required": True,
        "required_endpoint_status_attestor_id": (
            "attestor.workflow-protected-endpoint-store-status"
        ),
        "required_endpoint_status_attestor_version": "1.0",
        "required_credential_status_attestor_id": (
            "attestor.workflow-protected-credential-store-status"
        ),
        "required_credential_status_attestor_version": "1.0",
    }
    return WorkflowEventPhysicalTransportTargetContextAccessAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedArtifactStatusAttestation:
    """Signed metadata-only evidence about one protected artifact's current status."""

    artifact_kind: WorkflowProtectedArtifactKind
    materialization_id: str
    materialization_digest: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    protected_store_attestor_id: str
    protected_store_attestor_version: str
    attestation_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    usable: bool
    revoked: bool
    destroyed: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_kind, WorkflowProtectedArtifactKind):
            raise ValueError("protected artifact status attestation kind is invalid")
        for value, name in (
            (self.materialization_id, "protected artifact materialization id"),
            (self.target_context_binding_id, "target context binding id"),
            (self.protected_store_attestor_id, "protected store attestor id"),
            (self.protected_store_attestor_version, "protected store attestor version"),
            (self.attestation_id, "protected artifact status attestation id"),
            (self.signing_key_id, "protected artifact status signing key id"),
            (self.signature_algorithm, "protected artifact status signature algorithm"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.materialization_digest, "protected artifact materialization digest"),
            (self.target_context_binding_digest, "target context binding digest"),
            (self.target_context_commitment, "target context commitment"),
            (self.request_nonce_digest, "protected artifact status request nonce digest"),
            (self.canonical_digest, "protected artifact status attestation digest"),
        ):
            _require_digest(value, name=name)
        if (
            not self.integrity_signature
            or self.integrity_signature != self.integrity_signature.strip()
            or len(self.integrity_signature) > 2048
            or any(character.isspace() for character in self.integrity_signature)
        ):
            raise ValueError("protected artifact status integrity signature is invalid")
        if self.observed_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("protected artifact status attestation times must be timezone-aware")
        if self.observed_at >= self.valid_until:
            raise ValueError("protected artifact status attestation must have a usable window")
        if self.usable is not True or self.revoked is not False or self.destroyed is not False:
            raise ValueError("protected artifact status attestation is not usable")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("protected artifact status attestation canonical digest mismatch")

    def signature_payload(self) -> dict[str, object]:
        return {
            "artifact_kind": self.artifact_kind.value,
            "attestation_id": self.attestation_id,
            "destroyed": self.destroyed,
            "materialization_digest": self.materialization_digest,
            "materialization_id": self.materialization_id,
            "observed_at": self.observed_at.isoformat(),
            "protected_store_attestor_id": self.protected_store_attestor_id,
            "protected_store_attestor_version": self.protected_store_attestor_version,
            "request_nonce_digest": self.request_nonce_digest,
            "revoked": self.revoked,
            "signature_algorithm": self.signature_algorithm,
            "signing_key_id": self.signing_key_id,
            "target_context_binding_digest": self.target_context_binding_digest,
            "target_context_binding_id": self.target_context_binding_id,
            "target_context_commitment": self.target_context_commitment,
            "usable": self.usable,
            "valid_until": self.valid_until.isoformat(),
        }

    def digest_payload(self) -> dict[str, object]:
        return {
            **self.signature_payload(),
            "integrity_signature": self.integrity_signature,
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority:
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = True
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        values = self.canonical_value()
        if values["protected_artifact_access_authorized"] is not True or any(
            value is not False
            for name, value in values.items()
            if name != "protected_artifact_access_authorized"
        ):
            raise ValueError("target context access leases grant only protected artifact access")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease:
    """Single-use access authority that never opens either protected artifact."""

    authorization_lease_id: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    endpoint_status_attestation_id: str
    endpoint_status_attestation_digest: str
    endpoint_status_attestation_valid_until: datetime
    credential_status_attestation_id: str
    credential_status_attestation_digest: str
    credential_status_attestation_valid_until: datetime
    scope: WorkflowScope
    accessor_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    issued_at: datetime
    valid_until: datetime
    joint_usable_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    state: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState
    authority: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.authorization_lease_id, "target context access authorization lease id"),
            (self.target_context_binding_id, "target context binding id"),
            (self.endpoint_status_attestation_id, "endpoint status attestation id"),
            (self.credential_status_attestation_id, "credential status attestation id"),
            (self.accessor_subject_id, "target context accessor subject id"),
            (self.policy_id, "target context access policy id"),
            (self.policy_version, "target context access policy version"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.target_context_binding_digest, "target context binding digest"),
            (self.target_context_commitment, "target context commitment"),
            (self.endpoint_status_attestation_digest, "endpoint status attestation digest"),
            (self.credential_status_attestation_digest, "credential status attestation digest"),
            (self.policy_digest, "target context access policy digest"),
            (self.canonical_digest, "target context access authorization lease digest"),
        ):
            _require_digest(value, name=name)
        if any(
            value.tzinfo is None
            for value in (
                self.endpoint_status_attestation_valid_until,
                self.credential_status_attestation_valid_until,
                self.issued_at,
                self.valid_until,
                self.joint_usable_until,
            )
        ):
            raise ValueError("target context access authorization times must be timezone-aware")
        if self.valid_until - self.issued_at != timedelta(seconds=5):
            raise ValueError("target context access lease must have an exact 5-second window")
        if self.issued_at >= self.valid_until or any(
            self.valid_until > deadline
            for deadline in (
                self.joint_usable_until,
                self.endpoint_status_attestation_valid_until,
                self.credential_status_attestation_valid_until,
            )
        ):
            raise ValueError("target context access lease exceeds its evidence window")
        if (
            self.single_use is not True
            or self.renewable is not False
            or self.transferable is not False
        ):
            raise ValueError("target context access lease must be single-use and non-transferable")
        if (
            self.state
            is not (
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
        ):
            raise ValueError("target context access lease must remain authorized_unconsumed")
        if (
            self.authority
            != WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority()
        ):
            raise ValueError("target context access lease has invalid authority declarations")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context access authorization lease canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            "accessor_subject_id": self.accessor_subject_id,
            "authority": self.authority.canonical_value(),
            "authorization_lease_id": self.authorization_lease_id,
            "credential_status_attestation_digest": self.credential_status_attestation_digest,
            "credential_status_attestation_id": self.credential_status_attestation_id,
            "credential_status_attestation_valid_until": (
                self.credential_status_attestation_valid_until.isoformat()
            ),
            "endpoint_status_attestation_digest": self.endpoint_status_attestation_digest,
            "endpoint_status_attestation_id": self.endpoint_status_attestation_id,
            "endpoint_status_attestation_valid_until": (
                self.endpoint_status_attestation_valid_until.isoformat()
            ),
            "issued_at": self.issued_at.isoformat(),
            "joint_usable_until": self.joint_usable_until.isoformat(),
            "policy_digest": self.policy_digest,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "renewable": self.renewable,
            "scope": self.scope.canonical_value(),
            "single_use": self.single_use,
            "state": self.state.value,
            "target_context_binding_digest": self.target_context_binding_digest,
            "target_context_binding_id": self.target_context_binding_id,
            "target_context_commitment": self.target_context_commitment,
            "transferable": self.transferable,
            "valid_until": self.valid_until.isoformat(),
        }

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, evaluated_at: datetime
    ) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState:
        if evaluated_at.tzinfo is None:
            raise ValueError("target context access evaluation time must be aware")
        if self.issued_at <= evaluated_at < self.valid_until:
            return (
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState
            ).ACTIVE
        return (
            WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState
        ).EXPIRED


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


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority:
    """Explicit zero-authority contract for every opening record."""

    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    endpoint_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("target context artifact opening records cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


def _target_context_artifact_opening_payload(instance: object) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowScope,
                    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority,
                ),
            )
            else value
        )
        for name, value in (
            (field.name, getattr(instance, field.name)) for field in fields(cast(Any, instance))
        )
        if name != "canonical_digest"
    }


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicy:
    policy_id: str
    policy_version: str
    required_opener_contract_id: str
    required_opener_attestor_id: str
    capsule_schema_id: str
    capsule_schema_version: str
    maximum_capsule_lifetime_seconds: int
    paired_open_required: bool
    raw_material_return_forbidden: bool
    network_activity_forbidden: bool
    delivery_forbidden: bool
    runtime_use_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.policy_id, "target context artifact opening policy id"),
            (self.policy_version, "target context artifact opening policy version"),
            (self.required_opener_contract_id, "target context artifact opener contract id"),
            (self.required_opener_attestor_id, "target context artifact opener attestor id"),
            (self.capsule_schema_id, "target context capsule schema id"),
            (self.capsule_schema_version, "target context capsule schema version"),
        ):
            _require_identifier(value, name=name)
        if (
            self.policy_id
            != "policy.workflow-event-physical-transport-target-context-artifact-opening"
            or self.policy_version != "1.0"
            or self.required_opener_contract_id
            != "contract.workflow-protected-target-context-artifact-opener.v1"
            or self.required_opener_attestor_id
            != "attestor.workflow-protected-target-context-artifact-opener"
            or self.capsule_schema_id != "schema.workflow-sealed-target-context-capsule-lineage"
            or self.capsule_schema_version != "1.0"
            or self.maximum_capsule_lifetime_seconds != 3
            or self.paired_open_required is not True
            or self.raw_material_return_forbidden is not True
            or self.network_activity_forbidden is not True
            or self.delivery_forbidden is not True
            or self.runtime_use_forbidden is not True
        ):
            raise ValueError("target context artifact opening policy is not code-owned")
        _require_digest(self.canonical_digest, name="target context artifact opening policy digest")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context artifact opening policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_artifact_opening_payload(self)


def code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy() -> (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicy
):
    values: dict[str, object] = {
        "policy_id": "policy.workflow-event-physical-transport-target-context-artifact-opening",
        "policy_version": "1.0",
        "required_opener_contract_id": (
            "contract.workflow-protected-target-context-artifact-opener.v1"
        ),
        "required_opener_attestor_id": (
            "attestor.workflow-protected-target-context-artifact-opener"
        ),
        "capsule_schema_id": "schema.workflow-sealed-target-context-capsule-lineage",
        "capsule_schema_version": "1.0",
        "maximum_capsule_lifetime_seconds": 3,
        "paired_open_required": True,
        "raw_material_return_forbidden": True,
        "network_activity_forbidden": True,
        "delivery_forbidden": True,
        "runtime_use_forbidden": True,
    }
    return WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim:
    claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    attempt_id: str
    opening_id: str
    scope: WorkflowScope
    accessor_subject_id: str
    claimed_at: datetime
    request_fingerprint: str
    idempotency_digest: str
    authority: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.claim_id, "target context access consumption claim id"),
            (self.authorization_lease_id, "target context access authorization lease id"),
            (self.target_context_binding_id, "target context binding id"),
            (self.attempt_id, "target context artifact opening attempt id"),
            (self.opening_id, "target context artifact opening id"),
            (self.accessor_subject_id, "target context accessor subject id"),
        ):
            _require_identifier(value, name=name)
        for value, name in (
            (self.authorization_lease_digest, "target context access lease digest"),
            (self.target_context_binding_digest, "target context binding digest"),
            (self.target_context_commitment, "target context commitment"),
            (self.request_fingerprint, "target context opening request fingerprint"),
            (self.idempotency_digest, "target context opening idempotency digest"),
            (self.canonical_digest, "target context access consumption claim digest"),
        ):
            _require_digest(value, name=name)
        if self.claimed_at.tzinfo is None or any(self.authority.canonical_value().values()):
            raise ValueError("target context access consumption claim is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context access consumption claim canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_artifact_opening_payload(self)


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt:
    attempt_id: str
    opening_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    endpoint_materialization_id: str
    endpoint_materialization_digest: str
    endpoint_protected_artifact_id: str
    endpoint_protected_artifact_digest: str
    endpoint_status_attestation_id: str
    endpoint_status_attestation_digest: str
    credential_materialization_id: str
    credential_materialization_digest: str
    credential_protected_artifact_id: str
    credential_protected_artifact_digest: str
    credential_status_attestation_id: str
    credential_status_attestation_digest: str
    request_nonce_digest: str
    opener_contract_id: str
    opener_attestor_id: str
    scope: WorkflowScope
    accessor_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    lease_valid_until: datetime
    joint_usable_until: datetime
    evidence_valid_until: datetime
    state: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptState
    authority: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        identifiers = (
            self.attempt_id,
            self.opening_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.target_context_binding_id,
            self.endpoint_materialization_id,
            self.endpoint_protected_artifact_id,
            self.endpoint_status_attestation_id,
            self.credential_materialization_id,
            self.credential_protected_artifact_id,
            self.credential_status_attestation_id,
            self.opener_contract_id,
            self.opener_attestor_id,
            self.accessor_subject_id,
            self.policy_id,
            self.policy_version,
        )
        for value in identifiers:
            _require_identifier(value, name="target context artifact opening attempt identifier")
        digests = (
            self.authorization_lease_digest,
            self.target_context_binding_digest,
            self.target_context_commitment,
            self.endpoint_materialization_digest,
            self.endpoint_protected_artifact_digest,
            self.endpoint_status_attestation_digest,
            self.credential_materialization_digest,
            self.credential_protected_artifact_digest,
            self.credential_status_attestation_digest,
            self.request_nonce_digest,
            self.policy_digest,
            self.canonical_digest,
        )
        for value in digests:
            _require_digest(value, name="target context artifact opening attempt digest")
        deadlines = (
            self.lease_valid_until,
            self.joint_usable_until,
            self.evidence_valid_until,
        )
        if (
            self.started_at.tzinfo is None
            or any(value.tzinfo is None for value in deadlines)
            or not self.started_at < min(deadlines)
            or self.state
            is not (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptState
            ).OPENING_STARTED
            or any(self.authority.canonical_value().values())
        ):
            raise ValueError("target context artifact opening attempt is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context artifact opening attempt canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_artifact_opening_payload(self)


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction:
    opening_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    endpoint_materialization_id: str
    endpoint_materialization_digest: str
    endpoint_protected_artifact_id: str
    endpoint_protected_artifact_digest: str
    endpoint_status_attestation_digest: str
    credential_materialization_id: str
    credential_materialization_digest: str
    credential_protected_artifact_id: str
    credential_protected_artifact_digest: str
    credential_status_attestation_digest: str
    scope: WorkflowScope
    accessor_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    opener_contract_id: str
    opener_attestor_id: str
    capsule_schema_id: str
    capsule_schema_version: str
    started_at: datetime
    lease_valid_until: datetime
    joint_usable_until: datetime
    evidence_valid_until: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.opening_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.target_context_binding_id,
            self.endpoint_materialization_id,
            self.endpoint_protected_artifact_id,
            self.credential_materialization_id,
            self.credential_protected_artifact_id,
            self.accessor_subject_id,
            self.policy_id,
            self.policy_version,
            self.opener_contract_id,
            self.opener_attestor_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
        ):
            _require_identifier(
                value, name="target context artifact opening instruction identifier"
            )
        for value in (
            self.authorization_lease_digest,
            self.target_context_binding_digest,
            self.target_context_commitment,
            self.endpoint_materialization_digest,
            self.endpoint_protected_artifact_digest,
            self.endpoint_status_attestation_digest,
            self.credential_materialization_digest,
            self.credential_protected_artifact_digest,
            self.credential_status_attestation_digest,
            self.policy_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="target context artifact opening instruction digest")
        if (
            self.started_at.tzinfo is None
            or any(
                value.tzinfo is None
                for value in (
                    self.lease_valid_until,
                    self.joint_usable_until,
                    self.evidence_valid_until,
                )
            )
            or not self.started_at
            < min(self.lease_valid_until, self.joint_usable_until, self.evidence_valid_until)
        ):
            raise ValueError("target context artifact opening instruction is outside its window")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError(
                "target context artifact opening instruction canonical digest mismatch"
            )

    def digest_payload(self) -> dict[str, object]:
        return _target_context_artifact_opening_payload(self)


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt:
    opening_id: str
    attempt_id: str
    consumption_claim_id: str
    instruction_digest: str
    opener_contract_id: str
    opener_id: str
    opener_version: str
    attested_by: str
    accessor_subject_id: str
    state: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
    failure_class: WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass | None
    sealed_capsule_id: str | None
    sealed_capsule_digest: str | None
    capsule_is_bearer_capability: bool
    capsule_schema_id: str
    capsule_schema_version: str
    endpoint_opened: bool
    credential_opened: bool
    pair_commitment_verified: bool
    raw_endpoint_returned: bool
    raw_credential_returned: bool
    network_activity_performed: bool
    delivery_performed: bool
    runtime_use_performed: bool
    protected_sources_closed: bool
    cleanup_confirmed: bool
    completed_at: datetime
    usable_until: datetime | None
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.opening_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.opener_contract_id,
            self.opener_id,
            self.opener_version,
            self.attested_by,
            self.accessor_subject_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.signing_key_id,
            self.signature_algorithm,
        ):
            _require_identifier(value, name="target context artifact opening receipt identifier")
        for value in (self.instruction_digest, self.integrity_signature, self.canonical_digest):
            _require_digest(value, name="target context artifact opening receipt digest")
        if self.completed_at.tzinfo is None or any(
            (
                self.raw_endpoint_returned,
                self.raw_credential_returned,
                self.network_activity_performed,
                self.delivery_performed,
                self.runtime_use_performed,
            )
        ):
            raise ValueError("target context artifact opening receipt violates zero-authority")
        if self.capsule_is_bearer_capability is not False:
            raise ValueError("sealed target context capsule is lineage, not a bearer capability")
        if (
            self.state
            is (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            ).OPENED_PROTECTED
        ):
            if (
                self.failure_class is not None
                or self.sealed_capsule_id is None
                or self.sealed_capsule_digest is None
                or self.usable_until is None
                or not self.completed_at < self.usable_until
                or not self.endpoint_opened
                or not self.credential_opened
                or not self.pair_commitment_verified
                or not self.protected_sources_closed
                or not self.cleanup_confirmed
            ):
                raise ValueError("successful target context artifact opening receipt is invalid")
            _require_identifier(self.sealed_capsule_id, name="sealed target context capsule id")
            _require_digest(self.sealed_capsule_digest, name="sealed target context capsule digest")
        elif (
            self.state
            is not (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            ).OPENING_FAILED
            or self.failure_class is None
            or self.sealed_capsule_id is not None
            or self.sealed_capsule_digest is not None
            or self.usable_until is not None
            or not self.protected_sources_closed
            or not self.cleanup_confirmed
        ):
            raise ValueError("failed target context artifact opening receipt is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context artifact opening receipt canonical digest mismatch")

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _target_context_artifact_opening_payload(self)


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult:
    opening_id: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    scope: WorkflowScope
    accessor_subject_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    opener_id: str
    opener_version: str
    opening_receipt_digest: str
    state: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
    failure_class: WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass | None
    sealed_capsule_id: str | None
    sealed_capsule_digest: str | None
    capsule_is_bearer_capability: bool
    capsule_schema_id: str
    capsule_schema_version: str
    completed_at: datetime
    usable_until: datetime | None
    protected_sources_closed: bool
    cleanup_confirmed: bool
    authority: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.opening_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.target_context_binding_id,
            self.accessor_subject_id,
            self.policy_id,
            self.policy_version,
            self.opener_id,
            self.opener_version,
            self.capsule_schema_id,
            self.capsule_schema_version,
        ):
            _require_identifier(value, name="target context artifact opening result identifier")
        for value in (
            self.attempt_digest,
            self.consumption_claim_digest,
            self.authorization_lease_digest,
            self.target_context_binding_digest,
            self.target_context_commitment,
            self.policy_digest,
            self.opening_receipt_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="target context artifact opening result digest")
        if (
            self.completed_at.tzinfo is None
            or self.capsule_is_bearer_capability is not False
            or any(self.authority.canonical_value().values())
        ):
            raise ValueError("target context artifact opening result is invalid")
        if (
            self.state
            is (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            ).OPENED_PROTECTED
        ):
            if (
                self.failure_class is not None
                or self.sealed_capsule_id is None
                or self.sealed_capsule_digest is None
                or self.usable_until is None
                or not self.completed_at < self.usable_until
                or not self.protected_sources_closed
                or not self.cleanup_confirmed
            ):
                raise ValueError("successful target context artifact opening result is invalid")
            _require_identifier(self.sealed_capsule_id, name="sealed target context capsule id")
            _require_digest(self.sealed_capsule_digest, name="sealed target context capsule digest")
        elif (
            self.state
            is not (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            ).OPENING_FAILED
            or self.failure_class is None
            or self.sealed_capsule_id is not None
            or self.sealed_capsule_digest is not None
            or self.usable_until is not None
            or not self.protected_sources_closed
            or not self.cleanup_confirmed
        ):
            raise ValueError("failed target context artifact opening result is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context artifact opening result canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_artifact_opening_payload(self)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority:
    """Explicit zero-authority contract for capsule consumer binding evidence."""

    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("target context capsule consumer bindings cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
        }


def _target_context_capsule_consumer_binding_payload(instance: object) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowScope,
                    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority,
                ),
            )
            else value
        )
        for name, value in (
            (field.name, getattr(instance, field.name)) for field in fields(cast(Any, instance))
        )
        if name != "canonical_digest"
    }


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicy:
    policy_id: str
    policy_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    minimum_remaining_lifetime_seconds: int
    successful_opening_required: bool
    exact_pending_event_lineage_required: bool
    one_binding_per_opening_result_required: bool
    one_binding_per_capsule_required: bool
    handoff_forbidden: bool
    unsealing_forbidden: bool
    external_io_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.policy_version,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
        ):
            _require_identifier(value, name="target context capsule consumer binding policy value")
        if (
            self.policy_id
            != "policy.workflow-protected-transport-target-context-capsule-consumer-binding"
            or self.policy_version != "1.0"
            or self.consumer_subject_id
            != "service.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_audience
            != "audience.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_contract_id
            != "contract.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_contract_version != "1.0"
            or self.purpose_id
            != "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
            or self.minimum_remaining_lifetime_seconds != 1
            or self.successful_opening_required is not True
            or self.exact_pending_event_lineage_required is not True
            or self.one_binding_per_opening_result_required is not True
            or self.one_binding_per_capsule_required is not True
            or self.handoff_forbidden is not True
            or self.unsealing_forbidden is not True
            or self.external_io_forbidden is not True
        ):
            raise ValueError("target context capsule consumer binding policy is not code-owned")
        _require_digest(
            self.canonical_digest,
            name="target context capsule consumer binding policy digest",
        )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError(
                "target context capsule consumer binding policy canonical digest mismatch"
            )

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_consumer_binding_payload(self)


def code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy() -> (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicy
):
    values: dict[str, object] = {
        "policy_id": (
            "policy.workflow-protected-transport-target-context-capsule-consumer-binding"
        ),
        "policy_version": "1.0",
        "consumer_subject_id": (
            "service.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_audience": (
            "audience.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_contract_id": (
            "contract.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_contract_version": "1.0",
        "purpose_id": (
            "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
        ),
        "minimum_remaining_lifetime_seconds": 1,
        "successful_opening_required": True,
        "exact_pending_event_lineage_required": True,
        "one_binding_per_opening_result_required": True,
        "one_binding_per_capsule_required": True,
        "handoff_forbidden": True,
        "unsealing_forbidden": True,
        "external_io_forbidden": True,
    }
    return WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleConsumerBinding:
    """Immutable capsule-to-consumer evidence without handoff or runtime authority."""

    binding_id: str
    opening_result_id: str
    opening_result_digest: str
    opening_attempt_id: str
    opening_attempt_digest: str
    lease_consumption_claim_id: str
    lease_consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    capsule_is_bearer_capability: bool
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    outbox_entry_id: str
    outbox_entry_digest: str
    event_id: str
    event_digest: str
    event_artifact_id: str
    event_artifact_digest: str
    logical_channel_binding_id: str
    logical_channel_binding_digest: str
    physical_transport_route_binding_id: str
    physical_transport_route_binding_digest: str
    transport_route_snapshot_id: str
    transport_route_snapshot_digest: str
    physical_transport_credential_assignment_binding_id: str
    physical_transport_credential_assignment_binding_digest: str
    credential_assignment_snapshot_id: str
    credential_assignment_snapshot_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    workflow_execution_attempt_id: str
    workflow_execution_attempt_digest: str
    target_id: str
    target_type: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    scope: WorkflowScope
    binder_subject_id: str
    binder_audience: str
    bound_at: datetime
    effective_until: datetime
    policy_id: str
    policy_version: str
    policy_digest: str
    request_fingerprint: str
    idempotency_digest: str
    authorization_audit_digest: str
    state: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState
    authority: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        identifiers = (
            self.binding_id,
            self.opening_result_id,
            self.opening_attempt_id,
            self.lease_consumption_claim_id,
            self.authorization_lease_id,
            self.sealed_capsule_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.target_context_binding_id,
            self.outbox_entry_id,
            self.event_id,
            self.event_artifact_id,
            self.logical_channel_binding_id,
            self.physical_transport_route_binding_id,
            self.transport_route_snapshot_id,
            self.physical_transport_credential_assignment_binding_id,
            self.credential_assignment_snapshot_id,
            self.plan_id,
            self.run_id,
            self.step_run_id,
            self.workflow_execution_attempt_id,
            self.target_id,
            self.target_type,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.binder_subject_id,
            self.binder_audience,
            self.policy_id,
            self.policy_version,
        )
        for value in identifiers:
            _require_identifier(value, name="target context capsule consumer binding identifier")
        digests = (
            self.opening_result_digest,
            self.opening_attempt_digest,
            self.lease_consumption_claim_digest,
            self.authorization_lease_digest,
            self.sealed_capsule_digest,
            self.target_context_binding_digest,
            self.target_context_commitment,
            self.outbox_entry_digest,
            self.event_digest,
            self.event_artifact_digest,
            self.logical_channel_binding_digest,
            self.physical_transport_route_binding_digest,
            self.transport_route_snapshot_digest,
            self.physical_transport_credential_assignment_binding_digest,
            self.credential_assignment_snapshot_digest,
            self.plan_digest,
            self.run_digest,
            self.step_run_digest,
            self.workflow_execution_attempt_digest,
            self.policy_digest,
            self.request_fingerprint,
            self.idempotency_digest,
            self.authorization_audit_digest,
            self.canonical_digest,
        )
        for value in digests:
            _require_digest(value, name="target context capsule consumer binding digest")
        policy = (
            code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
        )
        if (
            self.capsule_is_bearer_capability is not False
            or self.bound_at.tzinfo is None
            or self.effective_until.tzinfo is None
            or not self.bound_at < self.effective_until
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.state
            is not WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND
            or any(self.authority.canonical_value().values())
        ):
            raise ValueError("target context capsule consumer binding is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context capsule consumer binding canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_consumer_binding_payload(self)

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


def _target_context_capsule_handoff_payload(instance: object) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowScope,
                    WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
                ),
            )
            else value
        )
        for name, value in (
            (field.name, getattr(instance, field.name)) for field in fields(cast(Any, instance))
        )
        if name != "canonical_digest"
    }


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationPolicy:
    policy_id: str
    policy_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    validity_window_seconds: int
    full_window_required: bool
    consumer_subject_bound: bool
    single_use_required: bool
    renewable_allowed: bool
    transferable_allowed: bool
    capsule_lifecycle_attestation_required: bool
    required_capsule_lifecycle_attestor_id: str
    required_capsule_lifecycle_attestor_version: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.policy_version,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.required_capsule_lifecycle_attestor_id,
            self.required_capsule_lifecycle_attestor_version,
        ):
            _require_identifier(value, name="target context capsule handoff policy value")
        if (
            self.policy_id
            != "policy.workflow-protected-transport-target-context-capsule-handoff-authorization"
            or self.policy_version != "1.0"
            or self.consumer_subject_id
            != "service.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_audience
            != "audience.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_contract_id
            != "contract.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_contract_version != "1.0"
            or self.purpose_id
            != "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
            or self.validity_window_seconds != 1
            or self.full_window_required is not True
            or self.consumer_subject_bound is not True
            or self.single_use_required is not True
            or self.renewable_allowed is not False
            or self.transferable_allowed is not False
            or self.capsule_lifecycle_attestation_required is not True
            or self.required_capsule_lifecycle_attestor_id
            != "attestor.workflow-protected-target-context-capsule-lifecycle"
            or self.required_capsule_lifecycle_attestor_version != "1.0"
        ):
            raise ValueError("target context capsule handoff policy is not code-owned")
        _require_digest(
            self.canonical_digest,
            name="target context capsule handoff policy digest",
        )
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context capsule handoff policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_payload(self)


def code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy() -> (  # noqa: E501
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationPolicy
):
    values: dict[str, object] = {
        "policy_id": (
            "policy.workflow-protected-transport-target-context-capsule-handoff-authorization"
        ),
        "policy_version": "1.0",
        "consumer_subject_id": (
            "service.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_audience": (
            "audience.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_contract_id": (
            "contract.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_contract_version": "1.0",
        "purpose_id": (
            "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
        ),
        "validity_window_seconds": 1,
        "full_window_required": True,
        "consumer_subject_bound": True,
        "single_use_required": True,
        "renewable_allowed": False,
        "transferable_allowed": False,
        "capsule_lifecycle_attestation_required": True,
        "required_capsule_lifecycle_attestor_id": (
            "attestor.workflow-protected-target-context-capsule-lifecycle"
        ),
        "required_capsule_lifecycle_attestor_version": "1.0",
    }
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleLifecycleAttestation:
    """Signed metadata-only evidence for one sealed capsule's current lifecycle."""

    attestation_id: str
    protected_store_attestor_id: str
    protected_store_attestor_version: str
    opening_result_id: str
    opening_result_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    usable: bool
    revoked: bool
    destroyed: bool
    sealed: bool
    capsule_is_bearer_capability: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.attestation_id,
            self.protected_store_attestor_id,
            self.protected_store_attestor_version,
            self.opening_result_id,
            self.consumer_binding_id,
            self.sealed_capsule_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.signing_key_id,
            self.signature_algorithm,
        ):
            _require_identifier(value, name="target context capsule lifecycle identifier")
        for value in (
            self.opening_result_digest,
            self.consumer_binding_digest,
            self.sealed_capsule_digest,
            self.request_nonce_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="target context capsule lifecycle digest")
        if (
            not self.integrity_signature
            or self.integrity_signature != self.integrity_signature.strip()
            or len(self.integrity_signature) > 2048
            or any(character.isspace() for character in self.integrity_signature)
        ):
            raise ValueError("target context capsule lifecycle signature is invalid")
        if (
            self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.observed_at >= self.valid_until
            or self.usable is not True
            or self.revoked is not False
            or self.destroyed is not False
            or self.sealed is not True
            or self.capsule_is_bearer_capability is not False
        ):
            raise ValueError("target context capsule lifecycle attestation is not usable")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("target context capsule lifecycle attestation digest mismatch")

    def signature_payload(self) -> dict[str, object]:
        return {
            "attestation_id": self.attestation_id,
            "capsule_is_bearer_capability": self.capsule_is_bearer_capability,
            "capsule_schema_id": self.capsule_schema_id,
            "capsule_schema_version": self.capsule_schema_version,
            "consumer_binding_digest": self.consumer_binding_digest,
            "consumer_binding_id": self.consumer_binding_id,
            "destroyed": self.destroyed,
            "observed_at": self.observed_at.isoformat(),
            "opening_result_digest": self.opening_result_digest,
            "opening_result_id": self.opening_result_id,
            "protected_store_attestor_id": self.protected_store_attestor_id,
            "protected_store_attestor_version": self.protected_store_attestor_version,
            "request_nonce_digest": self.request_nonce_digest,
            "revoked": self.revoked,
            "sealed": self.sealed,
            "sealed_capsule_digest": self.sealed_capsule_digest,
            "sealed_capsule_id": self.sealed_capsule_id,
            "signature_algorithm": self.signature_algorithm,
            "signing_key_id": self.signing_key_id,
            "usable": self.usable,
            "valid_until": self.valid_until.isoformat(),
        }

    def digest_payload(self) -> dict[str, object]:
        return {**self.signature_payload(), "integrity_signature": self.integrity_signature}

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority:
    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    target_context_capsule_handoff_authorized: bool = True

    def __post_init__(self) -> None:
        values = self.canonical_value()
        if values["target_context_capsule_handoff_authorized"] is not True or any(
            value is not False
            for name, value in values.items()
            if name != "target_context_capsule_handoff_authorized"
        ):
            raise ValueError("target context capsule handoff leases grant only handoff authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
            "target_context_capsule_handoff_authorized": (
                self.target_context_capsule_handoff_authorized
            ),
        }


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease:
    """Single-use handoff-request authority that never moves or opens a capsule."""

    authorization_lease_id: str
    consumer_binding_id: str
    consumer_binding_digest: str
    opening_result_id: str
    opening_result_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    lifecycle_attestation_id: str
    lifecycle_attestation_digest: str
    lifecycle_attestation_valid_until: datetime
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState
    authority: WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.opening_result_id,
            self.sealed_capsule_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.lifecycle_attestation_id,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.policy_id,
            self.policy_version,
        ):
            _require_identifier(value, name="target context capsule handoff lease identifier")
        for value in (
            self.consumer_binding_digest,
            self.opening_result_digest,
            self.sealed_capsule_digest,
            self.lifecycle_attestation_digest,
            self.policy_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="target context capsule handoff lease digest")
        if any(
            value.tzinfo is None
            for value in (
                self.lifecycle_attestation_valid_until,
                self.issued_at,
                self.valid_until,
                self.effective_until,
            )
        ):
            raise ValueError("target context capsule handoff lease times must be timezone-aware")
        if (
            self.valid_until - self.issued_at != timedelta(seconds=1)
            or self.issued_at >= self.valid_until
            or self.valid_until > self.effective_until
            or self.valid_until > self.lifecycle_attestation_valid_until
            or self.single_use is not True
            or self.renewable is not False
            or self.transferable is not False
            or self.lease_is_bearer_capability is not False
            or self.state
            is not (
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or self.authority
            != WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority()
        ):
            raise ValueError("target context capsule handoff lease is invalid")
        policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy()  # noqa: E501
        if (
            self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.canonical_digest != canonical_digest(self.digest_payload())
        ):
            raise ValueError("target context capsule handoff lease is not code-owned")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_payload(self)

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}

    def effective_state(
        self, *, evaluated_at: datetime
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState:
        if evaluated_at.tzinfo is None:
            raise ValueError("target context capsule handoff evaluation time must be aware")
        if self.issued_at <= evaluated_at < self.valid_until:
            return (
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState
            ).ACTIVE
        return (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState
        ).EXPIRED


def _target_context_capsule_handoff_consumption_payload(
    instance: object,
) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in (
            (field.name, getattr(instance, field.name)) for field in fields(cast(Any, instance))
        )
        if name != "canonical_digest"
    }


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority:
    """Explicit zero-authority evidence after lease consumption."""

    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    target_context_capsule_handoff_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("consumed target context capsule handoff evidence grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
            "target_context_capsule_handoff_authorized": (
                self.target_context_capsule_handoff_authorized
            ),
        }


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionPolicy:
    policy_id: str
    policy_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    required_lifecycle_attestor_id: str
    required_lifecycle_attestor_version: str
    required_acceptance_attestor_id: str
    required_acceptance_attestor_version: str
    required_adapter_contract_id: str
    required_adapter_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    minimum_remaining_budget_milliseconds: int
    irreversible_consumption_required: bool
    automatic_retry_allowed: bool
    unsealing_allowed: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.policy_version,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.required_lifecycle_attestor_id,
            self.required_lifecycle_attestor_version,
            self.required_acceptance_attestor_id,
            self.required_acceptance_attestor_version,
            self.required_adapter_contract_id,
            self.required_adapter_contract_version,
            self.approved_adapter_id,
            self.approved_adapter_version,
            self.destination_boundary_id,
            self.destination_deployment_id,
            self.custody_contract_id,
            self.custody_contract_version,
            self.verification_signing_key_id,
        ):
            _require_identifier(value, name="target context capsule handoff consumption policy")
        if (
            self.policy_id
            != "policy.workflow-protected-transport-target-context-capsule-handoff-consumption"
            or self.policy_version != "1.0"
            or self.consumer_subject_id
            != "service.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_audience
            != "audience.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_contract_id
            != "contract.workflow-protected-transport-target-context-capsule-consumer"
            or self.consumer_contract_version != "1.0"
            or self.purpose_id
            != "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
            or self.required_lifecycle_attestor_id
            != "attestor.workflow-protected-target-context-capsule-handoff-lifecycle"
            or self.required_lifecycle_attestor_version != "1.0"
            or self.required_acceptance_attestor_id
            != "attestor.workflow-protected-target-context-consumer-boundary-acceptance"
            or self.required_acceptance_attestor_version != "1.0"
            or self.required_adapter_contract_id
            != "contract.workflow-protected-target-context-capsule-sealed-handoff"
            or self.required_adapter_contract_version != "1.0"
            or self.approved_adapter_id
            != "adapter.workflow-protected-target-context-capsule-sealed-handoff"
            or self.approved_adapter_version != "1.0"
            or self.destination_boundary_id
            != "boundary.workflow-protected-target-context-capsule-consumer"
            or self.destination_deployment_id
            != "deployment.workflow-protected-target-context-capsule-consumer"
            or self.destination_generation != 1
            or self.custody_contract_id
            != "contract.workflow-protected-target-context-capsule-custody"
            or self.custody_contract_version != "1.0"
            or self.verification_signing_key_id
            != "key.workflow-protected-target-context-capsule-handoff-receipt.v1"
            or self.minimum_remaining_budget_milliseconds != 100
            or self.irreversible_consumption_required is not True
            or self.automatic_retry_allowed is not False
            or self.unsealing_allowed is not False
        ):
            raise ValueError("target context capsule handoff consumption policy is not code-owned")
        _require_digest(self.canonical_digest, name="handoff consumption policy digest")
        _require_digest(
            self.destination_fencing_token_digest,
            name="handoff destination fencing token digest",
        )
        _require_digest(self.trusted_profile_digest, name="handoff trusted profile digest")
        profile = {
            "approved_adapter_id": self.approved_adapter_id,
            "approved_adapter_version": self.approved_adapter_version,
            "custody_contract_id": self.custody_contract_id,
            "custody_contract_version": self.custody_contract_version,
            "destination_boundary_id": self.destination_boundary_id,
            "destination_deployment_id": self.destination_deployment_id,
            "destination_fencing_token_digest": self.destination_fencing_token_digest,
            "destination_generation": self.destination_generation,
            "verification_signing_key_id": self.verification_signing_key_id,
        }
        if self.trusted_profile_digest != canonical_digest(profile):
            raise ValueError("handoff trusted profile digest mismatch")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("handoff consumption policy canonical digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_consumption_payload(self)


def code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy() -> (
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionPolicy
):
    destination_fencing_token_digest = canonical_digest(
        {
            "destination_boundary_id": (
                "boundary.workflow-protected-target-context-capsule-consumer"
            ),
            "destination_deployment_id": (
                "deployment.workflow-protected-target-context-capsule-consumer"
            ),
            "destination_generation": 1,
        }
    )
    trusted_profile = {
        "approved_adapter_id": ("adapter.workflow-protected-target-context-capsule-sealed-handoff"),
        "approved_adapter_version": "1.0",
        "custody_contract_id": ("contract.workflow-protected-target-context-capsule-custody"),
        "custody_contract_version": "1.0",
        "destination_boundary_id": ("boundary.workflow-protected-target-context-capsule-consumer"),
        "destination_deployment_id": (
            "deployment.workflow-protected-target-context-capsule-consumer"
        ),
        "destination_fencing_token_digest": destination_fencing_token_digest,
        "destination_generation": 1,
        "verification_signing_key_id": (
            "key.workflow-protected-target-context-capsule-handoff-receipt.v1"
        ),
    }
    values: dict[str, object] = {
        "policy_id": (
            "policy.workflow-protected-transport-target-context-capsule-handoff-consumption"
        ),
        "policy_version": "1.0",
        "consumer_subject_id": (
            "service.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_audience": (
            "audience.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_contract_id": (
            "contract.workflow-protected-transport-target-context-capsule-consumer"
        ),
        "consumer_contract_version": "1.0",
        "purpose_id": (
            "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
        ),
        "required_lifecycle_attestor_id": (
            "attestor.workflow-protected-target-context-capsule-handoff-lifecycle"
        ),
        "required_lifecycle_attestor_version": "1.0",
        "required_acceptance_attestor_id": (
            "attestor.workflow-protected-target-context-consumer-boundary-acceptance"
        ),
        "required_acceptance_attestor_version": "1.0",
        "required_adapter_contract_id": (
            "contract.workflow-protected-target-context-capsule-sealed-handoff"
        ),
        "required_adapter_contract_version": "1.0",
        **trusted_profile,
        "trusted_profile_digest": canonical_digest(trusted_profile),
        "minimum_remaining_budget_milliseconds": 100,
        "irreversible_consumption_required": True,
        "automatic_retry_allowed": False,
        "unsealing_allowed": False,
    }
    return WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    handoff_eligible: bool
    revoked: bool
    destroyed: bool
    sealed: bool
    already_handed_off: bool
    capsule_is_bearer_capability: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.attestation_id,
            self.attestor_id,
            self.attestor_version,
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.sealed_capsule_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.signing_key_id,
            self.signature_algorithm,
        ):
            _require_identifier(value, name="capsule handoff lifecycle attestation identifier")
        for value in (
            self.authorization_lease_digest,
            self.consumer_binding_digest,
            self.sealed_capsule_digest,
            self.request_nonce_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="capsule handoff lifecycle attestation digest")
        if (
            self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.observed_at >= self.valid_until
            or self.handoff_eligible is not True
            or self.revoked is not False
            or self.destroyed is not False
            or self.sealed is not True
            or self.already_handed_off is not False
            or self.capsule_is_bearer_capability is not False
            or not self.integrity_signature
            or any(character.isspace() for character in self.integrity_signature)
        ):
            raise ValueError("capsule handoff lifecycle attestation is unsafe")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("capsule handoff lifecycle attestation digest mismatch")

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in _target_context_capsule_handoff_consumption_payload(self).items()
            if name not in {"integrity_signature"}
        }

    def digest_payload(self) -> dict[str, object]:
        return {**self.signature_payload(), "integrity_signature": self.integrity_signature}

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    capsule_schema_id: str
    capsule_schema_version: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    acceptance_eligible: bool
    destination_is_protected_boundary: bool
    runtime_use_authorized: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.attestation_id,
            self.attestor_id,
            self.attestor_version,
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.destination_boundary_id,
            self.destination_deployment_id,
            self.custody_contract_id,
            self.custody_contract_version,
            self.approved_adapter_id,
            self.approved_adapter_version,
            self.verification_signing_key_id,
            self.signing_key_id,
            self.signature_algorithm,
        ):
            _require_identifier(value, name="consumer boundary acceptance identifier")
        for value in (
            self.authorization_lease_digest,
            self.consumer_binding_digest,
            self.request_nonce_digest,
            self.destination_fencing_token_digest,
            self.trusted_profile_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="consumer boundary acceptance digest")
        if (
            self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.observed_at >= self.valid_until
            or self.acceptance_eligible is not True
            or self.destination_is_protected_boundary is not True
            or self.runtime_use_authorized is not False
            or self.destination_generation < 1
            or not self.integrity_signature
            or any(character.isspace() for character in self.integrity_signature)
        ):
            raise ValueError("consumer boundary acceptance attestation is unsafe")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("consumer boundary acceptance attestation digest mismatch")

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in _target_context_capsule_handoff_consumption_payload(self).items()
            if name not in {"integrity_signature"}
        }

    def digest_payload(self) -> dict[str, object]:
        return {**self.signature_payload(), "integrity_signature": self.integrity_signature}

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim:
    claim_id: str
    handoff_id: str
    attempt_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    request_fingerprint: str
    idempotency_digest: str
    consumption_authorization_audit_digest: str
    claimed_at: datetime
    authority: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.claim_id,
            self.handoff_id,
            self.attempt_id,
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.sealed_capsule_id,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.policy_id,
            self.policy_version,
        ):
            _require_identifier(value, name="capsule handoff claim identifier")
        for value in (
            self.authorization_lease_digest,
            self.consumer_binding_digest,
            self.sealed_capsule_digest,
            self.policy_digest,
            self.request_fingerprint,
            self.idempotency_digest,
            self.consumption_authorization_audit_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="capsule handoff claim digest")
        policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()  # noqa: E501
        if (
            self.claimed_at.tzinfo is None
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or any(self.authority.canonical_value().values())
            or self.canonical_digest != canonical_digest(self.digest_payload())
        ):
            raise ValueError("capsule handoff claim is invalid")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_consumption_payload(self)

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt:
    attempt_id: str
    handoff_id: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    adapter_contract_id: str
    adapter_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    lifecycle_attestation_id: str
    lifecycle_attestation_digest: str
    acceptance_attestation_id: str
    acceptance_attestation_digest: str
    request_nonce_digest: str
    started_at: datetime
    handoff_deadline: datetime
    lease_valid_until: datetime
    binding_effective_until: datetime
    source_effective_until: datetime
    lifecycle_attestation_valid_until: datetime
    acceptance_attestation_valid_until: datetime
    state: WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptState
    authority: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.attempt_id,
            self.handoff_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.sealed_capsule_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.policy_id,
            self.policy_version,
            self.adapter_contract_id,
            self.adapter_contract_version,
            self.approved_adapter_id,
            self.approved_adapter_version,
            self.destination_boundary_id,
            self.destination_deployment_id,
            self.custody_contract_id,
            self.custody_contract_version,
            self.verification_signing_key_id,
            self.lifecycle_attestation_id,
            self.acceptance_attestation_id,
        ):
            _require_identifier(value, name="capsule handoff attempt identifier")
        for value in (
            self.consumption_claim_digest,
            self.authorization_lease_digest,
            self.consumer_binding_digest,
            self.sealed_capsule_digest,
            self.policy_digest,
            self.lifecycle_attestation_digest,
            self.acceptance_attestation_digest,
            self.request_nonce_digest,
            self.destination_fencing_token_digest,
            self.trusted_profile_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="capsule handoff attempt digest")
        policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()  # noqa: E501
        if (
            self.started_at.tzinfo is None
            or self.handoff_deadline.tzinfo is None
            or any(
                value.tzinfo is None
                for value in (
                    self.lease_valid_until,
                    self.binding_effective_until,
                    self.source_effective_until,
                    self.lifecycle_attestation_valid_until,
                    self.acceptance_attestation_valid_until,
                )
            )
            or not self.started_at < self.handoff_deadline
            or self.handoff_deadline
            > min(
                self.lease_valid_until,
                self.binding_effective_until,
                self.source_effective_until,
                self.lifecycle_attestation_valid_until,
                self.acceptance_attestation_valid_until,
            )
            or self.state
            is not WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptState.STARTED
            or self.adapter_contract_id != policy.required_adapter_contract_id
            or self.adapter_contract_version != policy.required_adapter_contract_version
            or self.approved_adapter_id != policy.approved_adapter_id
            or self.approved_adapter_version != policy.approved_adapter_version
            or self.destination_boundary_id != policy.destination_boundary_id
            or self.destination_deployment_id != policy.destination_deployment_id
            or self.destination_generation != policy.destination_generation
            or self.destination_fencing_token_digest != policy.destination_fencing_token_digest
            or self.custody_contract_id != policy.custody_contract_id
            or self.custody_contract_version != policy.custody_contract_version
            or self.verification_signing_key_id != policy.verification_signing_key_id
            or self.trusted_profile_digest != policy.trusted_profile_digest
            or any(self.authority.canonical_value().values())
            or self.canonical_digest != canonical_digest(self.digest_payload())
        ):
            raise ValueError("capsule handoff attempt is invalid")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_consumption_payload(self)

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction:
    handoff_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    adapter_contract_id: str
    adapter_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    started_at: datetime
    handoff_deadline: datetime
    lifecycle_attestation_digest: str
    acceptance_attestation_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.handoff_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.sealed_capsule_id,
            self.capsule_schema_id,
            self.capsule_schema_version,
            self.consumer_subject_id,
            self.consumer_audience,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.adapter_contract_id,
            self.adapter_contract_version,
            self.approved_adapter_id,
            self.approved_adapter_version,
            self.destination_boundary_id,
            self.destination_deployment_id,
            self.custody_contract_id,
            self.custody_contract_version,
            self.verification_signing_key_id,
        ):
            _require_identifier(value, name="sealed capsule handoff instruction identifier")
        for value in (
            self.authorization_lease_digest,
            self.consumer_binding_digest,
            self.sealed_capsule_digest,
            self.lifecycle_attestation_digest,
            self.acceptance_attestation_digest,
            self.destination_fencing_token_digest,
            self.trusted_profile_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="sealed capsule handoff instruction digest")
        if (
            self.started_at.tzinfo is None
            or self.handoff_deadline.tzinfo is None
            or not self.started_at < self.handoff_deadline
            or self.destination_generation < 1
            or self.canonical_digest != canonical_digest(self.digest_payload())
        ):
            raise ValueError("sealed capsule handoff instruction is invalid")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_consumption_payload(self)


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt:
    handoff_id: str
    attempt_id: str
    consumption_claim_id: str
    instruction_digest: str
    adapter_id: str
    adapter_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    trusted_profile_digest: str
    state: WorkflowProtectedTransportTargetContextCapsuleHandoffResultState
    failure_class: WorkflowProtectedTransportTargetContextCapsuleHandoffFailureClass | None
    consumer_receipt_id: str | None
    consumer_receipt_is_bearer_capability: bool
    sealed_capsule_handed_off: bool
    capsule_remained_sealed: bool
    source_cleanup_confirmed: bool
    runtime_use_performed: bool
    network_activity_performed: bool
    completed_at: datetime
    usable_until: datetime | None
    attested_by: str
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.handoff_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.adapter_id,
            self.adapter_version,
            self.adapter_contract_id,
            self.adapter_contract_version,
            self.destination_boundary_id,
            self.destination_deployment_id,
            self.custody_contract_id,
            self.custody_contract_version,
            self.attested_by,
            self.signing_key_id,
            self.signature_algorithm,
        ):
            _require_identifier(value, name="sealed capsule handoff receipt identifier")
        for value in (
            self.instruction_digest,
            self.destination_fencing_token_digest,
            self.trusted_profile_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="sealed capsule handoff receipt digest")
        if (
            self.completed_at.tzinfo is None
            or self.consumer_receipt_is_bearer_capability is not False
            or self.capsule_remained_sealed is not True
            or self.runtime_use_performed is not False
            or self.network_activity_performed is not False
            or self.destination_generation < 1
            or not self.integrity_signature
            or any(character.isspace() for character in self.integrity_signature)
        ):
            raise ValueError("sealed capsule handoff receipt is unsafe")
        if (
            self.state
            is WorkflowProtectedTransportTargetContextCapsuleHandoffResultState.HANDED_OFF_SEALED
        ):
            if (
                self.failure_class is not None
                or self.consumer_receipt_id is None
                or self.sealed_capsule_handed_off is not True
                or self.usable_until is None
                or not self.completed_at < self.usable_until
            ):
                raise ValueError("successful sealed capsule handoff receipt is invalid")
            _require_identifier(self.consumer_receipt_id, name="consumer receipt id")
        elif (
            self.failure_class is None
            or self.consumer_receipt_id is not None
            or self.sealed_capsule_handed_off is not False
            or self.usable_until is not None
            or self.source_cleanup_confirmed is not True
        ):
            raise ValueError("failed sealed capsule handoff receipt is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("sealed capsule handoff receipt digest mismatch")

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in _target_context_capsule_handoff_consumption_payload(self).items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return {**self.signature_payload(), "integrity_signature": self.integrity_signature}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffResult:
    handoff_id: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    scope: WorkflowScope
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    adapter_contract_id: str
    adapter_contract_version: str
    receipt_digest: str
    state: WorkflowProtectedTransportTargetContextCapsuleHandoffResultState
    failure_class: WorkflowProtectedTransportTargetContextCapsuleHandoffFailureClass | None
    consumer_receipt_id: str | None
    consumer_receipt_is_bearer_capability: bool
    sealed_capsule_handed_off: bool
    completed_at: datetime
    usable_until: datetime | None
    source_cleanup_confirmed: bool
    authority: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.handoff_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.authorization_lease_id,
            self.consumer_binding_id,
            self.consumer_contract_id,
            self.consumer_contract_version,
            self.purpose_id,
            self.policy_id,
            self.policy_version,
            self.adapter_contract_id,
            self.adapter_contract_version,
        ):
            _require_identifier(value, name="sealed capsule handoff result identifier")
        for value in (
            self.attempt_digest,
            self.consumption_claim_digest,
            self.authorization_lease_digest,
            self.consumer_binding_digest,
            self.policy_digest,
            self.receipt_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="sealed capsule handoff result digest")
        policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()  # noqa: E501
        if (
            self.completed_at.tzinfo is None
            or self.consumer_receipt_is_bearer_capability is not False
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.adapter_contract_id != policy.required_adapter_contract_id
            or self.adapter_contract_version != policy.required_adapter_contract_version
            or any(self.authority.canonical_value().values())
        ):
            raise ValueError("sealed capsule handoff result is invalid")
        if (
            self.state
            is WorkflowProtectedTransportTargetContextCapsuleHandoffResultState.HANDED_OFF_SEALED
        ):
            if (
                self.failure_class is not None
                or self.consumer_receipt_id is None
                or self.sealed_capsule_handed_off is not True
                or self.usable_until is None
                or not self.completed_at < self.usable_until
            ):
                raise ValueError("successful sealed capsule handoff result is invalid")
            _require_identifier(self.consumer_receipt_id, name="consumer receipt id")
        elif (
            self.failure_class is None
            or self.consumer_receipt_id is not None
            or self.sealed_capsule_handed_off is not False
            or self.usable_until is not None
            or self.source_cleanup_confirmed is not True
        ):
            raise ValueError("failed sealed capsule handoff result is invalid")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("sealed capsule handoff result digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_consumption_payload(self)

    def canonical_value(self) -> dict[str, object]:
        return {**self.digest_payload(), "canonical_digest": self.canonical_digest}


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState(
    StrEnum
):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority:
    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    target_context_capsule_handoff_authorized: bool = False
    target_context_capsule_opening_authorized: bool = True

    def __post_init__(self) -> None:
        values = self.canonical_value()
        if values["target_context_capsule_opening_authorized"] is not True or any(
            value is not False
            for name, value in values.items()
            if name != "target_context_capsule_opening_authorized"
        ):
            raise ValueError("capsule opening leases grant only opening-request authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "credential_access_authorized": self.credential_access_authorized,
            "credential_assignment_binding_authorized": (
                self.credential_assignment_binding_authorized
            ),
            "credential_brokerage_authorized": self.credential_brokerage_authorized,
            "credential_delivery_authorized": self.credential_delivery_authorized,
            "credential_resolution_authorized": self.credential_resolution_authorized,
            "credential_selection_authorized": self.credential_selection_authorized,
            "delivery_authorized": self.delivery_authorized,
            "dispatch_authorized": self.dispatch_authorized,
            "endpoint_resolution_authorized": self.endpoint_resolution_authorized,
            "execution_authorized": self.execution_authorized,
            "infrastructure_mutation_authorized": self.infrastructure_mutation_authorized,
            "network_access_authorized": self.network_access_authorized,
            "protected_artifact_access_authorized": self.protected_artifact_access_authorized,
            "publication_authorized": self.publication_authorized,
            "readiness_probe_authorized": self.readiness_probe_authorized,
            "route_binding_authorized": self.route_binding_authorized,
            "route_selection_authorized": self.route_selection_authorized,
            "target_context_capsule_handoff_authorized": (
                self.target_context_capsule_handoff_authorized
            ),
            "target_context_capsule_opening_authorized": (
                self.target_context_capsule_opening_authorized
            ),
        }


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationPolicy:
    policy_id: str
    policy_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    required_attestor_id: str
    required_attestor_version: str
    validity_window_seconds: int
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy_values()  # noqa: E501
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("capsule opening authorization policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("capsule opening authorization policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name != "canonical_digest"
        }


def code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy_values() -> (  # noqa: E501
    dict[str, object]
):
    handoff = (
        code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()
    )
    return {
        "policy_id": (
            "policy.workflow-protected-transport-target-context-capsule-opening-authorization"
        ),
        "policy_version": "1.0",
        "consumer_subject_id": handoff.consumer_subject_id,
        "consumer_audience": handoff.consumer_audience,
        "consumer_contract_id": handoff.consumer_contract_id,
        "consumer_contract_version": handoff.consumer_contract_version,
        "purpose_id": (
            "purpose.workflow-protected-transport-target-context-capsule-opening-evaluation"
        ),
        "destination_boundary_id": handoff.destination_boundary_id,
        "destination_deployment_id": handoff.destination_deployment_id,
        "destination_generation": handoff.destination_generation,
        "destination_fencing_token_digest": handoff.destination_fencing_token_digest,
        "custody_contract_id": handoff.custody_contract_id,
        "custody_contract_version": handoff.custody_contract_version,
        "approved_adapter_id": handoff.approved_adapter_id,
        "approved_adapter_version": handoff.approved_adapter_version,
        "verification_signing_key_id": handoff.verification_signing_key_id,
        "trusted_profile_digest": handoff.trusted_profile_digest,
        "required_attestor_id": (
            "attestor.workflow-protected-target-context-capsule-destination-custody"
        ),
        "required_attestor_version": "1.0",
        "validity_window_seconds": 1,
    }


def code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy() -> (  # noqa: E501
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationPolicy
):
    values = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy_values()  # noqa: E501
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    handoff_id: str
    handoff_result_digest: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    consumer_receipt_id: str
    receipt_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    handed_off_sealed: bool
    destination_custody_confirmed: bool
    custody_finality_confirmed: bool
    capsule_remains_sealed: bool
    revoked: bool
    destroyed: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.attestation_id,
            self.attestor_id,
            self.attestor_version,
            self.handoff_id,
            self.attempt_id,
            self.consumption_claim_id,
            self.consumer_binding_id,
            self.sealed_capsule_id,
            self.consumer_receipt_id,
            self.destination_boundary_id,
            self.destination_deployment_id,
            self.custody_contract_id,
            self.custody_contract_version,
            self.approved_adapter_id,
            self.approved_adapter_version,
            self.verification_signing_key_id,
            self.signing_key_id,
            self.signature_algorithm,
        ):
            _require_identifier(value, name="destination custody attestation identifier")
        for value in (
            self.handoff_result_digest,
            self.attempt_digest,
            self.consumption_claim_digest,
            self.consumer_binding_digest,
            self.sealed_capsule_digest,
            self.receipt_digest,
            self.destination_fencing_token_digest,
            self.trusted_profile_digest,
            self.request_nonce_digest,
            self.canonical_digest,
        ):
            _require_digest(value, name="destination custody attestation digest")
        if (
            self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or not self.observed_at < self.valid_until
            or self.handed_off_sealed is not True
            or self.destination_custody_confirmed is not True
            or self.custody_finality_confirmed is not True
            or self.capsule_remains_sealed is not True
            or self.revoked is not False
            or self.destroyed is not False
            or self.destination_generation < 1
            or not self.integrity_signature
            or any(character.isspace() for character in self.integrity_signature)
            or self.canonical_digest != canonical_digest(self.digest_payload())
        ):
            raise ValueError("destination custody attestation is unsafe")

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in _target_context_capsule_handoff_consumption_payload(self).items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return {**self.signature_payload(), "integrity_signature": self.integrity_signature}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
    authorization_lease_id: str
    handoff_id: str
    handoff_result_digest: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    upstream_authorization_lease_id: str
    upstream_authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    consumer_receipt_id: str
    receipt_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    custody_attestation_id: str
    custody_attestation_digest: str
    custody_attestation_valid_until: datetime
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState
    authority: WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
        if (
            any(
                value.tzinfo is None
                for value in (
                    self.custody_attestation_valid_until,
                    self.issued_at,
                    self.valid_until,
                    self.effective_until,
                )
            )
            or self.valid_until - self.issued_at != timedelta(seconds=1)
            or self.valid_until > self.effective_until
            or self.valid_until > self.custody_attestation_valid_until
            or self.single_use is not True
            or self.renewable is not False
            or self.transferable is not False
            or self.lease_is_bearer_capability is not False
            or self.state
            is not (
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            )
            or self.authority
            != WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority()
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.destination_boundary_id != policy.destination_boundary_id
            or self.destination_deployment_id != policy.destination_deployment_id
            or self.destination_generation != policy.destination_generation
            or self.destination_fencing_token_digest != policy.destination_fencing_token_digest
            or self.custody_contract_id != policy.custody_contract_id
            or self.custody_contract_version != policy.custody_contract_version
            or self.approved_adapter_id != policy.approved_adapter_id
            or self.approved_adapter_version != policy.approved_adapter_version
            or self.verification_signing_key_id != policy.verification_signing_key_id
            or self.trusted_profile_digest != policy.trusted_profile_digest
            or self.canonical_digest != canonical_digest(self.digest_payload())
        ):
            raise ValueError("target context capsule opening authorization lease is invalid")

    def digest_payload(self) -> dict[str, object]:
        return _target_context_capsule_handoff_consumption_payload(self)

    def effective_state(
        self, *, evaluated_at: datetime
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState:
        if evaluated_at.tzinfo is None:
            raise ValueError("capsule opening lease evaluation time must be aware")
        if self.issued_at <= evaluated_at < self.valid_until:
            return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState.ACTIVE  # noqa: E501
        return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseEffectiveState.EXPIRED  # noqa: E501
