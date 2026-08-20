from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaim,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationClaim,
    WorkflowProtectedRuntimeReadinessAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessAttempt,
    WorkflowProtectedRuntimeReadinessConsumptionClaim,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessResult,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_ID = (
    "attestor.workflow-protected-runtime-process-creation-lifecycle"
)
WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_VERSION = "1.0"
WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTATION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-process-creation-lifecycle.v1"
)


class WorkflowProtectedRuntimeProcessCreationAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationSource:
    """Canonical ADR-176 success and its exact authorization/assessment lineage."""

    result: WorkflowProtectedRuntimeReadinessResult
    attempt: WorkflowProtectedRuntimeReadinessAttempt
    readiness_claim: WorkflowProtectedRuntimeReadinessConsumptionClaim
    readiness_receipt: WorkflowProtectedRuntimeReadinessReceipt
    readiness_authorization_lease: WorkflowProtectedRuntimeReadinessAuthorizationLease
    readiness_authorization_claim: WorkflowProtectedRuntimeReadinessAuthorizationClaim


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest:
    readiness_result_id: str
    readiness_result_digest: str
    readiness_consumption_id: str
    readiness_attempt_id: str
    readiness_attempt_digest: str
    readiness_claim_id: str
    readiness_claim_digest: str
    readiness_authorization_lease_id: str
    readiness_authorization_lease_digest: str
    readiness_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationLifecycleAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    readiness_result_id: str
    readiness_result_digest: str
    readiness_consumption_id: str
    readiness_attempt_id: str
    readiness_attempt_digest: str
    readiness_claim_id: str
    readiness_claim_digest: str
    readiness_authorization_lease_id: str
    readiness_authorization_lease_digest: str
    readiness_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
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
    exact_readiness_result_confirmed: bool
    runtime_started_confirmed: bool
    runtime_ready_confirmed: bool
    readiness_assessment_confirmed: bool
    metadata_only_confirmed: bool
    runtime_envelope_current: bool
    runtime_envelope_started: bool
    destination_generation_current: bool
    destination_fence_current: bool
    protected_slot_generation_current: bool
    readiness_profile_eligible: bool
    prior_process_creation_claim_absent: bool
    prior_process_creation_lease_absent: bool
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


class WorkflowProtectedRuntimeProcessCreationLifecycleAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_process_creation_lifecycle(
        self, request: WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessCreationLifecycleAttestation: ...


class WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier(Protocol):
    def verify_runtime_process_creation_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeProcessCreationLifecycleAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest:
    readiness_result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier
    offline_readiness_receipt_signature_verifier: (
        WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeProcessCreationAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationSourceRequest:
    readiness_result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeProcessCreationAuthorizationSource
    lifecycle_attestation: WorkflowProtectedRuntimeProcessCreationLifecycleAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier
    offline_readiness_receipt_signature_verifier: (
        WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeProcessCreationAuthorizationClaim
    candidate: WorkflowProtectedRuntimeProcessCreationAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeProcessCreationAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeProcessCreationAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState
    protected_runtime_process_creation_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(evaluated_at=self.evaluated_at, consumed=self.consumed)
        expected = (
            WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected
            or self.protected_runtime_process_creation_authority_granted is not active
        ):
            raise ValueError("runtime process-creation authorization presentation is inconsistent")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationInventory:
    server_time: datetime
    presentations: tuple[WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation, ...]

    def __post_init__(self) -> None:
        if self.server_time.tzinfo is None or any(
            presentation.evaluated_at != self.server_time for presentation in self.presentations
        ):
            raise ValueError(
                "runtime process-creation authorization inventory has inconsistent time"
            )


class WorkflowProtectedRuntimeProcessCreationAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_process_creation_authorization(
        self, request: WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightResult: ...

    async def get_protected_runtime_process_creation_authorization_source(
        self, request: WorkflowProtectedRuntimeProcessCreationAuthorizationSourceRequest
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationSource | None: ...

    async def authorize_protected_runtime_process_creation(
        self, request: WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseResult: ...

    async def list_protected_runtime_process_creation_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_process_creation_authorization_request(
    request: WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest,
) -> None:
    source = request.source
    attestation = request.lifecycle_attestation
    candidate = request.candidate
    claim = request.candidate_claim
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    readiness_policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    confirmations = (
        attestation.exact_readiness_result_confirmed,
        attestation.runtime_started_confirmed,
        attestation.runtime_ready_confirmed,
        attestation.readiness_assessment_confirmed,
        attestation.metadata_only_confirmed,
        attestation.runtime_envelope_current,
        attestation.runtime_envelope_started,
        attestation.destination_generation_current,
        attestation.destination_fence_current,
        attestation.protected_slot_generation_current,
        attestation.readiness_profile_eligible,
        attestation.prior_process_creation_claim_absent,
        attestation.prior_process_creation_lease_absent,
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
        or attestation.consumer_subject_id != policy.consumer_subject_id
        or attestation.consumer_audience != policy.consumer_audience
        or attestation.consumer_contract_id != policy.consumer_contract_id
        or attestation.consumer_contract_version != policy.consumer_contract_version
        or attestation.purpose_id != policy.purpose_id
        or attestation.readiness_profile_id != readiness_policy.readiness_profile_id
        or attestation.readiness_profile_version != readiness_policy.readiness_profile_version
        or attestation.readiness_profile_digest != readiness_policy.readiness_profile_digest
        or attestation.process_creation_profile_id != policy.process_creation_profile_id
        or attestation.process_creation_profile_version != policy.process_creation_profile_version
        or attestation.process_creation_profile_digest != policy.process_creation_profile_digest
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
        or attestation.valid_until - attestation.observed_at
        > timedelta(seconds=policy.maximum_attestation_freshness_seconds)
        or attestation.attestor_id != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_ID
        or attestation.attestor_version
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_VERSION
        or attestation.signing_key_id
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTATION_SIGNING_KEY_ID
        or not all(confirmations)
        or any(forbidden)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not (
            request.offline_signature_verifier
        ).verify_runtime_process_creation_lifecycle_attestation(attestation)
        or not request.offline_readiness_receipt_signature_verifier.verify_receipt(
            source.readiness_receipt
        )
        or not workflow_protected_runtime_process_creation_readiness_receipt_matches_source(source)
        or not _attestation_matches_source(attestation, source)
        or candidate.readiness_result_id != source.result.result_id
        or candidate.readiness_result_digest != source.result.canonical_digest
        or candidate.lifecycle_attestation_id != attestation.attestation_id
        or candidate.lifecycle_attestation_digest != attestation.canonical_digest
        or candidate.lifecycle_attestation_valid_until != attestation.valid_until
        or candidate.runtime_envelope_eligible_until != attestation.runtime_envelope_eligible_until
        or candidate.readiness_profile_id != attestation.readiness_profile_id
        or candidate.readiness_profile_version != attestation.readiness_profile_version
        or candidate.readiness_profile_digest != attestation.readiness_profile_digest
        or candidate.process_creation_profile_id != attestation.process_creation_profile_id
        or candidate.process_creation_profile_version
        != attestation.process_creation_profile_version
        or candidate.process_creation_profile_digest != attestation.process_creation_profile_digest
        or candidate.attestation_metadata_only is not True
        or candidate.runtime_started is not True
        or candidate.process_created is not False
        or candidate.process_scheduled is not False
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or claim.readiness_result_id != source.result.result_id
        or claim.readiness_result_digest != source.result.canonical_digest
        or claim.claimed_at != request.requested_at
        or candidate.claim_id != claim.claim_id
        or candidate.claim_digest != claim.canonical_digest
        or candidate.canonical_digest != canonical_digest(candidate.digest_payload())
        or claim.canonical_digest != canonical_digest(claim.digest_payload())
    ):
        raise ValueError("runtime process-creation authorization evidence is invalid")


def _attestation_matches_source(
    attestation: WorkflowProtectedRuntimeProcessCreationLifecycleAttestation,
    source: WorkflowProtectedRuntimeProcessCreationAuthorizationSource,
) -> bool:
    result = source.result
    attempt = source.attempt
    claim = source.readiness_claim
    lease = source.readiness_authorization_lease
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    readiness_policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    return (
        attestation.readiness_result_id == result.result_id
        and attestation.readiness_result_digest == result.canonical_digest
        and attestation.readiness_consumption_id
        == result.consumption_id
        == attempt.consumption_id
        == claim.consumption_id
        and attestation.readiness_attempt_id == result.attempt_id == attempt.attempt_id
        and attestation.readiness_attempt_digest
        == result.attempt_digest
        == attempt.canonical_digest
        and attestation.readiness_claim_id == result.claim_id == claim.claim_id
        and attestation.readiness_claim_digest == result.claim_digest == claim.canonical_digest
        and attestation.readiness_authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        == claim.authorization_lease_id
        == lease.authorization_lease_id
        and attestation.readiness_authorization_lease_digest
        == result.authorization_lease_digest
        == attempt.authorization_lease_digest
        == claim.authorization_lease_digest
        == lease.canonical_digest
        and attestation.readiness_receipt_digest
        == result.assessor_receipt_digest
        == source.readiness_receipt.canonical_digest
        and attestation.destination_deployment_id == result.destination_deployment_id
        and attestation.destination_generation == result.destination_generation
        and attestation.destination_fencing_token_digest == attempt.destination_fencing_token_digest
        and attestation.protected_slot_commitment == attempt.protected_slot_commitment
        and attestation.protected_slot_generation == attempt.protected_slot_generation
        and attestation.runtime_envelope_id == attempt.runtime_envelope_id
        and attestation.runtime_envelope_commitment == result.runtime_envelope_commitment
        and attestation.runtime_envelope_generation == result.runtime_envelope_generation
        and attestation.scope == result.scope == attempt.scope
        and attestation.consumer_subject_id
        == attempt.consumer_subject_id
        == policy.consumer_subject_id
        and attestation.consumer_audience == attempt.consumer_audience == policy.consumer_audience
        and attestation.consumer_contract_id
        == attempt.consumer_contract_id
        == policy.consumer_contract_id
        and attestation.consumer_contract_version
        == attempt.consumer_contract_version
        == policy.consumer_contract_version
        and attestation.purpose_id == policy.purpose_id
        and attestation.readiness_profile_id == readiness_policy.readiness_profile_id
        and attestation.readiness_profile_version == readiness_policy.readiness_profile_version
        and attestation.readiness_profile_digest == readiness_policy.readiness_profile_digest
        and attestation.process_creation_profile_id == policy.process_creation_profile_id
        and attestation.process_creation_profile_version == policy.process_creation_profile_version
        and attestation.process_creation_profile_digest == policy.process_creation_profile_digest
    )


def workflow_protected_runtime_process_creation_readiness_receipt_matches_source(
    source: WorkflowProtectedRuntimeProcessCreationAuthorizationSource,
) -> bool:
    """Bind the signed ADR-176 receipt to the complete locked attempt lineage."""

    receipt = source.readiness_receipt
    attempt = source.attempt
    result = source.result
    readiness_policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    instruction_payload = {
        "consumption_id": attempt.consumption_id,
        "attempt_id": attempt.attempt_id,
        "attempt_digest": attempt.canonical_digest,
        "claim_id": attempt.claim_id,
        "claim_digest": attempt.claim_digest,
        "authorization_lease_id": attempt.authorization_lease_id,
        "authorization_lease_digest": attempt.authorization_lease_digest,
        "start_result_id": attempt.start_result_id,
        "start_result_digest": attempt.start_result_digest,
        "protected_operation_reference": attempt.protected_operation_reference,
        "destination_deployment_id": attempt.destination_deployment_id,
        "destination_generation": attempt.destination_generation,
        "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
        "protected_slot_commitment": attempt.protected_slot_commitment,
        "protected_slot_generation": attempt.protected_slot_generation,
        "runtime_envelope_id": attempt.runtime_envelope_id,
        "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
        "runtime_envelope_generation": attempt.runtime_envelope_generation,
        "readiness_profile_id": attempt.readiness_profile_id,
        "readiness_profile_version": attempt.readiness_profile_version,
        "readiness_profile_digest": attempt.readiness_profile_digest,
        "expected_assessment_count_pre": attempt.expected_assessment_count_pre,
        "expected_assessment_count_post": attempt.expected_assessment_count_post,
        "assessor_contract_id": attempt.assessor_contract_id,
        "assessor_contract_version": attempt.assessor_contract_version,
        "assessor_id": attempt.assessor_id,
        "assessor_version": attempt.assessor_version,
        "request_nonce_digest": attempt.request_nonce_digest,
        "scope": attempt.scope,
        "policy_id": attempt.policy_id,
        "policy_version": attempt.policy_version,
        "policy_digest": attempt.policy_digest,
        "started_at": attempt.started_at,
        "invocation_deadline": attempt.invocation_deadline,
    }
    instruction_digest = canonical_digest(
        {name: _canonical_value(value) for name, value in instruction_payload.items()}
    )
    return (
        receipt.consumption_id == result.consumption_id == attempt.consumption_id
        and receipt.attempt_id == result.attempt_id == attempt.attempt_id
        and receipt.attempt_digest == result.attempt_digest == attempt.canonical_digest
        and receipt.claim_id == result.claim_id == attempt.claim_id
        and receipt.claim_digest == result.claim_digest == attempt.claim_digest
        and receipt.instruction_digest == instruction_digest
        and receipt.protected_operation_reference == attempt.protected_operation_reference
        and receipt.authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        and receipt.authorization_lease_digest
        == result.authorization_lease_digest
        == attempt.authorization_lease_digest
        and receipt.start_result_id == result.start_result_id == attempt.start_result_id
        and receipt.start_result_digest == result.start_result_digest == attempt.start_result_digest
        and receipt.destination_deployment_id
        == result.destination_deployment_id
        == attempt.destination_deployment_id
        and receipt.destination_generation
        == result.destination_generation
        == attempt.destination_generation
        and receipt.destination_fencing_token_digest == attempt.destination_fencing_token_digest
        and receipt.protected_slot_commitment == attempt.protected_slot_commitment
        and receipt.protected_slot_generation == attempt.protected_slot_generation
        and receipt.runtime_envelope_id == attempt.runtime_envelope_id
        and receipt.runtime_envelope_commitment
        == result.runtime_envelope_commitment
        == attempt.runtime_envelope_commitment
        and receipt.runtime_envelope_generation
        == result.runtime_envelope_generation
        == attempt.runtime_envelope_generation
        and receipt.readiness_profile_id
        == result.readiness_profile_id
        == attempt.readiness_profile_id
        and receipt.readiness_profile_version
        == result.readiness_profile_version
        == attempt.readiness_profile_version
        and receipt.readiness_profile_digest
        == result.readiness_profile_digest
        == attempt.readiness_profile_digest
        and receipt.request_nonce_digest == attempt.request_nonce_digest
        and receipt.result_state is result.state
        and receipt.assessment_count_pre == attempt.expected_assessment_count_pre == 0
        and receipt.assessment_count_post == attempt.expected_assessment_count_post == 1
        and receipt.assessor_contract_id
        == attempt.assessor_contract_id
        == readiness_policy.required_assessor_contract_id
        and receipt.assessor_contract_version
        == attempt.assessor_contract_version
        == readiness_policy.required_assessor_contract_version
        and receipt.assessor_id == attempt.assessor_id == readiness_policy.approved_assessor_id
        and receipt.assessor_version
        == attempt.assessor_version
        == readiness_policy.approved_assessor_version
        and receipt.signing_key_id
        == attempt.receipt_verification_signing_key_id
        == readiness_policy.receipt_verification_signing_key_id
        and receipt.signature_algorithm == readiness_policy.receipt_signature_algorithm
        and receipt.completed_at == result.completed_at
        and attempt.consumer_subject_id == readiness_policy.consumer_subject_id
        and attempt.consumer_audience == readiness_policy.consumer_audience
        and attempt.consumer_contract_id == readiness_policy.consumer_contract_id
        and attempt.consumer_contract_version == readiness_policy.consumer_contract_version
        and attempt.purpose_id == readiness_policy.purpose_id
        and attempt.policy_id == readiness_policy.policy_id
        and attempt.policy_version == readiness_policy.policy_version
        and attempt.policy_digest == readiness_policy.canonical_digest
        and bool(receipt.integrity_signature)
        and not any(character.isspace() for character in receipt.integrity_signature)
        and receipt.canonical_digest == canonical_digest(receipt.digest_payload())
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
    "WorkflowProtectedRuntimeProcessCreationAuthorizationError",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationInventory",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationRepository",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationSource",
    "WorkflowProtectedRuntimeProcessCreationLifecycleAttestation",
    "WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest",
    "WorkflowProtectedRuntimeProcessCreationLifecycleAttestor",
    "WorkflowProtectedRuntimeProcessCreationLifecycleSignatureVerifier",
    "validate_workflow_protected_runtime_process_creation_authorization_request",
]
