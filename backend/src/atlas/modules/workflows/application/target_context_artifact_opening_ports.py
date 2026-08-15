from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.application.target_context_access_authorization_lease_ports import (
    WorkflowProtectedArtifactStatusSignatureVerifier,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowProtectedArtifactKind,
    WorkflowProtectedArtifactStatusAttestation,
    WorkflowScope,
    canonical_digest,
)


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError(
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError
):
    pass


class WorkflowTargetContextArtifactOpeningClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


class WorkflowTargetContextArtifactOpeningResultStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextArtifactOpeningClaimRequest:
    """Offline evidence for the locked, database-timed point of no return."""

    claim_id: str
    attempt_id: str
    opening_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    expected_target_context_binding_id: str
    expected_target_context_binding_digest: str
    expected_target_context_commitment: str
    expected_endpoint_materialization_id: str
    expected_endpoint_materialization_digest: str
    expected_endpoint_protected_artifact_id: str
    expected_endpoint_protected_artifact_digest: str
    expected_endpoint_usable_until: datetime
    expected_credential_materialization_id: str
    expected_credential_materialization_digest: str
    expected_credential_protected_artifact_id: str
    expected_credential_protected_artifact_digest: str
    expected_credential_usable_until: datetime
    endpoint_status_attestation: WorkflowProtectedArtifactStatusAttestation
    credential_status_attestation: WorkflowProtectedArtifactStatusAttestation
    expected_request_nonce_digest: str
    offline_signature_verifier: WorkflowProtectedArtifactStatusSignatureVerifier
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_opener_contract_id: str
    expected_opener_attestor_id: str
    scope: WorkflowScope
    accessor_subject_id: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextArtifactOpeningClaimResult:
    status: WorkflowTargetContextArtifactOpeningClaimStatus
    claim: WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim | None
    attempt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt | None
    result: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult | None


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextArtifactOpeningResultRequest:
    result: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult
    expected_claim_digest: str
    expected_attempt_digest: str
    expected_lease_valid_until: datetime
    expected_target_context_binding_digest: str
    expected_endpoint_materialization_digest: str
    expected_credential_materialization_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextArtifactOpeningResultWrite:
    status: WorkflowTargetContextArtifactOpeningResultStatus
    result: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult | None


class WorkflowPhysicalTransportTargetContextArtifactOpener(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def opener_contract_id(self) -> str: ...

    async def open_paired_artifacts(
        self, instruction: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt: ...

    def verify_receipt(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> bool: ...

    async def destroy_capsule(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> bool: ...


class WorkflowTargetContextArtifactOpeningRepository(Protocol):
    """Owns fixed-order locking, DB time and append-only single-use persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_target_context_access_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease | None: ...

    async def get_target_context_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportTargetContextBinding | None: ...

    async def get_endpoint_materialization_result_by_id(
        self, *, materialization_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult | None: ...

    async def get_credential_materialization_result_by_id(
        self, *, materialization_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResult | None: ...

    async def claim_target_context_artifact_opening(
        self, request: WorkflowTargetContextArtifactOpeningClaimRequest
    ) -> WorkflowTargetContextArtifactOpeningClaimResult:
        """Atomically revalidate and append one irreversible claim plus attempt."""
        ...

    async def record_target_context_artifact_opening_result(
        self, request: WorkflowTargetContextArtifactOpeningResultRequest
    ) -> WorkflowTargetContextArtifactOpeningResultWrite:
        """Append one terminal result without changing lease, claim or attempt."""
        ...

    async def list_target_context_artifact_opening_results(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...]: ...


def validate_workflow_target_context_artifact_opening_claim_request(
    request: WorkflowTargetContextArtifactOpeningClaimRequest,
) -> None:
    endpoint = request.endpoint_status_attestation
    credential = request.credential_status_attestation
    if (
        request.irreversible_consumption_acknowledged is not True
        or request.uncertain_outcome_requires_new_authorization_acknowledged is not True
        or request.accessor_subject_id != "service.workflow-protected-transport-context-accessor"
        or request.expected_policy_id
        != "policy.workflow-event-physical-transport-target-context-artifact-opening"
        or request.expected_policy_version != "1.0"
        or request.expected_opener_contract_id
        != "contract.workflow-protected-target-context-artifact-opener.v1"
        or request.expected_opener_attestor_id
        != "attestor.workflow-protected-target-context-artifact-opener"
        or endpoint.artifact_kind is not WorkflowProtectedArtifactKind.ENDPOINT
        or credential.artifact_kind is not WorkflowProtectedArtifactKind.CREDENTIAL
        or endpoint.protected_store_attestor_id
        != "attestor.workflow-protected-endpoint-store-status"
        or endpoint.protected_store_attestor_version != "1.0"
        or credential.protected_store_attestor_id
        != "attestor.workflow-protected-credential-store-status"
        or credential.protected_store_attestor_version != "1.0"
        or endpoint.materialization_id != request.expected_endpoint_materialization_id
        or endpoint.materialization_digest != request.expected_endpoint_materialization_digest
        or credential.materialization_id != request.expected_credential_materialization_id
        or credential.materialization_digest != request.expected_credential_materialization_digest
        or endpoint.target_context_binding_id != request.expected_target_context_binding_id
        or credential.target_context_binding_id != request.expected_target_context_binding_id
        or endpoint.target_context_binding_digest != request.expected_target_context_binding_digest
        or credential.target_context_binding_digest
        != request.expected_target_context_binding_digest
        or endpoint.target_context_commitment != request.expected_target_context_commitment
        or credential.target_context_commitment != request.expected_target_context_commitment
        or endpoint.request_nonce_digest != request.expected_request_nonce_digest
        or credential.request_nonce_digest != request.expected_request_nonce_digest
        or endpoint.request_nonce_digest != credential.request_nonce_digest
        or not endpoint.usable
        or endpoint.revoked
        or endpoint.destroyed
        or not credential.usable
        or credential.revoked
        or credential.destroyed
        or endpoint.canonical_digest != canonical_digest(endpoint.digest_payload())
        or credential.canonical_digest != canonical_digest(credential.digest_payload())
        or endpoint.valid_until <= endpoint.observed_at
        or credential.valid_until <= credential.observed_at
        or request.expected_endpoint_usable_until.tzinfo is None
        or request.expected_credential_usable_until.tzinfo is None
    ):
        raise ValueError("target context artifact opening claim evidence is unsafe")
    try:
        endpoint_valid = request.offline_signature_verifier.verify_status_attestation(endpoint)
        credential_valid = request.offline_signature_verifier.verify_status_attestation(credential)
    except Exception as exc:
        raise ValueError("target context artifact opening status signature is invalid") from exc
    if endpoint_valid is not True or credential_valid is not True:
        raise ValueError("target context artifact opening status signature is invalid")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("target context artifact opening idempotency key is invalid")
    for value in (
        request.authorization_lease_digest,
        request.expected_target_context_binding_digest,
        request.expected_target_context_commitment,
        request.expected_endpoint_materialization_digest,
        request.expected_endpoint_protected_artifact_digest,
        request.expected_credential_materialization_digest,
        request.expected_credential_protected_artifact_digest,
        request.expected_request_nonce_digest,
        request.expected_policy_digest,
        request.idempotency_digest,
        request.request_fingerprint,
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("target context artifact opening claim digest is invalid")


__all__ = [
    "WorkflowEventPhysicalTransportTargetContextArtifactOpeningError",
    "WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError",
    "WorkflowPhysicalTransportTargetContextArtifactOpener",
    "WorkflowTargetContextArtifactOpeningClaimRequest",
    "WorkflowTargetContextArtifactOpeningClaimResult",
    "WorkflowTargetContextArtifactOpeningClaimStatus",
    "WorkflowTargetContextArtifactOpeningRepository",
    "WorkflowTargetContextArtifactOpeningResultRequest",
    "WorkflowTargetContextArtifactOpeningResultStatus",
    "WorkflowTargetContextArtifactOpeningResultWrite",
    "validate_workflow_target_context_artifact_opening_claim_request",
]
