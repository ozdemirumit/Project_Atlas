from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedTransportTargetContextCapsuleOpeningError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


class WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus(StrEnum):
    NONE = "none"
    TERMINAL = "terminal"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"


class WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleOpeningSource:
    lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease
    capsule_schema_id: str
    capsule_schema_version: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    handoff_id: str
    handoff_result_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    consumer_receipt_id: str
    consumer_receipt_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    authorization_lease_id: str
    authorization_lease_digest: str
    handoff_id: str
    handoff_result_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    consumer_receipt_id: str
    consumer_receipt_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    capsule_remains_sealed: bool
    destination_custody_final: bool
    source_reuse_authority_terminated: bool
    sealed_capsule_is_bearer_capability: bool
    consumer_receipt_is_bearer_capability: bool
    runtime_authority_granted: bool
    runtime_authority_count: int
    revoked: bool
    destroyed: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    consumer_receipt_id: str
    consumer_receipt_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
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
    opener_contract_id: str
    opener_contract_version: str
    opener_id: str
    opener_version: str
    verification_signing_key_id: str
    trusted_opener_profile_digest: str
    scope: WorkflowScope
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleOpenabilityAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    authorization_lease_id: str
    authorization_lease_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    consumer_receipt_id: str
    consumer_receipt_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
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
    opener_contract_id: str
    opener_contract_version: str
    opener_id: str
    opener_version: str
    verification_signing_key_id: str
    trusted_opener_profile_digest: str
    scope: WorkflowScope
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    acceptance_eligible: bool
    capsule_openable: bool
    exact_capsule_binding_confirmed: bool
    protected_destination_confirmed: bool
    protected_resident_context_profile_confirmed: bool
    sealed_capsule_is_bearer_capability: bool
    consumer_receipt_is_bearer_capability: bool
    raw_material_return_authorized: bool
    runtime_handle_creation_authorized: bool
    network_activity_authorized: bool
    delivery_authorized: bool
    execution_authorized: bool
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


class WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_opening_custody(
        self, request: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation: ...


class WorkflowProtectedTargetContextCapsuleOpenabilityAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_capsule_openability(
        self, request: WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleOpenabilityAttestation: ...


class WorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier(Protocol):
    def verify_opening_custody_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation
    ) -> bool: ...

    def verify_capsule_openability_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleOpenabilityAttestation
    ) -> bool: ...


class WorkflowProtectedTargetContextCapsuleTrustedOpener(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def opener_contract_id(self) -> str: ...

    @property
    def opener_contract_version(self) -> str: ...

    @property
    def opener_id(self) -> str: ...

    @property
    def opener_version(self) -> str: ...

    async def open_capsule(
        self, instruction: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction
    ) -> WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt: ...

    def verify_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleOpeningReplayLookupRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    opening_id: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleOpeningReplayLookup:
    status: WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus
    attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt | None
    result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleOpeningClaimRequest:
    claim_id: str
    attempt_id: str
    opening_id: str
    source: WorkflowProtectedTransportTargetContextCapsuleOpeningSource
    custody_attestation: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation
    openability_attestation: WorkflowProtectedTargetContextCapsuleOpenabilityAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: (
        WorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_custody_attestor_id: str
    expected_custody_attestor_version: str
    expected_openability_attestor_id: str
    expected_openability_attestor_version: str
    expected_opener_contract_id: str
    expected_opener_contract_version: str
    expected_opener_id: str
    expected_opener_version: str
    expected_trusted_opener_profile_digest: str
    expected_verification_signing_key_id: str
    minimum_remaining_budget_milliseconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    consumption_authorization_audit_payload: dict[str, object]
    consumption_authorization_audit_digest: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleOpeningClaimResult:
    status: WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus
    claim: WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim | None
    attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt | None
    result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleOpeningResultRequest:
    result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult
    receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleOpeningResultWrite:
    status: WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus
    result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None


class WorkflowTargetContextCapsuleOpeningRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_target_context_capsule_opening_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningSource | None: ...

    async def lookup_target_context_capsule_opening_replay(
        self, request: WorkflowTargetContextCapsuleOpeningReplayLookupRequest
    ) -> WorkflowTargetContextCapsuleOpeningReplayLookup: ...

    async def claim_target_context_capsule_opening(
        self, request: WorkflowTargetContextCapsuleOpeningClaimRequest
    ) -> WorkflowTargetContextCapsuleOpeningClaimResult: ...

    async def record_target_context_capsule_opening_result(
        self, request: WorkflowTargetContextCapsuleOpeningResultRequest
    ) -> WorkflowTargetContextCapsuleOpeningResultWrite: ...

    async def list_target_context_capsule_opening_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt, ...]: ...

    async def get_target_context_capsule_opening_results_by_opening_ids(
        self, *, scope: WorkflowScope, opening_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningResult, ...]: ...


def validate_workflow_target_context_capsule_opening_claim_request(
    request: WorkflowTargetContextCapsuleOpeningClaimRequest,
) -> None:
    source = request.source
    lease = source.lease
    custody = request.custody_attestation
    openability = request.openability_attestation
    audit_payload: dict[str, object] = {
        "schema_id": "audit.workflow-target-context-capsule-opening-consumption-authorization",
        "schema_version": "1.0",
        "event_type": "target_context_capsule_opening_lease_consumption_authorized",
        "claim_id": request.claim_id,
        "attempt_id": request.attempt_id,
        "opening_id": request.opening_id,
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "scope": request.scope.canonical_value(),
        "consumer_subject_id": request.consumer_subject_id,
        "consumer_audience": request.consumer_audience,
        "policy_id": request.expected_policy_id,
        "policy_version": request.expected_policy_version,
        "policy_digest": request.expected_policy_digest,
        "idempotency_digest": request.idempotency_digest,
        "request_fingerprint": request.request_fingerprint,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
    }
    exact = (
        custody.authorization_lease_id == lease.authorization_lease_id
        and custody.authorization_lease_digest == lease.canonical_digest
        and openability.authorization_lease_id == lease.authorization_lease_id
        and openability.authorization_lease_digest == lease.canonical_digest
        and custody.handoff_id == lease.handoff_id
        and custody.handoff_result_digest == lease.handoff_result_digest
        and custody.sealed_capsule_id == lease.sealed_capsule_id
        and custody.sealed_capsule_digest == lease.sealed_capsule_digest
        and custody.consumer_receipt_id == lease.consumer_receipt_id
        and custody.consumer_receipt_digest == lease.receipt_digest
        and openability.sealed_capsule_id == lease.sealed_capsule_id
        and openability.sealed_capsule_digest == lease.sealed_capsule_digest
        and openability.consumer_receipt_id == lease.consumer_receipt_id
        and openability.consumer_receipt_digest == lease.receipt_digest
        and openability.capsule_schema_id == source.capsule_schema_id
        and openability.capsule_schema_version == source.capsule_schema_version
        and custody.scope == request.scope == lease.scope == openability.scope
        and custody.consumer_subject_id == request.consumer_subject_id
        and openability.consumer_subject_id == request.consumer_subject_id
        and custody.consumer_audience == request.consumer_audience
        and openability.consumer_audience == request.consumer_audience
        and custody.consumer_contract_id == lease.consumer_contract_id
        and openability.consumer_contract_id == lease.consumer_contract_id
        and custody.consumer_contract_version == lease.consumer_contract_version
        and openability.consumer_contract_version == lease.consumer_contract_version
        and custody.purpose_id == lease.purpose_id == openability.purpose_id
        and custody.request_nonce_digest == request.expected_request_nonce_digest
        and openability.request_nonce_digest == request.expected_request_nonce_digest
        and custody.destination_boundary_id == lease.destination_boundary_id
        and openability.destination_boundary_id == lease.destination_boundary_id
        and custody.destination_deployment_id == lease.destination_deployment_id
        and openability.destination_deployment_id == lease.destination_deployment_id
        and custody.destination_generation == lease.destination_generation
        and openability.destination_generation == lease.destination_generation
        and custody.destination_fencing_token_digest == lease.destination_fencing_token_digest
        and openability.destination_fencing_token_digest == lease.destination_fencing_token_digest
        and custody.custody_contract_id == lease.custody_contract_id
        and openability.custody_contract_id == lease.custody_contract_id
        and custody.custody_contract_version == lease.custody_contract_version
        and openability.custody_contract_version == lease.custody_contract_version
        and openability.opener_contract_id == request.expected_opener_contract_id
        and openability.opener_contract_version == request.expected_opener_contract_version
        and openability.opener_id == request.expected_opener_id
        and openability.opener_version == request.expected_opener_version
        and openability.trusted_opener_profile_digest
        == request.expected_trusted_opener_profile_digest
        and openability.verification_signing_key_id == request.expected_verification_signing_key_id
        and custody.attestor_id == request.expected_custody_attestor_id
        and custody.attestor_version == request.expected_custody_attestor_version
        and openability.attestor_id == request.expected_openability_attestor_id
        and openability.attestor_version == request.expected_openability_attestor_version
    )
    safe = (
        request.irreversible_consumption_acknowledged is True
        and request.uncertain_outcome_requires_new_authorization_acknowledged is True
        and custody.capsule_remains_sealed is True
        and custody.destination_custody_final is True
        and custody.source_reuse_authority_terminated is True
        and custody.sealed_capsule_is_bearer_capability is False
        and custody.consumer_receipt_is_bearer_capability is False
        and custody.runtime_authority_granted is False
        and custody.runtime_authority_count == 0
        and custody.revoked is False
        and custody.destroyed is False
        and openability.acceptance_eligible is True
        and openability.capsule_openable is True
        and openability.exact_capsule_binding_confirmed is True
        and openability.protected_destination_confirmed is True
        and openability.protected_resident_context_profile_confirmed is True
        and openability.sealed_capsule_is_bearer_capability is False
        and openability.consumer_receipt_is_bearer_capability is False
        and openability.raw_material_return_authorized is False
        and openability.runtime_handle_creation_authorized is False
        and openability.network_activity_authorized is False
        and openability.delivery_authorized is False
        and openability.execution_authorized is False
    )
    if (
        not exact
        or not safe
        or request.minimum_remaining_budget_milliseconds != 100
        or request.consumption_authorization_audit_payload != audit_payload
        or request.consumption_authorization_audit_digest != canonical_digest(audit_payload)
        or custody.canonical_digest != canonical_digest(custody.digest_payload())
        or openability.canonical_digest != canonical_digest(openability.digest_payload())
        or not 8 <= len(request.idempotency_key) <= 128
    ):
        raise ValueError("target context capsule opening claim evidence is unsafe")
    try:
        custody_valid = request.offline_signature_verifier.verify_opening_custody_attestation(
            custody
        )
        openability_valid = (
            request.offline_signature_verifier.verify_capsule_openability_attestation(openability)
        )
    except Exception as exc:
        raise ValueError("target context capsule opening attestation signature is invalid") from exc
    if custody_valid is not True or openability_valid is not True:
        raise ValueError("target context capsule opening attestation signature is invalid")
    for value in (
        lease.canonical_digest,
        request.expected_request_nonce_digest,
        request.expected_policy_digest,
        request.expected_trusted_opener_profile_digest,
        request.idempotency_digest,
        request.request_fingerprint,
        request.consumption_authorization_audit_digest,
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("target context capsule opening claim digest is invalid")


def _payload(value: Any, *, exclude: tuple[str, ...]) -> dict[str, object]:
    return {
        field.name: (
            item.isoformat()
            if isinstance(item, datetime)
            else item.canonical_value()
            if hasattr(item, "canonical_value")
            else item
        )
        for field in fields(value)
        if field.name not in exclude
        for item in (getattr(value, field.name),)
    }


__all__ = [
    name for name in globals() if name.startswith("Workflow") or name.startswith("validate_")
]
