from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationClaim,
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedResidentContextAccessAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessAuthorizationSource:
    """Canonical ADR-165 success lineage; no resident material or runtime locator."""

    result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult
    attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt
    consumption_claim: WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim
    authorization_lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease
    opening_receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt
    protected_resident_context_id: str
    protected_resident_context_digest: str
    protected_resident_context_created_at: datetime
    protected_resident_context_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    opening_receipt_digest: str
    opening_receipt_signing_key_id: str
    opening_receipt_signature_algorithm: str
    opening_receipt_integrity_signature: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextLifecycleAttestationRequest:
    opening_id: str
    opening_result_digest: str
    opening_attempt_id: str
    opening_attempt_digest: str
    opening_consumption_claim_id: str
    opening_consumption_claim_digest: str
    opening_authorization_lease_id: str
    opening_authorization_lease_digest: str
    opening_receipt_digest: str
    opening_receipt_signing_key_id: str
    protected_resident_context_id: str
    protected_resident_context_digest: str
    protected_resident_context_created_at: datetime
    protected_resident_context_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    opening_id: str
    opening_result_digest: str
    opening_attempt_id: str
    opening_attempt_digest: str
    opening_consumption_claim_id: str
    opening_consumption_claim_digest: str
    opening_authorization_lease_id: str
    opening_authorization_lease_digest: str
    opening_receipt_digest: str
    opening_receipt_signing_key_id: str
    protected_resident_context_id: str
    protected_resident_context_digest: str
    protected_resident_context_created_at: datetime
    protected_resident_context_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    resident_context_present: bool
    resident_context_is_bearer_capability: bool
    resident_context_unexpired: bool
    resident_context_unrevoked: bool
    resident_context_undestroyed: bool
    resident_context_unconsumed: bool
    resident_context_handle_outstanding: bool
    raw_context_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    bearer_token_included: bool
    locator_included: bool
    provider_payload_included: bool
    runtime_handle_creation_authorized: bool
    network_activity_authorized: bool
    execution_authorized: bool
    infrastructure_mutation_authorized: bool
    integrity_signature: str
    canonical_digest: str

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _canonical_payload(self, exclude=("canonical_digest",))


class WorkflowProtectedResidentContextLifecycleAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_resident_context_lifecycle(
        self, request: WorkflowProtectedResidentContextLifecycleAttestationRequest
    ) -> WorkflowProtectedResidentContextLifecycleAttestation: ...


class WorkflowProtectedResidentContextLifecycleSignatureVerifier(Protocol):
    def verify_lifecycle_attestation(
        self, attestation: WorkflowProtectedResidentContextLifecycleAttestation
    ) -> bool: ...


class WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier(Protocol):
    def verify_opening_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest:
    opening_id: str
    opening_result_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessAuthorizationPreflightResult:
    status: WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus
    lease: WorkflowProtectedResidentContextAccessAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessAuthorizationLeaseRequest:
    source: WorkflowProtectedResidentContextAccessAuthorizationSource
    lifecycle_attestation: WorkflowProtectedResidentContextLifecycleAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedResidentContextLifecycleSignatureVerifier
    offline_opening_receipt_signature_verifier: (
        WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    requested_at: datetime
    candidate_claim: WorkflowProtectedResidentContextAccessAuthorizationClaim
    candidate: WorkflowProtectedResidentContextAccessAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessAuthorizationLeaseResult:
    status: WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus
    lease: WorkflowProtectedResidentContextAccessAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessAuthorizationPresentation:
    lease: WorkflowProtectedResidentContextAccessAuthorizationLease
    consumed: bool
    evaluated_at: datetime


class WorkflowProtectedResidentContextAccessAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_resident_context_access_authorization(
        self, request: WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest
    ) -> WorkflowProtectedResidentContextAccessAuthorizationPreflightResult: ...

    async def get_protected_resident_context_access_authorization_source(
        self, *, opening_id: str
    ) -> WorkflowProtectedResidentContextAccessAuthorizationSource | None: ...

    async def authorize_protected_resident_context_access(
        self, request: WorkflowProtectedResidentContextAccessAuthorizationLeaseRequest
    ) -> WorkflowProtectedResidentContextAccessAuthorizationLeaseResult: ...

    async def list_protected_resident_context_access_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedResidentContextAccessAuthorizationPresentation, ...]: ...


def validate_workflow_protected_resident_context_access_authorization_request(
    request: WorkflowProtectedResidentContextAccessAuthorizationLeaseRequest,
) -> None:
    source = request.source
    attestation = request.lifecycle_attestation
    candidate = request.candidate
    if (
        request.expected_validity_window_seconds != 1
        or len(request.expected_policy_digest) != 64
        or any(c not in "0123456789abcdef" for c in request.expected_policy_digest)
        or request.expected_policy_digest != candidate.policy_digest
        or request.scope != source.result.scope
        or request.consumer_subject_id != source.consumer_subject_id
        or request.consumer_audience != source.consumer_audience
        or request.expected_request_nonce_digest != attestation.request_nonce_digest
        or attestation.opening_id != source.result.opening_id
        or attestation.opening_result_digest != source.result.canonical_digest
        or attestation.opening_attempt_id != source.attempt.attempt_id
        or attestation.opening_attempt_digest != source.attempt.canonical_digest
        or attestation.opening_consumption_claim_id != source.consumption_claim.claim_id
        or attestation.opening_consumption_claim_digest != source.consumption_claim.canonical_digest
        or attestation.opening_authorization_lease_id
        != source.authorization_lease.authorization_lease_id
        or attestation.opening_authorization_lease_digest
        != source.authorization_lease.canonical_digest
        or attestation.opening_receipt_digest != source.opening_receipt_digest
        or attestation.protected_resident_context_id != source.protected_resident_context_id
        or attestation.protected_resident_context_digest != source.protected_resident_context_digest
        or attestation.protected_resident_context_created_at
        != source.protected_resident_context_created_at
        or attestation.protected_resident_context_usable_until
        != source.protected_resident_context_usable_until
        or attestation.destination_boundary_id != source.destination_boundary_id
        or attestation.destination_deployment_id != source.destination_deployment_id
        or attestation.destination_generation != source.destination_generation
        or attestation.destination_fencing_token_digest != source.destination_fencing_token_digest
        or attestation.scope != request.scope
        or attestation.consumer_subject_id != request.consumer_subject_id
        or attestation.consumer_audience != request.consumer_audience
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_lifecycle_attestation(attestation)
        or not request.offline_opening_receipt_signature_verifier.verify_opening_receipt(
            source.opening_receipt
        )
        or candidate.opening_id != source.result.opening_id
        or candidate.opening_result_digest != source.result.canonical_digest
        or candidate.protected_resident_context_id != source.protected_resident_context_id
        or candidate.protected_resident_context_digest != source.protected_resident_context_digest
        or canonical_digest(candidate.digest_payload()) != candidate.canonical_digest
        or canonical_digest(request.candidate_claim.digest_payload())
        != request.candidate_claim.canonical_digest
    ):
        raise ValueError("resident context access authorization evidence is invalid")


def _canonical_payload(value: Any, *, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        field.name: _canonical_value(getattr(value, field.name))
        for field in fields(value)
        if field.name not in exclude
    }


def _canonical_value(value: Any) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


__all__ = [
    "WorkflowProtectedResidentContextAccessAuthorizationError",
    "WorkflowProtectedResidentContextAccessAuthorizationLeaseRequest",
    "WorkflowProtectedResidentContextAccessAuthorizationLeaseResult",
    "WorkflowProtectedResidentContextAccessAuthorizationLeaseStatus",
    "WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest",
    "WorkflowProtectedResidentContextAccessAuthorizationPreflightResult",
    "WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus",
    "WorkflowProtectedResidentContextAccessAuthorizationRepository",
    "WorkflowProtectedResidentContextAccessAuthorizationSource",
    "WorkflowProtectedResidentContextLifecycleAttestation",
    "WorkflowProtectedResidentContextLifecycleAttestationRequest",
    "WorkflowProtectedResidentContextLifecycleAttestor",
    "WorkflowProtectedResidentContextLifecycleSignatureVerifier",
    "WorkflowProtectedResidentContextOpeningReceiptSignatureVerifier",
    "validate_workflow_protected_resident_context_access_authorization_request",
]
