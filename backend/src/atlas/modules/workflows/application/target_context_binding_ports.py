from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowScope,
)


class WorkflowEventPhysicalTransportTargetContextBindingError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventPhysicalTransportTargetContextBindingStatus(StrEnum):
    BOUND = "bound"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_BOUND = "already_bound"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextBindingRequest:
    expected_endpoint_materialization_id: str
    expected_endpoint_materialization_digest: str
    expected_credential_materialization_id: str
    expected_credential_materialization_digest: str
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    scope: WorkflowScope
    binder_subject_id: str
    requested_at: datetime
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportTargetContextBindingResult:
    status: WorkflowEventPhysicalTransportTargetContextBindingStatus
    binding: WorkflowEventPhysicalTransportTargetContextBinding | None


class WorkflowEventPhysicalTransportTargetContextBindingRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def bind_target_context(
        self,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
    ) -> WorkflowEventPhysicalTransportTargetContextBindingResult: ...

    async def list_target_context_bindings(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextBinding, ...]: ...


__all__ = [
    "WorkflowEventPhysicalTransportTargetContextBindingError",
    "WorkflowEventPhysicalTransportTargetContextBindingRepository",
    "WorkflowEventPhysicalTransportTargetContextBindingRequest",
    "WorkflowEventPhysicalTransportTargetContextBindingResult",
    "WorkflowEventPhysicalTransportTargetContextBindingStatus",
]
