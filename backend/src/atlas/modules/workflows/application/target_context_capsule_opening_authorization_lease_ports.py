from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource:
    result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult
    attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt
    consumption_claim: WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim
    upstream_authorization_lease: (
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease
    )
    consumer_binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest:
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
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    destination_custody_final: bool
    source_reuse_authority_terminated: bool
    consumer_receipt_is_bearer_capability: bool
    sealed_capsule_is_bearer_capability: bool
    runtime_authority_granted: bool
    runtime_authority_count: int
    request_nonce_digest: str
    requested_at: datetime


class WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_destination_custody(
        self,
        request: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
    ) -> WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation: ...


class WorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier(Protocol):
    def verify_destination_custody_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest:
    source: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource
    custody_attestation: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: (
        WorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    requested_at: datetime
    candidate: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResult:
    status: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus
    lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease | None
    evaluated_at: datetime | None = None


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_target_context_capsule_opening_authorization_source(
        self, *, handoff_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource | None: ...

    async def authorize_target_context_capsule_opening(
        self,
        request: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResult: ...

    async def list_target_context_capsule_opening_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease, ...]: ...


def validate_workflow_protected_transport_target_context_capsule_opening_authorization_request(
    request: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest,
) -> None:
    source = request.source
    result = source.result
    attempt = source.attempt
    claim = source.consumption_claim
    upstream = source.upstream_authorization_lease
    binding = source.consumer_binding
    attestation = request.custody_attestation
    candidate = request.candidate
    authority = candidate.authority.canonical_value()
    if (
        candidate.handoff_id != result.handoff_id
        or attestation.handoff_id != result.handoff_id
        or candidate.handoff_result_digest != result.canonical_digest
        or attestation.handoff_result_digest != result.canonical_digest
        or result.attempt_id != attempt.attempt_id
        or result.attempt_digest != attempt.canonical_digest
        or result.consumption_claim_id != claim.claim_id
        or result.consumption_claim_digest != claim.canonical_digest
        or result.authorization_lease_id != upstream.authorization_lease_id
        or result.authorization_lease_digest != upstream.canonical_digest
        or result.consumer_binding_id != binding.binding_id
        or result.consumer_binding_digest != binding.canonical_digest
        or candidate.consumer_receipt_id != result.consumer_receipt_id
        or candidate.receipt_digest != result.receipt_digest
        or candidate.sealed_capsule_id != attempt.sealed_capsule_id
        or candidate.sealed_capsule_digest != attempt.sealed_capsule_digest
        or candidate.scope != request.scope
        or result.scope != request.scope
        or candidate.consumer_subject_id != request.consumer_subject_id
        or candidate.consumer_audience != request.consumer_audience
        or candidate.consumer_contract_id != attestation.consumer_contract_id
        or candidate.consumer_contract_version != attestation.consumer_contract_version
        or candidate.purpose_id != attestation.purpose_id
        or attestation.scope != request.scope
        or attestation.consumer_subject_id != request.consumer_subject_id
        or attestation.consumer_audience != request.consumer_audience
        or attestation.consumer_contract_id != candidate.consumer_contract_id
        or attestation.consumer_contract_version != candidate.consumer_contract_version
        or attestation.purpose_id != candidate.purpose_id
        or attestation.destination_custody_final is not True
        or attestation.source_reuse_authority_terminated is not True
        or attestation.consumer_receipt_is_bearer_capability is not False
        or attestation.sealed_capsule_is_bearer_capability is not False
        or attestation.runtime_authority_granted is not False
        or attestation.runtime_authority_count != 0
        or candidate.policy_digest != request.expected_policy_digest
        or candidate.issued_at != request.requested_at
        or candidate.valid_until - candidate.issued_at
        != timedelta(seconds=request.expected_validity_window_seconds)
        or candidate.custody_attestation_id != attestation.attestation_id
        or candidate.custody_attestation_digest != attestation.canonical_digest
        or candidate.custody_attestation_valid_until != attestation.valid_until
        or attestation.request_nonce_digest != request.expected_request_nonce_digest
        or canonical_digest(attestation.digest_payload()) != attestation.canonical_digest
        or authority.get("target_context_capsule_opening_authorized") is not True
        or any(
            value is not False
            for name, value in authority.items()
            if name != "target_context_capsule_opening_authorized"
        )
    ):
        raise ValueError("target context capsule opening authorization payload is unsafe")
    if (
        request.offline_signature_verifier.verify_destination_custody_attestation(attestation)
        is not True
    ):
        raise ValueError("destination custody attestation signature is invalid")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("capsule opening authorization idempotency key is invalid")
    if request.requested_at.tzinfo is None:
        raise ValueError("capsule opening authorization request time must be aware")


__all__ = [
    name for name in globals() if name.startswith("Workflow") or name.startswith("validate_")
]
