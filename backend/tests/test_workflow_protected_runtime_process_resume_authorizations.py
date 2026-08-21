from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_protected_runtime_process_scheduling_consumptions import (
    _consume as _consume_process_scheduling,
)
from test_workflow_protected_runtime_process_scheduling_consumptions import (
    _Repository as _ProcessSchedulingRepository,
)
from test_workflow_protected_runtime_process_scheduling_consumptions import (
    _service as _process_scheduling_service,
)
from test_workflow_protected_runtime_process_scheduling_consumptions import (
    _source as _process_scheduling_source,
)
from workflow_process_creation_consumption_support import NOW, SCOPE

from atlas.modules.workflows.adapters.protected_runtime_process_resume_authorization_memory import (
    InMemoryWorkflowProtectedRuntimeProcessResumeAuthorizationRepository,
)
from atlas.modules.workflows.adapters.protected_runtime_process_schedulers import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_process_resume_authorization_ports import (  # noqa: E501
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION,
    WorkflowProtectedRuntimeProcessResumeAuthorizationError,
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
    WorkflowProtectedRuntimeProcessResumeStateAttestation,
    WorkflowProtectedRuntimeProcessResumeStateAttestationRequest,
    validate_workflow_protected_runtime_process_resume_authorization_request,
)
from atlas.modules.workflows.application.protected_runtime_process_resume_authorizations import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingResultRequest,
    WorkflowProtectedRuntimeProcessSchedulingResultWrite,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_resume_authorization_domain import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
    code_owned_workflow_protected_runtime_process_resume_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingReceipt,
)


class _SourceRepository(_ProcessSchedulingRepository):
    def __init__(self, source: object) -> None:
        super().__init__(cast(Any, source))
        self.receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt | None = None

    async def record_protected_runtime_process_scheduling_result(
        self, request: WorkflowProtectedRuntimeProcessSchedulingResultRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingResultWrite:
        self.receipt = request.receipt
        return await super().record_protected_runtime_process_scheduling_result(request)


async def _source() -> WorkflowProtectedRuntimeProcessResumeAuthorizationSource:
    repository = _SourceRepository(await _process_scheduling_source())
    service, _ = _process_scheduling_service(repository)
    await _consume_process_scheduling(service)
    assert repository.result is not None
    assert repository.attempt is not None
    assert repository.claim is not None
    assert repository.receipt is not None
    return WorkflowProtectedRuntimeProcessResumeAuthorizationSource(
        result=repository.result,
        attempt=repository.attempt,
        process_scheduling_claim=repository.claim,
        process_scheduling_receipt=repository.receipt,
        process_scheduling_authorization_lease=repository.source.authorization_lease,
        process_scheduling_authorization_claim=repository.source.authorization_claim,
    )


class _Repository:
    durable = True

    def __init__(self, source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource) -> None:
        self.source = source
        self.events: list[str] = []
        self.requests: list[WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest] = []
        self.leases: list[WorkflowProtectedRuntimeProcessResumeAuthorizationLease] = []
        self.preflight_status = (
            WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.NONE
        )
        self.replay_lease: WorkflowProtectedRuntimeProcessResumeAuthorizationLease | None = None

    async def get_authoritative_time(self) -> datetime:
        self.events.append("time")
        return self.source.result.recorded_at + timedelta(milliseconds=200)

    async def preflight_protected_runtime_process_resume_authorization(
        self, request: WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult:
        del request
        self.events.append("preflight")
        return WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightResult(
            status=self.preflight_status,
            lease=self.replay_lease,
            evaluated_at=self.source.result.recorded_at,
        )

    async def get_protected_runtime_process_resume_authorization_source(
        self, request: WorkflowProtectedRuntimeProcessResumeAuthorizationSourceRequest
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationSource:
        assert request.process_scheduling_result_id == self.source.result.result_id
        self.events.append("source")
        return self.source

    async def authorize_protected_runtime_process_resume(
        self, request: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult:
        self.events.append("authorize")
        validate_workflow_protected_runtime_process_resume_authorization_request(request)
        self.requests.append(request)
        self.leases.append(request.candidate)
        return WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseResult(
            status=WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseStatus.AUTHORIZED,
            lease=request.candidate,
            evaluated_at=self.source.result.recorded_at + timedelta(milliseconds=250),
        )

    async def list_protected_runtime_process_resume_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation, ...]:
        leases = [
            lease
            for lease in self.leases
            if lease.scope == scope
            and (
                authorization_lease_ids is None
                or lease.authorization_lease_id in authorization_lease_ids
            )
        ][:limit]
        return tuple(
            WorkflowProtectedRuntimeProcessResumeAuthorizationPresentation(
                lease=lease,
                consumed=False,
                evaluated_at=evaluated_at,
                effective_state=(
                    WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState.ACTIVE
                    if lease.is_active(evaluated_at=evaluated_at)
                    else WorkflowProtectedRuntimeProcessResumeAuthorizationPresentationState.EXPIRED
                ),
                protected_runtime_process_resume_authority_granted=lease.is_active(
                    evaluated_at=evaluated_at
                ),
            )
            for lease in leases
        )


class _Attestor:
    available = True

    def __init__(self, repository: _Repository, **overrides: object) -> None:
        self.repository = repository
        self.overrides = overrides

    async def attest_runtime_process_resume_state(
        self, request: WorkflowProtectedRuntimeProcessResumeStateAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessResumeStateAttestation:
        self.repository.events.append("attest")
        values: dict[str, object] = {
            **{
                name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
            },
            "attestation_id": "process-resume-state-attestation.test",
            "attestor_id": WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID,
            "attestor_version": WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION,
            "signing_key_id": (
                WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID
            ),
            "signature_algorithm": "hmac-sha256",
            "observed_at": self.repository.source.result.recorded_at + timedelta(milliseconds=100),
            "valid_until": self.repository.source.result.recorded_at + timedelta(milliseconds=900),
            "process_state_eligible_until": self.repository.source.result.recorded_at
            + timedelta(seconds=1),
            "exact_process_scheduling_result_confirmed": True,
            "terminal_success_confirmed": True,
            "metadata_only_confirmed": True,
            "process_created_confirmed": True,
            "process_sealed_confirmed": True,
            "process_suspended_confirmed": True,
            "process_scheduled_confirmed": True,
            "process_not_runnable_confirmed": True,
            "process_not_resumed_confirmed": True,
            "process_not_dispatched_confirmed": True,
            "process_not_executed_confirmed": True,
            "runtime_envelope_current": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "protected_slot_generation_current": True,
            "prior_process_resume_claim_absent": True,
            "prior_process_resume_lease_absent": True,
            "pending_or_conflicting_resume_absent": True,
            "pending_or_conflicting_dispatch_absent": True,
            "pending_or_conflicting_execution_absent": True,
            "pending_or_conflicting_supervision_absent": True,
            "pending_or_conflicting_stop_absent": True,
            "pending_or_conflicting_cleanup_absent": True,
            "pending_or_conflicting_replacement_absent": True,
            "pending_or_conflicting_rescheduling_absent": True,
            "scheduling_performed": False,
            "resume_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "mcp_activity_performed": False,
            "provider_activity_performed": False,
            "infrastructure_mutation_performed": False,
            "process_locator_included": False,
            "process_identifier_included": False,
            "process_material_included": False,
            "runtime_material_included": False,
            "command_material_included": False,
            "argument_material_included": False,
            "environment_material_included": False,
            "prompt_material_included": False,
            "model_material_included": False,
            "endpoint_material_included": False,
            "credential_material_included": False,
            "secret_material_included": False,
            "integrity_signature": "a" * 64,
            **self.overrides,
        }
        attestation = WorkflowProtectedRuntimeProcessResumeStateAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        return replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )

    def verify_runtime_process_resume_state_attestation(
        self,
        attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation,
    ) -> bool:
        del attestation
        return True


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def record(self, record: object) -> None:
        self.records.append(record)


def _context(
    *,
    subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-229",
        decision_id="decision.imp-229",
        requested_at=NOW,
    )


def _service(
    repository: _Repository,
    *,
    overrides: dict[str, object] | None = None,
    audit: _AuditSink | None = None,
) -> WorkflowProtectedRuntimeProcessResumeAuthorizationService:
    attestor = _Attestor(repository, **(overrides or {}))
    return WorkflowProtectedRuntimeProcessResumeAuthorizationService(
        authorization_repository=cast(Any, repository),
        process_state_attestor=attestor,
        process_state_signature_verifier=attestor,
        process_scheduling_receipt_signature_verifier=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier(
                development_enabled=True
            )
        ),
        audit_sink=cast(Any, audit or _AuditSink()),
    )


async def _authorize(
    service: WorkflowProtectedRuntimeProcessResumeAuthorizationService,
    source: WorkflowProtectedRuntimeProcessResumeAuthorizationSource,
) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLease:
    policy = code_owned_workflow_protected_runtime_process_resume_authorization_policy()
    return await service.authorize(
        process_scheduling_result_id=source.result.result_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        single_use_nonrenewable_nontransferable_future_request_acknowledged=True,
        single_use_future_request_only_acknowledged=True,
        idempotency_key="process-resume-auth.test",
        context=_context(),
    )


@pytest.mark.asyncio
async def test_canonical_source_issues_only_bounded_future_request_authority() -> None:
    source = await _source()
    repository = _Repository(source)
    audit = _AuditSink()
    service = _service(repository, audit=audit)
    lease = await _authorize(service, source)

    assert repository.events == ["preflight", "source", "attest", "time", "authorize"]
    assert lease.authorization_lease_id.startswith(
        "workflow-protected-runtime-process-resume-authorization-lease."
    )
    assert lease.valid_until - lease.issued_at <= timedelta(seconds=1)
    assert lease.valid_until - lease.issued_at >= timedelta(milliseconds=100)
    assert repository.requests[0].expected_minimum_remaining_safety_margin_milliseconds == 100
    authority = lease.authority.canonical_value()
    assert authority.pop("protected_runtime_process_resume_authority_granted") is True
    assert not any(authority.values())
    assert not inspect.signature(service.authorize).parameters.keys() & {
        "command",
        "executable",
        "network",
        "connector",
        "provider",
    }
    metadata = dict(cast(Any, audit.records[-1]).target_metadata)
    assert metadata["scheduling_performed"] == "false"
    assert metadata["execution_authority"] == "false"
    assert metadata["infrastructure_mutation_authority"] == "false"


@pytest.mark.asyncio
async def test_attestation_drift_and_non_workload_fail_before_authorization() -> None:
    source = await _source()
    repository = _Repository(source)
    with pytest.raises(WorkflowProtectedRuntimeProcessResumeAuthorizationError):
        await _authorize(_service(repository, overrides={"scheduling_performed": True}), source)
    assert "authorize" not in repository.events

    denied_repository = _Repository(source)
    service = _service(denied_repository)
    policy = service.policy
    with pytest.raises(WorkflowProtectedRuntimeProcessResumeAuthorizationError):
        await service.authorize(
            process_scheduling_result_id=source.result.result_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            single_use_nonrenewable_nontransferable_future_request_acknowledged=True,
            single_use_future_request_only_acknowledged=True,
            idempotency_key="process-resume-auth.test",
            context=_context(subject_id="human.user"),
        )
    assert denied_repository.events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confirmation",
    (
        "pending_or_conflicting_resume_absent",
        "pending_or_conflicting_dispatch_absent",
        "pending_or_conflicting_execution_absent",
        "pending_or_conflicting_supervision_absent",
        "pending_or_conflicting_stop_absent",
        "pending_or_conflicting_cleanup_absent",
        "pending_or_conflicting_replacement_absent",
        "pending_or_conflicting_rescheduling_absent",
    ),
)
async def test_pending_or_conflicting_process_state_fails_closed(
    confirmation: str,
) -> None:
    source = await _source()
    repository = _Repository(source)

    with pytest.raises(WorkflowProtectedRuntimeProcessResumeAuthorizationError):
        await _authorize(_service(repository, overrides={confirmation: False}), source)

    assert "authorize" not in repository.events


@pytest.mark.asyncio
async def test_insufficient_remaining_safety_margin_fails_closed() -> None:
    source = await _source()
    repository = _Repository(source)
    deadline = source.result.recorded_at + timedelta(milliseconds=250)

    with pytest.raises(WorkflowProtectedRuntimeProcessResumeAuthorizationError):
        await _authorize(
            _service(
                repository,
                overrides={
                    "valid_until": deadline,
                    "process_state_eligible_until": deadline,
                },
            ),
            source,
        )

    assert "authorize" not in repository.events


@pytest.mark.asyncio
async def test_code_owned_safety_margin_is_bound_into_repository_request() -> None:
    source = await _source()
    repository = _Repository(source)
    await _authorize(_service(repository), source)
    request = repository.requests[0]

    with pytest.raises(ValueError, match="evidence is invalid"):
        validate_workflow_protected_runtime_process_resume_authorization_request(
            replace(
                request,
                expected_minimum_remaining_safety_margin_milliseconds=0,
            )
        )


@pytest.mark.asyncio
async def test_exact_replay_returns_same_lease_without_protected_state_io() -> None:
    source = await _source()
    initial_repository = _Repository(source)
    lease = await _authorize(_service(initial_repository), source)
    replay_repository = _Repository(source)
    replay_repository.preflight_status = (
        WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.REPLAY
    )
    replay_repository.replay_lease = lease

    replay = await _authorize(_service(replay_repository), source)

    assert replay == lease
    assert replay_repository.events == ["preflight"]


@pytest.mark.asyncio
async def test_in_memory_repository_cannot_become_production_authority() -> None:
    source = await _source()
    repository = InMemoryWorkflowProtectedRuntimeProcessResumeAuthorizationRepository(
        sources=(source,), clock=lambda: NOW
    )
    assert repository.durable is False
    with pytest.raises(
        WorkflowProtectedRuntimeProcessResumeAuthorizationError,
        match="denied",
    ):
        await _authorize(_service(cast(Any, repository)), source)
