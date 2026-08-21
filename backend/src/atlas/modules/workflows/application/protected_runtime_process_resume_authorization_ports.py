from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_resume_authorization_domain import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationClaim,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
    code_owned_workflow_protected_runtime_process_resume_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingAttempt,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
    WorkflowProtectedRuntimeProcessSchedulingReceipt,
    WorkflowProtectedRuntimeProcessSchedulingResult,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID = (
    "attestor.workflow-protected-runtime-process-resume-state"
)
WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION = "1.0"
WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-process-resume-state.v1"
)


class WorkflowProtectedRuntimeProcessResumeAuthorizationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus(StrEnum):
    NONE = "none"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


class WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationSource:
    """One canonical terminal ADR-180 success and its complete immutable lineage."""

    result: WorkflowProtectedRuntimeProcessSchedulingResult
    attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt
    process_scheduling_claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim
    process_scheduling_receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt
    process_scheduling_authorization_lease: (
        WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease
    )
    process_scheduling_authorization_claim: (
        WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeStateAttestationRequest:
    process_scheduling_result_id: str
    process_scheduling_result_digest: str
    process_scheduling_consumption_id: str
    process_scheduling_attempt_id: str
    process_scheduling_attempt_digest: str
    process_scheduling_claim_id: str
    process_scheduling_claim_digest: str
    process_scheduling_authorization_lease_id: str
    process_scheduling_authorization_lease_digest: str
    process_scheduling_authorization_claim_id: str
    process_scheduling_authorization_claim_digest: str
    process_scheduling_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_scheduling_profile_id: str
    process_scheduling_profile_version: str
    process_scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    resume_profile_id: str
    resume_profile_version: str
    resume_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeStateAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    process_scheduling_result_id: str
    process_scheduling_result_digest: str
    process_scheduling_consumption_id: str
    process_scheduling_attempt_id: str
    process_scheduling_attempt_digest: str
    process_scheduling_claim_id: str
    process_scheduling_claim_digest: str
    process_scheduling_authorization_lease_id: str
    process_scheduling_authorization_lease_digest: str
    process_scheduling_authorization_claim_id: str
    process_scheduling_authorization_claim_digest: str
    process_scheduling_receipt_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_scheduling_profile_id: str
    process_scheduling_profile_version: str
    process_scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    resume_profile_id: str
    resume_profile_version: str
    resume_profile_digest: str
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
    exact_process_scheduling_result_confirmed: bool
    terminal_success_confirmed: bool
    metadata_only_confirmed: bool
    process_created_confirmed: bool
    process_sealed_confirmed: bool
    process_suspended_confirmed: bool
    process_scheduled_confirmed: bool
    process_not_runnable_confirmed: bool
    process_not_resumed_confirmed: bool
    process_not_dispatched_confirmed: bool
    process_not_executed_confirmed: bool
    runtime_envelope_current: bool
    destination_generation_current: bool
    destination_fence_current: bool
    protected_slot_generation_current: bool
    prior_process_resume_claim_absent: bool
    prior_process_resume_lease_absent: bool
    pending_or_conflicting_resume_absent: bool
    pending_or_conflicting_dispatch_absent: bool
    pending_or_conflicting_execution_absent: bool
    pending_or_conflicting_supervision_absent: bool
    pending_or_conflicting_stop_absent: bool
    pending_or_conflicting_cleanup_absent: bool
    pending_or_conflicting_replacement_absent: bool
    pending_or_conflicting_rescheduling_absent: bool
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


class WorkflowProtectedRuntimeProcessResumeStateAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_process_resume_state(
        self, request: WorkflowProtectedRuntimeProcessResumeStateAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessResumeStateAttestation: ...


class WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier(Protocol):
    def verify_runtime_process_resume_state_attestation(
        self, attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest:
    process_scheduling_result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    offline_signature_verifier: WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier
    offline_process_scheduling_receipt_signature_verifier: (
        WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult:
    status: WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus
    lease: WorkflowProtectedRuntimeProcessResumeAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest:
    process_scheduling_result_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest:
    source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource
    process_state_attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier
    offline_process_scheduling_receipt_signature_verifier: (
        WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
    )
    expected_policy_digest: str
    expected_validity_window_seconds: int
    expected_minimum_remaining_safety_margin_milliseconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    pre_attestation_observed_at: datetime
    requested_at: datetime
    candidate_claim: WorkflowProtectedRuntimeProcessResumeAuthorizationClaim
    candidate: WorkflowProtectedRuntimeProcessResumeAuthorizationLease
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult:
    status: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus
    lease: WorkflowProtectedRuntimeProcessResumeAuthorizationLease | None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation:
    lease: WorkflowProtectedRuntimeProcessResumeAuthorizationLease
    consumed: bool
    evaluated_at: datetime
    effective_state: WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState
    protected_runtime_process_resume_authority_granted: bool

    def __post_init__(self) -> None:
        active = self.lease.is_active(evaluated_at=self.evaluated_at, consumed=self.consumed)
        expected = (
            WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState.ACTIVE
            if active
            else WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState.EXPIRED
        )
        if (
            self.effective_state is not expected
            or self.protected_runtime_process_resume_authority_granted is not active
        ):
            raise ValueError("runtime process-resume authorization presentation is inconsistent")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationInventory:
    server_time: datetime
    presentations: tuple[WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation, ...]

    def __post_init__(self) -> None:
        if self.server_time.tzinfo is None or any(
            presentation.evaluated_at != self.server_time for presentation in self.presentations
        ):
            raise ValueError("runtime process-resume authorization inventory has inconsistent time")


class WorkflowProtectedRuntimeProcessResumeAuthorizationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def preflight_protected_runtime_process_resume_authorization(
        self, request: WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult: ...

    async def get_protected_runtime_process_resume_authorization_source(
        self, request: WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationSource | None: ...

    async def authorize_protected_runtime_process_resume(
        self, request: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult: ...

    async def list_protected_runtime_process_resume_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation, ...]: ...


def validate_workflow_protected_runtime_process_resume_authorization_request(
    request: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest,
) -> None:
    source = request.source
    attestation = request.process_state_attestation
    candidate = request.candidate
    claim = request.candidate_claim
    policy = code_owned_workflow_protected_runtime_process_resume_authorization_policy()
    source_policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    minimum_remaining_safety_margin = timedelta(
        milliseconds=policy.minimum_remaining_safety_margin_milliseconds
    )
    confirmations = (
        attestation.exact_process_scheduling_result_confirmed,
        attestation.terminal_success_confirmed,
        attestation.metadata_only_confirmed,
        attestation.process_created_confirmed,
        attestation.process_sealed_confirmed,
        attestation.process_suspended_confirmed,
        attestation.process_scheduled_confirmed,
        attestation.process_not_runnable_confirmed,
        attestation.process_not_resumed_confirmed,
        attestation.process_not_dispatched_confirmed,
        attestation.process_not_executed_confirmed,
        attestation.runtime_envelope_current,
        attestation.destination_generation_current,
        attestation.destination_fence_current,
        attestation.protected_slot_generation_current,
        attestation.prior_process_resume_claim_absent,
        attestation.prior_process_resume_lease_absent,
        attestation.pending_or_conflicting_resume_absent,
        attestation.pending_or_conflicting_dispatch_absent,
        attestation.pending_or_conflicting_execution_absent,
        attestation.pending_or_conflicting_supervision_absent,
        attestation.pending_or_conflicting_stop_absent,
        attestation.pending_or_conflicting_cleanup_absent,
        attestation.pending_or_conflicting_replacement_absent,
        attestation.pending_or_conflicting_rescheduling_absent,
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
        or request.expected_minimum_remaining_safety_margin_milliseconds
        != policy.minimum_remaining_safety_margin_milliseconds
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
        or attestation.process_scheduling_profile_id != source_policy.scheduling_profile_id
        or attestation.process_scheduling_profile_version
        != source_policy.scheduling_profile_version
        or attestation.process_scheduling_profile_digest != source_policy.scheduling_profile_digest
        or attestation.primitive_id != source_policy.primitive_id
        or attestation.primitive_version != source_policy.primitive_version
        or attestation.primitive_digest != source_policy.primitive_digest
        or attestation.resume_profile_id != policy.resume_profile_id
        or attestation.resume_profile_version != policy.resume_profile_version
        or attestation.resume_profile_digest != policy.resume_profile_digest
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
        or request.requested_at + minimum_remaining_safety_margin > attestation.valid_until
        or request.requested_at + minimum_remaining_safety_margin
        > attestation.process_state_eligible_until
        or attestation.valid_until - attestation.observed_at
        > timedelta(seconds=policy.maximum_attestation_freshness_seconds)
        or attestation.attestor_id != WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID
        or attestation.attestor_version
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION
        or attestation.signing_key_id
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID
        or not all(confirmations)
        or any(forbidden)
        or not attestation.integrity_signature
        or any(character.isspace() for character in attestation.integrity_signature)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_signature_verifier.verify_runtime_process_resume_state_attestation(
            attestation
        )
        or not request.offline_process_scheduling_receipt_signature_verifier.verify_receipt(
            source.process_scheduling_receipt
        )
        or not workflow_protected_runtime_process_resume_receipt_matches_source(source)
        or not _attestation_matches_source(attestation, source)
        or candidate.process_scheduling_result_id != source.result.result_id
        or candidate.process_scheduling_result_digest != source.result.canonical_digest
        or candidate.process_state_attestation_id != attestation.attestation_id
        or candidate.process_state_attestation_digest != attestation.canonical_digest
        or candidate.process_state_attestation_valid_until != attestation.valid_until
        or candidate.process_state_eligible_until != attestation.process_state_eligible_until
        or candidate.attestation_metadata_only is not True
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or candidate.valid_until - candidate.issued_at < minimum_remaining_safety_margin
        or candidate.effective_until - candidate.issued_at < minimum_remaining_safety_margin
        or claim.process_scheduling_result_id != source.result.result_id
        or claim.process_scheduling_result_digest != source.result.canonical_digest
        or claim.claimed_at != request.requested_at
        or candidate.claim_id != claim.claim_id
        or candidate.claim_digest != claim.canonical_digest
        or candidate.canonical_digest != canonical_digest(candidate.digest_payload())
        or claim.canonical_digest != canonical_digest(claim.digest_payload())
    ):
        raise ValueError("runtime process-resume authorization evidence is invalid")


def _attestation_matches_source(
    attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation,
    source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
) -> bool:
    result = source.result
    attempt = source.attempt
    claim = source.process_scheduling_claim
    lease = source.process_scheduling_authorization_lease
    authorization_claim = source.process_scheduling_authorization_claim
    receipt = source.process_scheduling_receipt
    return (
        attestation.process_scheduling_result_id == result.result_id
        and attestation.process_scheduling_result_digest == result.canonical_digest
        and attestation.process_scheduling_consumption_id
        == result.consumption_id
        == attempt.consumption_id
        == claim.consumption_id
        and attestation.process_scheduling_attempt_id == result.attempt_id == attempt.attempt_id
        and attestation.process_scheduling_attempt_digest
        == result.attempt_digest
        == attempt.canonical_digest
        and attestation.process_scheduling_claim_id == result.claim_id == claim.claim_id
        and attestation.process_scheduling_claim_digest
        == result.claim_digest
        == claim.canonical_digest
        and attestation.process_scheduling_authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        == claim.authorization_lease_id
        == lease.authorization_lease_id
        and attestation.process_scheduling_authorization_lease_digest
        == result.authorization_lease_digest
        == attempt.authorization_lease_digest
        == claim.authorization_lease_digest
        == lease.canonical_digest
        and attestation.process_scheduling_authorization_claim_id
        == lease.claim_id
        == authorization_claim.claim_id
        and attestation.process_scheduling_authorization_claim_digest
        == lease.claim_digest
        == authorization_claim.canonical_digest
        and attestation.process_scheduling_receipt_digest
        == result.receipt_digest
        == receipt.canonical_digest
        and attestation.destination_deployment_id == result.scope.site_id
        and attestation.destination_generation == lease.destination_generation
        and attestation.destination_fencing_token_digest == lease.destination_fencing_token_digest
        and attestation.protected_slot_commitment == lease.protected_slot_commitment
        and attestation.protected_slot_generation == lease.protected_slot_generation
        and attestation.runtime_envelope_id == lease.runtime_envelope_id
        and attestation.runtime_envelope_commitment == lease.runtime_envelope_commitment
        and attestation.runtime_envelope_generation == lease.runtime_envelope_generation
        and attestation.process_scheduling_profile_id == result.scheduling_profile_id
        and attestation.process_scheduling_profile_version == result.scheduling_profile_version
        and attestation.process_scheduling_profile_digest == result.scheduling_profile_digest
        and attestation.primitive_id == result.primitive_id == attempt.primitive_id
        and attestation.primitive_version == result.primitive_version == attempt.primitive_version
        and attestation.primitive_digest == result.primitive_digest == attempt.primitive_digest
        and attestation.scope == result.scope == attempt.scope
    )


def workflow_protected_runtime_process_resume_receipt_matches_source(
    source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
) -> bool:
    """Bind the signed ADR-180 receipt to the exact terminal result and locked attempt."""

    receipt = source.process_scheduling_receipt
    result = source.result
    attempt = source.attempt
    source_policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    return (
        receipt.consumption_id == result.consumption_id == attempt.consumption_id
        and receipt.attempt_id == result.attempt_id == attempt.attempt_id
        and receipt.authorization_lease_id
        == result.authorization_lease_id
        == attempt.authorization_lease_id
        and receipt.scheduling_profile_id
        == result.scheduling_profile_id
        == attempt.scheduling_profile_id
        and receipt.scheduling_profile_version
        == result.scheduling_profile_version
        == attempt.scheduling_profile_version
        and receipt.scheduling_profile_digest
        == result.scheduling_profile_digest
        == attempt.scheduling_profile_digest
        and receipt.primitive_id == result.primitive_id == attempt.primitive_id
        and receipt.primitive_version == result.primitive_version == attempt.primitive_version
        and receipt.primitive_digest == result.primitive_digest == attempt.primitive_digest
        and receipt.request_nonce_digest == attempt.request_nonce_digest
        and receipt.result_state is result.result_state
        and receipt.process_suspended is result.process_suspended is True
        and receipt.process_scheduled is result.process_scheduled is True
        and receipt.process_runnable is result.process_runnable is False
        and receipt.process_resumed is result.process_resumed is False
        and receipt.process_dispatched is result.process_dispatched is False
        and receipt.process_executed is result.process_executed is False
        and receipt.process_locator_returned is False
        and receipt.process_identifier_returned is False
        and receipt.queue_or_priority_returned is False
        and receipt.caller_material_used is False
        and receipt.network_activity_performed is False
        and receipt.model_activity_performed is False
        and receipt.mcp_activity_performed is False
        and receipt.connector_activity_performed is False
        and receipt.provider_activity_performed is False
        and receipt.infrastructure_mutation_performed is False
        and receipt.scheduler_contract_id == attempt.scheduler_contract_id
        and receipt.scheduler_contract_version == attempt.scheduler_contract_version
        and receipt.scheduler_id == attempt.scheduler_id
        and receipt.scheduler_version == attempt.scheduler_version
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
    "WorkflowProtectedRuntimeProcessResumeAuthorizationError",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationInventory",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationRepository",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationSource",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest",
    "WorkflowProtectedRuntimeProcessResumeStateAttestation",
    "WorkflowProtectedRuntimeProcessResumeStateAttestationRequest",
    "WorkflowProtectedRuntimeProcessResumeStateAttestor",
    "WorkflowProtectedRuntimeProcessResumeStateSignatureVerifier",
    "validate_workflow_protected_runtime_process_resume_authorization_request",
    "workflow_protected_runtime_process_resume_receipt_matches_source",
]
