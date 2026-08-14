from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowScope,
)


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord:
    request_fingerprint: str
    lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest:
    """Expected evidence for the locked, database-timed authorization transaction."""

    authorization_lease_id: str
    expected_freshness_admission_id: str
    expected_freshness_admission_digest: str
    expected_freshness_admission_valid_until: datetime
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
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    resolver_subject_id: str
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult:
    status: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus
    lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository(Protocol):
    """Owns database time, fixed-order locking, and atomic lease/claim persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime:
        """Return repository-authoritative time for preflight and replay decisions."""
        ...

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

    async def get_endpoint_resolution_authorization_lease(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None: ...

    async def list_endpoint_resolution_authorization_leases(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease, ...]: ...

    async def get_endpoint_resolution_authorization_lease_request(
        self,
        *,
        scope: WorkflowScope,
        resolver_subject_id: str,
        idempotency_key: str,
    ) -> (
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord | None
    ): ...

    async def authorize_endpoint_resolution(
        self,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult:
        """Lock sources, use database time, revalidate, and persist atomically."""
        ...


__all__ = [
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError",
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord",
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository",
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest",
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult",
    "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus",
]
