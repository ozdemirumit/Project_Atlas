from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaim,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeProcessCreationAttempt,
    WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
    WorkflowProtectedRuntimeProcessCreationInstruction,
    WorkflowProtectedRuntimeProcessCreationInvocation,
    WorkflowProtectedRuntimeProcessCreationReceipt,
    WorkflowProtectedRuntimeProcessCreationResult,
    WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)


class WorkflowProtectedRuntimeProcessCreationConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus(StrEnum):
    NONE = "none"
    ATTEMPT_PENDING = "attempt_pending"
    ATTEMPT_UNCERTAIN = "attempt_uncertain"
    TERMINAL = "terminal"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_PENDING = "replay_pending"
    REPLAY_UNCERTAIN = "replay_uncertain"
    REPLAY_TERMINAL = "replay_terminal"
    LEASE_EXPIRED = "lease_expired"
    LEASE_CONSUMED = "lease_consumed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedRuntimeProcessCreationResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationConsumptionSource:
    authorization_lease: WorkflowProtectedRuntimeProcessCreationAuthorizationLease
    authorization_claim: WorkflowProtectedRuntimeProcessCreationAuthorizationClaim


class WorkflowProtectedRuntimeProcessCreationInstructionSigner(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def signing_key_id(self) -> str: ...

    @property
    def signature_algorithm(self) -> str: ...

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str: ...


class WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope
    ) -> bool: ...


class WorkflowProtectedRuntimeProcessCreator(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def creator_contract_id(self) -> str: ...

    @property
    def creator_contract_version(self) -> str: ...

    @property
    def creator_id(self) -> str: ...

    @property
    def creator_version(self) -> str: ...

    @property
    def process_creation_profile_id(self) -> str: ...

    @property
    def process_creation_profile_version(self) -> str: ...

    @property
    def process_creation_profile_digest(self) -> str: ...

    @property
    def primitive_id(self) -> str: ...

    @property
    def primitive_version(self) -> str: ...

    @property
    def primitive_digest(self) -> str: ...

    async def create_sealed_suspended_process(
        self, invocation: WorkflowProtectedRuntimeProcessCreationInvocation
    ) -> WorkflowProtectedRuntimeProcessCreationReceipt: ...


class WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(Protocol):
    @property
    def available(self) -> bool: ...

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeProcessCreationReceipt) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationReplayLookupRequest:
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
class WorkflowProtectedRuntimeProcessCreationReplayLookup:
    status: WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus
    attempt: WorkflowProtectedRuntimeProcessCreationAttempt | None = None
    result: WorkflowProtectedRuntimeProcessCreationResult | None = None
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationClaimRequest:
    source: WorkflowProtectedRuntimeProcessCreationConsumptionSource
    candidate_claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim
    candidate_attempt: WorkflowProtectedRuntimeProcessCreationAttempt
    signed_instruction_envelope: WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope
    offline_instruction_signature_verifier: (
        WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    minimum_invocation_margin_milliseconds: int
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationClaimWrite:
    status: WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus
    claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim | None = None
    attempt: WorkflowProtectedRuntimeProcessCreationAttempt | None = None
    result: WorkflowProtectedRuntimeProcessCreationResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationResultRequest:
    result: WorkflowProtectedRuntimeProcessCreationResult
    receipt: WorkflowProtectedRuntimeProcessCreationReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationResultWrite:
    status: WorkflowProtectedRuntimeProcessCreationResultWriteStatus
    result: WorkflowProtectedRuntimeProcessCreationResult | None = None


class WorkflowProtectedRuntimeProcessCreationConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_runtime_process_creation_replay(
        self, request: WorkflowProtectedRuntimeProcessCreationReplayLookupRequest
    ) -> WorkflowProtectedRuntimeProcessCreationReplayLookup: ...

    async def get_protected_runtime_process_creation_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionSource | None: ...

    async def claim_protected_runtime_process_creation(
        self, request: WorkflowProtectedRuntimeProcessCreationClaimRequest
    ) -> WorkflowProtectedRuntimeProcessCreationClaimWrite: ...

    async def record_protected_runtime_process_creation_result(
        self, request: WorkflowProtectedRuntimeProcessCreationResultRequest
    ) -> WorkflowProtectedRuntimeProcessCreationResultWrite: ...

    async def list_protected_runtime_process_creation_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeProcessCreationAttempt, ...]: ...

    async def get_protected_runtime_process_creation_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeProcessCreationResult, ...]: ...


def build_workflow_protected_runtime_process_creation_instruction(
    attempt: WorkflowProtectedRuntimeProcessCreationAttempt,
) -> WorkflowProtectedRuntimeProcessCreationInstruction:
    aliases = {"attempt_digest": attempt.canonical_digest}
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeProcessCreationInstruction):
        if field.name == "canonical_digest":
            continue
        values[field.name] = (
            aliases[field.name] if field.name in aliases else getattr(attempt, field.name)
        )
    return WorkflowProtectedRuntimeProcessCreationInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def build_workflow_protected_runtime_process_creation_signed_instruction_envelope(
    instruction: WorkflowProtectedRuntimeProcessCreationInstruction,
    signer: WorkflowProtectedRuntimeProcessCreationInstructionSigner,
) -> WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope:
    if (
        not signer.available
        or signer.signing_key_id
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNING_KEY_ID
        or signer.signature_algorithm
        != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNATURE_ALGORITHM
    ):
        raise WorkflowProtectedRuntimeProcessCreationConsumptionError(
            "protected_runtime_process_creation_instruction_signer_unavailable"
        )
    signature_payload = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": signer.signing_key_id,
        "signature_algorithm": signer.signature_algorithm,
    }
    signature = signer.sign_instruction_envelope_digest(canonical_digest(signature_payload))
    values = signature_payload | {"integrity_signature": signature}
    return WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=signer.signing_key_id,
        signature_algorithm=signer.signature_algorithm,
        integrity_signature=signature,
        canonical_digest=canonical_digest(values),
    )


def build_workflow_protected_runtime_process_creation_invocation(
    envelope: WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope,
) -> WorkflowProtectedRuntimeProcessCreationInvocation:
    instruction = envelope.instruction
    return WorkflowProtectedRuntimeProcessCreationInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        invocation_deadline=instruction.invocation_deadline,
        signed_instruction_envelope=envelope,
    )


def validate_workflow_protected_runtime_process_creation_claim_request(
    request: WorkflowProtectedRuntimeProcessCreationClaimRequest,
) -> None:
    policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    source_policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
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
        or lease.claim_digest != authorization_claim.canonical_digest
        or lease.policy_id != source_policy.policy_id
        or lease.policy_version != source_policy.policy_version
        or lease.policy_digest != source_policy.canonical_digest
        or authorization_claim.policy_id != source_policy.policy_id
        or authorization_claim.policy_version != source_policy.policy_version
        or authorization_claim.policy_digest != source_policy.canonical_digest
        or lease.state
        is not (
            WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState
        ).AUTHORIZED_UNCONSUMED
        or lease.single_use is not True
        or lease.renewable is not False
        or lease.transferable is not False
        or lease.lease_is_bearer_capability is not False
        or lease.authority.protected_runtime_process_creation_authority_granted is not True
        or authorization_claim.authority.protected_runtime_process_creation_authority_granted
        is not False
        or lease.scope != authorization_claim.scope
        or lease.scope != claim.scope
        or claim.scope != attempt.scope
        or lease.runtime_envelope_id != authorization_claim.runtime_envelope_id
        or lease.runtime_envelope_id != claim.runtime_envelope_id
        or claim.runtime_envelope_id != attempt.runtime_envelope_id
        or lease.runtime_envelope_commitment != authorization_claim.runtime_envelope_commitment
        or lease.runtime_envelope_commitment != claim.runtime_envelope_commitment
        or claim.runtime_envelope_commitment != attempt.runtime_envelope_commitment
        or lease.runtime_envelope_generation != authorization_claim.runtime_envelope_generation
        or lease.runtime_envelope_generation != claim.runtime_envelope_generation
        or claim.runtime_envelope_generation != attempt.runtime_envelope_generation
        or lease.process_creation_profile_digest != claim.process_creation_profile_digest
        or claim.process_creation_profile_digest != attempt.process_creation_profile_digest
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
        raise WorkflowProtectedRuntimeProcessCreationConsumptionError(
            "protected_runtime_process_creation_claim_request_invalid"
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
    "WorkflowProtectedRuntimeProcessCreationClaimRequest",
    "WorkflowProtectedRuntimeProcessCreationClaimWrite",
    "WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus",
    "WorkflowProtectedRuntimeProcessCreationConsumptionError",
    "WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus",
    "WorkflowProtectedRuntimeProcessCreationConsumptionRepository",
    "WorkflowProtectedRuntimeProcessCreationConsumptionSource",
    "WorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier",
    "WorkflowProtectedRuntimeProcessCreationInstructionSigner",
    "WorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier",
    "WorkflowProtectedRuntimeProcessCreationReplayLookup",
    "WorkflowProtectedRuntimeProcessCreationReplayLookupRequest",
    "WorkflowProtectedRuntimeProcessCreationResultRequest",
    "WorkflowProtectedRuntimeProcessCreationResultWrite",
    "WorkflowProtectedRuntimeProcessCreationResultWriteStatus",
    "WorkflowProtectedRuntimeProcessCreator",
    "build_workflow_protected_runtime_process_creation_instruction",
    "build_workflow_protected_runtime_process_creation_invocation",
    "build_workflow_protected_runtime_process_creation_signed_instruction_envelope",
    "validate_workflow_protected_runtime_process_creation_claim_request",
]
