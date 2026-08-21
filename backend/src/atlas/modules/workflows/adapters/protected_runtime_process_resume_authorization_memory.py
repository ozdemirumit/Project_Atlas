from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from atlas.modules.workflows.application.protected_runtime_process_resume_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState,
    WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
    WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest,
    validate_workflow_protected_runtime_process_resume_authorization_request,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_process_resume_authorization_domain import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
)


class InMemoryWorkflowProtectedRuntimeProcessResumeAuthorizationRepository:
    """Non-durable contract adapter for focused tests; never a production authority."""

    durable = False

    def __init__(
        self,
        *,
        sources: Iterable[WorkflowProtectedRuntimeProcessResumeAuthorizationSource] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()
        self._sources = {
            (source.result.scope, source.result.result_id): source for source in sources
        }
        self._leases: dict[
            tuple[WorkflowScope, str],
            WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
        ] = {}
        self._replays: dict[
            tuple[WorkflowScope, str],
            tuple[str, str, WorkflowProtectedRuntimeProcessResumeAuthorizationLease],
        ] = {}
        self._source_grants: dict[
            tuple[WorkflowScope, str],
            WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
        ] = {}

    async def get_authoritative_time(self) -> datetime:
        observed_at = self._clock()
        if observed_at.tzinfo is None:
            raise ValueError("in-memory scheduling authorization clock must be timezone-aware")
        return observed_at

    async def preflight_protected_runtime_process_resume_authorization(
        self,
        request: WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest,
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult:
        evaluated_at = await self.get_authoritative_time()
        replay = self._replays.get((request.scope, request.idempotency_key))
        if replay is not None:
            stored_idempotency_digest, stored_fingerprint, lease = replay
            status = (
                WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.REPLAY
                if (
                    stored_idempotency_digest == request.idempotency_digest
                    and stored_fingerprint == request.request_fingerprint
                )
                else (
                    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.IDEMPOTENCY_CONFLICT
                )
            )
            return WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult(
                status=status,
                lease=lease if status.value == "replay" else None,
                evaluated_at=evaluated_at,
            )
        if (request.scope, request.process_scheduling_result_id) in self._source_grants:
            return WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult(
                status=(
                    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.ALREADY_AUTHORIZED
                ),
                lease=None,
                evaluated_at=evaluated_at,
            )
        return WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult(
            status=WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.NONE,
            lease=None,
            evaluated_at=evaluated_at,
        )

    async def get_protected_runtime_process_resume_authorization_source(
        self,
        request: WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest,
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationSource | None:
        source = self._sources.get((request.scope, request.process_scheduling_result_id))
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

    async def authorize_protected_runtime_process_resume(
        self,
        request: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest,
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult:
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
                    return WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult(
                        status=(
                            WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus.REPLAY
                        ),
                        lease=lease,
                        evaluated_at=evaluated_at,
                    )
                return WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult(
                    status=(
                        WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT
                    ),
                    lease=None,
                    evaluated_at=evaluated_at,
                )
            source_key = (request.scope, request.source.result.result_id)
            if source_key in self._source_grants:
                return WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult(
                    status=(
                        WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus.ALREADY_AUTHORIZED
                    ),
                    lease=None,
                    evaluated_at=evaluated_at,
                )
            try:
                validate_workflow_protected_runtime_process_resume_authorization_request(request)
            except ValueError:
                return WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult(
                    status=(
                        WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus.EVIDENCE_CONFLICT
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
            return WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult(
                status=WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus.AUTHORIZED,
                lease=lease,
                evaluated_at=evaluated_at,
            )

    async def list_protected_runtime_process_resume_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation, ...]:
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
            WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation(
                lease=lease,
                consumed=False,
                evaluated_at=evaluated_at,
                effective_state=(
                    WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState.ACTIVE
                    if lease.is_active(evaluated_at=evaluated_at)
                    else (
                        WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState.EXPIRED
                    )
                ),
                protected_runtime_process_resume_authority_granted=lease.is_active(
                    evaluated_at=evaluated_at
                ),
            )
            for lease in leases
        )


__all__ = [
    "InMemoryWorkflowProtectedRuntimeProcessResumeAuthorizationRepository",
]
