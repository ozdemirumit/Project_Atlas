from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult,
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus(StrEnum):
    NONE = "none"
    TERMINAL = "terminal"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_CONSUMED = "already_consumed"


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus(StrEnum):
    CONSUMED = "consumed"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_CONSUMED = "already_consumed"
    LEASE_EXPIRED = "lease_expired"
    SOURCE_NOT_FOUND = "source_not_found"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest:
    authorization_lease_id: str
    consumption_id: str
    consumption_claim_id: str
    result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    source_policy_id: str
    source_policy_version: str
    source_policy_digest: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup:
    status: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus
    claim: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim | None = None
    result: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest:
    authorization_lease_id: str
    consumption_id: str
    consumption_claim_id: str
    result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    source_policy_id: str
    source_policy_version: str
    source_policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    consumption_audit_payload: dict[str, object]
    consumption_audit_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite:
    status: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus
    claim: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim | None = None
    result: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
    claim: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim
    result: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult

    def __post_init__(self) -> None:
        terminal_state = type(self.result.state).AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE
        if (
            self.result.state is not terminal_state
            or self.result.consumption_id != self.claim.consumption_id
            or self.result.consumption_claim_id != self.claim.consumption_claim_id
            or self.result.consumption_claim_digest != self.claim.canonical_digest
            or self.result.authorization_lease_id != self.claim.authorization_lease_id
            or self.result.authorization_lease_digest != self.claim.authorization_lease_digest
            or self.result.scope != self.claim.scope
            or self.result.consumer_subject_id != self.claim.consumer_subject_id
            or self.result.consumer_audience != self.claim.consumer_audience
            or self.result.policy_digest != self.claim.policy_digest
            or self.result.source_policy_digest != self.claim.source_policy_digest
            or self.result.consumed_at != self.claim.claimed_at
        ):
            raise ValueError("runtime context use consumption presentation is inconsistent")


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def lookup_protected_runtime_context_use_authorization_consumption_replay(
        self,
        request: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup: ...

    async def consume_protected_runtime_context_use_authorization(
        self, request: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite:
        """Lock, re-time, revalidate and atomically append terminal claim plus result."""

    async def list_protected_runtime_context_use_authorization_consumption_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation, ...]: ...


def validate_workflow_protected_runtime_context_use_authorization_consumption_request(
    request: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest,
) -> None:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
    expected_audit_payload: dict[str, object] = {
        "schema_id": ("audit.workflow-protected-runtime-context-use-authorization-consumption"),
        "schema_version": "1.0",
        "event_type": ("protected_runtime_context_use_authorization_consumed_without_runtime_use"),
        "consumption_id": request.consumption_id,
        "consumption_claim_id": request.consumption_claim_id,
        "result_id": request.result_id,
        "authorization_lease_id": request.authorization_lease_id,
        "scope": request.scope.canonical_value(),
        "consumer_subject_id": request.consumer_subject_id,
        "consumer_audience": request.consumer_audience,
        "policy_id": request.policy_id,
        "policy_version": request.policy_version,
        "policy_digest": request.policy_digest,
        "source_policy_id": request.source_policy_id,
        "source_policy_version": request.source_policy_version,
        "source_policy_digest": request.source_policy_digest,
        "idempotency_digest": request.idempotency_digest,
        "request_fingerprint": request.request_fingerprint,
        "irreversible_consumption_acknowledged": True,
        "context_accessed": False,
        "context_used": False,
        "runtime_started": False,
        "runtime_resumed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
    }
    expected_audit_digest = canonical_digest(expected_audit_payload)
    identifiers = (
        request.authorization_lease_id,
        request.consumption_id,
        request.consumption_claim_id,
        request.result_id,
    )
    digests = (
        request.policy_digest,
        request.source_policy_digest,
        request.idempotency_digest,
        request.request_fingerprint,
        request.consumption_audit_digest,
    )
    if (
        request.consumer_subject_id != policy.consumer_subject_id
        or request.consumer_audience != policy.consumer_audience
        or request.consumer_contract_id != policy.consumer_contract_id
        or request.consumer_contract_version != policy.consumer_contract_version
        or request.purpose_id != policy.purpose_id
        or request.policy_id != policy.policy_id
        or request.policy_version != policy.policy_version
        or request.policy_digest != policy.canonical_digest
        or request.source_policy_id != policy.source_policy_id
        or request.source_policy_version != policy.source_policy_version
        or request.source_policy_digest != policy.source_policy_digest
        or request.irreversible_consumption_acknowledged is not True
        or request.consumption_audit_payload != expected_audit_payload
        or request.consumption_audit_digest != expected_audit_digest
        or any(
            not value
            or value != value.strip()
            or len(value) > 240
            or any(character.isspace() for character in value)
            for value in identifiers
        )
        or any(
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            for value in digests
        )
    ):
        raise WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError(
            "protected_runtime_context_use_authorization_consumption_request_invalid"
        )


__all__ = [
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRepository",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus",
    "validate_workflow_protected_runtime_context_use_authorization_consumption_request",
]
