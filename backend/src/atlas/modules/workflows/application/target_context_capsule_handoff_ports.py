from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction,
    WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedTransportTargetContextCapsuleHandoffError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus(StrEnum):
    NONE = "none"
    TERMINAL = "terminal"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"


class WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    capsule_schema_id: str
    capsule_schema_version: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    custody_contract_id: str
    custody_contract_version: str
    approved_adapter_id: str
    approved_adapter_version: str
    verification_signing_key_id: str
    trusted_profile_digest: str
    scope: WorkflowScope
    request_nonce_digest: str
    requested_at: datetime


class WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor(Protocol):
    async def attest_capsule_handoff_lifecycle(
        self, request: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation: ...


class WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor(Protocol):
    async def attest_consumer_boundary_acceptance(
        self,
        request: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest,
    ) -> WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation: ...


class WorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier(Protocol):
    def verify_capsule_handoff_lifecycle_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation
    ) -> bool: ...

    def verify_consumer_boundary_acceptance_attestation(
        self, attestation: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation
    ) -> bool: ...


class WorkflowProtectedTargetContextCapsuleSealedHandoffAdapter(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def adapter_id(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    @property
    def adapter_contract_id(self) -> str: ...

    @property
    def adapter_contract_version(self) -> str: ...

    async def handoff_sealed_capsule(
        self, instruction: WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt: ...

    def verify_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleHandoffReplayLookupRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    handoff_id: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleHandoffReplayLookup:
    status: WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus
    attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt | None
    result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult | None


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleHandoffClaimRequest:
    claim_id: str
    attempt_id: str
    handoff_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    expected_consumer_binding_id: str
    expected_consumer_binding_digest: str
    expected_sealed_capsule_id: str
    expected_sealed_capsule_digest: str
    expected_capsule_schema_id: str
    expected_capsule_schema_version: str
    lifecycle_attestation: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation
    acceptance_attestation: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: (
        WorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_adapter_contract_id: str
    expected_adapter_contract_version: str
    expected_approved_adapter_id: str
    expected_approved_adapter_version: str
    expected_destination_boundary_id: str
    expected_destination_deployment_id: str
    expected_destination_generation: int
    expected_destination_fencing_token_digest: str
    expected_custody_contract_id: str
    expected_custody_contract_version: str
    expected_verification_signing_key_id: str
    expected_trusted_profile_digest: str
    minimum_remaining_budget_milliseconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    consumption_authorization_audit_payload: dict[str, object]
    consumption_authorization_audit_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleHandoffClaimResult:
    status: WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus
    claim: WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim | None
    attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt | None
    result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult | None


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleHandoffResultRequest:
    result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult
    receipt: WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextCapsuleHandoffResultWrite:
    status: WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus
    result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult | None


class WorkflowTargetContextCapsuleHandoffRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_target_context_capsule_handoff_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease | None: ...

    async def get_target_context_capsule_consumer_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None: ...

    async def lookup_target_context_capsule_handoff_replay(
        self, request: WorkflowTargetContextCapsuleHandoffReplayLookupRequest
    ) -> WorkflowTargetContextCapsuleHandoffReplayLookup: ...

    async def claim_target_context_capsule_handoff(
        self, request: WorkflowTargetContextCapsuleHandoffClaimRequest
    ) -> WorkflowTargetContextCapsuleHandoffClaimResult: ...

    async def record_target_context_capsule_handoff_result(
        self, request: WorkflowTargetContextCapsuleHandoffResultRequest
    ) -> WorkflowTargetContextCapsuleHandoffResultWrite: ...

    async def list_target_context_capsule_handoff_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt, ...]: ...

    async def get_target_context_capsule_handoff_results_by_handoff_ids(
        self, *, scope: WorkflowScope, handoff_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffResult, ...]: ...


def validate_workflow_target_context_capsule_handoff_claim_request(
    request: WorkflowTargetContextCapsuleHandoffClaimRequest,
) -> None:
    lifecycle = request.lifecycle_attestation
    acceptance = request.acceptance_attestation
    expected_audit_payload: dict[str, object] = {
        "schema_id": "audit.workflow-target-context-capsule-handoff-consumption-authorization",
        "schema_version": "1.0",
        "event_type": "target_context_capsule_handoff_lease_consumption_authorized",
        "claim_id": request.claim_id,
        "attempt_id": request.attempt_id,
        "handoff_id": request.handoff_id,
        "authorization_lease_id": request.authorization_lease_id,
        "authorization_lease_digest": request.authorization_lease_digest,
        "scope": request.scope.canonical_value(),
        "consumer_subject_id": request.consumer_subject_id,
        "consumer_audience": request.consumer_audience,
        "policy_id": request.expected_policy_id,
        "policy_version": request.expected_policy_version,
        "policy_digest": request.expected_policy_digest,
        "idempotency_digest": request.idempotency_digest,
        "request_fingerprint": request.request_fingerprint,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
    }
    if (
        request.irreversible_consumption_acknowledged is not True
        or request.uncertain_outcome_requires_new_authorization_acknowledged is not True
        or request.consumer_subject_id
        != "service.workflow-protected-transport-target-context-capsule-consumer"
        or request.consumer_audience
        != "audience.workflow-protected-transport-target-context-capsule-consumer"
        or request.expected_policy_id
        != "policy.workflow-protected-transport-target-context-capsule-handoff-consumption"
        or request.expected_policy_version != "1.0"
        or request.expected_adapter_contract_id
        != "contract.workflow-protected-target-context-capsule-sealed-handoff"
        or request.expected_adapter_contract_version != "1.0"
        or request.expected_approved_adapter_id
        != "adapter.workflow-protected-target-context-capsule-sealed-handoff"
        or request.expected_approved_adapter_version != "1.0"
        or request.expected_destination_boundary_id
        != "boundary.workflow-protected-target-context-capsule-consumer"
        or request.expected_destination_deployment_id
        != "deployment.workflow-protected-target-context-capsule-consumer"
        or request.expected_destination_generation != 1
        or request.expected_custody_contract_id
        != "contract.workflow-protected-target-context-capsule-custody"
        or request.expected_custody_contract_version != "1.0"
        or request.expected_verification_signing_key_id
        != "key.workflow-protected-target-context-capsule-handoff-receipt.v1"
        or request.minimum_remaining_budget_milliseconds != 100
        or lifecycle.attestor_id
        != "attestor.workflow-protected-target-context-capsule-handoff-lifecycle"
        or lifecycle.attestor_version != "1.0"
        or acceptance.attestor_id
        != "attestor.workflow-protected-target-context-consumer-boundary-acceptance"
        or acceptance.attestor_version != "1.0"
        or lifecycle.authorization_lease_id != request.authorization_lease_id
        or lifecycle.authorization_lease_digest != request.authorization_lease_digest
        or acceptance.authorization_lease_id != request.authorization_lease_id
        or acceptance.authorization_lease_digest != request.authorization_lease_digest
        or lifecycle.consumer_binding_id != request.expected_consumer_binding_id
        or lifecycle.consumer_binding_digest != request.expected_consumer_binding_digest
        or acceptance.consumer_binding_id != request.expected_consumer_binding_id
        or acceptance.consumer_binding_digest != request.expected_consumer_binding_digest
        or lifecycle.sealed_capsule_id != request.expected_sealed_capsule_id
        or lifecycle.sealed_capsule_digest != request.expected_sealed_capsule_digest
        or lifecycle.capsule_schema_id != request.expected_capsule_schema_id
        or lifecycle.capsule_schema_version != request.expected_capsule_schema_version
        or acceptance.capsule_schema_id != request.expected_capsule_schema_id
        or acceptance.capsule_schema_version != request.expected_capsule_schema_version
        or acceptance.destination_boundary_id != request.expected_destination_boundary_id
        or acceptance.destination_deployment_id != request.expected_destination_deployment_id
        or acceptance.destination_generation != request.expected_destination_generation
        or acceptance.destination_fencing_token_digest
        != request.expected_destination_fencing_token_digest
        or acceptance.custody_contract_id != request.expected_custody_contract_id
        or acceptance.custody_contract_version != request.expected_custody_contract_version
        or acceptance.approved_adapter_id != request.expected_approved_adapter_id
        or acceptance.approved_adapter_version != request.expected_approved_adapter_version
        or acceptance.verification_signing_key_id != request.expected_verification_signing_key_id
        or acceptance.trusted_profile_digest != request.expected_trusted_profile_digest
        or acceptance.consumer_subject_id != request.consumer_subject_id
        or acceptance.consumer_audience != request.consumer_audience
        or acceptance.consumer_contract_id != request.consumer_contract_id
        or acceptance.consumer_contract_version != request.consumer_contract_version
        or acceptance.purpose_id != request.purpose_id
        or lifecycle.request_nonce_digest != request.expected_request_nonce_digest
        or acceptance.request_nonce_digest != request.expected_request_nonce_digest
        or lifecycle.canonical_digest != canonical_digest(lifecycle.digest_payload())
        or acceptance.canonical_digest != canonical_digest(acceptance.digest_payload())
        or lifecycle.handoff_eligible is not True
        or lifecycle.revoked is not False
        or lifecycle.destroyed is not False
        or lifecycle.sealed is not True
        or lifecycle.already_handed_off is not False
        or lifecycle.capsule_is_bearer_capability is not False
        or acceptance.acceptance_eligible is not True
        or acceptance.destination_is_protected_boundary is not True
        or acceptance.runtime_use_authorized is not False
        or request.consumption_authorization_audit_payload != expected_audit_payload
        or request.consumption_authorization_audit_digest
        != canonical_digest(expected_audit_payload)
    ):
        raise ValueError("target context capsule handoff claim evidence is unsafe")
    try:
        lifecycle_valid = (
            request.offline_signature_verifier.verify_capsule_handoff_lifecycle_attestation(
                lifecycle
            )
        )
        acceptance_valid = (
            request.offline_signature_verifier.verify_consumer_boundary_acceptance_attestation(
                acceptance
            )
        )
    except Exception as exc:
        raise ValueError("target context capsule handoff attestation signature is invalid") from exc
    if lifecycle_valid is not True or acceptance_valid is not True:
        raise ValueError("target context capsule handoff attestation signature is invalid")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("target context capsule handoff idempotency key is invalid")
    for value in (
        request.authorization_lease_digest,
        request.expected_consumer_binding_digest,
        request.expected_sealed_capsule_digest,
        request.expected_request_nonce_digest,
        request.expected_policy_digest,
        request.expected_destination_fencing_token_digest,
        request.expected_trusted_profile_digest,
        request.idempotency_digest,
        request.request_fingerprint,
        request.consumption_authorization_audit_digest,
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("target context capsule handoff claim digest is invalid")


__all__ = [
    "WorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier",
    "WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest",
    "WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor",
    "WorkflowProtectedTargetContextCapsuleSealedHandoffAdapter",
    "WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest",
    "WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffError",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus",
    "WorkflowTargetContextCapsuleHandoffClaimRequest",
    "WorkflowTargetContextCapsuleHandoffClaimResult",
    "WorkflowTargetContextCapsuleHandoffReplayLookup",
    "WorkflowTargetContextCapsuleHandoffReplayLookupRequest",
    "WorkflowTargetContextCapsuleHandoffRepository",
    "WorkflowTargetContextCapsuleHandoffResultRequest",
    "WorkflowTargetContextCapsuleHandoffResultWrite",
    "validate_workflow_target_context_capsule_handoff_claim_request",
]
