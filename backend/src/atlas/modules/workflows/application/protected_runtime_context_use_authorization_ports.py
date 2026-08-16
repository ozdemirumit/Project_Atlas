from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_context_injection_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_injection_consumption_domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
    WorkflowProtectedRuntimeContextInjectionConsumptionClaim,
    WorkflowProtectedRuntimeContextInjectionConsumptionResult,
    WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationClaim,
    WorkflowProtectedRuntimeContextUseAuthorizationLease,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)


class WorkflowProtectedRuntimeContextUseAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeContextUseAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationSource:
    """Canonical ADR-169 inert-slot success and its signed evidence lineage."""

    result: WorkflowProtectedRuntimeContextInjectionConsumptionResult
    attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt
    consumption_claim: WorkflowProtectedRuntimeContextInjectionConsumptionClaim
    injector_receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeSlotLifecycleAttestationRequest:
    injection_result_id: str
    injection_result_digest: str
    injection_id: str
    injection_attempt_id: str
    injection_attempt_digest: str
    injection_consumption_claim_id: str
    injection_consumption_claim_digest: str
    injection_authorization_lease_id: str
    injection_authorization_lease_digest: str
    injector_receipt_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    injected_context_usable_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeSlotLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    injection_result_id: str
    injection_result_digest: str
    injection_id: str
    injection_attempt_id: str
    injection_attempt_digest: str
    injection_consumption_claim_id: str
    injection_consumption_claim_digest: str
    injection_authorization_lease_id: str
    injection_authorization_lease_digest: str
    injector_receipt_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    injected_context_usable_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    exact_runtime_slot_confirmed: bool
    inert_context_present: bool
    runtime_slot_inert: bool
    runtime_slot_unused: bool
    runtime_slot_unrevoked: bool
    destination_generation_current: bool
    destination_fence_current: bool
    use_profile_eligible: bool
    raw_context_included: bool
    runtime_payload_included: bool
    runtime_slot_locator_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    bearer_token_included: bool
    runtime_use_authorized: bool
    runtime_start_authorized: bool
    runtime_resume_authorized: bool
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


class WorkflowProtectedRuntimeSlotLifecycleAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_slot_lifecycle(
        self, request: WorkflowProtectedRuntimeSlotLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeSlotLifecycleAttestation: ...


class WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier(Protocol):
    def verify_runtime_slot_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest:
    injection_result_id: str
    injection_result_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier
    offline_injector_receipt_signature_verifier: (
        WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeContextUseAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeContextUseAuthorizationSource
    lifecycle_attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier
    offline_injector_receipt_signature_verifier: (
        WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeContextUseAuthorizationClaim
    candidate: WorkflowProtectedRuntimeContextUseAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeContextUseAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeContextUseAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeContextUseAuthorizationPresentationState
    protected_runtime_context_use_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(evaluated_at=self.evaluated_at, consumed=self.consumed)
        expected = (
            WorkflowProtectedRuntimeContextUseAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeContextUseAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected
            or self.protected_runtime_context_use_authority_granted is not active
        ):
            raise ValueError("runtime context use authorization presentation is inconsistent")


class WorkflowProtectedRuntimeContextUseAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_context_use_authorization(
        self, request: WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationPreflightResult: ...

    async def get_protected_runtime_context_use_authorization_source(
        self, *, injection_result_id: str
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationSource | None: ...

    async def authorize_protected_runtime_context_use(
        self, request: WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationLeaseResult: ...

    async def list_protected_runtime_context_use_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_context_use_authorization_request(
    request: WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest,
) -> None:
    source = request.source
    result = source.result
    attestation = request.lifecycle_attestation
    candidate = request.candidate
    claim = request.candidate_claim
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    unsafe_attestation = (
        attestation.raw_context_included,
        attestation.runtime_payload_included,
        attestation.runtime_slot_locator_included,
        attestation.endpoint_included,
        attestation.credential_included,
        attestation.secret_included,
        attestation.bearer_token_included,
        attestation.runtime_use_authorized,
        attestation.runtime_start_authorized,
        attestation.runtime_resume_authorized,
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
        or request.expected_policy_digest != policy.canonical_digest
        or request.expected_request_nonce_digest != attestation.request_nonce_digest
        or request.scope != source.attempt.scope
        or request.consumer_subject_id != policy.consumer_subject_id
        or request.consumer_audience != policy.consumer_audience
        or request.pre_attestation_observed_at.tzinfo is None
        or request.requested_at.tzinfo is None
        or attestation.observed_at.tzinfo is None
        or attestation.valid_until.tzinfo is None
        or attestation.injected_context_usable_until.tzinfo is None
        or not result.recorded_at
        <= request.pre_attestation_observed_at
        <= attestation.observed_at
        <= request.requested_at
        < attestation.valid_until
        or request.requested_at >= attestation.injected_context_usable_until
        or attestation.valid_until > attestation.injected_context_usable_until
        or attestation.attestor_id != policy.required_attestor_id
        or attestation.attestor_version != policy.required_attestor_version
        or attestation.signing_key_id != policy.verification_signing_key_id
        or not attestation.exact_runtime_slot_confirmed
        or not attestation.inert_context_present
        or not attestation.runtime_slot_inert
        or not attestation.runtime_slot_unused
        or not attestation.runtime_slot_unrevoked
        or not attestation.destination_generation_current
        or not attestation.destination_fence_current
        or not attestation.use_profile_eligible
        or any(unsafe_attestation)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_runtime_slot_lifecycle_attestation(
            attestation
        )
        or not request.offline_injector_receipt_signature_verifier.verify_receipt(
            source.injector_receipt
        )
        or not _attestation_matches_source(attestation, source)
        or candidate.injection_result_id != result.result_id
        or candidate.injection_result_digest != result.canonical_digest
        or candidate.lifecycle_attestation_id != attestation.attestation_id
        or candidate.lifecycle_attestation_digest != attestation.canonical_digest
        or candidate.lifecycle_attestation_valid_until != attestation.valid_until
        or candidate.injected_context_usable_until != attestation.injected_context_usable_until
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or candidate.valid_until > attestation.injected_context_usable_until
        or claim.injection_result_id != result.result_id
        or claim.injection_result_digest != result.canonical_digest
        or claim.injected_context_usable_until != attestation.injected_context_usable_until
        or claim.claimed_at != request.requested_at
        or candidate.claim_id != claim.claim_id
        or candidate.claim_digest != claim.canonical_digest
        or candidate.canonical_digest != canonical_digest(candidate.digest_payload())
        or claim.canonical_digest != canonical_digest(claim.digest_payload())
    ):
        raise ValueError("runtime context use authorization evidence is invalid")


def _attestation_matches_source(
    attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation,
    source: WorkflowProtectedRuntimeContextUseAuthorizationSource,
) -> bool:
    result = source.result
    attempt = source.attempt
    claim = source.consumption_claim
    return (
        attestation.injection_result_id == result.result_id
        and attestation.injection_result_digest == result.canonical_digest
        and attestation.injection_id == result.injection_id
        and attestation.injection_attempt_id == attempt.attempt_id
        and attestation.injection_attempt_digest == attempt.canonical_digest
        and attestation.injection_consumption_claim_id == claim.claim_id
        and attestation.injection_consumption_claim_digest == claim.canonical_digest
        and attestation.injection_authorization_lease_id == result.authorization_lease_id
        and attestation.injection_authorization_lease_digest == result.authorization_lease_digest
        and attestation.injector_receipt_digest == source.injector_receipt.canonical_digest
        and attestation.destination_boundary_id == result.destination_boundary_id
        and attestation.destination_deployment_id == result.destination_deployment_id
        and attestation.destination_generation == result.destination_generation
        and attestation.destination_fencing_token_digest == result.destination_fencing_token_digest
        and attestation.runtime_slot_profile_id == result.runtime_slot_profile_id
        and attestation.runtime_slot_profile_version == result.runtime_slot_profile_version
        and attestation.runtime_slot_profile_digest == result.runtime_slot_profile_digest
        and attestation.runtime_slot_commitment == result.runtime_slot_commitment
        and attestation.runtime_slot_post_generation == result.runtime_slot_post_generation
        and attestation.injected_context_usable_until
        == attempt.protected_runtime_handle_usable_until
        and attestation.use_profile_id == policy_value("use_profile_id")
        and attestation.use_profile_version == policy_value("use_profile_version")
        and attestation.use_profile_digest == policy_value("use_profile_digest")
        and attestation.scope == attempt.scope
    )


def policy_value(name: str) -> object:
    return getattr(code_owned_workflow_protected_runtime_context_use_authorization_policy(), name)


def _canonical_payload(value: object, *, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        field.name: _canonical_value(getattr(value, field.name))
        for field in fields(cast(Any, value))
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
    "WorkflowProtectedRuntimeContextUseAuthorizationError",
    "WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeContextUseAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeContextUseAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeContextUseAuthorizationPresentation",
    "WorkflowProtectedRuntimeContextUseAuthorizationPresentationState",
    "WorkflowProtectedRuntimeContextUseAuthorizationRepository",
    "WorkflowProtectedRuntimeContextUseAuthorizationSource",
    "WorkflowProtectedRuntimeSlotLifecycleAttestation",
    "WorkflowProtectedRuntimeSlotLifecycleAttestationRequest",
    "WorkflowProtectedRuntimeSlotLifecycleAttestor",
    "WorkflowProtectedRuntimeSlotLifecycleSignatureVerifier",
    "validate_workflow_protected_runtime_context_use_authorization_request",
]
