from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from atlas.modules.workflows.application.protected_runtime_process_scheduling_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest,
    validate_workflow_protected_runtime_process_scheduling_authorization_request,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
)


class InMemoryWorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository:
    """Non-durable contract adapter for focused tests; never a production authority."""

    durable = False

    def __init__(
        self,
        *,
        sources: Iterable[WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()
        self._sources = {
            (source.result.scope, source.result.result_id): source for source in sources
        }
        self._leases: dict[
            tuple[WorkflowScope, str],
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
        ] = {}
        self._replays: dict[
            tuple[WorkflowScope, str],
            tuple[str, str, WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease],
        ] = {}
        self._source_grants: dict[
            tuple[WorkflowScope, str],
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
        ] = {}

    async def get_authoritative_time(self) -> datetime:
        observed_at = self._clock()
        if observed_at.tzinfo is None:
            raise ValueError("in-memory scheduling authorization clock must be timezone-aware")
        return observed_at

    async def preflight_protected_runtime_process_scheduling_authorization(
        self,
        request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest,
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult:
        evaluated_at = await self.get_authoritative_time()
        replay = self._replays.get((request.scope, request.idempotency_key))
        if replay is not None:
            stored_idempotency_digest, stored_fingerprint, lease = replay
            status = (
                WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus.REPLAY
                if (
                    stored_idempotency_digest == request.idempotency_digest
                    and stored_fingerprint == request.request_fingerprint
                )
                else (
                    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus.IDEMPOTENCY_CONFLICT
                )
            )
            return WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult(
                status=status,
                lease=lease if status.value == "replay" else None,
                evaluated_at=evaluated_at,
            )
        if (request.scope, request.process_creation_result_id) in self._source_grants:
            return WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult(
                status=(
                    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus.ALREADY_AUTHORIZED
                ),
                lease=None,
                evaluated_at=evaluated_at,
            )
        return WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightResult(
            status=WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus.NONE,
            lease=None,
            evaluated_at=evaluated_at,
        )

    async def get_protected_runtime_process_scheduling_authorization_source(
        self,
        request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest,
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationSource | None:
        source = self._sources.get((request.scope, request.process_creation_result_id))
        if source is None:
            return None
        result = source.result
        if (
            result.consumer_subject_id != request.consumer_subject_id
            or result.consumer_audience != request.consumer_audience
            or result.consumer_contract_id != request.consumer_contract_id
            or result.consumer_contract_version != request.consumer_contract_version
        ):
            return None
        return source

    async def authorize_protected_runtime_process_scheduling(
        self,
        request: WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest,
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult:
        async with self._lock:
            evaluated_at = await self.get_authoritative_time()
            replay_key = (request.scope, request.idempotency_key)
            replay = self._replays.get(replay_key)
            if replay is not None:
                stored_idempotency_digest, stored_fingerprint, lease = replay
                if (
                    stored_idempotency_digest == request.idempotency_digest
                    and stored_fingerprint == request.request_fingerprint
                ):
                    return WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult(
                        status=(
                            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.REPLAY
                        ),
                        lease=lease,
                        evaluated_at=evaluated_at,
                    )
                return WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult(
                    status=(
                        WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT
                    ),
                    lease=None,
                    evaluated_at=evaluated_at,
                )
            source_key = (request.scope, request.source.result.result_id)
            if source_key in self._source_grants:
                return WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult(
                    status=(
                        WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.ALREADY_AUTHORIZED
                    ),
                    lease=None,
                    evaluated_at=evaluated_at,
                )
            try:
                validate_workflow_protected_runtime_process_scheduling_authorization_request(
                    request
                )
            except ValueError:
                return WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult(
                    status=(
                        WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.EVIDENCE_CONFLICT
                    ),
                    lease=None,
                    evaluated_at=evaluated_at,
                )
            lease = request.candidate
            self._leases[(request.scope, lease.authorization_lease_id)] = lease
            self._source_grants[source_key] = lease
            self._replays[replay_key] = (
                request.idempotency_digest,
                request.request_fingerprint,
                lease,
            )
            return WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseResult(
                status=WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.AUTHORIZED,
                lease=lease,
                evaluated_at=evaluated_at,
            )

    async def list_protected_runtime_process_scheduling_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation, ...]:
        if evaluated_at.tzinfo is None:
            raise ValueError("scheduling authorization presentation time must be aware")
        requested_ids = set(authorization_lease_ids or ())
        leases = sorted(
            (
                lease
                for (lease_scope, _), lease in self._leases.items()
                if lease_scope == scope
                and (
                    authorization_lease_ids is None or lease.authorization_lease_id in requested_ids
                )
            ),
            key=lambda lease: (lease.issued_at, lease.authorization_lease_id),
            reverse=True,
        )[: max(0, limit)]
        return tuple(
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentation(
                lease=lease,
                consumed=False,
                evaluated_at=evaluated_at,
                effective_state=(
                    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState.ACTIVE
                    if lease.is_active(evaluated_at=evaluated_at)
                    else (
                        WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState.EXPIRED
                    )
                ),
                protected_runtime_process_scheduling_authority_granted=lease.is_active(
                    evaluated_at=evaluated_at
                ),
            )
            for lease in leases
        )


__all__ = [
    "InMemoryWorkflowProtectedRuntimeProcessSchedulingAuthorizationRepository",
]
