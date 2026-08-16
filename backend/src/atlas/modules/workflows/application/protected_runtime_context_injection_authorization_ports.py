from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E501
    WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedResidentContextAccessConsumptionAttempt,
    WorkflowProtectedResidentContextAccessConsumptionClaim,
    WorkflowProtectedResidentContextAccessConsumptionResult,
    WorkflowProtectedResidentContextTrustedAccessorReceipt,
    WorkflowProtectedRuntimeContextInjectionAuthorizationClaim,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
)


class WorkflowProtectedRuntimeContextInjectionAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionAuthorizationSource:
    """Canonical ADR-167 success lineage with metadata-only handle identity."""

    result: WorkflowProtectedResidentContextAccessConsumptionResult
    attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt
    consumption_claim: WorkflowProtectedResidentContextAccessConsumptionClaim
    access_authorization_lease: WorkflowProtectedResidentContextAccessAuthorizationLease
    accessor_receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt
    protected_runtime_handle_id: str
    protected_runtime_handle_digest: str
    protected_runtime_handle_created_at: datetime
    protected_runtime_handle_usable_until: datetime
    protected_resident_context_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    accessor_receipt_digest: str
    accessor_receipt_signing_key_id: str
    accessor_receipt_signature_algorithm: str
    accessor_receipt_integrity_signature: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeHandleLifecycleAttestationRequest:
    access_result_id: str
    access_result_digest: str
    access_attempt_id: str
    access_attempt_digest: str
    access_consumption_claim_id: str
    access_consumption_claim_digest: str
    access_authorization_lease_id: str
    access_authorization_lease_digest: str
    accessor_receipt_digest: str
    accessor_receipt_signing_key_id: str
    protected_runtime_handle_id: str
    protected_runtime_handle_digest: str
    protected_runtime_handle_created_at: datetime
    protected_runtime_handle_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeHandleLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    access_result_id: str
    access_result_digest: str
    access_attempt_id: str
    access_attempt_digest: str
    access_consumption_claim_id: str
    access_consumption_claim_digest: str
    access_authorization_lease_id: str
    access_authorization_lease_digest: str
    accessor_receipt_digest: str
    accessor_receipt_signing_key_id: str
    protected_runtime_handle_id: str
    protected_runtime_handle_digest: str
    protected_runtime_handle_created_at: datetime
    protected_runtime_handle_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    runtime_handle_present: bool
    runtime_handle_is_bearer_capability: bool
    runtime_handle_unexpired: bool
    runtime_handle_unrevoked: bool
    runtime_handle_undestroyed: bool
    runtime_handle_uninjected: bool
    runtime_handle_unused: bool
    destination_generation_current: bool
    destination_fence_current: bool
    injector_profile_eligible: bool
    runtime_slot_profile_eligible: bool
    raw_context_included: bool
    runtime_handle_material_included: bool
    runtime_payload_included: bool
    runtime_handle_locator_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    bearer_token_included: bool
    provider_payload_included: bool
    handle_lookup_authorized: bool
    handle_retrieval_authorized: bool
    handle_use_authorized: bool
    runtime_use_authorized: bool
    runtime_context_injection_authorized: bool
    injection_consumption_outstanding: bool
    connector_activity_authorized: bool
    network_activity_authorized: bool
    readiness_probe_authorized: bool
    publication_authorized: bool
    delivery_authorized: bool
    dispatch_authorized: bool
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


class WorkflowProtectedRuntimeHandleLifecycleAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_handle_lifecycle(
        self, request: WorkflowProtectedRuntimeHandleLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeHandleLifecycleAttestation: ...


class WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier(Protocol):
    def verify_runtime_handle_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest:
    access_result_id: str
    access_result_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier
    offline_accessor_receipt_signature_verifier: (
        WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeContextInjectionAuthorizationSource
    lifecycle_attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier
    offline_accessor_receipt_signature_verifier: (
        WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeContextInjectionAuthorizationClaim
    candidate: WorkflowProtectedRuntimeContextInjectionAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState
    protected_runtime_context_injection_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(
            evaluated_at=self.evaluated_at,
            consumed=self.consumed,
        )
        expected_state = (
            WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected_state
            or self.protected_runtime_context_injection_authority_granted is not active
        ):
            raise ValueError("runtime context injection presentation is inconsistent")


class WorkflowProtectedRuntimeContextInjectionAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_context_injection_authorization(
        self,
        request: WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest,
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightResult: ...

    async def get_protected_runtime_context_injection_authorization_source(
        self, *, access_result_id: str
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationSource | None: ...

    async def authorize_protected_runtime_context_injection(
        self,
        request: WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseResult: ...

    async def list_protected_runtime_context_injection_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_context_injection_authorization_request(
    request: WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
) -> None:
    source = request.source
    attestation = request.lifecycle_attestation
    candidate = request.candidate
    candidate_claim = request.candidate_claim
    result = source.result
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    unsafe_attestation = (
        attestation.runtime_handle_is_bearer_capability,
        attestation.raw_context_included,
        attestation.runtime_handle_material_included,
        attestation.runtime_payload_included,
        attestation.runtime_handle_locator_included,
        attestation.endpoint_included,
        attestation.credential_included,
        attestation.secret_included,
        attestation.bearer_token_included,
        attestation.provider_payload_included,
        attestation.handle_lookup_authorized,
        attestation.handle_retrieval_authorized,
        attestation.handle_use_authorized,
        attestation.runtime_use_authorized,
        attestation.runtime_context_injection_authorized,
        attestation.injection_consumption_outstanding,
        attestation.connector_activity_authorized,
        attestation.network_activity_authorized,
        attestation.readiness_probe_authorized,
        attestation.publication_authorized,
        attestation.delivery_authorized,
        attestation.dispatch_authorized,
        attestation.execution_authorized,
        attestation.infrastructure_mutation_authorized,
    )
    if (
        request.expected_validity_window_seconds != 1
        or len(request.expected_policy_digest) != 64
        or any(c not in "0123456789abcdef" for c in request.expected_policy_digest)
        or request.expected_policy_digest != candidate.policy_digest
        or request.scope != result.scope
        or request.consumer_subject_id != source.consumer_subject_id
        or request.consumer_audience != source.consumer_audience
        or request.expected_request_nonce_digest != attestation.request_nonce_digest
        or attestation.attestor_id != policy.required_attestor_id
        or attestation.attestor_version != policy.required_attestor_version
        or attestation.signing_key_id != policy.verification_signing_key_id
        or request.pre_attestation_observed_at.tzinfo is None
        or request.requested_at.tzinfo is None
        or attestation.observed_at.tzinfo is None
        or attestation.valid_until.tzinfo is None
        or not result.recorded_at
        <= request.pre_attestation_observed_at
        <= attestation.observed_at
        <= request.requested_at
        < attestation.valid_until
        or attestation.valid_until > source.protected_runtime_handle_usable_until
        or attestation.access_result_id != result.access_id
        or attestation.access_result_digest != result.canonical_digest
        or attestation.access_attempt_id != source.attempt.attempt_id
        or attestation.access_attempt_digest != source.attempt.canonical_digest
        or attestation.access_consumption_claim_id != source.consumption_claim.claim_id
        or attestation.access_consumption_claim_digest != source.consumption_claim.canonical_digest
        or attestation.access_authorization_lease_id
        != source.access_authorization_lease.authorization_lease_id
        or attestation.access_authorization_lease_digest
        != source.access_authorization_lease.canonical_digest
        or attestation.accessor_receipt_digest != source.accessor_receipt_digest
        or attestation.protected_runtime_handle_id != source.protected_runtime_handle_id
        or attestation.protected_runtime_handle_digest != source.protected_runtime_handle_digest
        or attestation.protected_runtime_handle_created_at
        != source.protected_runtime_handle_created_at
        or attestation.protected_runtime_handle_usable_until
        != source.protected_runtime_handle_usable_until
        or attestation.destination_boundary_id != source.destination_boundary_id
        or attestation.destination_deployment_id != source.destination_deployment_id
        or attestation.destination_generation != source.destination_generation
        or attestation.destination_fencing_token_digest != source.destination_fencing_token_digest
        or attestation.runtime_handle_profile_id != source.runtime_handle_profile_id
        or attestation.runtime_handle_profile_version != source.runtime_handle_profile_version
        or attestation.runtime_handle_profile_digest != source.runtime_handle_profile_digest
        or attestation.injector_contract_id != policy.required_injector_contract_id
        or attestation.injector_contract_version != policy.required_injector_contract_version
        or attestation.injector_id != policy.approved_injector_id
        or attestation.injector_version != policy.approved_injector_version
        or attestation.runtime_slot_profile_id != policy.runtime_slot_profile_id
        or attestation.runtime_slot_profile_version != policy.runtime_slot_profile_version
        or attestation.runtime_slot_profile_digest != policy.runtime_slot_profile_digest
        or attestation.scope != request.scope
        or attestation.consumer_subject_id != request.consumer_subject_id
        or attestation.consumer_audience != request.consumer_audience
        or not attestation.runtime_handle_present
        or not attestation.runtime_handle_unexpired
        or not attestation.runtime_handle_unrevoked
        or not attestation.runtime_handle_undestroyed
        or not attestation.runtime_handle_uninjected
        or not attestation.runtime_handle_unused
        or not attestation.destination_generation_current
        or not attestation.destination_fence_current
        or not attestation.injector_profile_eligible
        or not attestation.runtime_slot_profile_eligible
        or any(unsafe_attestation)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_runtime_handle_lifecycle_attestation(
            attestation
        )
        or not request.offline_accessor_receipt_signature_verifier.verify_receipt(
            source.accessor_receipt
        )
        or candidate.access_result_id != result.access_id
        or candidate.access_result_digest != result.canonical_digest
        or candidate.protected_runtime_handle_id != source.protected_runtime_handle_id
        or candidate.protected_runtime_handle_digest != source.protected_runtime_handle_digest
        or candidate.lifecycle_attestation_id != attestation.attestation_id
        or candidate.lifecycle_attestation_digest != attestation.canonical_digest
        or candidate.lifecycle_attestation_valid_until != attestation.valid_until
        or candidate.injector_contract_id != attestation.injector_contract_id
        or candidate.injector_contract_version != attestation.injector_contract_version
        or candidate.injector_id != attestation.injector_id
        or candidate.injector_version != attestation.injector_version
        or candidate.runtime_slot_profile_id != attestation.runtime_slot_profile_id
        or candidate.runtime_slot_profile_version != attestation.runtime_slot_profile_version
        or candidate.runtime_slot_profile_digest != attestation.runtime_slot_profile_digest
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or candidate.valid_until > source.protected_runtime_handle_usable_until
        or candidate_claim.access_result_id != result.access_id
        or candidate_claim.access_result_digest != result.canonical_digest
        or candidate_claim.protected_runtime_handle_id != source.protected_runtime_handle_id
        or candidate_claim.protected_runtime_handle_digest != source.protected_runtime_handle_digest
        or candidate_claim.claimed_at != request.requested_at
        or canonical_digest(candidate.digest_payload()) != candidate.canonical_digest
        or canonical_digest(candidate_claim.digest_payload()) != candidate_claim.canonical_digest
    ):
        raise ValueError("runtime context injection authorization evidence is invalid")


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
    "WorkflowProtectedRuntimeContextInjectionAuthorizationError",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationRepository",
    "WorkflowProtectedRuntimeContextInjectionAuthorizationSource",
    "WorkflowProtectedRuntimeHandleLifecycleAttestation",
    "WorkflowProtectedRuntimeHandleLifecycleAttestationRequest",
    "WorkflowProtectedRuntimeHandleLifecycleAttestor",
    "WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier",
    "validate_workflow_protected_runtime_context_injection_authorization_request",
]
