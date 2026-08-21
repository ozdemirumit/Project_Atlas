from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_protected_runtime_process_scheduling_authorizations import (
    _authorize,
)
from test_workflow_protected_runtime_process_scheduling_authorizations import (
    _Repository as _AuthorizationRepository,
)
from test_workflow_protected_runtime_process_scheduling_authorizations import (
    _service as _authorization_service,
)
from test_workflow_protected_runtime_process_scheduling_authorizations import (
    _source as _authorization_source,
)
from workflow_process_creation_consumption_support import NOW

from atlas.modules.workflows.adapters.protected_runtime_process_schedulers import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
    DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingClaimRequest,
    WorkflowProtectedRuntimeProcessSchedulingClaimWrite,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionSource,
    WorkflowProtectedRuntimeProcessSchedulingReplayLookup,
    WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest,
    WorkflowProtectedRuntimeProcessSchedulingResultRequest,
    WorkflowProtectedRuntimeProcessSchedulingResultWrite,
    WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus,
    validate_workflow_protected_runtime_process_scheduling_claim_request,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumptions import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionService,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingAttempt,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
    WorkflowProtectedRuntimeProcessSchedulingInvocation,
    WorkflowProtectedRuntimeProcessSchedulingReceipt,
    WorkflowProtectedRuntimeProcessSchedulingResult,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)


async def _source() -> WorkflowProtectedRuntimeProcessSchedulingConsumptionSource:
    source = await _authorization_source()
    repository = _AuthorizationRepository(source)
    lease = await _authorize(_authorization_service(repository), source)
    request = repository.requests[-1]
    return WorkflowProtectedRuntimeProcessSchedulingConsumptionSource(
        authorization_lease=lease,
        authorization_claim=request.candidate_claim,
    )


class _Repository:
    durable = True

    def __init__(self, source: WorkflowProtectedRuntimeProcessSchedulingConsumptionSource) -> None:
        self.source = source
        self.claim: WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim | None = None
        self.attempt: WorkflowProtectedRuntimeProcessSchedulingAttempt | None = None
        self.result: WorkflowProtectedRuntimeProcessSchedulingResult | None = None
        self.events: list[str] = []
        self.source_reads = 0
        self.time_reads = 0

    async def get_authoritative_time(self) -> datetime:
        self.time_reads += 1
        return NOW + timedelta(milliseconds=300)

    async def lookup_protected_runtime_process_scheduling_replay(
        self, request: WorkflowProtectedRuntimeProcessSchedulingReplayLookupRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingReplayLookup:
        del request
        if self.result is not None:
            states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
            status = (
                WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.ATTEMPT_UNCERTAIN
                if self.result.result_state is states.PROCESS_SCHEDULING_OUTCOME_UNCERTAIN
                else WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.TERMINAL
            )
            return WorkflowProtectedRuntimeProcessSchedulingReplayLookup(
                status=status, attempt=self.attempt, result=self.result
            )
        if self.attempt is not None:
            return WorkflowProtectedRuntimeProcessSchedulingReplayLookup(
                status=WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.ATTEMPT_PENDING,
                attempt=self.attempt,
            )
        return WorkflowProtectedRuntimeProcessSchedulingReplayLookup(
            status=WorkflowProtectedRuntimeProcessSchedulingConsumptionReplayStatus.NONE
        )

    async def get_protected_runtime_process_scheduling_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionSource:
        self.source_reads += 1
        assert authorization_lease_id == self.source.authorization_lease.authorization_lease_id
        return self.source

    async def claim_protected_runtime_process_scheduling(
        self, request: WorkflowProtectedRuntimeProcessSchedulingClaimRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingClaimWrite:
        validate_workflow_protected_runtime_process_scheduling_claim_request(request)
        self.events.append("claim_and_attempt_committed")
        self.claim = request.candidate_claim
        self.attempt = request.candidate_attempt
        return WorkflowProtectedRuntimeProcessSchedulingClaimWrite(
            status=WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimStatus.CLAIMED,
            claim=request.candidate_claim,
            attempt=request.candidate_attempt,
        )

    async def record_protected_runtime_process_scheduling_result(
        self, request: WorkflowProtectedRuntimeProcessSchedulingResultRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingResultWrite:
        assert self.claim is not None
        assert self.attempt is not None
        assert request.expected_claim_digest == self.claim.canonical_digest
        assert request.expected_attempt_digest == self.attempt.canonical_digest
        self.events.append("result_recorded")
        self.result = request.result
        return WorkflowProtectedRuntimeProcessSchedulingResultWrite(
            status=WorkflowProtectedRuntimeProcessSchedulingResultWriteStatus.RECORDED,
            result=request.result,
        )

    async def list_protected_runtime_process_scheduling_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeProcessSchedulingAttempt, ...]:
        assert scope == self.source.authorization_lease.scope
        assert limit == 256
        return () if self.attempt is None else (self.attempt,)

    async def get_protected_runtime_process_scheduling_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedRuntimeProcessSchedulingResult, ...]:
        assert scope == self.source.authorization_lease.scope
        if self.result is None or self.result.consumption_id not in consumption_ids:
            return ()
        return (self.result,)


class _Scheduler:
    def __init__(
        self,
        repository: _Repository,
        outcome: DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome = (
            DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.SUCCESS
        ),
    ) -> None:
        self._repository = repository
        self._delegate = DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler(
            development_enabled=True,
            clock=lambda: NOW + timedelta(milliseconds=350),
            outcome=outcome,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def schedule_suspended_process(
        self, invocation: WorkflowProtectedRuntimeProcessSchedulingInvocation
    ) -> WorkflowProtectedRuntimeProcessSchedulingReceipt:
        assert self._repository.events == ["claim_and_attempt_committed"]
        self._repository.events.append("scheduler_called")
        return await self._delegate.schedule_suspended_process(invocation)

    @property
    def calls(self) -> list[WorkflowProtectedRuntimeProcessSchedulingInvocation]:
        return self._delegate.calls


def _service(
    repository: _Repository,
    *,
    outcome: DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome = (
        DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.SUCCESS
    ),
) -> tuple[WorkflowProtectedRuntimeProcessSchedulingConsumptionService, _Scheduler]:
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner(
        development_enabled=True
    )
    verifier = DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier(  # noqa: E501
        development_enabled=True
    )
    scheduler = _Scheduler(repository, outcome)
    service = WorkflowProtectedRuntimeProcessSchedulingConsumptionService(
        repository=repository,
        instruction_signer=signer,
        instruction_signature_verifier=verifier,
        receipt_signature_verifier=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier(
                development_enabled=True
            )
        ),
        scheduler=scheduler,
    )
    return service, scheduler


async def _consume(
    service: WorkflowProtectedRuntimeProcessSchedulingConsumptionService,
    **changes: object,
) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation:
    policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    values = {
        "authorization_lease_id": (
            service.repository.source.authorization_lease.authorization_lease_id  # type: ignore[attr-defined]
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "idempotency_key": "process-scheduling-idempotency.test",
    }
    values.update(changes)
    return await service.consume(**cast(Any, values))


@pytest.mark.asyncio
async def test_claim_commit_precedes_one_scheduler_call_and_replay_has_no_io() -> None:
    repository = _Repository(await _source())
    service, scheduler = _service(repository)

    first = await _consume(service)
    replay = await _consume(service)

    assert first == replay
    assert first.result is not None
    states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    assert first.result.result_state is states.PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
    assert first.result.process_scheduled is True
    assert first.result.process_suspended is True
    assert first.result.process_runnable is False
    assert not any(first.result.authority.canonical_value().values())
    assert repository.events == [
        "claim_and_attempt_committed",
        "scheduler_called",
        "result_recorded",
    ]
    assert len(scheduler.calls) == 1
    assert repository.source_reads == 1
    assert repository.time_reads == 1


@pytest.mark.asyncio
async def test_ambiguous_post_commit_outcome_is_permanent_and_never_retried() -> None:
    repository = _Repository(await _source())
    service, scheduler = _service(
        repository,
        outcome=DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.OUTCOME_UNCERTAIN,
    )

    first = await _consume(service)
    assert first.result is not None
    states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    assert first.result.result_state is states.PROCESS_SCHEDULING_OUTCOME_UNCERTAIN
    assert first.result.process_scheduled is None
    assert first.result.process_suspended is None
    assert first.result.process_runnable is None
    with pytest.raises(
        WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
        match="permanently_uncertain",
    ):
        await _consume(service)
    assert len(scheduler.calls) == 1
    assert repository.source_reads == 1
    assert repository.time_reads == 1


@pytest.mark.asyncio
async def test_wrong_policy_or_missing_acknowledgement_fails_before_repository_io() -> None:
    repository = _Repository(await _source())
    service, scheduler = _service(repository)

    with pytest.raises(
        WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
        match="code_owned_policy_required",
    ):
        await _consume(service, policy_id="policy.caller-controlled")
    with pytest.raises(
        WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
        match="acknowledgement_required",
    ):
        await _consume(service, uncertainty_no_retry_acknowledged=False)
    assert repository.source_reads == 0
    assert repository.time_reads == 0
    assert scheduler.calls == []


def test_public_service_surface_accepts_only_bounded_consumption_metadata() -> None:
    parameters = inspect.signature(
        WorkflowProtectedRuntimeProcessSchedulingConsumptionService.consume
    ).parameters

    assert set(parameters) == {
        "self",
        "authorization_lease_id",
        "policy_id",
        "policy_version",
        "irreversible_consumption_acknowledged",
        "uncertainty_no_retry_acknowledged",
        "idempotency_key",
    }
    assert set(parameters).isdisjoint(
        {
            "process_locator",
            "process_identifier",
            "runtime_locator",
            "command",
            "executable",
            "args",
            "environment",
            "scheduler",
            "queue",
            "priority",
            "affinity",
            "resources",
        }
    )
