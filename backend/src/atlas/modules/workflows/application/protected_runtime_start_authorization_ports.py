from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseAttempt,
    WorkflowProtectedRuntimeContextUseClaim,
    WorkflowProtectedRuntimeContextUseReceipt,
    WorkflowProtectedRuntimeContextUseResult,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationClaim,
    WorkflowProtectedRuntimeStartAuthorizationLease,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)


class WorkflowProtectedRuntimeStartAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeStartAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeStartAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeStartAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationSource:
    """Canonical ADR-172 success and its complete signed evidence lineage."""

    result: WorkflowProtectedRuntimeContextUseResult
    attempt: WorkflowProtectedRuntimeContextUseAttempt
    use_claim: WorkflowProtectedRuntimeContextUseClaim
    use_receipt: WorkflowProtectedRuntimeContextUseReceipt


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartLifecycleAttestationRequest:
    use_result_id: str
    use_result_digest: str
    use_id: str
    use_attempt_id: str
    use_attempt_digest: str
    use_claim_id: str
    use_claim_digest: str
    use_receipt_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    use_count_post: int
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    use_result_id: str
    use_result_digest: str
    use_id: str
    use_attempt_id: str
    use_attempt_digest: str
    use_claim_id: str
    use_claim_digest: str
    use_receipt_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    use_count_post: int
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    exact_use_result_confirmed: bool
    context_adoption_confirmed: bool
    context_terminal_non_reusable: bool
    runtime_envelope_current: bool
    runtime_envelope_inactive: bool
    runtime_not_started: bool
    runtime_not_resumed: bool
    process_not_created: bool
    destination_generation_current: bool
    destination_fence_current: bool
    runtime_slot_generation_current: bool
    raw_context_included: bool
    runtime_payload_included: bool
    runtime_envelope_locator_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    bearer_token_included: bool
    runtime_use_authorized: bool
    runtime_start_authorized: bool
    runtime_resume_authorized: bool
    process_creation_authorized: bool
    scheduling_authorized: bool
    prompt_construction_authorized: bool
    model_inference_authorized: bool
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


class WorkflowProtectedRuntimeStartLifecycleAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_start_lifecycle(
        self, request: WorkflowProtectedRuntimeStartLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeStartLifecycleAttestation: ...


class WorkflowProtectedRuntimeStartLifecycleSignatureVerifier(Protocol):
    def verify_runtime_start_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeStartLifecycleAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationPreflightRequest:
    use_result_id: str
    use_result_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeStartLifecycleSignatureVerifier
    offline_use_receipt_signature_verifier: (
        WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeStartAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeStartAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeStartAuthorizationSource
    lifecycle_attestation: WorkflowProtectedRuntimeStartLifecycleAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeStartLifecycleSignatureVerifier
    offline_use_receipt_signature_verifier: (
        WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeStartAuthorizationClaim
    candidate: WorkflowProtectedRuntimeStartAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeStartAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeStartAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeStartAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeStartAuthorizationPresentationState
    protected_runtime_start_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(evaluated_at=self.evaluated_at, consumed=self.consumed)
        expected = (
            WorkflowProtectedRuntimeStartAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeStartAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected
            or self.protected_runtime_start_authority_granted is not active
        ):
            raise ValueError("runtime start authorization presentation is inconsistent")


class WorkflowProtectedRuntimeStartAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_start_authorization(
        self, request: WorkflowProtectedRuntimeStartAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeStartAuthorizationPreflightResult: ...

    async def get_protected_runtime_start_authorization_source(
        self, *, use_result_id: str
    ) -> WorkflowProtectedRuntimeStartAuthorizationSource | None: ...

    async def authorize_protected_runtime_start(
        self, request: WorkflowProtectedRuntimeStartAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeStartAuthorizationLeaseResult: ...

    async def list_protected_runtime_start_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeStartAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_start_authorization_request(
    request: WorkflowProtectedRuntimeStartAuthorizationLeaseRequest,
) -> None:
    source = request.source
    result = source.result
    attestation = request.lifecycle_attestation
    candidate = request.candidate
    claim = request.candidate_claim
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()
    unsafe_attestation = (
        attestation.raw_context_included,
        attestation.runtime_payload_included,
        attestation.runtime_envelope_locator_included,
        attestation.endpoint_included,
        attestation.credential_included,
        attestation.secret_included,
        attestation.bearer_token_included,
        attestation.runtime_use_authorized,
        attestation.runtime_start_authorized,
        attestation.runtime_resume_authorized,
        attestation.process_creation_authorized,
        attestation.scheduling_authorized,
        attestation.prompt_construction_authorized,
        attestation.model_inference_authorized,
        attestation.connector_activity_authorized,
        attestation.network_activity_authorized,
        attestation.readiness_probe_authorized,
        attestation.publication_authorized,
        attestation.delivery_authorized,
        attestation.dispatch_authorized,
        attestation.execution_authorized,
        attestation.infrastructure_mutation_authorized,
    )
    confirmations = (
        attestation.exact_use_result_confirmed,
        attestation.context_adoption_confirmed,
        attestation.context_terminal_non_reusable,
        attestation.runtime_envelope_current,
        attestation.runtime_envelope_inactive,
        attestation.runtime_not_started,
        attestation.runtime_not_resumed,
        attestation.process_not_created,
        attestation.destination_generation_current,
        attestation.destination_fence_current,
        attestation.runtime_slot_generation_current,
    )
    if (
        request.expected_validity_window_seconds != policy.maximum_lifetime_seconds
        or request.expected_policy_digest != policy.canonical_digest
        or request.expected_request_nonce_digest != attestation.request_nonce_digest
        or request.scope != source.attempt.scope
        or request.consumer_subject_id != policy.consumer_subject_id
        or request.consumer_audience != policy.consumer_audience
        or any(
            value.tzinfo is None
            for value in (
                request.pre_attestation_observed_at,
                request.requested_at,
                attestation.observed_at,
                attestation.valid_until,
            )
        )
        or not result.recorded_at
        <= request.pre_attestation_observed_at
        <= attestation.observed_at
        <= request.requested_at
        < attestation.valid_until
        or attestation.attestor_id != policy.required_attestor_id
        or attestation.attestor_version != policy.required_attestor_version
        or attestation.signing_key_id != policy.verification_signing_key_id
        or not all(confirmations)
        or any(unsafe_attestation)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_runtime_start_lifecycle_attestation(
            attestation
        )
        or not request.offline_use_receipt_signature_verifier.verify_receipt(source.use_receipt)
        or not _attestation_matches_source(attestation, source)
        or candidate.use_result_id != result.result_id
        or candidate.use_result_digest != result.canonical_digest
        or candidate.lifecycle_attestation_id != attestation.attestation_id
        or candidate.lifecycle_attestation_digest != attestation.canonical_digest
        or candidate.lifecycle_attestation_valid_until != attestation.valid_until
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or claim.use_result_id != result.result_id
        or claim.use_result_digest != result.canonical_digest
        or claim.claimed_at != request.requested_at
        or candidate.claim_id != claim.claim_id
        or candidate.claim_digest != claim.canonical_digest
        or candidate.canonical_digest != canonical_digest(candidate.digest_payload())
        or claim.canonical_digest != canonical_digest(claim.digest_payload())
    ):
        raise ValueError("runtime start authorization evidence is invalid")


def _attestation_matches_source(
    attestation: WorkflowProtectedRuntimeStartLifecycleAttestation,
    source: WorkflowProtectedRuntimeStartAuthorizationSource,
) -> bool:
    result = source.result
    attempt = source.attempt
    claim = source.use_claim
    receipt = source.use_receipt
    return (
        attestation.use_result_id == result.result_id
        and attestation.use_result_digest == result.canonical_digest
        and attestation.use_id == result.use_id == attempt.use_id == claim.use_id
        and attestation.use_attempt_id == result.attempt_id == attempt.attempt_id
        and attestation.use_attempt_digest == result.attempt_digest == attempt.canonical_digest
        and attestation.use_claim_id == result.claim_id == claim.claim_id
        and attestation.use_claim_digest == result.claim_digest == claim.canonical_digest
        and attestation.use_receipt_digest
        == result.executor_receipt_digest
        == receipt.canonical_digest
        and attestation.authorization_consumption_result_id
        == result.authorization_consumption_result_id
        == attempt.authorization_consumption_result_id
        == claim.authorization_consumption_result_id
        and attestation.authorization_consumption_result_digest
        == result.authorization_consumption_result_digest
        == attempt.authorization_consumption_result_digest
        == claim.authorization_consumption_result_digest
        and attestation.destination_deployment_id == result.destination_deployment_id
        and attestation.destination_generation == result.destination_generation
        and attestation.destination_fencing_token_digest == result.destination_fencing_token_digest
        and attestation.runtime_slot_commitment == result.runtime_slot_commitment
        and attestation.runtime_slot_post_generation == result.runtime_slot_post_generation
        and attestation.use_count_post == result.use_count_post
        and attestation.use_profile_id == result.use_profile_id
        and attestation.use_profile_version == result.use_profile_version
        and attestation.use_profile_digest == result.use_profile_digest
        and attestation.scope == attempt.scope
    )


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
    "WorkflowProtectedRuntimeStartAuthorizationError",
    "WorkflowProtectedRuntimeStartAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeStartAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeStartAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeStartAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeStartAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeStartAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeStartAuthorizationPresentation",
    "WorkflowProtectedRuntimeStartAuthorizationPresentationState",
    "WorkflowProtectedRuntimeStartAuthorizationRepository",
    "WorkflowProtectedRuntimeStartAuthorizationSource",
    "WorkflowProtectedRuntimeStartLifecycleAttestation",
    "WorkflowProtectedRuntimeStartLifecycleAttestationRequest",
    "WorkflowProtectedRuntimeStartLifecycleAttestor",
    "WorkflowProtectedRuntimeStartLifecycleSignatureVerifier",
    "validate_workflow_protected_runtime_start_authorization_request",
]
