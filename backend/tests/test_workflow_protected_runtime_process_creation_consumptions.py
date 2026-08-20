from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest
from workflow_process_creation_consumption_support import NOW, SCOPE, authorization_source

from atlas.modules.workflows.adapters.protected_runtime_process_creators import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator,
    DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationClaimRequest,
    WorkflowProtectedRuntimeProcessCreationClaimWrite,
    WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus,
    WorkflowProtectedRuntimeProcessCreationConsumptionError,
    WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus,
    WorkflowProtectedRuntimeProcessCreationConsumptionSource,
    WorkflowProtectedRuntimeProcessCreationReplayLookup,
    WorkflowProtectedRuntimeProcessCreationReplayLookupRequest,
    WorkflowProtectedRuntimeProcessCreationResultRequest,
    WorkflowProtectedRuntimeProcessCreationResultWrite,
    WorkflowProtectedRuntimeProcessCreationResultWriteStatus,
    validate_workflow_protected_runtime_process_creation_claim_request,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumptions import (
    WorkflowProtectedRuntimeProcessCreationConsumptionPresentation,
    WorkflowProtectedRuntimeProcessCreationConsumptionService,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationAttempt,
    WorkflowProtectedRuntimeProcessCreationConsumptionClaim,
    WorkflowProtectedRuntimeProcessCreationConsumptionResultState,
    WorkflowProtectedRuntimeProcessCreationInvocation,
    WorkflowProtectedRuntimeProcessCreationReceipt,
    WorkflowProtectedRuntimeProcessCreationResult,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)


class _Repository:
    durable = True

    def __init__(self) -> None:
        claim, lease = authorization_source()
        self.source = WorkflowProtectedRuntimeProcessCreationConsumptionSource(
            authorization_lease=lease, authorization_claim=claim
        )
        self.claim: WorkflowProtectedRuntimeProcessCreationConsumptionClaim | None = None
        self.attempt: WorkflowProtectedRuntimeProcessCreationAttempt | None = None
        self.result: WorkflowProtectedRuntimeProcessCreationResult | None = None
        self.events: list[str] = []
        self.source_reads = 0
        self.time_reads = 0

    async def get_authoritative_time(self) -> datetime:
        self.time_reads += 1
        return NOW

    async def lookup_protected_runtime_process_creation_replay(
        self, request: WorkflowProtectedRuntimeProcessCreationReplayLookupRequest
    ) -> WorkflowProtectedRuntimeProcessCreationReplayLookup:
        del request
        if self.result is not None:
            status = (
                WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.ATTEMPT_UNCERTAIN
                if self.result.result_state
                is (
                    WorkflowProtectedRuntimeProcessCreationConsumptionResultState
                ).PROCESS_CREATION_OUTCOME_UNCERTAIN
                else WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.TERMINAL
            )
            return WorkflowProtectedRuntimeProcessCreationReplayLookup(
                status=status, attempt=self.attempt, result=self.result
            )
        if self.attempt is not None:
            return WorkflowProtectedRuntimeProcessCreationReplayLookup(
                status=(
                    WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.ATTEMPT_PENDING
                ),
                attempt=self.attempt,
            )
        return WorkflowProtectedRuntimeProcessCreationReplayLookup(
            status=WorkflowProtectedRuntimeProcessCreationConsumptionReplayStatus.NONE
        )

    async def get_protected_runtime_process_creation_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionSource:
        self.source_reads += 1
        assert authorization_lease_id == self.source.authorization_lease.authorization_lease_id
        return self.source

    async def claim_protected_runtime_process_creation(
        self, request: WorkflowProtectedRuntimeProcessCreationClaimRequest
    ) -> WorkflowProtectedRuntimeProcessCreationClaimWrite:
        validate_workflow_protected_runtime_process_creation_claim_request(request)
        self.events.append("claim_and_attempt_committed")
        self.claim = request.candidate_claim
        self.attempt = request.candidate_attempt
        return WorkflowProtectedRuntimeProcessCreationClaimWrite(
            status=WorkflowProtectedRuntimeProcessCreationConsumptionClaimStatus.CLAIMED,
            claim=request.candidate_claim,
            attempt=request.candidate_attempt,
        )

    async def record_protected_runtime_process_creation_result(
        self, request: WorkflowProtectedRuntimeProcessCreationResultRequest
    ) -> WorkflowProtectedRuntimeProcessCreationResultWrite:
        assert self.claim is not None
        assert self.attempt is not None
        assert request.expected_claim_digest == self.claim.canonical_digest
        assert request.expected_attempt_digest == self.attempt.canonical_digest
        self.events.append("result_recorded")
        self.result = request.result
        return WorkflowProtectedRuntimeProcessCreationResultWrite(
            status=WorkflowProtectedRuntimeProcessCreationResultWriteStatus.RECORDED,
            result=request.result,
        )

    async def list_protected_runtime_process_creation_attempts(
        self, **kwargs: Any
    ) -> tuple[WorkflowProtectedRuntimeProcessCreationAttempt, ...]:
        del kwargs
        return () if self.attempt is None else (self.attempt,)

    async def get_protected_runtime_process_creation_results(
        self, **kwargs: Any
    ) -> tuple[WorkflowProtectedRuntimeProcessCreationResult, ...]:
        del kwargs
        return () if self.result is None else (self.result,)


class _Creator:
    def __init__(
        self,
        repository: _Repository,
        outcome: DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome = (
            DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome.SUCCESS
        ),
    ) -> None:
        self._repository = repository
        self._delegate = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
            development_enabled=True, clock=lambda: NOW, outcome=outcome
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def create_sealed_suspended_process(
        self, invocation: WorkflowProtectedRuntimeProcessCreationInvocation
    ) -> WorkflowProtectedRuntimeProcessCreationReceipt:
        assert self._repository.events == ["claim_and_attempt_committed"]
        self._repository.events.append("creator_called")
        return await self._delegate.create_sealed_suspended_process(invocation)

    @property
    def calls(self) -> list[WorkflowProtectedRuntimeProcessCreationInvocation]:
        return self._delegate.calls


def _service(
    repository: _Repository,
    *,
    outcome: DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome = (
        DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome.SUCCESS
    ),
) -> tuple[WorkflowProtectedRuntimeProcessCreationConsumptionService, _Creator]:
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner(
        development_enabled=True
    )
    verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier(
            development_enabled=True
        )
    )
    creator = _Creator(repository, outcome)
    service = WorkflowProtectedRuntimeProcessCreationConsumptionService(
        repository=repository,
        instruction_signer=signer,
        instruction_signature_verifier=verifier,
        receipt_signature_verifier=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(
                development_enabled=True
            )
        ),
        creator=creator,
    )
    return service, creator


async def _consume(
    service: WorkflowProtectedRuntimeProcessCreationConsumptionService,
    **changes: object,
) -> WorkflowProtectedRuntimeProcessCreationConsumptionPresentation:
    policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    values = {
        "authorization_lease_id": "process-creation-authorization-lease.test",
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "idempotency_key": "process-creation-idempotency.test",
    }
    values.update(changes)
    return await service.consume(**cast(Any, values))


@pytest.mark.asyncio
async def test_claim_commit_precedes_one_creator_call_and_replay_has_no_io() -> None:
    repository = _Repository()
    service, creator = _service(repository)

    first = await _consume(service)
    replay = await _consume(service)

    assert first == replay
    assert first.result is not None
    assert first.result.result_state.value == "process_created_suspended_in_protected_boundary"
    assert repository.events == [
        "claim_and_attempt_committed",
        "creator_called",
        "result_recorded",
    ]
    assert len(creator.calls) == 1
    assert repository.source_reads == 1
    assert repository.time_reads == 1


@pytest.mark.asyncio
async def test_ambiguous_post_commit_outcome_records_permanent_uncertainty_without_retry() -> None:
    repository = _Repository()
    service, creator = _service(
        repository,
        outcome=DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome.OUTCOME_UNCERTAIN,
    )

    first = await _consume(service)
    assert first.result is not None
    assert first.result.result_state.value == "process_creation_outcome_uncertain"
    assert first.result.process_created is None
    assert first.result.process_sealed is None
    assert first.result.process_suspended is None
    with pytest.raises(
        WorkflowProtectedRuntimeProcessCreationConsumptionError,
        match="permanently_uncertain",
    ):
        await _consume(service)
    assert len(creator.calls) == 1
    assert repository.source_reads == 1
    assert repository.time_reads == 1


@pytest.mark.asyncio
async def test_human_or_ai_identity_is_rejected_before_repository_io() -> None:
    repository = _Repository()
    service, creator = _service(repository)

    with pytest.raises(
        WorkflowProtectedRuntimeProcessCreationConsumptionError,
        match="exact_workload_required",
    ):
        await _consume(service, consumer_subject_id="human.admin")
    with pytest.raises(
        WorkflowProtectedRuntimeProcessCreationConsumptionError,
        match="exact_workload_required",
    ):
        await _consume(service, consumer_subject_id="ai.agent")
    assert repository.source_reads == 0
    assert repository.time_reads == 0
    assert creator.calls == []


def test_public_service_surface_accepts_no_process_or_runtime_material() -> None:
    names = WorkflowProtectedRuntimeProcessCreationConsumptionService.consume.__annotations__

    assert set(names).isdisjoint(
        {
            "command",
            "executable",
            "args",
            "environment",
            "working_directory",
            "runtime_locator",
            "runtime_material",
        }
    )
