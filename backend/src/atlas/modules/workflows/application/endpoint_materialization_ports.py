from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
    WorkflowEventPhysicalTransportEndpointMaterializationInstruction,
    WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowScope,
)


class WorkflowEventPhysicalTransportEndpointMaterializationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowEventPhysicalTransportEndpointMaterializationUncertainError(
    WorkflowEventPhysicalTransportEndpointMaterializationError
):
    pass


class WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowEventPhysicalTransportEndpointMaterializationResultStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest:
    """Expected evidence for the locked, database-timed point of no return."""

    claim_id: str
    attempt_id: str
    materialization_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    expected_freshness_admission_id: str
    expected_freshness_admission_digest: str
    expected_freshness_valid_until: datetime
    expected_physical_transport_route_binding_id: str
    expected_physical_transport_route_binding_digest: str
    expected_transport_route_snapshot_id: str
    expected_transport_route_snapshot_digest: str
    expected_current_selection_head_id: str
    expected_current_selection_head_digest: str
    expected_current_selection_head_generation: int
    expected_current_selection_head_fencing_token_digest: str
    expected_route_set_id: str
    expected_route_set_revision: str
    expected_selection_epoch_id: str
    expected_selection_epoch_revision: str
    expected_selected_route_id: str
    expected_selected_route_revision: str
    expected_selected_route_digest: str
    expected_selection_active: bool
    expected_selection_eligible: bool
    expected_selection_suspended: bool
    expected_selection_withdrawn: bool
    expected_selection_superseded: bool
    expected_lease_state: str
    expected_endpoint_resolution_authorized: bool
    expected_materialization_policy_id: str
    expected_materialization_policy_version: str
    expected_materialization_policy_digest: str
    scope: WorkflowScope
    resolver_subject_id: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationClaimResult:
    status: WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus
    claim: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim | None
    attempt: WorkflowEventPhysicalTransportEndpointMaterializationAttempt | None
    result: WorkflowEventPhysicalTransportEndpointMaterializationResult | None


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationResultRequest:
    result: WorkflowEventPhysicalTransportEndpointMaterializationResult
    expected_claim_digest: str
    expected_attempt_digest: str
    expected_current_selection_head_id: str
    expected_current_selection_head_digest: str
    expected_current_selection_head_generation: int
    expected_current_selection_head_fencing_token_digest: str
    expected_lease_valid_until: datetime


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointMaterializationResultWrite:
    status: WorkflowEventPhysicalTransportEndpointMaterializationResultStatus
    result: WorkflowEventPhysicalTransportEndpointMaterializationResult | None


class WorkflowPhysicalTransportEndpointMaterializer(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def materializer_contract_id(self) -> str: ...

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportEndpointMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationReceipt: ...


class WorkflowEventPhysicalTransportEndpointMaterializationRepository(Protocol):
    """Owns fixed-order locking, database time, and append-only persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_endpoint_resolution_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None: ...

    async def get_route_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None: ...

    async def get_physical_transport_route_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None: ...

    async def get_transport_route_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportRouteSnapshot | None: ...

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> DeploymentEventTransportRouteSelectionHead | None: ...

    async def get_endpoint_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim | None: ...

    async def get_endpoint_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttempt | None: ...

    async def list_endpoint_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointMaterializationAttempt, ...]: ...

    async def get_endpoint_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult | None: ...

    async def claim_endpoint_materialization(
        self, request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationClaimResult:
        """Atomically lock/revalidate and append one claim plus one started attempt."""
        ...

    async def record_endpoint_materialization_result(
        self, request: WorkflowEventPhysicalTransportEndpointMaterializationResultRequest
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResultWrite:
        """Append one known result without changing its claim, attempt, or lease."""
        ...


__all__ = [
    "WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest",
    "WorkflowEventPhysicalTransportEndpointMaterializationClaimResult",
    "WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus",
    "WorkflowEventPhysicalTransportEndpointMaterializationError",
    "WorkflowEventPhysicalTransportEndpointMaterializationRepository",
    "WorkflowEventPhysicalTransportEndpointMaterializationResultRequest",
    "WorkflowEventPhysicalTransportEndpointMaterializationResultStatus",
    "WorkflowEventPhysicalTransportEndpointMaterializationResultWrite",
    "WorkflowEventPhysicalTransportEndpointMaterializationUncertainError",
    "WorkflowPhysicalTransportEndpointMaterializer",
]
