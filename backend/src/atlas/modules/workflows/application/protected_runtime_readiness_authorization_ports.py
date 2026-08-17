from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationClaim,
    WorkflowProtectedRuntimeReadinessAuthorizationLease,
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationClaim,
    WorkflowProtectedRuntimeStartAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionAttempt,
    WorkflowProtectedRuntimeStartConsumptionClaim,
    WorkflowProtectedRuntimeStartConsumptionResult,
    WorkflowProtectedRuntimeStartReceipt,
)


class WorkflowProtectedRuntimeReadinessAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeReadinessAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationSource:
    """Canonical ADR-174 success and the exact authorization/start lineage."""

    result: WorkflowProtectedRuntimeStartConsumptionResult
    attempt: WorkflowProtectedRuntimeStartConsumptionAttempt
    start_claim: WorkflowProtectedRuntimeStartConsumptionClaim
    starter_receipt: WorkflowProtectedRuntimeStartReceipt
    start_authorization_lease: WorkflowProtectedRuntimeStartAuthorizationLease
    start_authorization_claim: WorkflowProtectedRuntimeStartAuthorizationClaim


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest:
    start_result_id: str
    start_result_digest: str
    start_consumption_id: str
    start_attempt_id: str
    start_attempt_digest: str
    start_claim_id: str
    start_claim_digest: str
    start_authorization_lease_id: str
    start_authorization_lease_digest: str
    starter_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    start_result_id: str
    start_result_digest: str
    start_consumption_id: str
    start_attempt_id: str
    start_attempt_digest: str
    start_claim_id: str
    start_claim_digest: str
    start_authorization_lease_id: str
    start_authorization_lease_digest: str
    starter_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    runtime_envelope_eligible_until: datetime
    exact_start_result_confirmed: bool
    runtime_started_confirmed: bool
    runtime_envelope_current: bool
    runtime_envelope_started: bool
    destination_generation_current: bool
    destination_fence_current: bool
    protected_slot_generation_current: bool
    readiness_profile_eligible: bool
    prior_readiness_claim_absent: bool
    prior_readiness_lease_absent: bool
    prior_readiness_attempt_absent: bool
    prior_readiness_result_absent: bool
    runtime_resumed: bool
    runtime_stopped: bool
    runtime_restarted: bool
    generic_process_created: bool
    scheduling_performed: bool
    readiness_probe_performed: bool
    network_activity_performed: bool
    connector_activity_performed: bool
    publication_performed: bool
    delivery_performed: bool
    dispatch_performed: bool
    execution_performed: bool
    infrastructure_mutation_performed: bool
    runtime_locator_included: bool
    process_identifier_included: bool
    context_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    command_included: bool
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


class WorkflowProtectedRuntimeReadinessLifecycleAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_readiness_lifecycle(
        self, request: WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeReadinessLifecycleAttestation: ...


class WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier(Protocol):
    def verify_runtime_readiness_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeReadinessLifecycleAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest:
    start_result_id: str
    start_result_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier
    offline_start_receipt_signature_verifier: WorkflowProtectedRuntimeStartReceiptSignatureVerifier


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeReadinessAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeReadinessAuthorizationSource
    lifecycle_attestation: WorkflowProtectedRuntimeReadinessLifecycleAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier
    offline_start_receipt_signature_verifier: WorkflowProtectedRuntimeStartReceiptSignatureVerifier
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeReadinessAuthorizationClaim
    candidate: WorkflowProtectedRuntimeReadinessAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeReadinessAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeReadinessAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeReadinessAuthorizationPresentationState
    protected_runtime_readiness_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(evaluated_at=self.evaluated_at, consumed=self.consumed)
        expected = (
            WorkflowProtectedRuntimeReadinessAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeReadinessAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected
            or self.protected_runtime_readiness_authority_granted is not active
        ):
            raise ValueError("runtime readiness authorization presentation is inconsistent")


class WorkflowProtectedRuntimeReadinessAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_readiness_authorization(
        self, request: WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationPreflightResult: ...

    async def get_protected_runtime_readiness_authorization_source(
        self, *, start_result_id: str
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationSource | None: ...

    async def authorize_protected_runtime_readiness(
        self, request: WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationLeaseResult: ...

    async def list_protected_runtime_readiness_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeReadinessAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_readiness_authorization_request(
    request: WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest,
) -> None:
    source = request.source
    attestation = request.lifecycle_attestation
    candidate = request.candidate
    claim = request.candidate_claim
    policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
    confirmations = (
        attestation.exact_start_result_confirmed,
        attestation.runtime_started_confirmed,
        attestation.runtime_envelope_current,
        attestation.runtime_envelope_started,
        attestation.destination_generation_current,
        attestation.destination_fence_current,
        attestation.protected_slot_generation_current,
        attestation.readiness_profile_eligible,
        attestation.prior_readiness_claim_absent,
        attestation.prior_readiness_lease_absent,
        attestation.prior_readiness_attempt_absent,
        attestation.prior_readiness_result_absent,
    )
    forbidden = (
        attestation.runtime_resumed,
        attestation.runtime_stopped,
        attestation.runtime_restarted,
        attestation.generic_process_created,
        attestation.scheduling_performed,
        attestation.readiness_probe_performed,
        attestation.network_activity_performed,
        attestation.connector_activity_performed,
        attestation.publication_performed,
        attestation.delivery_performed,
        attestation.dispatch_performed,
        attestation.execution_performed,
        attestation.infrastructure_mutation_performed,
        attestation.runtime_locator_included,
        attestation.process_identifier_included,
        attestation.context_included,
        attestation.endpoint_included,
        attestation.credential_included,
        attestation.secret_included,
        attestation.command_included,
    )
    if (
        request.expected_validity_window_seconds != policy.maximum_lifetime_seconds
        or request.expected_policy_digest != policy.canonical_digest
        or request.expected_request_nonce_digest != attestation.request_nonce_digest
        or request.scope != source.result.scope
        or request.consumer_subject_id != policy.consumer_subject_id
        or request.consumer_audience != policy.consumer_audience
        or any(
            value.tzinfo is None
            for value in (
                request.pre_attestation_observed_at,
                request.requested_at,
                attestation.observed_at,
                attestation.valid_until,
                attestation.runtime_envelope_eligible_until,
            )
        )
        or not source.result.recorded_at
        <= request.pre_attestation_observed_at
        <= attestation.observed_at
        <= request.requested_at
        < attestation.valid_until
        <= attestation.runtime_envelope_eligible_until
        or attestation.attestor_id != policy.required_attestor_id
        or attestation.attestor_version != policy.required_attestor_version
        or attestation.signing_key_id != policy.verification_signing_key_id
        or not all(confirmations)
        or any(forbidden)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_runtime_readiness_lifecycle_attestation(
            attestation
        )
        or not request.offline_start_receipt_signature_verifier.verify_receipt(
            source.starter_receipt
        )
        or not _attestation_matches_source(attestation, source)
        or candidate.start_result_id != source.result.result_id
        or candidate.start_result_digest != source.result.canonical_digest
        or candidate.lifecycle_attestation_id != attestation.attestation_id
        or candidate.lifecycle_attestation_digest != attestation.canonical_digest
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or claim.start_result_id != source.result.result_id
        or claim.start_result_digest != source.result.canonical_digest
        or claim.claimed_at != request.requested_at
        or candidate.claim_id != claim.claim_id
        or candidate.claim_digest != claim.canonical_digest
        or candidate.canonical_digest != canonical_digest(candidate.digest_payload())
        or claim.canonical_digest != canonical_digest(claim.digest_payload())
    ):
        raise ValueError("runtime readiness authorization evidence is invalid")


def _attestation_matches_source(
    attestation: WorkflowProtectedRuntimeReadinessLifecycleAttestation,
    source: WorkflowProtectedRuntimeReadinessAuthorizationSource,
) -> bool:
    result = source.result
    attempt = source.attempt
    claim = source.start_claim
    lease = source.start_authorization_lease
    return (
        attestation.start_result_id == result.result_id
        and attestation.start_result_digest == result.canonical_digest
        and attestation.start_consumption_id
        == result.consumption_id
        == attempt.consumption_id
        == claim.consumption_id
        and attestation.start_attempt_id == result.attempt_id == attempt.attempt_id
        and attestation.start_attempt_digest == result.attempt_digest == attempt.canonical_digest
        and attestation.start_claim_id == result.claim_id == claim.claim_id
        and attestation.start_claim_digest == result.claim_digest == claim.canonical_digest
        and attestation.start_authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        == claim.authorization_lease_id
        == lease.authorization_lease_id
        and attestation.start_authorization_lease_digest
        == result.authorization_lease_digest
        == attempt.authorization_lease_digest
        == claim.authorization_lease_digest
        == lease.canonical_digest
        and attestation.starter_receipt_digest
        == result.starter_receipt_digest
        == source.starter_receipt.canonical_digest
        and attestation.destination_deployment_id == result.destination_deployment_id
        and attestation.destination_generation == result.destination_generation
        and attestation.destination_fencing_token_digest == attempt.destination_fencing_token_digest
        and attestation.protected_slot_commitment == attempt.runtime_slot_commitment
        and attestation.protected_slot_generation == attempt.runtime_slot_generation
        and attestation.runtime_envelope_id == attempt.runtime_envelope_id
        and attestation.runtime_envelope_commitment == result.runtime_envelope_commitment
        and attestation.runtime_envelope_generation == result.runtime_envelope_generation
        and attestation.runtime_start_profile_id == result.runtime_start_profile_id
        and attestation.runtime_start_profile_version == result.runtime_start_profile_version
        and attestation.runtime_start_profile_digest == result.runtime_start_profile_digest
        and attestation.scope == result.scope == attempt.scope
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
    "WorkflowProtectedRuntimeReadinessAuthorizationError",
    "WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeReadinessAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeReadinessAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeReadinessAuthorizationPresentation",
    "WorkflowProtectedRuntimeReadinessAuthorizationPresentationState",
    "WorkflowProtectedRuntimeReadinessAuthorizationRepository",
    "WorkflowProtectedRuntimeReadinessAuthorizationSource",
    "WorkflowProtectedRuntimeReadinessLifecycleAttestation",
    "WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest",
    "WorkflowProtectedRuntimeReadinessLifecycleAttestor",
    "WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier",
    "validate_workflow_protected_runtime_readiness_authorization_request",
]
