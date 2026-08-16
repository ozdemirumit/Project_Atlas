from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_runtime_context_injection_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionAuthorizationSource,
    WorkflowProtectedRuntimeHandleLifecycleAttestation,
    WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
    WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
    WorkflowProtectedRuntimeContextInjectionConsumptionClaim,
    WorkflowProtectedRuntimeContextInjectionConsumptionResult,
    WorkflowProtectedRuntimeContextTrustedInjectorInstruction,
    WorkflowProtectedRuntimeContextTrustedInjectorInvocation,
    WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedRuntimeContextInjectionConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus(StrEnum):
    NONE = "none"
    TERMINAL = "terminal"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"


class WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


class WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionSource:
    authorization_lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease
    authorization_source: WorkflowProtectedRuntimeContextInjectionAuthorizationSource


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeSlotReadinessAttestationRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_runtime_handle_digest: str
    protected_runtime_handle_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeSlotReadinessAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_runtime_handle_digest: str
    protected_runtime_handle_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    request_nonce_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    observed_at: datetime
    valid_until: datetime
    exact_runtime_slot_confirmed: bool
    runtime_slot_empty: bool
    runtime_slot_inert: bool
    runtime_slot_eligible: bool
    atomic_compare_and_swap_supported: bool
    destination_generation_current: bool
    destination_fence_current: bool
    injector_profile_eligible: bool
    runtime_autostart_disabled: bool
    raw_context_included: bool
    runtime_handle_material_included: bool
    runtime_payload_included: bool
    runtime_slot_locator_included: bool
    endpoint_included: bool
    credential_included: bool
    bearer_token_included: bool
    connector_activity_authorized: bool
    network_activity_authorized: bool
    readiness_probe_authorized: bool
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


class WorkflowProtectedRuntimeSlotReadinessAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_runtime_slot_readiness(
        self, request: WorkflowProtectedRuntimeSlotReadinessAttestationRequest
    ) -> WorkflowProtectedRuntimeSlotReadinessAttestation: ...


class WorkflowProtectedRuntimeSlotReadinessSignatureVerifier(Protocol):
    def verify_runtime_slot_readiness_attestation(
        self, attestation: WorkflowProtectedRuntimeSlotReadinessAttestation
    ) -> bool: ...


class WorkflowProtectedRuntimeContextTrustedInjector(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def injector_contract_id(self) -> str: ...

    @property
    def injector_contract_version(self) -> str: ...

    @property
    def injector_id(self) -> str: ...

    @property
    def injector_version(self) -> str: ...

    @property
    def runtime_slot_profile_id(self) -> str: ...

    @property
    def runtime_slot_profile_version(self) -> str: ...

    @property
    def runtime_slot_profile_digest(self) -> str: ...

    async def inject_context(
        self, invocation: WorkflowProtectedRuntimeContextTrustedInjectorInvocation
    ) -> WorkflowProtectedRuntimeContextTrustedInjectorReceipt: ...


class WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier(Protocol):
    def verify_receipt(
        self, receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookupRequest:
    authorization_lease_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    injection_id: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup:
    status: WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus
    attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt | None
    result: WorkflowProtectedRuntimeContextInjectionConsumptionResult | None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionClaimRequest:
    claim_id: str
    attempt_id: str
    injection_id: str
    source: WorkflowProtectedRuntimeContextInjectionConsumptionSource
    lifecycle_attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    slot_readiness_attestation: WorkflowProtectedRuntimeSlotReadinessAttestation
    expected_request_nonce_digest: str
    offline_lifecycle_signature_verifier: WorkflowProtectedRuntimeHandleLifecycleSignatureVerifier
    offline_slot_readiness_signature_verifier: (
        WorkflowProtectedRuntimeSlotReadinessSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_lifecycle_attestor_id: str
    expected_lifecycle_attestor_version: str
    expected_slot_readiness_attestor_id: str
    expected_slot_readiness_attestor_version: str
    expected_injector_contract_id: str
    expected_injector_contract_version: str
    expected_injector_id: str
    expected_injector_version: str
    expected_runtime_slot_profile_id: str
    expected_runtime_slot_profile_version: str
    expected_runtime_slot_profile_digest: str
    expected_slot_readiness_verification_signing_key_id: str
    expected_receipt_verification_signing_key_id: str
    minimum_remaining_budget_milliseconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    consumption_authorization_audit_payload: dict[str, object]
    consumption_authorization_audit_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite:
    status: WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus
    claim: WorkflowProtectedRuntimeContextInjectionConsumptionClaim | None
    attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt | None
    result: WorkflowProtectedRuntimeContextInjectionConsumptionResult | None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionResultRequest:
    result: WorkflowProtectedRuntimeContextInjectionConsumptionResult
    receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite:
    status: WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus
    result: WorkflowProtectedRuntimeContextInjectionConsumptionResult | None


class WorkflowProtectedRuntimeContextInjectionConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_runtime_context_injection_consumption_replay(
        self, request: WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookupRequest
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup: ...

    async def get_protected_runtime_context_injection_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionSource | None: ...

    async def claim_protected_runtime_context_injection_consumption(
        self, request: WorkflowProtectedRuntimeContextInjectionConsumptionClaimRequest
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite: ...

    async def record_protected_runtime_context_injection_consumption_result(
        self, request: WorkflowProtectedRuntimeContextInjectionConsumptionResultRequest
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite: ...

    async def list_protected_runtime_context_injection_consumption_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionConsumptionAttempt, ...]: ...

    async def get_protected_runtime_context_injection_consumption_results(
        self, *, scope: WorkflowScope, injection_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionConsumptionResult, ...]: ...


def build_workflow_protected_runtime_context_trusted_injector_instruction(
    attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
) -> WorkflowProtectedRuntimeContextTrustedInjectorInstruction:
    aliases = {
        "injector_contract_id": attempt.required_injector_contract_id,
        "injector_contract_version": attempt.required_injector_contract_version,
        "injector_id": attempt.approved_injector_id,
        "injector_version": attempt.approved_injector_version,
    }
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeContextTrustedInjectorInstruction):
        if field.name == "canonical_digest":
            continue
        values[field.name] = (
            aliases[field.name] if field.name in aliases else getattr(attempt, field.name)
        )
    return WorkflowProtectedRuntimeContextTrustedInjectorInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def build_workflow_protected_runtime_context_trusted_injector_invocation(
    instruction: WorkflowProtectedRuntimeContextTrustedInjectorInstruction,
) -> WorkflowProtectedRuntimeContextTrustedInjectorInvocation:
    return WorkflowProtectedRuntimeContextTrustedInjectorInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        injection_deadline=instruction.injection_deadline,
    )


def validate_workflow_protected_runtime_context_injection_consumption_claim_request(
    request: WorkflowProtectedRuntimeContextInjectionConsumptionClaimRequest,
) -> None:
    lease = request.source.authorization_lease
    lifecycle = request.lifecycle_attestation
    readiness = request.slot_readiness_attestation
    invalid = (
        lease.authorization_lease_id != request.source.authorization_lease.authorization_lease_id
        or lease.canonical_digest == ""
        or lease.protected_runtime_handle_digest != lifecycle.protected_runtime_handle_digest
        or lease.protected_runtime_handle_digest != readiness.protected_runtime_handle_digest
        or lease.destination_boundary_id != readiness.destination_boundary_id
        or lease.destination_deployment_id != readiness.destination_deployment_id
        or lease.destination_generation != readiness.destination_generation
        or lease.destination_fencing_token_digest != readiness.destination_fencing_token_digest
        or request.expected_request_nonce_digest != lifecycle.request_nonce_digest
        or request.expected_request_nonce_digest != readiness.request_nonce_digest
        or request.expected_policy_id != request.source.authorization_lease.policy_id
        or readiness.runtime_slot_pre_generation < 0
        or readiness.runtime_slot_commitment == ""
        or request.irreversible_consumption_acknowledged is not True
        or request.uncertain_outcome_requires_new_authorization_acknowledged is not True
        or request.consumption_authorization_audit_digest
        != canonical_digest(request.consumption_authorization_audit_payload)
        or lifecycle.canonical_digest != canonical_digest(lifecycle.digest_payload())
        or readiness.canonical_digest != canonical_digest(readiness.digest_payload())
        or not request.offline_lifecycle_signature_verifier.verify_runtime_handle_lifecycle_attestation(  # noqa: E501
            lifecycle
        )
        or not request.offline_slot_readiness_signature_verifier.verify_runtime_slot_readiness_attestation(  # noqa: E501
            readiness
        )
    )
    if invalid:
        raise WorkflowProtectedRuntimeContextInjectionConsumptionError(
            "protected_runtime_context_injection_consumption_claim_evidence_invalid"
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
    "WorkflowProtectedRuntimeContextInjectionConsumptionClaimRequest",
    "WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus",
    "WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite",
    "WorkflowProtectedRuntimeContextInjectionConsumptionError",
    "WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup",
    "WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookupRequest",
    "WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus",
    "WorkflowProtectedRuntimeContextInjectionConsumptionRepository",
    "WorkflowProtectedRuntimeContextInjectionConsumptionResultRequest",
    "WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite",
    "WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus",
    "WorkflowProtectedRuntimeContextInjectionConsumptionSource",
    "WorkflowProtectedRuntimeContextTrustedInjector",
    "WorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier",
    "WorkflowProtectedRuntimeSlotReadinessAttestation",
    "WorkflowProtectedRuntimeSlotReadinessAttestationRequest",
    "WorkflowProtectedRuntimeSlotReadinessAttestor",
    "WorkflowProtectedRuntimeSlotReadinessSignatureVerifier",
    "build_workflow_protected_runtime_context_trusted_injector_instruction",
    "build_workflow_protected_runtime_context_trusted_injector_invocation",
    "validate_workflow_protected_runtime_context_injection_consumption_claim_request",
]
