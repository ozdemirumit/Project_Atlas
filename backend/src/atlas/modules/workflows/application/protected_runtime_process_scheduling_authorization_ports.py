from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_process_creation_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaim,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationAttempt,
    WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
    WorkflowProtectedRuntimeProcessCreationReceipt,
    WorkflowProtectedRuntimeProcessCreationResult,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_ID = (
    "attestor.workflow-protected-runtime-process-scheduling-state"
)
WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_VERSION = "1.0"
WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTATION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-process-scheduling-state.v1"
)


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource:
    """One canonical terminal ADR-178 success and its complete immutable lineage."""

    result: WorkflowProtectedRuntimeProcessCreationResult
    attempt: WorkflowProtectedRuntimeProcessCreationAttempt
    process_creation_claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim
    process_creation_receipt: WorkflowProtectedRuntimeProcessCreationReceipt
    process_creation_authorization_lease: WorkflowProtectedRuntimeProcessCreationAuthorizationLease
    process_creation_authorization_claim: WorkflowProtectedRuntimeProcessCreationAuthorizationClaim


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest:
    process_creation_result_id: str
    process_creation_result_digest: str
    process_creation_consumption_id: str
    process_creation_attempt_id: str
    process_creation_attempt_digest: str
    process_creation_claim_id: str
    process_creation_claim_digest: str
    process_creation_authorization_lease_id: str
    process_creation_authorization_lease_digest: str
    process_creation_authorization_claim_id: str
    process_creation_authorization_claim_digest: str
    process_creation_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingStateAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    process_creation_result_id: str
    process_creation_result_digest: str
    process_creation_consumption_id: str
    process_creation_attempt_id: str
    process_creation_attempt_digest: str
    process_creation_claim_id: str
    process_creation_claim_digest: str
    process_creation_authorization_lease_id: str
    process_creation_authorization_lease_digest: str
    process_creation_authorization_claim_id: str
    process_creation_authorization_claim_digest: str
    process_creation_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    process_state_eligible_until: datetime
    exact_process_creation_result_confirmed: bool
    terminal_success_confirmed: bool
    metadata_only_confirmed: bool
    process_created_confirmed: bool
    process_sealed_confirmed: bool
    process_suspended_confirmed: bool
    process_not_scheduled_confirmed: bool
    process_not_resumed_confirmed: bool
    process_not_dispatched_confirmed: bool
    process_not_executed_confirmed: bool
    runtime_envelope_current: bool
    destination_generation_current: bool
    destination_fence_current: bool
    protected_slot_generation_current: bool
    prior_process_scheduling_claim_absent: bool
    prior_process_scheduling_lease_absent: bool
    scheduling_performed: bool
    resume_performed: bool
    dispatch_performed: bool
    execution_performed: bool
    network_activity_performed: bool
    connector_activity_performed: bool
    mcp_activity_performed: bool
    provider_activity_performed: bool
    infrastructure_mutation_performed: bool
    process_locator_included: bool
    process_identifier_included: bool
    process_material_included: bool
    runtime_material_included: bool
    command_material_included: bool
    argument_material_included: bool
    environment_material_included: bool
    prompt_material_included: bool
    model_material_included: bool
    endpoint_material_included: bool
    credential_material_included: bool
    secret_material_included: bool
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


class WorkflowProtectedRuntimeProcessSchedulingStateAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_process_scheduling_state(
        self, request: WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingStateAttestation: ...


class WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier(Protocol):
    def verify_runtime_process_scheduling_state_attestation(
        self, attestation: WorkflowProtectedRuntimeProcessSchedulingStateAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest:
    process_creation_result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier
    offline_process_creation_receipt_signature_verifier: (
        WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest:
    process_creation_result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource
    process_state_attestation: WorkflowProtectedRuntimeProcessSchedulingStateAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier
    offline_process_creation_receipt_signature_verifier: (
        WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim
    candidate: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState
    protected_runtime_process_scheduling_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(evaluated_at=self.evaluated_at, consumed=self.consumed)
        expected = (
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected
            or self.protected_runtime_process_scheduling_authority_granted is not active
        ):
            raise ValueError(
                "runtime process-scheduling authorization presentation is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventory:
    server_time: datetime
    presentations: tuple[WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation, ...]

    def __post_init__(self) -> None:
        if self.server_time.tzinfo is None or any(
            presentation.evaluated_at != self.server_time for presentation in self.presentations
        ):
            raise ValueError(
                "runtime process-scheduling authorization inventory has inconsistent time"
            )


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_process_scheduling_authorization(
        self, request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult: ...

    async def get_protected_runtime_process_scheduling_authorization_source(
        self, request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource | None: ...

    async def authorize_protected_runtime_process_scheduling(
        self, request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult: ...

    async def list_protected_runtime_process_scheduling_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_process_scheduling_authorization_request(
    request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest,
) -> None:
    source = request.source
    attestation = request.process_state_attestation
    candidate = request.candidate
    claim = request.candidate_claim
    policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    source_policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    confirmations = (
        attestation.exact_process_creation_result_confirmed,
        attestation.terminal_success_confirmed,
        attestation.metadata_only_confirmed,
        attestation.process_created_confirmed,
        attestation.process_sealed_confirmed,
        attestation.process_suspended_confirmed,
        attestation.process_not_scheduled_confirmed,
        attestation.process_not_resumed_confirmed,
        attestation.process_not_dispatched_confirmed,
        attestation.process_not_executed_confirmed,
        attestation.runtime_envelope_current,
        attestation.destination_generation_current,
        attestation.destination_fence_current,
        attestation.protected_slot_generation_current,
        attestation.prior_process_scheduling_claim_absent,
        attestation.prior_process_scheduling_lease_absent,
    )
    forbidden = (
        attestation.scheduling_performed,
        attestation.resume_performed,
        attestation.dispatch_performed,
        attestation.execution_performed,
        attestation.network_activity_performed,
        attestation.connector_activity_performed,
        attestation.mcp_activity_performed,
        attestation.provider_activity_performed,
        attestation.infrastructure_mutation_performed,
        attestation.process_locator_included,
        attestation.process_identifier_included,
        attestation.process_material_included,
        attestation.runtime_material_included,
        attestation.command_material_included,
        attestation.argument_material_included,
        attestation.environment_material_included,
        attestation.prompt_material_included,
        attestation.model_material_included,
        attestation.endpoint_material_included,
        attestation.credential_material_included,
        attestation.secret_material_included,
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
        or attestation.process_creation_profile_id != source_policy.process_creation_profile_id
        or attestation.process_creation_profile_version
        != source_policy.process_creation_profile_version
        or attestation.process_creation_profile_digest
        != source_policy.process_creation_profile_digest
        or attestation.primitive_id != source_policy.primitive_id
        or attestation.primitive_version != source_policy.primitive_version
        or attestation.primitive_digest != source_policy.primitive_digest
        or attestation.scheduling_profile_id != policy.scheduling_profile_id
        or attestation.scheduling_profile_version != policy.scheduling_profile_version
        or attestation.scheduling_profile_digest != policy.scheduling_profile_digest
        or any(
            value.tzinfo is None
            for value in (
                request.pre_attestation_observed_at,
                request.requested_at,
                attestation.observed_at,
                attestation.valid_until,
                attestation.process_state_eligible_until,
            )
        )
        or not source.result.recorded_at
        <= request.pre_attestation_observed_at
        <= attestation.observed_at
        <= request.requested_at
        < attestation.valid_until
        <= attestation.process_state_eligible_until
        or attestation.valid_until - attestation.observed_at
        > timedelta(seconds=policy.maximum_attestation_freshness_seconds)
        or attestation.attestor_id != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_ID
        or attestation.attestor_version
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_VERSION
        or attestation.signing_key_id
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTATION_SIGNING_KEY_ID
        or not all(confirmations)
        or any(forbidden)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_runtime_process_scheduling_state_attestation(  # noqa: E501
            attestation
        )
        or not request.offline_process_creation_receipt_signature_verifier.verify_receipt(
            source.process_creation_receipt
        )
        or not workflow_protected_runtime_process_scheduling_receipt_matches_source(source)
        or not _attestation_matches_source(attestation, source)
        or candidate.process_creation_result_id != source.result.result_id
        or candidate.process_creation_result_digest != source.result.canonical_digest
        or candidate.process_state_attestation_id != attestation.attestation_id
        or candidate.process_state_attestation_digest != attestation.canonical_digest
        or candidate.process_state_attestation_valid_until != attestation.valid_until
        or candidate.process_state_eligible_until != attestation.process_state_eligible_until
        or candidate.attestation_metadata_only is not True
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or claim.process_creation_result_id != source.result.result_id
        or claim.process_creation_result_digest != source.result.canonical_digest
        or claim.claimed_at != request.requested_at
        or candidate.claim_id != claim.claim_id
        or candidate.claim_digest != claim.canonical_digest
        or candidate.canonical_digest != canonical_digest(candidate.digest_payload())
        or claim.canonical_digest != canonical_digest(claim.digest_payload())
    ):
        raise ValueError("runtime process-scheduling authorization evidence is invalid")


def _attestation_matches_source(
    attestation: WorkflowProtectedRuntimeProcessSchedulingStateAttestation,
    source: WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource,
) -> bool:
    result = source.result
    attempt = source.attempt
    claim = source.process_creation_claim
    lease = source.process_creation_authorization_lease
    authorization_claim = source.process_creation_authorization_claim
    receipt = source.process_creation_receipt
    return (
        attestation.process_creation_result_id == result.result_id
        and attestation.process_creation_result_digest == result.canonical_digest
        and attestation.process_creation_consumption_id
        == result.consumption_id
        == attempt.consumption_id
        == claim.consumption_id
        and attestation.process_creation_attempt_id == result.attempt_id == attempt.attempt_id
        and attestation.process_creation_attempt_digest
        == result.attempt_digest
        == attempt.canonical_digest
        and attestation.process_creation_claim_id == result.claim_id == claim.claim_id
        and attestation.process_creation_claim_digest
        == result.claim_digest
        == claim.canonical_digest
        and attestation.process_creation_authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        == claim.authorization_lease_id
        == lease.authorization_lease_id
        and attestation.process_creation_authorization_lease_digest
        == result.authorization_lease_digest
        == attempt.authorization_lease_digest
        == claim.authorization_lease_digest
        == lease.canonical_digest
        and attestation.process_creation_authorization_claim_id
        == lease.claim_id
        == authorization_claim.claim_id
        and attestation.process_creation_authorization_claim_digest
        == lease.claim_digest
        == authorization_claim.canonical_digest
        and attestation.process_creation_receipt_digest
        == result.receipt_digest
        == receipt.canonical_digest
        and attestation.destination_deployment_id == result.scope.site_id
        and attestation.destination_generation == attempt.runtime_envelope_generation
        and attestation.destination_fencing_token_digest == attempt.runtime_envelope_commitment
        and attestation.protected_slot_commitment == attempt.runtime_envelope_commitment
        and attestation.protected_slot_generation == attempt.runtime_envelope_generation
        and attestation.runtime_envelope_id
        == result.runtime_envelope_id
        == attempt.runtime_envelope_id
        and attestation.runtime_envelope_commitment
        == result.runtime_envelope_commitment
        == attempt.runtime_envelope_commitment
        and attestation.runtime_envelope_generation
        == result.runtime_envelope_generation
        == attempt.runtime_envelope_generation
        and attestation.process_creation_profile_id == result.process_creation_profile_id
        and attestation.process_creation_profile_version == result.process_creation_profile_version
        and attestation.process_creation_profile_digest == result.process_creation_profile_digest
        and attestation.primitive_id == result.primitive_id == attempt.primitive_id
        and attestation.primitive_version == result.primitive_version == attempt.primitive_version
        and attestation.primitive_digest == result.primitive_digest == attempt.primitive_digest
        and attestation.scope == result.scope == attempt.scope
    )


def workflow_protected_runtime_process_scheduling_receipt_matches_source(
    source: WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource,
) -> bool:
    """Bind the signed ADR-178 receipt to the exact terminal result and locked attempt."""

    receipt = source.process_creation_receipt
    result = source.result
    attempt = source.attempt
    source_policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    return (
        receipt.consumption_id == result.consumption_id == attempt.consumption_id
        and receipt.attempt_id == result.attempt_id == attempt.attempt_id
        and receipt.authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        and receipt.runtime_envelope_id == result.runtime_envelope_id == attempt.runtime_envelope_id
        and receipt.runtime_envelope_commitment
        == result.runtime_envelope_commitment
        == attempt.runtime_envelope_commitment
        and receipt.runtime_envelope_generation
        == result.runtime_envelope_generation
        == attempt.runtime_envelope_generation
        and receipt.process_creation_profile_id
        == result.process_creation_profile_id
        == attempt.process_creation_profile_id
        and receipt.process_creation_profile_version
        == result.process_creation_profile_version
        == attempt.process_creation_profile_version
        and receipt.process_creation_profile_digest
        == result.process_creation_profile_digest
        == attempt.process_creation_profile_digest
        and receipt.primitive_id == result.primitive_id == attempt.primitive_id
        and receipt.primitive_version == result.primitive_version == attempt.primitive_version
        and receipt.primitive_digest == result.primitive_digest == attempt.primitive_digest
        and receipt.request_nonce_digest == attempt.request_nonce_digest
        and receipt.result_state is result.result_state
        and receipt.process_created is result.process_created is True
        and receipt.process_sealed is result.process_sealed is True
        and receipt.process_suspended is result.process_suspended is True
        and receipt.process_scheduled is result.process_scheduled is False
        and receipt.process_resumed is result.process_resumed is False
        and receipt.process_dispatched is result.process_dispatched is False
        and receipt.process_executed is result.process_executed is False
        and receipt.runtime_locator_returned is False
        and receipt.process_identifier_returned is False
        and receipt.caller_material_used is False
        and receipt.network_activity_performed is False
        and receipt.model_activity_performed is False
        and receipt.mcp_activity_performed is False
        and receipt.connector_activity_performed is False
        and receipt.provider_activity_performed is False
        and receipt.infrastructure_mutation_performed is False
        and receipt.creator_contract_id == attempt.creator_contract_id
        and receipt.creator_contract_version == attempt.creator_contract_version
        and receipt.creator_id == attempt.creator_id
        and receipt.creator_version == attempt.creator_version
        and receipt.signing_key_id
        == attempt.receipt_verification_signing_key_id
        == source_policy.receipt_verification_signing_key_id
        and receipt.signature_algorithm == source_policy.receipt_signature_algorithm
        and receipt.completed_at == result.completed_at
        and result.receipt_digest == receipt.canonical_digest
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
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationError",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventory",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource",
    "WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest",
    "WorkflowProtectedRuntimeProcessSchedulingStateAttestation",
    "WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest",
    "WorkflowProtectedRuntimeProcessSchedulingStateAttestor",
    "WorkflowProtectedRuntimeProcessSchedulingStateSignatureVerifier",
    "validate_workflow_protected_runtime_process_scheduling_authorization_request",
    "workflow_protected_runtime_process_scheduling_receipt_matches_source",
]
