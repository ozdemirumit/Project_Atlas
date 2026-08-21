from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeProcessSchedulingAttempt,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
    WorkflowProtectedRuntimeProcessSchedulingInstruction,
    WorkflowProtectedRuntimeProcessSchedulingInvocation,
    WorkflowProtectedRuntimeProcessSchedulingReceipt,
    WorkflowProtectedRuntimeProcessSchedulingResult,
    WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)


class WorkflowProtectedRuntimeProcessSchedulingConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus(StrEnum):
    NONE = "none"
    ATTEMPT_PENDING = "attempt_pending"
    ATTEMPT_UNCERTAIN = "attempt_uncertain"
    TERMINAL = "terminal"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_PENDING = "replay_pending"
    REPLAY_UNCERTAIN = "replay_uncertain"
    REPLAY_TERMINAL = "replay_terminal"
    LEASE_EXPIRED = "lease_expired"
    LEASE_CONSUMED = "lease_consumed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingConsumptionSource:
    authorization_lease: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease
    authorization_claim: WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim


class WorkflowProtectedRuntimeProcessSchedulingInstructionSigner(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def signing_key_id(self) -> str: ...

    @property
    def signature_algorithm(self) -> str: ...

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str: ...


class WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope
    ) -> bool: ...


class WorkflowProtectedRuntimeProcessScheduler(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def scheduler_contract_id(self) -> str: ...

    @property
    def scheduler_contract_version(self) -> str: ...

    @property
    def scheduler_id(self) -> str: ...

    @property
    def scheduler_version(self) -> str: ...

    @property
    def scheduling_profile_id(self) -> str: ...

    @property
    def scheduling_profile_version(self) -> str: ...

    @property
    def scheduling_profile_digest(self) -> str: ...

    @property
    def primitive_id(self) -> str: ...

    @property
    def primitive_version(self) -> str: ...

    @property
    def primitive_digest(self) -> str: ...

    async def schedule_suspended_process(
        self, invocation: WorkflowProtectedRuntimeProcessSchedulingInvocation
    ) -> WorkflowProtectedRuntimeProcessSchedulingReceipt: ...


class WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest:
    authorization_lease_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    consumption_id: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingReplayLookup:
    status: WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus
    attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt | None = None
    result: WorkflowProtectedRuntimeProcessSchedulingResult | None = None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingClaimRequest:
    source: WorkflowProtectedRuntimeProcessSchedulingConsumptionSource
    candidate_claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim
    candidate_attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt
    signed_instruction_envelope: WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope
    offline_instruction_signature_verifier: (
        WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    minimum_invocation_margin_milliseconds: int
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingClaimWrite:
    status: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus
    claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim | None = None
    attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt | None = None
    result: WorkflowProtectedRuntimeProcessSchedulingResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingResultRequest:
    result: WorkflowProtectedRuntimeProcessSchedulingResult
    receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingResultWrite:
    status: WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus
    result: WorkflowProtectedRuntimeProcessSchedulingResult


class WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_runtime_process_scheduling_replay(
        self, request: WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingReplayLookup: ...

    async def get_protected_runtime_process_scheduling_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionSource | None: ...

    async def claim_protected_runtime_process_scheduling(
        self, request: WorkflowProtectedRuntimeProcessSchedulingClaimRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingClaimWrite: ...

    async def record_protected_runtime_process_scheduling_result(
        self, request: WorkflowProtectedRuntimeProcessSchedulingResultRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingResultWrite: ...

    async def list_protected_runtime_process_scheduling_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeProcessSchedulingAttempt, ...]: ...

    async def get_protected_runtime_process_scheduling_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeProcessSchedulingResult, ...]: ...


def build_workflow_protected_runtime_process_scheduling_instruction(
    attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt,
) -> WorkflowProtectedRuntimeProcessSchedulingInstruction:
    values = {
        name: getattr(attempt, name)
        for name in (
            "consumption_id",
            "attempt_id",
            "claim_id",
            "claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_operation_reference",
            "scheduling_profile_id",
            "scheduling_profile_version",
            "scheduling_profile_digest",
            "primitive_id",
            "primitive_version",
            "primitive_digest",
            "scheduler_contract_id",
            "scheduler_contract_version",
            "scheduler_id",
            "scheduler_version",
            "request_nonce_digest",
            "scope",
            "policy_id",
            "policy_version",
            "policy_digest",
            "started_at",
            "invocation_deadline",
        )
    }
    values["attempt_digest"] = attempt.canonical_digest
    return WorkflowProtectedRuntimeProcessSchedulingInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def build_workflow_protected_runtime_process_scheduling_signed_instruction_envelope(
    instruction: WorkflowProtectedRuntimeProcessSchedulingInstruction,
    signer: WorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
) -> WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope:
    if (
        not signer.available
        or signer.signing_key_id
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNING_KEY_ID
        or signer.signature_algorithm
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM
    ):
        raise WorkflowProtectedRuntimeProcessSchedulingConsumptionError(
            "protected_runtime_process_scheduling_instruction_signer_invalid"
        )
    signature_payload = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": signer.signing_key_id,
        "signature_algorithm": signer.signature_algorithm,
    }
    signature = signer.sign_instruction_envelope_digest(canonical_digest(signature_payload))
    values = signature_payload | {"integrity_signature": signature}
    return WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=signer.signing_key_id,
        signature_algorithm=signer.signature_algorithm,
        integrity_signature=signature,
        canonical_digest=canonical_digest(values),
    )


def build_workflow_protected_runtime_process_scheduling_invocation(
    envelope: WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope,
) -> WorkflowProtectedRuntimeProcessSchedulingInvocation:
    instruction = envelope.instruction
    return WorkflowProtectedRuntimeProcessSchedulingInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        invocation_deadline=instruction.invocation_deadline,
        signed_instruction_envelope=envelope,
    )


def validate_workflow_protected_runtime_process_scheduling_claim_request(
    request: WorkflowProtectedRuntimeProcessSchedulingClaimRequest,
) -> None:
    policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    source_policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    lease = request.source.authorization_lease
    source_claim = request.source.authorization_claim
    claim = request.candidate_claim
    attempt = request.candidate_attempt
    instruction = request.signed_instruction_envelope.instruction
    if (
        request.expected_policy_id != policy.policy_id
        or request.expected_policy_version != policy.policy_version
        or request.expected_policy_digest != policy.canonical_digest
        or request.minimum_invocation_margin_milliseconds
        != policy.minimum_invocation_margin_milliseconds
        or lease.policy_id != source_policy.policy_id
        or lease.policy_version != source_policy.policy_version
        or lease.policy_digest != source_policy.canonical_digest
        or lease.state
        is not (
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState
        ).AUTHORIZED_UNCONSUMED
        or not lease.is_active(evaluated_at=claim.claimed_at)
        or claim.claimed_at + timedelta(milliseconds=request.minimum_invocation_margin_milliseconds)
        >= lease.valid_until
        or lease.claim_id != source_claim.claim_id
        or lease.claim_digest != source_claim.canonical_digest
        or lease.authority.protected_runtime_process_scheduling_authority_granted is not True
        or source_claim.authority.protected_runtime_process_scheduling_authority_granted
        is not False
        or lease.scheduling_profile_digest != policy.scheduling_profile_digest
        or claim.authorization_lease_id != lease.authorization_lease_id
        or claim.authorization_lease_digest != lease.canonical_digest
        or claim.authorization_claim_id != source_claim.claim_id
        or claim.authorization_claim_digest != source_claim.canonical_digest
        or claim.scope != lease.scope
        or claim.consumer_subject_id != lease.consumer_subject_id
        or claim.consumer_audience != lease.consumer_audience
        or claim.consumer_contract_id != lease.consumer_contract_id
        or claim.consumer_contract_version != lease.consumer_contract_version
        or claim.claim_id != attempt.claim_id
        or claim.canonical_digest != attempt.claim_digest
        or claim.attempt_id != attempt.attempt_id
        or claim.consumption_id != attempt.consumption_id
        or claim.idempotency_digest != request.idempotency_digest
        or claim.request_fingerprint != request.request_fingerprint
        or instruction.attempt_id != attempt.attempt_id
        or instruction.attempt_digest != attempt.canonical_digest
        or instruction.claim_digest != claim.canonical_digest
        or instruction.invocation_deadline > lease.valid_until
        or not request.offline_instruction_signature_verifier.verify_instruction_envelope(
            request.signed_instruction_envelope
        )
    ):
        raise WorkflowProtectedRuntimeProcessSchedulingConsumptionError(
            "protected_runtime_process_scheduling_claim_request_invalid"
        )


def _canonical_mapping(values: dict[str, object]) -> dict[str, object]:
    return {name: _canonical_value(value) for name, value in values.items()}


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    if hasattr(value, "digest_payload") and hasattr(value, "canonical_digest"):
        return value.digest_payload() | {"canonical_digest": value.canonical_digest}
    return value


__all__ = [
    "WorkflowProtectedRuntimeProcessScheduler",
    "WorkflowProtectedRuntimeProcessSchedulingClaimRequest",
    "WorkflowProtectedRuntimeProcessSchedulingClaimWrite",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionError",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionRepository",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionSource",
    "WorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier",
    "WorkflowProtectedRuntimeProcessSchedulingInstructionSigner",
    "WorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier",
    "WorkflowProtectedRuntimeProcessSchedulingReplayLookup",
    "WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest",
    "WorkflowProtectedRuntimeProcessSchedulingResultRequest",
    "WorkflowProtectedRuntimeProcessSchedulingResultWrite",
    "WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus",
    "build_workflow_protected_runtime_process_scheduling_instruction",
    "build_workflow_protected_runtime_process_scheduling_invocation",
    "build_workflow_protected_runtime_process_scheduling_signed_instruction_envelope",
    "validate_workflow_protected_runtime_process_scheduling_claim_request",
]
