from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowScope,
)


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus(StrEnum):
    ADMITTED_CURRENT = "admitted_current"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_ADMITTED = "already_admitted"


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord:
    request_fingerprint: str
    admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest:
    """Expected evidence that the repository must revalidate while holding source locks."""

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
    expected_policy_digest: str
    scope: WorkflowScope
    admitter_subject_id: str
    evaluated_at: datetime
    candidate: WorkflowEventPhysicalTransportRouteFreshnessAdmission
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult:
    status: WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus
    admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission | None


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository(Protocol):
    """Owns source reads and the atomic freshness-admission transaction boundary."""

    @property
    def durable(self) -> bool: ...

    async def synchronize_route_selection_heads(
        self, heads: tuple[DeploymentEventTransportRouteSelectionHead, ...]
    ) -> None:
        """Provision deployment-owned heads during internal application startup only."""
        ...

    async def get_physical_transport_route_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None: ...

    async def get_transport_route_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportRouteSnapshot | None: ...

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> DeploymentEventTransportRouteSelectionHead | None: ...

    async def get_route_freshness_admission(
        self, *, physical_transport_route_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None: ...

    async def list_route_freshness_admissions(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportRouteFreshnessAdmission, ...]: ...

    async def get_route_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord | None: ...

    async def admit_physical_transport_route_freshness(
        self, request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult:
        """Lock sources in order, revalidate them, and persist atomically."""
        ...


__all__ = [
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionError",
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord",
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository",
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest",
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult",
    "WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus",
]
