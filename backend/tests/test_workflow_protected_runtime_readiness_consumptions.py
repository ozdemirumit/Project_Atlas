from __future__ import annotations

import asyncio
import inspect
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessConsumptionClaimRequest,
    WorkflowProtectedRuntimeReadinessConsumptionClaimStatus,
    WorkflowProtectedRuntimeReadinessConsumptionClaimWrite,
    WorkflowProtectedRuntimeReadinessConsumptionError,
    WorkflowProtectedRuntimeReadinessConsumptionReplayLookup,
    WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeReadinessConsumptionReplayStatus,
    WorkflowProtectedRuntimeReadinessConsumptionResultRequest,
    WorkflowProtectedRuntimeReadinessConsumptionResultWrite,
    WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus,
    WorkflowProtectedRuntimeReadinessConsumptionSource,
    validate_workflow_protected_runtime_readiness_consumption_claim_request,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumptions import (
    WorkflowProtectedRuntimeReadinessConsumptionPresentation,
    WorkflowProtectedRuntimeReadinessConsumptionService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationAuthority,
    WorkflowProtectedRuntimeReadinessAuthorizationClaim,
    WorkflowProtectedRuntimeReadinessAuthorizationLease,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeReadinessAttempt,
    WorkflowProtectedRuntimeReadinessConsumptionClaim,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessResult,
    WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionResultState,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


class _AuditSink:
    def __init__(self) -> None:
        self.events: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.events.append(event)


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    if hasattr(value, "digest_payload") and hasattr(value, "canonical_digest"):
        return value.digest_payload() | {"canonical_digest": value.canonical_digest}
    return value


def _digest(values: dict[str, object]) -> str:
    return canonical_digest({name: _canonical_value(value) for name, value in values.items()})


def _authorization_source() -> WorkflowProtectedRuntimeReadinessConsumptionSource:
    policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
    claim_values: dict[str, object] = {
        "claim_id": "runtime-readiness-authorization-claim.imp-225",
        "start_result_id": "runtime-start-result.imp-224",
        "start_result_digest": "1" * 64,
        "start_consumption_id": "runtime-start-consumption.imp-224",
        "start_attempt_id": "runtime-start-attempt.imp-224",
        "start_attempt_digest": "2" * 64,
        "start_claim_id": "runtime-start-claim.imp-224",
        "start_claim_digest": "3" * 64,
        "start_authorization_lease_id": "runtime-start-authorization-lease.imp-223",
        "start_authorization_lease_digest": "4" * 64,
        "starter_receipt_digest": "5" * 64,
        "start_result_state": (
            WorkflowProtectedRuntimeStartConsumptionResultState
        ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY,
        "start_completed_at": NOW - timedelta(milliseconds=500),
        "start_result_recorded_at": NOW - timedelta(milliseconds=400),
        "start_outcome_known": True,
        "runtime_started": True,
        "destination_deployment_id": "deployment.imp-226",
        "destination_generation": 7,
        "destination_fencing_token_digest": "6" * 64,
        "protected_slot_commitment": "7" * 64,
        "protected_slot_generation": 11,
        "runtime_envelope_id": "runtime-envelope.imp-226",
        "runtime_envelope_commitment": "8" * 64,
        "runtime_envelope_generation": 11,
        "runtime_start_profile_id": "profile.runtime-start",
        "runtime_start_profile_version": "1.0",
        "runtime_start_profile_digest": "9" * 64,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "request_fingerprint": "a" * 64,
        "idempotency_digest": "b" * 64,
        "authorization_audit_digest": "c" * 64,
        "claimed_at": NOW - timedelta(milliseconds=100),
        "authority": WorkflowProtectedRuntimeReadinessAuthorizationAuthority(),
    }
    claim = WorkflowProtectedRuntimeReadinessAuthorizationClaim(
        **cast(Any, claim_values), canonical_digest=_digest(claim_values)
    )
    lease_aliases: dict[str, object] = {
        "authorization_lease_id": "runtime-readiness-authorization-lease.imp-225",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        "lifecycle_attestation_id": "runtime-readiness-attestation.imp-225",
        "lifecycle_attestation_digest": "d" * 64,
        "lifecycle_attestation_valid_until": NOW + timedelta(milliseconds=900),
        "runtime_envelope_eligible_until": NOW + timedelta(milliseconds=900),
        "readiness_profile_id": policy.readiness_profile_id,
        "readiness_profile_version": policy.readiness_profile_version,
        "readiness_profile_digest": policy.readiness_profile_digest,
        "issued_at": NOW - timedelta(milliseconds=50),
        "valid_until": NOW + timedelta(milliseconds=700),
        "effective_until": NOW + timedelta(milliseconds=700),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": WorkflowProtectedRuntimeReadinessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED,
        "authority": WorkflowProtectedRuntimeReadinessAuthorizationAuthority(
            protected_runtime_readiness_authority_granted=True
        ),
    }
    lease_values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeReadinessAuthorizationLease):
        if field.name == "canonical_digest":
            continue
        lease_values[field.name] = (
            lease_aliases[field.name] if field.name in lease_aliases else getattr(claim, field.name)
        )
    lease = WorkflowProtectedRuntimeReadinessAuthorizationLease(
        **cast(Any, lease_values), canonical_digest=_digest(lease_values)
    )
    return WorkflowProtectedRuntimeReadinessConsumptionSource(lease, claim)


def _context() -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-226",
        decision_id="decision.imp-226",
        requested_at=NOW,
    )


class _InstructionSigner:
    available = True
    signing_key_id = WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID
    signature_algorithm = WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        assert len(payload_digest) == 64
        return "e" * 64


class _InstructionVerifier:
    def __init__(self, *, valid: bool = True, available: bool = True) -> None:
        self.valid = valid
        self.available = available

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope
    ) -> bool:
        del envelope
        return self.valid


class _ReceiptVerifier:
    def __init__(self, *, valid: bool = True, available: bool = True) -> None:
        self.valid = valid
        self.available = available

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeReadinessReceipt) -> bool:
        del receipt
        return self.valid


class _Assessor:
    available = True

    def __init__(
        self,
        repository: _Repository,
        events: list[str],
        *,
        state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
        fail: bool = False,
        cancel: bool = False,
        late: bool = False,
        missing: bool = False,
    ) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        self.assessor_contract_id = policy.required_assessor_contract_id
        self.assessor_contract_version = policy.required_assessor_contract_version
        self.assessor_id = policy.approved_assessor_id
        self.assessor_version = policy.approved_assessor_version
        self.readiness_profile_id = policy.readiness_profile_id
        self.readiness_profile_version = policy.readiness_profile_version
        self.readiness_profile_digest = policy.readiness_profile_digest
        self._repository = repository
        self._events = events
        self._state = state
        self._fail = fail
        self._cancel = cancel
        self._late = late
        self._missing = missing
        self.calls = 0

    async def assess_runtime_readiness(
        self, invocation: Any
    ) -> WorkflowProtectedRuntimeReadinessReceipt:
        assert self._repository.committed is True
        self._events.append("assessor")
        self.calls += 1
        if self._cancel:
            raise asyncio.CancelledError
        if self._fail:
            raise TimeoutError("protected readiness assessor unavailable")
        if self._missing:
            return cast(WorkflowProtectedRuntimeReadinessReceipt, None)
        instruction = invocation.signed_instruction_envelope.instruction
        failed = (
            self._state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
        )
        ready = (
            self._state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
        )
        aliases: dict[str, object] = {
            "attempt_digest": instruction.attempt_digest,
            "instruction_digest": instruction.canonical_digest,
            "assessment_count_pre": 0,
            "assessment_count_post": 0 if failed else 1,
            "result_state": self._state,
            "runtime_ready": None if failed else ready,
            "readiness_assessment_performed": not failed,
            "runtime_locator_returned": False,
            "process_identifier_returned": False,
            "runtime_context_returned": False,
            "endpoint_material_returned": False,
            "credential_material_returned": False,
            "secret_material_returned": False,
            "command_constructed": False,
            "prompt_constructed": False,
            "model_inference_performed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "mcp_activity_performed": False,
            "publication_performed": False,
            "delivery_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
            "completed_at": NOW + timedelta(milliseconds=800 if self._late else 400),
            "signing_key_id": (
                code_owned_workflow_protected_runtime_readiness_consumption_policy()
            ).receipt_verification_signing_key_id,
            "signature_algorithm": (
                code_owned_workflow_protected_runtime_readiness_consumption_policy()
            ).receipt_signature_algorithm,
            "integrity_signature": "f" * 64,
        }
        values: dict[str, object] = {}
        for field in fields(WorkflowProtectedRuntimeReadinessReceipt):
            if field.name == "canonical_digest":
                continue
            values[field.name] = (
                aliases[field.name] if field.name in aliases else getattr(instruction, field.name)
            )
        return WorkflowProtectedRuntimeReadinessReceipt(
            **cast(Any, values), canonical_digest=_digest(values)
        )


class _Repository:
    durable = True

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.source = _authorization_source()
        self.claim: WorkflowProtectedRuntimeReadinessConsumptionClaim | None = None
        self.attempt: WorkflowProtectedRuntimeReadinessAttempt | None = None
        self.result: WorkflowProtectedRuntimeReadinessResult | None = None
        self.committed = False
        self.claim_commit_fails = False
        self.known_result_write_fails = False
        self.known_result_commit_ack_lost = False
        self.uncertainty_write_fails = False
        self.postcommit_authoritative_time = NOW + timedelta(milliseconds=500)
        self.force_replay_none = False
        self.replay_status: WorkflowProtectedRuntimeReadinessConsumptionReplayStatus | None = None
        self.claim_status = WorkflowProtectedRuntimeReadinessConsumptionClaimStatus.CLAIMED

    async def lookup_protected_runtime_readiness_consumption_replay(
        self, request: WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest
    ) -> WorkflowProtectedRuntimeReadinessConsumptionReplayLookup:
        del request
        self.events.append("replay")
        if self.attempt is None or self.force_replay_none:
            return WorkflowProtectedRuntimeReadinessConsumptionReplayLookup(
                WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.NONE
            )
        status = self.replay_status or (
            WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.TERMINAL
            if self.result is not None
            else WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.ATTEMPT_PENDING
        )
        return WorkflowProtectedRuntimeReadinessConsumptionReplayLookup(
            status,
            attempt=self.attempt,
            result=self.result,
            evaluated_at=NOW + timedelta(milliseconds=500),
        )

    async def get_protected_runtime_readiness_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeReadinessConsumptionSource:
        self.events.append("source")
        assert authorization_lease_id == self.source.authorization_lease.authorization_lease_id
        return self.source

    async def get_authoritative_time(self) -> datetime:
        self.events.append("time")
        return NOW if not self.committed else self.postcommit_authoritative_time

    async def claim_protected_runtime_readiness_consumption(
        self, request: WorkflowProtectedRuntimeReadinessConsumptionClaimRequest
    ) -> WorkflowProtectedRuntimeReadinessConsumptionClaimWrite:
        self.events.append("claim")
        validate_workflow_protected_runtime_readiness_consumption_claim_request(request)
        if self.claim_commit_fails:
            raise RuntimeError("ambiguous claim commit")
        if self.claim_status is not WorkflowProtectedRuntimeReadinessConsumptionClaimStatus.CLAIMED:
            return WorkflowProtectedRuntimeReadinessConsumptionClaimWrite(
                self.claim_status,
                claim=self.claim,
                attempt=self.attempt,
                result=self.result,
            )
        self.claim = request.candidate_claim
        self.attempt = request.candidate_attempt
        self.committed = True
        return WorkflowProtectedRuntimeReadinessConsumptionClaimWrite(
            self.claim_status,
            claim=self.claim,
            attempt=self.attempt,
            result=self.result,
        )

    async def record_protected_runtime_readiness_consumption_result(
        self, request: WorkflowProtectedRuntimeReadinessConsumptionResultRequest
    ) -> WorkflowProtectedRuntimeReadinessConsumptionResultWrite:
        self.events.append("result")
        uncertain = (
            request.result.state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
        )
        if self.known_result_write_fails and not uncertain:
            raise RuntimeError("known result write ambiguous")
        if self.known_result_commit_ack_lost and not uncertain:
            self.result = request.result
            raise RuntimeError("known result commit acknowledgement lost")
        if self.uncertainty_write_fails and uncertain:
            raise RuntimeError("uncertainty write unavailable")
        if self.result is None:
            self.result = request.result
            status = WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.RECORDED
        else:
            status = WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.REPLAY
        return WorkflowProtectedRuntimeReadinessConsumptionResultWrite(status, self.result)

    async def list_protected_runtime_readiness_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[Any, ...]:
        del scope, limit
        return (self.attempt,) if self.attempt is not None else ()

    async def get_protected_runtime_readiness_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[Any, ...]:
        del scope, consumption_ids
        return (self.result,) if self.result is not None else ()


def _service(
    *,
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState = (
        WorkflowProtectedRuntimeReadinessConsumptionResultState
    ).RUNTIME_READY_IN_PROTECTED_BOUNDARY,
    fail_assessor: bool = False,
    cancel_assessor: bool = False,
    late_receipt: bool = False,
    missing_receipt: bool = False,
    valid_instruction: bool = True,
    instruction_verifier_available: bool = True,
    valid_receipt: bool = True,
    receipt_verifier_available: bool = True,
    audit_sink: _AuditSink | None = None,
) -> tuple[WorkflowProtectedRuntimeReadinessConsumptionService, _Repository, _Assessor]:
    events: list[str] = []
    repository = _Repository(events)
    assessor = _Assessor(
        repository,
        events,
        state=state,
        fail=fail_assessor,
        cancel=cancel_assessor,
        late=late_receipt,
        missing=missing_receipt,
    )
    service = WorkflowProtectedRuntimeReadinessConsumptionService(
        repository=cast(Any, repository),
        assessor=assessor,
        instruction_signer=_InstructionSigner(),
        instruction_signature_verifier=_InstructionVerifier(
            valid=valid_instruction,
            available=instruction_verifier_available,
        ),
        receipt_signature_verifier=_ReceiptVerifier(
            valid=valid_receipt,
            available=receipt_verifier_available,
        ),
        audit_sink=audit_sink or _AuditSink(),
    )
    return service, repository, assessor


async def _consume(
    service: WorkflowProtectedRuntimeReadinessConsumptionService,
) -> WorkflowProtectedRuntimeReadinessConsumptionPresentation:
    return await service.consume(
        authorization_lease_id="runtime-readiness-authorization-lease.imp-225",
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertainty_no_retry_acknowledged=True,
        idempotency_key="imp-226-runtime-readiness",
        context=_context(),
    )


def test_public_surface_is_strict_and_has_no_operational_inputs() -> None:
    parameters = set(
        inspect.signature(WorkflowProtectedRuntimeReadinessConsumptionService.consume).parameters
    )
    assert parameters == {
        "self",
        "authorization_lease_id",
        "policy_id",
        "policy_version",
        "irreversible_consumption_acknowledged",
        "uncertainty_no_retry_acknowledged",
        "idempotency_key",
        "context",
    }
    prohibited = {
        "runtime_locator",
        "endpoint",
        "credential",
        "network",
        "connector",
        "mcp",
        "model",
        "operation",
        "prompt",
    }
    assert not prohibited.intersection(parameters)


@pytest.mark.asyncio
async def test_replay_first_commits_before_one_assessor_call_and_terminal_replays() -> None:
    service, repository, assessor = _service()

    presentation = await _consume(service)

    assert repository.events == [
        "replay",
        "source",
        "time",
        "claim",
        "assessor",
        "time",
        "result",
    ]
    assert assessor.calls == 1
    assert presentation.result is not None
    assert presentation.result.runtime_ready is True
    assert not any(presentation.attempt.authority.canonical_value().values())
    assert not any(presentation.result.authority.canonical_value().values())

    replayed = await _consume(service)
    assert replayed == presentation
    assert assessor.calls == 1
    assert repository.events[-1] == "replay"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "runtime_ready", "assessment_performed"),
    [
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY,
            True,
            True,
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
            False,
            True,
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT,
            None,
            False,
        ),
    ],
)
async def test_timely_signed_receipts_record_all_known_outcomes(
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
    runtime_ready: bool | None,
    assessment_performed: bool,
) -> None:
    service, _, assessor = _service(state=state)

    presentation = await _consume(service)

    assert presentation.result is not None
    assert presentation.result.state is state
    assert presentation.result.runtime_ready is runtime_ready
    assert presentation.result.assessment_performed is assessment_performed
    assert presentation.result.outcome_known is True
    assert presentation.result.assessor_receipt_digest is not None
    assert assessor.calls == 1


@pytest.mark.asyncio
async def test_pending_replay_never_calls_assessor() -> None:
    service, repository, assessor = _service()
    original = await _consume(service)
    repository.result = None
    repository.events.clear()

    replayed = await _consume(service)

    assert replayed.attempt == original.attempt
    assert replayed.result is None
    assert repository.events == ["replay"]
    assert assessor.calls == 1


@pytest.mark.asyncio
async def test_uncertain_replay_is_non_retryable_and_never_calls_assessor() -> None:
    service, repository, assessor = _service()
    await _consume(service)
    repository.result = None
    repository.replay_status = (
        WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.ATTEMPT_UNCERTAIN
    )
    repository.events.clear()

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_outcome_uncertain_no_retry",
    ):
        await _consume(service)

    assert repository.events == ["replay"]
    assert assessor.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["REPLAY_PENDING", "REPLAY_TERMINAL"])
async def test_claim_race_replay_never_calls_assessor(status: str) -> None:
    service, repository, assessor = _service()
    first = await _consume(service)
    repository.claim_status = getattr(
        WorkflowProtectedRuntimeReadinessConsumptionClaimStatus, status
    )
    repository.force_replay_none = True
    repository.events.clear()
    calls = assessor.calls
    if status == "REPLAY_PENDING":
        repository.result = None
    else:
        assert first.result is not None

    replayed = await _consume(service)

    assert replayed.attempt == first.attempt
    assert assessor.calls == calls
    assert repository.events == ["replay", "source", "time", "claim"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service_options",
    [
        {"fail_assessor": True},
        {"missing_receipt": True},
        {"valid_receipt": False},
        {"late_receipt": True},
    ],
)
async def test_assessor_or_receipt_uncertainty_is_persisted_without_retry(
    service_options: dict[str, bool],
) -> None:
    service, _, assessor = _service(**cast(Any, service_options))

    presentation = await _consume(service)

    assert presentation.result is not None
    assert (
        presentation.result.state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )
    assert presentation.result.runtime_ready is None
    assert presentation.result.assessment_performed is None
    assert assessor.calls == 1


@pytest.mark.asyncio
async def test_known_result_write_ambiguity_becomes_permanent_uncertainty() -> None:
    service, repository, assessor = _service()
    repository.known_result_write_fails = True

    presentation = await _consume(service)

    assert presentation.result is not None
    assert (
        presentation.result.state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )
    assert assessor.calls == 1
    assert repository.events[-2:] == ["time", "result"]


@pytest.mark.asyncio
async def test_exact_durable_read_resolves_result_commit_acknowledgement_loss() -> None:
    service, repository, assessor = _service()
    repository.known_result_commit_ack_lost = True

    presentation = await _consume(service)

    assert presentation.result is not None
    assert (
        presentation.result.state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )
    assert assessor.calls == 1
    assert repository.events[-2:] == ["result", "replay"]


@pytest.mark.asyncio
async def test_receipt_delivered_after_authoritative_deadline_is_uncertain() -> None:
    service, repository, assessor = _service()
    repository.postcommit_authoritative_time = NOW + timedelta(seconds=2)

    presentation = await _consume(service)

    assert presentation.result is not None
    assert (
        presentation.result.state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )
    assert assessor.calls == 1


@pytest.mark.asyncio
async def test_semantic_audit_distinguishes_attempt_invocation_and_terminal_result() -> None:
    audit_sink = _AuditSink()
    service, _, assessor = _service(audit_sink=audit_sink)

    presentation = await _consume(service)
    replayed = await _consume(service)

    assert presentation.result is not None
    assert replayed == presentation
    assert assessor.calls == 1
    assert [event.result_code for event in audit_sink.events] == [
        "protected_runtime_readiness_lease_consumed_attempt_committed",
        "protected_runtime_readiness_assessor_invocation_intent_recorded",
        "protected_runtime_readiness_assessor_invocation_returned",
        "protected_runtime_readiness_recorded_runtime_ready_in_protected_boundary",
        "protected_runtime_readiness_replayed_runtime_ready_in_protected_boundary",
    ]
    assert all(
        event.event_type == "atlas.workflow.protected-runtime-readiness-consumption.observation"
        for event in audit_sink.events
    )
    metadata = dict(audit_sink.events[-1].target_metadata)
    assert metadata["result_state"] == "runtime_ready_in_protected_boundary"
    assert metadata["assessment_authority"] == "false"
    assert metadata["execution_authority"] == "false"
    assert metadata["infrastructure_mutation_authority"] == "false"
    assert all(event.occurred_at > _context().requested_at for event in audit_sink.events)


@pytest.mark.asyncio
async def test_assessor_failure_audit_records_intent_failure_and_uncertainty() -> None:
    audit_sink = _AuditSink()
    service, _, assessor = _service(fail_assessor=True, audit_sink=audit_sink)

    presentation = await _consume(service)

    assert presentation.result is not None
    assert (
        presentation.result.state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )
    assert assessor.calls == 1
    assert [event.result_code for event in audit_sink.events] == [
        "protected_runtime_readiness_lease_consumed_attempt_committed",
        "protected_runtime_readiness_assessor_invocation_intent_recorded",
        "protected_runtime_readiness_assessor_invocation_failed",
        "protected_runtime_readiness_outcome_uncertain",
    ]
    assert audit_sink.events[2].occurred_at >= _context().requested_at


@pytest.mark.asyncio
async def test_assessor_cancellation_records_failure_and_uncertainty_before_propagating() -> None:
    audit_sink = _AuditSink()
    service, repository, assessor = _service(cancel_assessor=True, audit_sink=audit_sink)

    with pytest.raises(asyncio.CancelledError):
        await _consume(service)

    assert assessor.calls == 1
    assert repository.result is not None
    assert (
        repository.result.state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )
    assert [event.result_code for event in audit_sink.events] == [
        "protected_runtime_readiness_lease_consumed_attempt_committed",
        "protected_runtime_readiness_assessor_invocation_intent_recorded",
        "protected_runtime_readiness_assessor_invocation_failed",
        "protected_runtime_readiness_outcome_uncertain",
    ]


@pytest.mark.asyncio
async def test_uncertainty_write_failure_raises_non_retryable_error() -> None:
    service, repository, assessor = _service(fail_assessor=True)
    repository.uncertainty_write_fails = True

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_outcome_uncertain_no_retry",
    ):
        await _consume(service)

    assert assessor.calls == 1
    assert repository.result is None


@pytest.mark.asyncio
async def test_claim_commit_ambiguity_never_calls_assessor() -> None:
    service, repository, assessor = _service()
    repository.claim_commit_fails = True

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_consumption_claim_commit_uncertain",
    ):
        await _consume(service)

    assert assessor.calls == 0
    assert repository.events == ["replay", "source", "time", "claim"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service_options",
    [
        {"valid_instruction": False},
        {"instruction_verifier_available": False},
        {"receipt_verifier_available": False},
    ],
)
async def test_trusted_component_failures_happen_before_point_of_no_return(
    service_options: dict[str, bool],
) -> None:
    service, repository, assessor = _service(**cast(Any, service_options))

    with pytest.raises(WorkflowProtectedRuntimeReadinessConsumptionError):
        await _consume(service)

    assert repository.committed is False
    assert assessor.calls == 0
    assert repository.events[0] == "replay"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.IDEMPOTENCY_CONFLICT,
        WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.EVIDENCE_CONFLICT,
    ],
)
async def test_replay_conflicts_fail_before_source_or_assessor_io(
    status: WorkflowProtectedRuntimeReadinessConsumptionReplayStatus,
) -> None:
    service, repository, assessor = _service()
    repository.attempt = cast(Any, None)
    repository.replay_status = status

    original_lookup = repository.lookup_protected_runtime_readiness_consumption_replay

    async def conflict_lookup(
        request: WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionReplayLookup:
        del request
        repository.events.append("replay")
        return WorkflowProtectedRuntimeReadinessConsumptionReplayLookup(status)

    repository.lookup_protected_runtime_readiness_consumption_replay = conflict_lookup  # type: ignore[method-assign]
    del original_lookup

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match=f"protected_runtime_readiness_consumption_{status.value}",
    ):
        await _consume(service)

    assert repository.events == ["replay"]
    assert assessor.calls == 0


@pytest.mark.asyncio
async def test_expired_lease_is_rejected_before_claim_or_assessor_io() -> None:
    service, repository, assessor = _service()
    lease = repository.source.authorization_lease
    expired_values = {
        field.name: getattr(lease, field.name)
        for field in fields(WorkflowProtectedRuntimeReadinessAuthorizationLease)
        if field.name != "canonical_digest"
    }
    expired_values.update({"valid_until": NOW, "effective_until": NOW})
    expired = WorkflowProtectedRuntimeReadinessAuthorizationLease(
        **cast(Any, expired_values), canonical_digest=_digest(expired_values)
    )
    repository.source = WorkflowProtectedRuntimeReadinessConsumptionSource(
        expired, repository.source.authorization_claim
    )

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_consumption_source_invalid",
    ):
        await _consume(service)

    assert repository.events == ["replay", "source", "time"]
    assert assessor.calls == 0


@pytest.mark.asyncio
async def test_human_or_missing_acknowledgement_is_rejected_before_repository_io() -> None:
    service, repository, assessor = _service()
    context = _context()
    object.__setattr__(context, "actor_type", "human")

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_consumption_request_invalid",
    ):
        await service.consume(
            authorization_lease_id="runtime-readiness-authorization-lease.imp-225",
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            irreversible_consumption_acknowledged=False,
            uncertainty_no_retry_acknowledged=True,
            idempotency_key="imp-226-runtime-readiness",
            context=context,
        )

    assert repository.events == []
    assert assessor.calls == 0


@pytest.mark.asyncio
async def test_list_projection_maps_pending_and_terminal_attempts() -> None:
    service, repository, _ = _service()
    terminal = await _consume(service)

    assert await service.list_presentations(scope=SCOPE) == (terminal,)

    repository.result = None
    pending = await service.list_presentations(scope=SCOPE)
    assert pending == (
        WorkflowProtectedRuntimeReadinessConsumptionPresentation(
            cast(WorkflowProtectedRuntimeReadinessAttempt, repository.attempt), None
        ),
    )


@pytest.mark.asyncio
async def test_production_service_requires_durable_repository() -> None:
    service, repository, assessor = _service()
    repository.durable = False

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_consumption_durable_repository_required",
    ):
        await _consume(service)

    with pytest.raises(WorkflowProtectedRuntimeReadinessConsumptionError):
        await service.list_presentations(scope=SCOPE)
    assert repository.events == []
    assert assessor.calls == 0


def test_instruction_and_receipt_keys_and_dependencies_are_distinct() -> None:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    parameters = inspect.signature(
        WorkflowProtectedRuntimeReadinessConsumptionService.__init__
    ).parameters

    assert policy.instruction_signing_key_id != policy.receipt_verification_signing_key_id
    assert "instruction_signer" in parameters
    assert "instruction_signature_verifier" in parameters
    assert "assessor" in parameters
    assert "receipt_signature_verifier" in parameters


def test_port_records_expose_no_runtime_or_transport_material() -> None:
    public_fields = {
        field.name
        for model in (
            WorkflowProtectedRuntimeReadinessConsumptionReplayLookupRequest,
            WorkflowProtectedRuntimeReadinessConsumptionClaimRequest,
            WorkflowProtectedRuntimeReadinessConsumptionResultRequest,
        )
        for field in fields(model)
    }
    prohibited_fragments = (
        "locator",
        "endpoint",
        "credential",
        "secret",
        "network",
        "connector",
        "mcp",
        "model",
        "prompt",
        "command",
    )

    assert not any(fragment in name for name in public_fields for fragment in prohibited_fragments)
