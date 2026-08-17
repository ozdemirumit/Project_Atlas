from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationClaim,
    WorkflowProtectedRuntimeStartAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeStartConsumptionAttempt,
    WorkflowProtectedRuntimeStartConsumptionClaim,
    WorkflowProtectedRuntimeStartConsumptionResult,
    WorkflowProtectedRuntimeStartInstruction,
    WorkflowProtectedRuntimeStartInvocation,
    WorkflowProtectedRuntimeStartReceipt,
    WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)


class WorkflowProtectedRuntimeStartConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeStartConsumptionReplayStatus(StrEnum):
    NONE = "none"
    ATTEMPT_PENDING = "attempt_pending"
    ATTEMPT_UNCERTAIN = "attempt_uncertain"
    TERMINAL = "terminal"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeStartConsumptionClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_PENDING = "replay_pending"
    REPLAY_UNCERTAIN = "replay_uncertain"
    REPLAY_TERMINAL = "replay_terminal"
    LEASE_EXPIRED = "lease_expired"
    LEASE_CONSUMED = "lease_consumed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeStartConsumptionResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionSource:
    authorization_lease: WorkflowProtectedRuntimeStartAuthorizationLease
    authorization_claim: WorkflowProtectedRuntimeStartAuthorizationClaim


class WorkflowProtectedRuntimeStartInstructionSigner(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def signing_key_id(self) -> str: ...

    @property
    def signature_algorithm(self) -> str: ...

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str: ...


class WorkflowProtectedRuntimeStartInstructionSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope
    ) -> bool: ...


class WorkflowProtectedRuntimeStarter(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def starter_contract_id(self) -> str: ...

    @property
    def starter_contract_version(self) -> str: ...

    @property
    def starter_id(self) -> str: ...

    @property
    def starter_version(self) -> str: ...

    @property
    def runtime_start_profile_id(self) -> str: ...

    @property
    def runtime_start_profile_version(self) -> str: ...

    @property
    def runtime_start_profile_digest(self) -> str: ...

    async def start_runtime(
        self, invocation: WorkflowProtectedRuntimeStartInvocation
    ) -> WorkflowProtectedRuntimeStartReceipt: ...


class WorkflowProtectedRuntimeStartReceiptSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeStartReceipt) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest:
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
class WorkflowProtectedRuntimeStartConsumptionReplayLookup:
    status: WorkflowProtectedRuntimeStartConsumptionReplayStatus
    attempt: WorkflowProtectedRuntimeStartConsumptionAttempt | None = None
    result: WorkflowProtectedRuntimeStartConsumptionResult | None = None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionClaimRequest:
    source: WorkflowProtectedRuntimeStartConsumptionSource
    candidate_claim: WorkflowProtectedRuntimeStartConsumptionClaim
    candidate_attempt: WorkflowProtectedRuntimeStartConsumptionAttempt
    signed_instruction_envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope
    offline_instruction_signature_verifier: (
        WorkflowProtectedRuntimeStartInstructionSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    minimum_invocation_margin_milliseconds: int
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionClaimWrite:
    status: WorkflowProtectedRuntimeStartConsumptionClaimStatus
    claim: WorkflowProtectedRuntimeStartConsumptionClaim | None = None
    attempt: WorkflowProtectedRuntimeStartConsumptionAttempt | None = None
    result: WorkflowProtectedRuntimeStartConsumptionResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionResultRequest:
    result: WorkflowProtectedRuntimeStartConsumptionResult
    receipt: WorkflowProtectedRuntimeStartReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionResultWrite:
    status: WorkflowProtectedRuntimeStartConsumptionResultWriteStatus
    result: WorkflowProtectedRuntimeStartConsumptionResult | None = None


class WorkflowProtectedRuntimeStartConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_runtime_start_consumption_replay(
        self, request: WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest
    ) -> WorkflowProtectedRuntimeStartConsumptionReplayLookup: ...

    async def get_protected_runtime_start_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeStartConsumptionSource | None: ...

    async def claim_protected_runtime_start_consumption(
        self, request: WorkflowProtectedRuntimeStartConsumptionClaimRequest
    ) -> WorkflowProtectedRuntimeStartConsumptionClaimWrite: ...

    async def record_protected_runtime_start_consumption_result(
        self, request: WorkflowProtectedRuntimeStartConsumptionResultRequest
    ) -> WorkflowProtectedRuntimeStartConsumptionResultWrite: ...

    async def list_protected_runtime_start_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeStartConsumptionAttempt, ...]: ...

    async def get_protected_runtime_start_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeStartConsumptionResult, ...]: ...


def build_workflow_protected_runtime_start_instruction(
    attempt: WorkflowProtectedRuntimeStartConsumptionAttempt,
) -> WorkflowProtectedRuntimeStartInstruction:
    aliases = {"attempt_digest": attempt.canonical_digest}
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeStartInstruction):
        if field.name == "canonical_digest":
            continue
        values[field.name] = (
            aliases[field.name] if field.name in aliases else getattr(attempt, field.name)
        )
    return WorkflowProtectedRuntimeStartInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def build_workflow_protected_runtime_start_signed_instruction_envelope(
    instruction: WorkflowProtectedRuntimeStartInstruction,
    signer: WorkflowProtectedRuntimeStartInstructionSigner,
) -> WorkflowProtectedRuntimeStartSignedInstructionEnvelope:
    if (
        not signer.available
        or signer.signing_key_id != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID
        or signer.signature_algorithm
        != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM
    ):
        raise WorkflowProtectedRuntimeStartConsumptionError(
            "protected_runtime_start_instruction_signer_unavailable"
        )
    signature_payload = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": signer.signing_key_id,
        "signature_algorithm": signer.signature_algorithm,
    }
    signature = signer.sign_instruction_envelope_digest(canonical_digest(signature_payload))
    values = signature_payload | {"integrity_signature": signature}
    return WorkflowProtectedRuntimeStartSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=signer.signing_key_id,
        signature_algorithm=signer.signature_algorithm,
        integrity_signature=signature,
        canonical_digest=canonical_digest(values),
    )


def build_workflow_protected_runtime_start_invocation(
    envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
) -> WorkflowProtectedRuntimeStartInvocation:
    instruction = envelope.instruction
    return WorkflowProtectedRuntimeStartInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        invocation_deadline=instruction.invocation_deadline,
        signed_instruction_envelope=envelope,
    )


def validate_workflow_protected_runtime_start_consumption_claim_request(
    request: WorkflowProtectedRuntimeStartConsumptionClaimRequest,
) -> None:
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
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
        or instruction.invocation_deadline > lease.valid_until
        or not request.offline_instruction_signature_verifier.verify_instruction_envelope(
            request.signed_instruction_envelope
        )
    ):
        raise WorkflowProtectedRuntimeStartConsumptionError(
            "protected_runtime_start_consumption_claim_request_invalid"
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
    "WorkflowProtectedRuntimeStartConsumptionClaimRequest",
    "WorkflowProtectedRuntimeStartConsumptionClaimStatus",
    "WorkflowProtectedRuntimeStartConsumptionClaimWrite",
    "WorkflowProtectedRuntimeStartConsumptionError",
    "WorkflowProtectedRuntimeStartConsumptionReplayLookup",
    "WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest",
    "WorkflowProtectedRuntimeStartConsumptionReplayStatus",
    "WorkflowProtectedRuntimeStartConsumptionRepository",
    "WorkflowProtectedRuntimeStartConsumptionResultRequest",
    "WorkflowProtectedRuntimeStartConsumptionResultWrite",
    "WorkflowProtectedRuntimeStartConsumptionResultWriteStatus",
    "WorkflowProtectedRuntimeStartConsumptionSource",
    "WorkflowProtectedRuntimeStartInstructionSignatureVerifier",
    "WorkflowProtectedRuntimeStartInstructionSigner",
    "WorkflowProtectedRuntimeStartReceiptSignatureVerifier",
    "WorkflowProtectedRuntimeStarter",
    "build_workflow_protected_runtime_start_instruction",
    "build_workflow_protected_runtime_start_invocation",
    "build_workflow_protected_runtime_start_signed_instruction_envelope",
    "validate_workflow_protected_runtime_start_consumption_claim_request",
]
