from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeContextUseAttempt,
    WorkflowProtectedRuntimeContextUseClaim,
    WorkflowProtectedRuntimeContextUseInstruction,
    WorkflowProtectedRuntimeContextUseInvocation,
    WorkflowProtectedRuntimeContextUseReceipt,
    WorkflowProtectedRuntimeContextUseResult,
    WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_context_use_policy,
)


class WorkflowProtectedRuntimeContextUseError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeContextUseReplayStatus(StrEnum):
    NONE = "none"
    TERMINAL = "terminal"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_CONSUMED = "already_consumed"


class WorkflowProtectedRuntimeContextUseClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_CONSUMED = "already_consumed"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


class WorkflowProtectedRuntimeContextUseResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseSource:
    authorization_consumption_claim: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim
    authorization_consumption_result: (
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest:
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    authorization_consumption_claim_id: str
    authorization_consumption_claim_digest: str
    injection_result_id: str
    injection_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_generation: int
    injected_context_usable_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    executor_contract_id: str
    executor_contract_version: str
    executor_id: str
    executor_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseEligibilityAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    authorization_consumption_claim_id: str
    authorization_consumption_claim_digest: str
    injection_result_id: str
    injection_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_generation: int
    injected_context_usable_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    executor_contract_id: str
    executor_contract_version: str
    executor_id: str
    executor_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    purpose_id: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    context_present: bool
    context_inert: bool
    context_unexpired: bool
    context_unrevoked: bool
    context_uncleared: bool
    context_unsuperseded: bool
    context_unused: bool
    use_count: int
    competing_use_absent: bool
    destination_generation_current: bool
    destination_fence_current: bool
    runtime_slot_generation_current: bool
    use_profile_eligible: bool
    executor_profile_eligible: bool
    atomic_compare_and_swap_supported: bool
    raw_context_included: bool
    runtime_handle_included: bool
    runtime_slot_locator_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    bearer_token_included: bool
    runtime_start_authorized: bool
    runtime_resume_authorized: bool
    process_creation_authorized: bool
    prompt_construction_authorized: bool
    model_inference_authorized: bool
    connector_activity_authorized: bool
    network_activity_authorized: bool
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


class WorkflowProtectedRuntimeContextUseEligibilityAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_context_use_eligibility(
        self, request: WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest
    ) -> WorkflowProtectedRuntimeContextUseEligibilityAttestation: ...


class WorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier(Protocol):
    def verify_context_use_eligibility_attestation(
        self, attestation: WorkflowProtectedRuntimeContextUseEligibilityAttestation
    ) -> bool: ...


class WorkflowProtectedRuntimeContextUseInstructionSigner(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def signing_key_id(self) -> str: ...

    @property
    def signature_algorithm(self) -> str: ...

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str: ...


class WorkflowProtectedRuntimeContextUseInstructionSignatureVerifier(Protocol):
    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope
    ) -> bool: ...


class WorkflowProtectedRuntimeContextTrustedUser(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def executor_contract_id(self) -> str: ...

    @property
    def executor_contract_version(self) -> str: ...

    @property
    def executor_id(self) -> str: ...

    @property
    def executor_version(self) -> str: ...

    @property
    def use_profile_id(self) -> str: ...

    @property
    def use_profile_version(self) -> str: ...

    @property
    def use_profile_digest(self) -> str: ...

    async def use_context(
        self, invocation: WorkflowProtectedRuntimeContextUseInvocation
    ) -> WorkflowProtectedRuntimeContextUseReceipt: ...


class WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier(Protocol):
    def verify_receipt(self, receipt: WorkflowProtectedRuntimeContextUseReceipt) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseReplayLookupRequest:
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    use_id: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseReplayLookup:
    status: WorkflowProtectedRuntimeContextUseReplayStatus
    attempt: WorkflowProtectedRuntimeContextUseAttempt | None = None
    result: WorkflowProtectedRuntimeContextUseResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseClaimRequest:
    claim_id: str
    attempt_id: str
    use_id: str
    source: WorkflowProtectedRuntimeContextUseSource
    eligibility_attestation: WorkflowProtectedRuntimeContextUseEligibilityAttestation
    expected_request_nonce_digest: str
    offline_attestation_signature_verifier: (
        WorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_attestor_id: str
    expected_attestor_version: str
    expected_executor_contract_id: str
    expected_executor_contract_version: str
    expected_executor_id: str
    expected_executor_version: str
    expected_use_profile_id: str
    expected_use_profile_version: str
    expected_use_profile_digest: str
    expected_attestation_verification_signing_key_id: str
    expected_receipt_verification_signing_key_id: str
    minimum_remaining_budget_milliseconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_use_acknowledged: bool
    uncertainty_no_retry_acknowledged: bool
    use_authorization_audit_payload: dict[str, object]
    use_authorization_audit_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseClaimWrite:
    status: WorkflowProtectedRuntimeContextUseClaimStatus
    claim: WorkflowProtectedRuntimeContextUseClaim | None = None
    attempt: WorkflowProtectedRuntimeContextUseAttempt | None = None
    result: WorkflowProtectedRuntimeContextUseResult | None = None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseResultRequest:
    result: WorkflowProtectedRuntimeContextUseResult
    receipt: WorkflowProtectedRuntimeContextUseReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseResultWrite:
    status: WorkflowProtectedRuntimeContextUseResultWriteStatus
    result: WorkflowProtectedRuntimeContextUseResult | None = None


class WorkflowProtectedRuntimeContextUseRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_runtime_context_use_replay(
        self, request: WorkflowProtectedRuntimeContextUseReplayLookupRequest
    ) -> WorkflowProtectedRuntimeContextUseReplayLookup: ...

    async def get_protected_runtime_context_use_source(
        self,
        *,
        authorization_consumption_result_id: str,
        authorization_consumption_result_digest: str,
    ) -> WorkflowProtectedRuntimeContextUseSource | None: ...

    async def claim_protected_runtime_context_use(
        self, request: WorkflowProtectedRuntimeContextUseClaimRequest
    ) -> WorkflowProtectedRuntimeContextUseClaimWrite: ...

    async def record_protected_runtime_context_use_result(
        self, request: WorkflowProtectedRuntimeContextUseResultRequest
    ) -> WorkflowProtectedRuntimeContextUseResultWrite: ...

    async def list_protected_runtime_context_use_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAttempt, ...]: ...

    async def get_protected_runtime_context_use_results(
        self, *, scope: WorkflowScope, use_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeContextUseResult, ...]: ...


def build_workflow_protected_runtime_context_use_instruction(
    attempt: WorkflowProtectedRuntimeContextUseAttempt,
) -> WorkflowProtectedRuntimeContextUseInstruction:
    aliases = {
        "attempt_digest": attempt.canonical_digest,
        "executor_contract_id": attempt.required_executor_contract_id,
        "executor_contract_version": attempt.required_executor_contract_version,
        "executor_id": attempt.approved_executor_id,
        "executor_version": attempt.approved_executor_version,
    }
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeContextUseInstruction):
        if field.name == "canonical_digest":
            continue
        values[field.name] = (
            aliases[field.name] if field.name in aliases else getattr(attempt, field.name)
        )
    return WorkflowProtectedRuntimeContextUseInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def build_workflow_protected_runtime_context_use_signed_instruction_envelope(
    instruction: WorkflowProtectedRuntimeContextUseInstruction,
    signer: WorkflowProtectedRuntimeContextUseInstructionSigner,
) -> WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope:
    if (
        not signer.available
        or signer.signing_key_id
        != WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID
        or signer.signature_algorithm
        != WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM
    ):
        raise WorkflowProtectedRuntimeContextUseError(
            "protected_runtime_context_use_instruction_signer_unavailable"
        )
    signature_payload = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": signer.signing_key_id,
        "signature_algorithm": signer.signature_algorithm,
    }
    integrity_signature = signer.sign_instruction_envelope_digest(
        canonical_digest(signature_payload)
    )
    values = signature_payload | {"integrity_signature": integrity_signature}
    return WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=signer.signing_key_id,
        signature_algorithm=signer.signature_algorithm,
        integrity_signature=integrity_signature,
        canonical_digest=canonical_digest(values),
    )


def build_workflow_protected_runtime_context_use_invocation(
    instruction: WorkflowProtectedRuntimeContextUseInstruction,
    signed_instruction_envelope: WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope,
) -> WorkflowProtectedRuntimeContextUseInvocation:
    return WorkflowProtectedRuntimeContextUseInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        use_deadline=instruction.use_deadline,
        signed_instruction_envelope=signed_instruction_envelope,
    )


def validate_workflow_protected_runtime_context_use_claim_request(
    request: WorkflowProtectedRuntimeContextUseClaimRequest,
) -> None:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    source_claim = request.source.authorization_consumption_claim
    source_result = request.source.authorization_consumption_result
    attestation = request.eligibility_attestation
    forbidden_source_effects = (
        source_result.context_accessed,
        source_result.context_used,
        source_result.runtime_started,
        source_result.runtime_resumed,
        source_result.network_activity_performed,
        source_result.connector_activity_performed,
        source_result.readiness_probe_performed,
        source_result.publication_performed,
        source_result.delivery_performed,
        source_result.dispatch_performed,
        source_result.execution_performed,
        source_result.infrastructure_mutation_performed,
        source_result.renewal_created,
        source_result.transfer_created,
        source_result.replacement_created,
        source_result.retry_created,
    )
    invalid = (
        source_result.result_id != attestation.authorization_consumption_result_id
        or source_result.canonical_digest != attestation.authorization_consumption_result_digest
        or source_claim.consumption_claim_id != attestation.authorization_consumption_claim_id
        or source_claim.canonical_digest != attestation.authorization_consumption_claim_digest
        or source_result.consumption_claim_id != source_claim.consumption_claim_id
        or source_result.consumption_claim_digest != source_claim.canonical_digest
        or source_result.authorization_lease_id != source_claim.authorization_lease_id
        or source_result.authorization_lease_digest != source_claim.authorization_lease_digest
        or source_claim.injection_result_id != attestation.injection_result_id
        or source_claim.injection_result_digest != attestation.injection_result_digest
        or request.expected_request_nonce_digest != attestation.request_nonce_digest
        or source_result.state.value != policy.required_source_state
        or source_result.authorization_lease_consumed is not True
        or source_result.historical_result_only is not True
        or any(forbidden_source_effects)
        or any(source_result.authority.canonical_value().values())
        or any(source_claim.authority.canonical_value().values())
        or request.expected_policy_id != policy.policy_id
        or request.expected_policy_version != policy.policy_version
        or request.expected_policy_digest != policy.canonical_digest
        or request.expected_attestor_id != policy.required_attestor_id
        or request.expected_attestor_version != policy.required_attestor_version
        or request.expected_executor_contract_id != policy.required_executor_contract_id
        or request.expected_executor_contract_version != policy.required_executor_contract_version
        or request.expected_executor_id != policy.approved_executor_id
        or request.expected_executor_version != policy.approved_executor_version
        or request.expected_use_profile_id != policy.use_profile_id
        or request.expected_use_profile_version != policy.use_profile_version
        or request.expected_use_profile_digest != policy.use_profile_digest
        or request.expected_attestation_verification_signing_key_id
        != policy.attestation_verification_signing_key_id
        or request.expected_receipt_verification_signing_key_id
        != policy.receipt_verification_signing_key_id
        or request.minimum_remaining_budget_milliseconds
        != policy.minimum_remaining_budget_milliseconds
        or attestation.attestor_id != request.expected_attestor_id
        or attestation.attestor_version != request.expected_attestor_version
        or attestation.signing_key_id != request.expected_attestation_verification_signing_key_id
        or attestation.executor_contract_id != request.expected_executor_contract_id
        or attestation.executor_contract_version != request.expected_executor_contract_version
        or attestation.executor_id != request.expected_executor_id
        or attestation.executor_version != request.expected_executor_version
        or attestation.use_profile_id != request.expected_use_profile_id
        or attestation.use_profile_version != request.expected_use_profile_version
        or attestation.use_profile_digest != request.expected_use_profile_digest
        or attestation.scope != request.scope
        or attestation.consumer_subject_id != request.consumer_subject_id
        or attestation.consumer_audience != request.consumer_audience
        or source_claim.scope != request.scope
        or source_result.scope != request.scope
        or source_claim.consumer_subject_id != request.consumer_subject_id
        or source_result.consumer_subject_id != request.consumer_subject_id
        or source_claim.consumer_audience != request.consumer_audience
        or source_result.consumer_audience != request.consumer_audience
        or request.irreversible_use_acknowledged is not True
        or request.uncertainty_no_retry_acknowledged is not True
        or request.use_authorization_audit_digest
        != canonical_digest(request.use_authorization_audit_payload)
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        or not request.offline_attestation_signature_verifier.verify_context_use_eligibility_attestation(  # noqa: E501
            attestation
        )
    )
    if invalid:
        raise WorkflowProtectedRuntimeContextUseError(
            "protected_runtime_context_use_claim_evidence_invalid"
        )


def _canonical_payload(instance: object, *, exclude: tuple[str, ...]) -> dict[str, object]:
    return {
        field.name: _canonical_value(getattr(instance, field.name))
        for field in fields(cast(Any, instance))
        if field.name not in exclude
    }


def _canonical_mapping(values: dict[str, object]) -> dict[str, object]:
    return {name: _canonical_value(value) for name, value in values.items()}


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


__all__ = [
    "WorkflowProtectedRuntimeContextTrustedUser",
    "WorkflowProtectedRuntimeContextUseClaimRequest",
    "WorkflowProtectedRuntimeContextUseClaimStatus",
    "WorkflowProtectedRuntimeContextUseClaimWrite",
    "WorkflowProtectedRuntimeContextUseEligibilityAttestation",
    "WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest",
    "WorkflowProtectedRuntimeContextUseEligibilityAttestor",
    "WorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier",
    "WorkflowProtectedRuntimeContextUseError",
    "WorkflowProtectedRuntimeContextUseInstructionSignatureVerifier",
    "WorkflowProtectedRuntimeContextUseInstructionSigner",
    "WorkflowProtectedRuntimeContextUseReceiptSignatureVerifier",
    "WorkflowProtectedRuntimeContextUseReplayLookup",
    "WorkflowProtectedRuntimeContextUseReplayLookupRequest",
    "WorkflowProtectedRuntimeContextUseReplayStatus",
    "WorkflowProtectedRuntimeContextUseRepository",
    "WorkflowProtectedRuntimeContextUseResultRequest",
    "WorkflowProtectedRuntimeContextUseResultWrite",
    "WorkflowProtectedRuntimeContextUseResultWriteStatus",
    "WorkflowProtectedRuntimeContextUseSource",
    "build_workflow_protected_runtime_context_use_instruction",
    "build_workflow_protected_runtime_context_use_invocation",
    "build_workflow_protected_runtime_context_use_signed_instruction_envelope",
    "validate_workflow_protected_runtime_context_use_claim_request",
]
