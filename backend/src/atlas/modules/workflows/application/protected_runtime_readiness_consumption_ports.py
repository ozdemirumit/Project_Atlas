from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationClaim,
    WorkflowProtectedRuntimeReadinessAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeReadinessAttempt,
    WorkflowProtectedRuntimeReadinessConsumptionClaim,
    WorkflowProtectedRuntimeReadinessInstruction,
    WorkflowProtectedRuntimeReadinessInvocation,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessResult,
    WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)


class WorkflowProtectedRuntimeReadinessConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeReadinessConsumptionReplayStatus(StrEnum):
    NONE = "none"
    ATTEMPT_PENDING = "attempt_pending"
    ATTEMPT_UNCERTAIN = "attempt_uncertain"
    TERMINAL = "terminal"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeReadinessConsumptionClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_PENDING = "replay_pending"
    REPLAY_UNCERTAIN = "replay_uncertain"
    REPLAY_TERMINAL = "replay_terminal"
    LEASE_EXPIRED = "lease_expired"
    LEASE_CONSUMED = "lease_consumed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionSource:
    authorization_lease: WorkflowProtectedRuntimeReadinessAuthorizationLease
    authorization_claim: WorkflowProtectedRuntimeReadinessAuthorizationClaim


class WorkflowProtectedRuntimeReadinessInstructionSigner(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def signing_key_id(self) -> str: ...

    @property
    def signature_algorithm(self) -> str: ...

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str: ...


class WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope
    ) -> bool: ...


class WorkflowProtectedRuntimeReadinessAssessor(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def assessor_contract_id(self) -> str: ...

    @property
    def assessor_contract_version(self) -> str: ...

    @property
    def assessor_id(self) -> str: ...

    @property
    def assessor_version(self) -> str: ...

    @property
    def readiness_profile_id(self) -> str: ...

    @property
    def readiness_profile_version(self) -> str: ...

    @property
    def readiness_profile_digest(self) -> str: ...

    async def assess_runtime_readiness(
        self, invocation: WorkflowProtectedRuntimeReadinessInvocation
    ) -> WorkflowProtectedRuntimeReadinessReceipt: ...


class WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeReadinessReceipt) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest:
    authorization_lease_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    consumption_id: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionReplayLookup:
    status: WorkflowProtectedRuntimeReadinessConsumptionReplayStatus
    attempt: WorkflowProtectedRuntimeReadinessAttempt | None = None
    result: WorkflowProtectedRuntimeReadinessResult | None = None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionClaimRequest:
    source: WorkflowProtectedRuntimeReadinessConsumptionSource
    candidate_claim: WorkflowProtectedRuntimeReadinessConsumptionClaim
    candidate_attempt: WorkflowProtectedRuntimeReadinessAttempt
    signed_instruction_envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope
    offline_instruction_signature_verifier: (
        WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    minimum_invocation_margin_milliseconds: int
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionClaimWrite:
    status: WorkflowProtectedRuntimeReadinessConsumptionClaimStatus
    claim: WorkflowProtectedRuntimeReadinessConsumptionClaim | None = None
    attempt: WorkflowProtectedRuntimeReadinessAttempt | None = None
    result: WorkflowProtectedRuntimeReadinessResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionResultRequest:
    result: WorkflowProtectedRuntimeReadinessResult
    receipt: WorkflowProtectedRuntimeReadinessReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionResultWrite:
    status: WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus
    result: WorkflowProtectedRuntimeReadinessResult | None = None


class WorkflowProtectedRuntimeReadinessConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_runtime_readiness_consumption_replay(
        self, request: WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest
    ) -> WorkflowProtectedRuntimeReadinessConsumptionReplayLookup: ...

    async def get_protected_runtime_readiness_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeReadinessConsumptionSource | None: ...

    async def claim_protected_runtime_readiness_consumption(
        self, request: WorkflowProtectedRuntimeReadinessConsumptionClaimRequest
    ) -> WorkflowProtectedRuntimeReadinessConsumptionClaimWrite: ...

    async def record_protected_runtime_readiness_consumption_result(
        self, request: WorkflowProtectedRuntimeReadinessConsumptionResultRequest
    ) -> WorkflowProtectedRuntimeReadinessConsumptionResultWrite: ...

    async def list_protected_runtime_readiness_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeReadinessAttempt, ...]: ...

    async def get_protected_runtime_readiness_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeReadinessResult, ...]: ...


def build_workflow_protected_runtime_readiness_instruction(
    attempt: WorkflowProtectedRuntimeReadinessAttempt,
) -> WorkflowProtectedRuntimeReadinessInstruction:
    aliases = {"attempt_digest": attempt.canonical_digest}
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeReadinessInstruction):
        if field.name == "canonical_digest":
            continue
        values[field.name] = (
            aliases[field.name] if field.name in aliases else getattr(attempt, field.name)
        )
    return WorkflowProtectedRuntimeReadinessInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def build_workflow_protected_runtime_readiness_signed_instruction_envelope(
    instruction: WorkflowProtectedRuntimeReadinessInstruction,
    signer: WorkflowProtectedRuntimeReadinessInstructionSigner,
) -> WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope:
    if (
        not signer.available
        or signer.signing_key_id != WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID
        or signer.signature_algorithm
        != WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM
    ):
        raise WorkflowProtectedRuntimeReadinessConsumptionError(
            "protected_runtime_readiness_instruction_signer_unavailable"
        )
    signature_payload = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": signer.signing_key_id,
        "signature_algorithm": signer.signature_algorithm,
    }
    signature = signer.sign_instruction_envelope_digest(canonical_digest(signature_payload))
    values = signature_payload | {"integrity_signature": signature}
    return WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=signer.signing_key_id,
        signature_algorithm=signer.signature_algorithm,
        integrity_signature=signature,
        canonical_digest=canonical_digest(values),
    )


def build_workflow_protected_runtime_readiness_invocation(
    envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
) -> WorkflowProtectedRuntimeReadinessInvocation:
    instruction = envelope.instruction
    return WorkflowProtectedRuntimeReadinessInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        invocation_deadline=instruction.invocation_deadline,
        signed_instruction_envelope=envelope,
    )


def validate_workflow_protected_runtime_readiness_consumption_claim_request(
    request: WorkflowProtectedRuntimeReadinessConsumptionClaimRequest,
) -> None:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    lease = request.source.authorization_lease
    authorization_claim = request.source.authorization_claim
    claim = request.candidate_claim
    attempt = request.candidate_attempt
    instruction = request.signed_instruction_envelope.instruction
    if (
        request.expected_policy_id != policy.policy_id
        or request.expected_policy_version != policy.policy_version
        or request.expected_policy_digest != policy.canonical_digest
        or request.minimum_invocation_margin_milliseconds
        != policy.minimum_invocation_margin_milliseconds
        or lease.authorization_lease_id != claim.authorization_lease_id
        or lease.canonical_digest != claim.authorization_lease_digest
        or lease.claim_id != authorization_claim.claim_id
        or authorization_claim.canonical_digest != claim.authorization_claim_digest
        or claim.claim_id != attempt.claim_id
        or claim.canonical_digest != attempt.claim_digest
        or claim.attempt_id != attempt.attempt_id
        or claim.consumption_id != attempt.consumption_id
        or claim.idempotency_digest != request.idempotency_digest
        or claim.request_fingerprint != request.request_fingerprint
        or instruction.attempt_id != attempt.attempt_id
        or instruction.attempt_digest != attempt.canonical_digest
        or instruction.claim_digest != claim.canonical_digest
        or instruction.invocation_deadline > lease.effective_until
        or not request.offline_instruction_signature_verifier.verify_instruction_envelope(
            request.signed_instruction_envelope
        )
    ):
        raise WorkflowProtectedRuntimeReadinessConsumptionError(
            "protected_runtime_readiness_consumption_claim_request_invalid"
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
    return value


__all__ = [
    "WorkflowProtectedRuntimeReadinessAssessor",
    "WorkflowProtectedRuntimeReadinessConsumptionClaimRequest",
    "WorkflowProtectedRuntimeReadinessConsumptionClaimStatus",
    "WorkflowProtectedRuntimeReadinessConsumptionClaimWrite",
    "WorkflowProtectedRuntimeReadinessConsumptionError",
    "WorkflowProtectedRuntimeReadinessConsumptionReplayLookup",
    "WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest",
    "WorkflowProtectedRuntimeReadinessConsumptionReplayStatus",
    "WorkflowProtectedRuntimeReadinessConsumptionRepository",
    "WorkflowProtectedRuntimeReadinessConsumptionResultRequest",
    "WorkflowProtectedRuntimeReadinessConsumptionResultWrite",
    "WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus",
    "WorkflowProtectedRuntimeReadinessConsumptionSource",
    "WorkflowProtectedRuntimeReadinessInstructionSignatureVerifier",
    "WorkflowProtectedRuntimeReadinessInstructionSigner",
    "WorkflowProtectedRuntimeReadinessReceiptSignatureVerifier",
    "build_workflow_protected_runtime_readiness_instruction",
    "build_workflow_protected_runtime_readiness_invocation",
    "build_workflow_protected_runtime_readiness_signed_instruction_envelope",
    "validate_workflow_protected_runtime_readiness_consumption_claim_request",
]
