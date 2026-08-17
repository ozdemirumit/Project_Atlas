from __future__ import annotations

import inspect
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionClaimRequest,
    WorkflowProtectedRuntimeStartConsumptionClaimStatus,
    WorkflowProtectedRuntimeStartConsumptionClaimWrite,
    WorkflowProtectedRuntimeStartConsumptionError,
    WorkflowProtectedRuntimeStartConsumptionReplayLookup,
    WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeStartConsumptionReplayStatus,
    WorkflowProtectedRuntimeStartConsumptionResultRequest,
    WorkflowProtectedRuntimeStartConsumptionResultWrite,
    WorkflowProtectedRuntimeStartConsumptionResultWriteStatus,
    WorkflowProtectedRuntimeStartConsumptionSource,
    validate_workflow_protected_runtime_start_consumption_claim_request,
)
from atlas.modules.workflows.application.protected_runtime_start_consumptions import (
    WorkflowProtectedRuntimeStartConsumptionPresentation,
    WorkflowProtectedRuntimeStartConsumptionService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseResultState,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationAuthority,
    WorkflowProtectedRuntimeStartAuthorizationClaim,
    WorkflowProtectedRuntimeStartAuthorizationLease,
    WorkflowProtectedRuntimeStartAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeStartConsumptionAttempt,
    WorkflowProtectedRuntimeStartConsumptionClaim,
    WorkflowProtectedRuntimeStartConsumptionResult,
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartReceipt,
    WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


def _digest(values: dict[str, object]) -> str:
    return canonical_digest({name: _canonical_value(value) for name, value in values.items()})


def _authorization_source() -> WorkflowProtectedRuntimeStartConsumptionSource:
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()
    source_values: dict[str, object] = {
        "use_result_id": "runtime-use-result.imp-222",
        "use_result_digest": "1" * 64,
        "use_id": "runtime-use.imp-222",
        "use_attempt_id": "runtime-use-attempt.imp-222",
        "use_attempt_digest": "2" * 64,
        "use_claim_id": "runtime-use-claim.imp-222",
        "use_claim_digest": "3" * 64,
        "use_receipt_digest": "4" * 64,
        "authorization_consumption_result_id": "use-auth-consumption-result.imp-221",
        "authorization_consumption_result_digest": "5" * 64,
        "use_result_state": (
            WorkflowProtectedRuntimeContextUseResultState
        ).CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY,
        "use_completed_at": NOW - timedelta(seconds=3),
        "use_result_recorded_at": NOW - timedelta(seconds=2),
        "use_outcome_known": True,
        "context_adopted": True,
        "protected_runtime_context_use_performed": True,
        "context_terminal_non_reusable": True,
        "transient_material_zeroized": True,
        "destination_deployment_id": "deployment.imp-224",
        "destination_generation": 4,
        "destination_fencing_token_digest": "6" * 64,
        "runtime_slot_commitment": "7" * 64,
        "runtime_slot_post_generation": 8,
        "use_count_post": 1,
        "runtime_envelope_id": "runtime-envelope.imp-224",
        "runtime_envelope_commitment": "8" * 64,
        "runtime_envelope_generation": 8,
        "use_profile_id": "profile.workflow-protected-runtime-context-use",
        "use_profile_version": "1.0",
        "use_profile_digest": policy.source_policy_digest,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }
    claim_values = source_values | {
        "claim_id": "runtime-start-authorization-claim.imp-223",
        "request_fingerprint": "9" * 64,
        "idempotency_digest": "a" * 64,
        "authorization_audit_digest": "b" * 64,
        "claimed_at": NOW - timedelta(seconds=1),
        "authority": WorkflowProtectedRuntimeStartAuthorizationAuthority(),
    }
    claim = WorkflowProtectedRuntimeStartAuthorizationClaim(
        **cast(Any, claim_values),
        canonical_digest=_digest(claim_values),
    )
    lease_values = source_values | {
        "authorization_lease_id": "runtime-start-authorization-lease.imp-223",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        "lifecycle_attestation_id": "runtime-start-attestation.imp-223",
        "lifecycle_attestation_digest": "c" * 64,
        "lifecycle_attestation_valid_until": NOW + timedelta(seconds=1),
        "runtime_envelope_eligible_until": NOW + timedelta(seconds=1),
        "runtime_start_profile_id": policy.runtime_start_profile_id,
        "runtime_start_profile_version": policy.runtime_start_profile_version,
        "runtime_start_profile_digest": policy.runtime_start_profile_digest,
        "issued_at": NOW - timedelta(milliseconds=100),
        "valid_until": NOW + timedelta(milliseconds=800),
        "effective_until": NOW + timedelta(milliseconds=800),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": WorkflowProtectedRuntimeStartAuthorizationLeaseState.AUTHORIZED_UNCONSUMED,
        "authority": WorkflowProtectedRuntimeStartAuthorizationAuthority(
            protected_runtime_start_authority_granted=True
        ),
    }
    lease = WorkflowProtectedRuntimeStartAuthorizationLease(
        **cast(Any, lease_values),
        canonical_digest=_digest(lease_values),
    )
    return WorkflowProtectedRuntimeStartConsumptionSource(
        authorization_lease=lease,
        authorization_claim=claim,
    )


def _context() -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-224",
        decision_id="decision.imp-224",
        requested_at=NOW,
    )


class _InstructionSigner:
    available = True
    signing_key_id = WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID
    signature_algorithm = WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        assert len(payload_digest) == 64
        return "d" * 64


class _InstructionVerifier:
    def __init__(self, *, valid: bool = True, available: bool = True) -> None:
        self.valid = valid
        self.available = available

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope
    ) -> bool:
        del envelope
        return self.valid


class _ReceiptVerifier:
    def __init__(self, *, valid: bool = True, available: bool = True) -> None:
        self.valid = valid
        self.available = available

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeStartReceipt) -> bool:
        del receipt
        return self.valid


class _Starter:
    available = True

    def __init__(
        self,
        repository: _Repository,
        events: list[str],
        *,
        fail: bool = False,
        no_effect: bool = False,
        late: bool = False,
    ) -> None:
        policy = code_owned_workflow_protected_runtime_start_consumption_policy()
        self.starter_contract_id = policy.required_starter_contract_id
        self.starter_contract_version = policy.required_starter_contract_version
        self.starter_id = policy.approved_starter_id
        self.starter_version = policy.approved_starter_version
        self.runtime_start_profile_id = policy.runtime_start_profile_id
        self.runtime_start_profile_version = policy.runtime_start_profile_version
        self.runtime_start_profile_digest = policy.runtime_start_profile_digest
        self._repository = repository
        self._events = events
        self._fail = fail
        self._no_effect = no_effect
        self._late = late
        self.calls = 0

    async def start_runtime(self, invocation: Any) -> WorkflowProtectedRuntimeStartReceipt:
        assert self._repository.committed is True
        self._events.append("starter")
        self.calls += 1
        if self._fail:
            raise RuntimeError("protected starter response unavailable")
        instruction = invocation.signed_instruction_envelope.instruction
        success = not self._no_effect
        state = (
            WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
            if success
            else (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_START_FAILED_WITHOUT_START
        )
        values: dict[str, object] = {
            "consumption_id": instruction.consumption_id,
            "attempt_id": instruction.attempt_id,
            "instruction_digest": instruction.canonical_digest,
            "protected_operation_reference": instruction.protected_operation_reference,
            "authorization_lease_id": instruction.authorization_lease_id,
            "destination_deployment_id": instruction.destination_deployment_id,
            "destination_generation": instruction.destination_generation,
            "destination_fencing_token_digest": (instruction.destination_fencing_token_digest),
            "runtime_slot_commitment": instruction.runtime_slot_commitment,
            "runtime_slot_generation": instruction.runtime_slot_generation,
            "runtime_envelope_id": instruction.runtime_envelope_id,
            "runtime_envelope_commitment": instruction.runtime_envelope_commitment,
            "runtime_envelope_generation": instruction.runtime_envelope_generation,
            "request_nonce_digest": instruction.request_nonce_digest,
            "result_state": state,
            "runtime_started": success,
            "runtime_start_count_pre": 0,
            "runtime_start_count_post": 1 if success else 0,
            "runtime_envelope_current": True,
            "runtime_envelope_inactive": not success,
            "residual_process_absent": True,
            "residual_task_absent": True,
            "scheduling_performed": False,
            "runtime_resumed": False,
            "generic_process_created": False,
            "prompt_constructed": False,
            "model_inference_performed": False,
            "network_activity_performed": False,
            "readiness_probe_performed": False,
            "publication_performed": False,
            "delivery_performed": False,
            "connector_activity_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
            "starter_contract_id": self.starter_contract_id,
            "starter_contract_version": self.starter_contract_version,
            "starter_id": self.starter_id,
            "starter_version": self.starter_version,
            "signing_key_id": (
                code_owned_workflow_protected_runtime_start_consumption_policy()
            ).receipt_verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "completed_at": NOW + timedelta(milliseconds=900 if self._late else 400),
            "integrity_signature": "e" * 64,
        }
        return WorkflowProtectedRuntimeStartReceipt(
            **cast(Any, values),
            canonical_digest=_digest(values),
        )


class _Repository:
    durable = True

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.source = _authorization_source()
        self.claim: WorkflowProtectedRuntimeStartConsumptionClaim | None = None
        self.attempt: WorkflowProtectedRuntimeStartConsumptionAttempt | None = None
        self.result: WorkflowProtectedRuntimeStartConsumptionResult | None = None
        self.committed = False
        self.claim_commit_fails = False
        self.uncertainty_write_fails = False
        self.replay_status: WorkflowProtectedRuntimeStartConsumptionReplayStatus | None = None
        self.claim_status = WorkflowProtectedRuntimeStartConsumptionClaimStatus.CLAIMED

    async def lookup_protected_runtime_start_consumption_replay(
        self, request: WorkflowProtectedRuntimeStartConsumptionReplayLookupRequest
    ) -> WorkflowProtectedRuntimeStartConsumptionReplayLookup:
        self.events.append("replay")
        if self.attempt is None:
            return WorkflowProtectedRuntimeStartConsumptionReplayLookup(
                WorkflowProtectedRuntimeStartConsumptionReplayStatus.NONE
            )
        status = self.replay_status or (
            WorkflowProtectedRuntimeStartConsumptionReplayStatus.TERMINAL
            if self.result is not None
            else WorkflowProtectedRuntimeStartConsumptionReplayStatus.ATTEMPT_PENDING
        )
        return WorkflowProtectedRuntimeStartConsumptionReplayLookup(
            status,
            attempt=self.attempt,
            result=self.result,
            evaluated_at=NOW + timedelta(milliseconds=500),
        )

    async def get_protected_runtime_start_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeStartConsumptionSource:
        self.events.append("source")
        assert authorization_lease_id == self.source.authorization_lease.authorization_lease_id
        return self.source

    async def get_authoritative_time(self) -> datetime:
        self.events.append("time")
        return NOW if not self.committed else NOW + timedelta(milliseconds=500)

    async def claim_protected_runtime_start_consumption(
        self, request: WorkflowProtectedRuntimeStartConsumptionClaimRequest
    ) -> WorkflowProtectedRuntimeStartConsumptionClaimWrite:
        self.events.append("claim")
        validate_workflow_protected_runtime_start_consumption_claim_request(request)
        if self.claim_commit_fails:
            raise RuntimeError("ambiguous commit")
        self.claim = request.candidate_claim
        self.attempt = request.candidate_attempt
        self.committed = True
        return WorkflowProtectedRuntimeStartConsumptionClaimWrite(
            self.claim_status,
            claim=self.claim,
            attempt=self.attempt,
        )

    async def record_protected_runtime_start_consumption_result(
        self, request: WorkflowProtectedRuntimeStartConsumptionResultRequest
    ) -> WorkflowProtectedRuntimeStartConsumptionResultWrite:
        self.events.append("result")
        if (
            self.uncertainty_write_fails
            and request.result.state
            is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_OUTCOME_UNCERTAIN
        ):
            raise RuntimeError("uncertainty persistence unavailable")
        if self.result is None:
            self.result = request.result
            status = WorkflowProtectedRuntimeStartConsumptionResultWriteStatus.RECORDED
        else:
            status = WorkflowProtectedRuntimeStartConsumptionResultWriteStatus.REPLAY
        return WorkflowProtectedRuntimeStartConsumptionResultWrite(status, self.result)

    async def list_protected_runtime_start_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[Any, ...]:
        del scope, limit
        return (self.attempt,) if self.attempt is not None else ()

    async def get_protected_runtime_start_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[Any, ...]:
        del scope, consumption_ids
        return (self.result,) if self.result is not None else ()


def _service(
    *,
    fail_starter: bool = False,
    no_effect: bool = False,
    late_receipt: bool = False,
    valid_instruction: bool = True,
    instruction_verifier_available: bool = True,
    valid_receipt: bool = True,
    receipt_verifier_available: bool = True,
) -> tuple[WorkflowProtectedRuntimeStartConsumptionService, _Repository, _Starter]:
    events: list[str] = []
    repository = _Repository(events)
    starter = _Starter(
        repository,
        events,
        fail=fail_starter,
        no_effect=no_effect,
        late=late_receipt,
    )
    service = WorkflowProtectedRuntimeStartConsumptionService(
        repository=cast(Any, repository),
        starter=starter,
        instruction_signer=_InstructionSigner(),
        instruction_signature_verifier=_InstructionVerifier(
            valid=valid_instruction,
            available=instruction_verifier_available,
        ),
        receipt_signature_verifier=_ReceiptVerifier(
            valid=valid_receipt,
            available=receipt_verifier_available,
        ),
    )
    return service, repository, starter


async def _consume(
    service: WorkflowProtectedRuntimeStartConsumptionService,
) -> WorkflowProtectedRuntimeStartConsumptionPresentation:
    return await service.consume(
        authorization_lease_id="runtime-start-authorization-lease.imp-223",
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertainty_no_retry_acknowledged=True,
        idempotency_key="imp-224-runtime-start",
        context=_context(),
    )


def test_public_surface_accepts_only_lease_policy_acknowledgements_and_idempotency() -> None:
    assert set(
        inspect.signature(WorkflowProtectedRuntimeStartConsumptionService.consume).parameters
    ) == {
        "self",
        "authorization_lease_id",
        "policy_id",
        "policy_version",
        "irreversible_consumption_acknowledged",
        "uncertainty_no_retry_acknowledged",
        "idempotency_key",
        "context",
    }


@pytest.mark.asyncio
async def test_replay_first_commits_claim_and_attempt_before_one_starter_call() -> None:
    service, repository, starter = _service()

    presentation = await _consume(service)

    assert repository.events == [
        "replay",
        "source",
        "time",
        "claim",
        "starter",
        "time",
        "result",
    ]
    assert starter.calls == 1
    assert presentation.result is not None
    assert presentation.result.runtime_started is True
    assert not any(presentation.attempt.authority.canonical_value().values())
    assert not any(presentation.result.authority.canonical_value().values())

    replayed = await _consume(service)
    assert replayed == presentation
    assert starter.calls == 1
    assert repository.events[-1] == "replay"


@pytest.mark.asyncio
async def test_started_attempt_pending_before_deadline_is_never_retried() -> None:
    service, repository, starter = _service()
    original = await _consume(service)
    repository.result = None
    repository.events.clear()

    replayed = await _consume(service)

    assert replayed.attempt == original.attempt
    assert replayed.result is None
    assert repository.events == ["replay"]
    assert starter.calls == 1


@pytest.mark.asyncio
async def test_uncertain_attempt_replay_raises_no_retry_and_never_calls_starter() -> None:
    service, repository, starter = _service()
    await _consume(service)
    repository.result = None
    repository.replay_status = (
        WorkflowProtectedRuntimeStartConsumptionReplayStatus.ATTEMPT_UNCERTAIN
    )
    repository.events.clear()
    calls_before_replay = starter.calls

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_outcome_uncertain_no_retry",
    ) as exc_info:
        await _consume(service)

    assert exc_info.value.code == "protected_runtime_start_outcome_uncertain_no_retry"
    assert repository.events == ["replay"]
    assert starter.calls == calls_before_replay


@pytest.mark.asyncio
async def test_uncertain_claim_replay_raises_no_retry_before_starter_call() -> None:
    service, repository, starter = _service()
    repository.claim_status = WorkflowProtectedRuntimeStartConsumptionClaimStatus.REPLAY_UNCERTAIN

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_outcome_uncertain_no_retry",
    ) as exc_info:
        await _consume(service)

    assert exc_info.value.code == "protected_runtime_start_outcome_uncertain_no_retry"
    assert repository.events == ["replay", "source", "time", "claim"]
    assert starter.calls == 0


@pytest.mark.asyncio
async def test_starter_failure_records_permanent_uncertainty_without_retry() -> None:
    service, repository, starter = _service(fail_starter=True)

    presentation = await _consume(service)

    assert presentation.result is not None
    assert presentation.result.state is (
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_OUTCOME_UNCERTAIN
    )
    assert presentation.result.runtime_started is None
    assert starter.calls == 1

    replayed = await _consume(service)
    assert replayed == presentation
    assert starter.calls == 1
    assert repository.events[-1] == "replay"


@pytest.mark.asyncio
async def test_uncertainty_persistence_failure_raises_non_retryable_conflict() -> None:
    service, repository, starter = _service(fail_starter=True)
    repository.uncertainty_write_fails = True

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_outcome_uncertain_no_retry",
    ) as exc_info:
        await _consume(service)

    assert exc_info.value.code == "protected_runtime_start_outcome_uncertain_no_retry"
    assert starter.calls == 1
    assert repository.result is None
    assert repository.events == [
        "replay",
        "source",
        "time",
        "claim",
        "starter",
        "time",
        "result",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("service_option", ["invalid", "late"])
async def test_invalid_or_late_receipt_becomes_uncertain(service_option: str) -> None:
    service, _, starter = _service(
        valid_receipt=service_option != "invalid",
        late_receipt=service_option == "late",
    )

    presentation = await _consume(service)

    assert presentation.result is not None
    assert presentation.result.state.value == "runtime_start_outcome_uncertain"
    assert starter.calls == 1


@pytest.mark.asyncio
async def test_signed_no_effect_receipt_is_known_failure_not_uncertainty() -> None:
    service, _, starter = _service(no_effect=True)

    presentation = await _consume(service)

    assert presentation.result is not None
    assert presentation.result.state.value == "runtime_start_failed_without_start"
    assert presentation.result.outcome_known is True
    assert presentation.result.runtime_started is False
    assert starter.calls == 1


@pytest.mark.asyncio
async def test_invalid_instruction_signature_prevents_claim_and_starter_io() -> None:
    service, repository, starter = _service(valid_instruction=False)

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_instruction_envelope_invalid",
    ):
        await _consume(service)

    assert repository.events == ["replay", "source", "time"]
    assert repository.committed is False
    assert starter.calls == 0


@pytest.mark.asyncio
async def test_unavailable_receipt_verifier_fails_before_point_of_no_return() -> None:
    service, repository, starter = _service(receipt_verifier_available=False)

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_trusted_component_unavailable",
    ):
        await _consume(service)

    assert repository.events == ["replay"]
    assert repository.committed is False
    assert starter.calls == 0


@pytest.mark.asyncio
async def test_unavailable_instruction_verifier_fails_before_point_of_no_return() -> None:
    service, repository, starter = _service(instruction_verifier_available=False)

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_trusted_component_unavailable",
    ):
        await _consume(service)

    assert repository.events == ["replay"]
    assert repository.committed is False
    assert starter.calls == 0


@pytest.mark.asyncio
async def test_ambiguous_claim_commit_never_calls_starter() -> None:
    service, repository, starter = _service()
    repository.claim_commit_fails = True

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_consumption_claim_commit_uncertain",
    ):
        await _consume(service)

    assert starter.calls == 0


@pytest.mark.asyncio
async def test_human_or_missing_acknowledgement_is_rejected_before_repository_io() -> None:
    service, repository, starter = _service()
    context = _context()
    object.__setattr__(context, "actor_type", "human")

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_consumption_request_invalid",
    ):
        await service.consume(
            authorization_lease_id="runtime-start-authorization-lease.imp-223",
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            irreversible_consumption_acknowledged=False,
            uncertainty_no_retry_acknowledged=True,
            idempotency_key="imp-224-runtime-start",
            context=context,
        )

    assert repository.events == []
    assert starter.calls == 0


@pytest.mark.asyncio
async def test_list_presentations_requires_durable_repository() -> None:
    service, repository, starter = _service()
    repository.durable = False

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_consumption_durable_repository_required",
    ):
        await service.list_presentations(scope=SCOPE)

    assert repository.events == []
    assert starter.calls == 0


def test_instruction_signer_and_receipt_verifier_are_distinct_dependencies() -> None:
    parameters = inspect.signature(
        WorkflowProtectedRuntimeStartConsumptionService.__init__
    ).parameters

    assert "instruction_signer" in parameters
    assert "instruction_signature_verifier" in parameters
    assert "receipt_signature_verifier" in parameters
    assert parameters["instruction_signer"] is not parameters["receipt_signature_verifier"]


def test_authority_never_inherits_adr_173_future_request_authority() -> None:
    source = _authorization_source()

    assert source.authorization_lease.authority.protected_runtime_start_authority_granted is True
    assert len(fields(type(source.authorization_lease.authority))) == 27
