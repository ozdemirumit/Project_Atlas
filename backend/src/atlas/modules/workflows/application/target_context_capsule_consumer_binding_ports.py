from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowScope,
)


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowTargetContextCapsuleConsumerBindingStatus(StrEnum):
    BOUND = "bound"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_BOUND = "already_bound"


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleConsumerBindingRequest:
    """Minimal caller evidence plus code-owned expectations for one atomic bind."""

    opening_result_id: str
    opening_result_digest: str
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_consumer_subject_id: str
    expected_consumer_audience: str
    expected_consumer_contract_id: str
    expected_consumer_contract_version: str
    expected_purpose_id: str
    minimum_remaining_lifetime_seconds: int
    scope: WorkflowScope
    binder_subject_id: str
    binder_audience: str
    requested_at: datetime
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleConsumerBindingResult:
    status: WorkflowTargetContextCapsuleConsumerBindingStatus
    binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None


class WorkflowTargetContextCapsuleConsumerBindingRepository(Protocol):
    """Owns replay-first lookup, fixed-order locks and the append-only transaction."""

    @property
    def durable(self) -> bool: ...

    async def bind_target_context_capsule_consumer(
        self, request: WorkflowTargetContextCapsuleConsumerBindingRequest
    ) -> WorkflowTargetContextCapsuleConsumerBindingResult:
        """Replay or atomically validate and append one zero-authority binding."""
        ...

    async def list_target_context_capsule_consumer_bindings(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleConsumerBinding, ...]: ...


def validate_workflow_target_context_capsule_consumer_binding_request(
    request: WorkflowTargetContextCapsuleConsumerBindingRequest,
) -> None:
    identifiers = (
        request.opening_result_id,
        request.expected_policy_id,
        request.expected_policy_version,
        request.expected_consumer_subject_id,
        request.expected_consumer_audience,
        request.expected_consumer_contract_id,
        request.expected_consumer_contract_version,
        request.expected_purpose_id,
        request.binder_subject_id,
        request.binder_audience,
        request.idempotency_key,
    )
    if any(
        not value
        or value != value.strip()
        or len(value) > 240
        or any(character.isspace() for character in value)
        for value in identifiers
    ):
        raise ValueError("target context capsule consumer binding request identifier is invalid")
    if (
        request.expected_policy_id
        != "policy.workflow-protected-transport-target-context-capsule-consumer-binding"
        or request.expected_policy_version != "1.0"
        or request.expected_consumer_subject_id
        != "service.workflow-protected-transport-target-context-capsule-consumer"
        or request.expected_consumer_audience
        != "audience.workflow-protected-transport-target-context-capsule-consumer"
        or request.expected_consumer_contract_id
        != "contract.workflow-protected-transport-target-context-capsule-consumer"
        or request.expected_consumer_contract_version != "1.0"
        or request.expected_purpose_id
        != "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
        or request.binder_subject_id
        != "service.workflow-protected-transport-target-context-capsule-binder"
        or request.binder_audience
        != "audience.workflow-protected-transport-target-context-capsule-binder"
        or request.minimum_remaining_lifetime_seconds != 1
        or request.requested_at.tzinfo is None
        or not 8 <= len(request.idempotency_key) <= 128
    ):
        raise ValueError("target context capsule consumer binding request is unsafe")
    for value in (
        request.opening_result_digest,
        request.expected_policy_digest,
        request.idempotency_digest,
        request.request_fingerprint,
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("target context capsule consumer binding request digest is invalid")


__all__ = [
    "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError",
    "WorkflowTargetContextCapsuleConsumerBindingRepository",
    "WorkflowTargetContextCapsuleConsumerBindingRequest",
    "WorkflowTargetContextCapsuleConsumerBindingResult",
    "WorkflowTargetContextCapsuleConsumerBindingStatus",
    "validate_workflow_target_context_capsule_consumer_binding_request",
]
