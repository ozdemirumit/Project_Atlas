"""docs/050_API.md SS15/SS19/SS20: the operation resource itself.

`OperationResource` is the durable record a `202` response points at: real identity (who owns it,
what triggered it, what workflow run it belongs to), real lifecycle timestamps, a real current-step
description (not a fabricated percent-complete signal -- this codebase's real long-running work has
no meaningful progress fraction to report), and real terminal-state evidence (a result, a partial
result, or an error, plus any supporting evidence references). `__post_init__` enforces the state
machine directly on the dataclass, mirroring `bootstrap_end_to_end_verification.py`'s rigor: every
state has an exact, checked set of fields it is allowed -- and required -- to carry.

Only the Atlas-assigned identifiers (`operation_id`, `operation_type`, `owner_subject_id`,
`organization_id`, `environment_id`, `correlation_id`) go through `validate_stable_identifier`.
The reference fields (`input_artifact_reference`, `workflow_run_reference`, `result_reference`,
`partial_result_reference`, `error_reference`, `evidence_references`,
`required_human_task_reference`) point at whatever triggered or resulted from the operation, which
this generic framework cannot assume is always an Atlas stable identifier -- a future operation
type could reasonably reference an external system's own identifier shape. Those fields instead
get a real, non-stable-identifier bound: non-empty, printable, length-bounded text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_MAX_TEXT_LENGTH = 500
_MAX_REFERENCE_LENGTH = 200


class OperationState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


#: SS20: cancellation eligibility is structurally impossible once an operation has genuinely
#: finished. `PARTIAL`, `WAITING`, and `UNKNOWN` are deliberately excluded -- they describe an
#: operation that may still be actionable (a partial result awaiting a decision, a wait for an
#: external condition, or a state this framework cannot presently characterize), not a closed one.
TERMINAL_STATES = frozenset(
    {
        OperationState.SUCCEEDED,
        OperationState.FAILED,
        OperationState.CANCELLED,
        OperationState.TIMED_OUT,
    }
)


def _require_bounded_text(value: str, field_name: str, *, maximum: int) -> None:
    if not value.strip() or len(value) > maximum or any(ord(character) < 32 for character in value):
        raise ValueError(f"operation resource {field_name} is invalid")


def _require_optional_reference(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_bounded_text(value, field_name, maximum=_MAX_REFERENCE_LENGTH)


@dataclass(frozen=True, slots=True)
class OperationResource:
    operation_id: str
    operation_type: str
    owner_subject_id: str
    organization_id: str
    environment_id: str
    state: OperationState
    progress_summary: str
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    deadline_at: datetime | None
    expires_at: datetime | None
    input_artifact_reference: str
    workflow_run_reference: str | None
    correlation_id: str
    current_step: str
    result_reference: str | None
    partial_result_reference: str | None
    error_reference: str | None
    evidence_references: tuple[str, ...]
    cancellation_eligible: bool
    cancellation_reason: str | None
    required_human_task_reference: str | None

    def __post_init__(self) -> None:
        for value, label in (
            (self.operation_id, "operation id"),
            (self.operation_type, "operation type"),
            (self.owner_subject_id, "owner subject id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.correlation_id, "correlation id"),
        ):
            validate_stable_identifier(value, label)

        _require_bounded_text(self.progress_summary, "progress summary", maximum=_MAX_TEXT_LENGTH)
        _require_bounded_text(self.current_step, "current step", maximum=_MAX_TEXT_LENGTH)
        _require_bounded_text(
            self.input_artifact_reference,
            "input artifact reference",
            maximum=_MAX_REFERENCE_LENGTH,
        )
        _require_optional_reference(self.workflow_run_reference, "workflow run reference")
        _require_optional_reference(self.result_reference, "result reference")
        _require_optional_reference(self.partial_result_reference, "partial result reference")
        _require_optional_reference(self.error_reference, "error reference")
        _require_optional_reference(
            self.required_human_task_reference, "required human task reference"
        )
        for reference in self.evidence_references:
            _require_bounded_text(reference, "evidence reference", maximum=_MAX_REFERENCE_LENGTH)
        if len(self.evidence_references) != len(set(self.evidence_references)):
            raise ValueError("operation resource evidence references must be distinct")

        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("operation resource creation and update times must be timezone-aware")
        if self.started_at is not None and self.started_at.tzinfo is None:
            raise ValueError("operation resource start time must be timezone-aware")
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            raise ValueError("operation resource deadline must be timezone-aware")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("operation resource expiry must be timezone-aware")

        if self.updated_at < self.created_at:
            raise ValueError("an operation resource cannot be updated before it is created")
        if self.started_at is not None and not (
            self.created_at <= self.started_at <= self.updated_at
        ):
            raise ValueError("an operation resource's start time is inconsistent")
        if self.deadline_at is not None and self.deadline_at <= self.created_at:
            raise ValueError("an operation resource's deadline must be after its creation")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("an operation resource's expiry must be after its creation")

        if self.state is OperationState.SUCCEEDED:
            if self.result_reference is None:
                raise ValueError("a succeeded operation resource requires a result reference")
        elif self.result_reference is not None:
            raise ValueError("only a succeeded operation resource may carry a result reference")

        if self.state is OperationState.PARTIAL:
            if self.partial_result_reference is None:
                raise ValueError("a partial operation resource requires a partial result reference")
        elif self.partial_result_reference is not None:
            raise ValueError(
                "only a partial operation resource may carry a partial result reference"
            )

        if self.state is OperationState.FAILED and self.error_reference is None:
            raise ValueError("a failed operation resource requires an error reference")
        if self.error_reference is not None and self.state not in (
            OperationState.FAILED,
            OperationState.TIMED_OUT,
        ):
            raise ValueError(
                "only a failed or timed-out operation resource may carry an error reference"
            )

        if self.state is OperationState.CANCELLED:
            if self.cancellation_reason is None or not self.cancellation_reason.strip():
                raise ValueError("a cancelled operation resource requires a cancellation reason")
        elif self.cancellation_reason is not None:
            raise ValueError("only a cancelled operation resource may carry a cancellation reason")

        if self.state in TERMINAL_STATES and self.cancellation_eligible:
            raise ValueError("a terminal operation resource cannot remain cancellation-eligible")

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES
