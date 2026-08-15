from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
    WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowScope,
)


class WorkflowEventPhysicalTransportCredentialMaterializationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowEventPhysicalTransportCredentialMaterializationUncertainError(
    WorkflowEventPhysicalTransportCredentialMaterializationError
):
    pass


class WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


class WorkflowEventPhysicalTransportCredentialMaterializationResultStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest:
    """Expected evidence for the locked, database-timed point of no return."""

    claim_id: str
    attempt_id: str
    materialization_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    expected_freshness_admission_id: str
    expected_freshness_admission_digest: str
    expected_freshness_valid_until: datetime
    expected_credential_assignment_binding_id: str
    expected_credential_assignment_binding_digest: str
    expected_credential_assignment_snapshot_id: str
    expected_credential_assignment_snapshot_digest: str
    expected_assignment_id: str
    expected_assignment_revision: str
    expected_source_assignment_digest: str
    expected_credential_generation: int
    expected_rotation_epoch: int
    expected_assignment_activated_at: datetime
    expected_assignment_expires_at: datetime
    expected_assignment_active: bool
    expected_assignment_revoked: bool
    expected_lease_state: str
    expected_credential_access_authorized: bool
    expected_materialization_policy_id: str
    expected_materialization_policy_version: str
    expected_materialization_policy_digest: str
    scope: WorkflowScope
    accessor_subject_id: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationClaimResult:
    status: WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus
    claim: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim | None
    attempt: WorkflowEventPhysicalTransportCredentialMaterializationAttempt | None
    result: WorkflowEventPhysicalTransportCredentialMaterializationResult | None


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationResultRequest:
    result: WorkflowEventPhysicalTransportCredentialMaterializationResult
    expected_claim_digest: str
    expected_attempt_digest: str
    expected_assignment_id: str
    expected_assignment_revision: str
    expected_source_assignment_digest: str
    expected_credential_generation: int
    expected_rotation_epoch: int
    expected_lease_valid_until: datetime


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportCredentialMaterializationResultWrite:
    status: WorkflowEventPhysicalTransportCredentialMaterializationResultStatus
    result: WorkflowEventPhysicalTransportCredentialMaterializationResult | None


class WorkflowPhysicalTransportCredentialMaterializer(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def materializer_contract_id(self) -> str: ...

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportCredentialMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationReceipt: ...

    async def revoke_or_destroy(
        self, receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt
    ) -> bool: ...


class WorkflowEventPhysicalTransportCredentialMaterializationRepository(Protocol):
    """Owns fixed-order locking, DB time, and append-only consumption persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_credential_access_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease | None: ...

    async def get_credential_assignment_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission | None: ...

    async def get_credential_assignment_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None: ...

    async def get_credential_assignment_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None: ...

    async def get_current_credential_assignment_head(
        self, *, assignment_id: str
    ) -> DeploymentPhysicalTransportCredentialAssignment | None: ...

    async def get_credential_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim | None: ...

    async def get_credential_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationAttempt | None: ...

    async def list_credential_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportCredentialMaterializationAttempt, ...]: ...

    async def get_credential_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResult | None: ...

    async def claim_credential_materialization(
        self, request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationClaimResult:
        """Atomically revalidate and append one claim plus one started attempt."""
        ...

    async def record_credential_materialization_result(
        self, request: WorkflowEventPhysicalTransportCredentialMaterializationResultRequest
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResultWrite:
        """Append one known result without changing claim, attempt, or lease."""
        ...


__all__ = [
    "WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest",
    "WorkflowEventPhysicalTransportCredentialMaterializationClaimResult",
    "WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus",
    "WorkflowEventPhysicalTransportCredentialMaterializationError",
    "WorkflowEventPhysicalTransportCredentialMaterializationRepository",
    "WorkflowEventPhysicalTransportCredentialMaterializationResultRequest",
    "WorkflowEventPhysicalTransportCredentialMaterializationResultStatus",
    "WorkflowEventPhysicalTransportCredentialMaterializationResultWrite",
    "WorkflowEventPhysicalTransportCredentialMaterializationUncertainError",
    "WorkflowPhysicalTransportCredentialMaterializer",
]
