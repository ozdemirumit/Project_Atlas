from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationError,
    WorkflowProtectedRuntimeStartAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeStartAuthorizationLeaseResult,
    WorkflowProtectedRuntimeStartAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeStartAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeStartAuthorizationPreflightResult,
    WorkflowProtectedRuntimeStartAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeStartAuthorizationSource,
    WorkflowProtectedRuntimeStartLifecycleAttestation,
    WorkflowProtectedRuntimeStartLifecycleAttestationRequest,
    validate_workflow_protected_runtime_start_authorization_request,
)
from atlas.modules.workflows.application.protected_runtime_start_authorizations import (
    WorkflowProtectedRuntimeStartAuthorizationService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseAuthority,
    WorkflowProtectedRuntimeContextUseFailureClass,
    WorkflowProtectedRuntimeContextUseResultState,
    code_owned_workflow_protected_runtime_context_use_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationLease,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


class _Evidence(SimpleNamespace):
    def __init__(self, kind: str, key: str, **values: object) -> None:
        super().__init__(**values)
        self._digest_values: dict[str, object] = {"kind": kind, "key": key}
        self.canonical_digest = canonical_digest(self._digest_values)

    def digest_payload(self) -> dict[str, object]:
        return self._digest_values


def _source(
    *,
    state: WorkflowProtectedRuntimeContextUseResultState = (
        WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
    ),
) -> WorkflowProtectedRuntimeStartAuthorizationSource:
    source_policy = code_owned_workflow_protected_runtime_context_use_policy()
    zero = WorkflowProtectedRuntimeContextUseAuthority()
    claim = _Evidence(
        "claim",
        "imp-222",
        claim_id="runtime-use-claim.imp-222",
        use_id="runtime-use.imp-222",
        attempt_id="runtime-use-attempt.imp-222",
        authorization_consumption_result_id="use-auth-consumption-result.imp-221",
        authorization_consumption_result_digest="1" * 64,
        authority=zero,
    )
    attempt = _Evidence(
        "attempt",
        "imp-222",
        attempt_id=claim.attempt_id,
        use_id=claim.use_id,
        claim_id=claim.claim_id,
        claim_digest=claim.canonical_digest,
        authorization_consumption_result_id=claim.authorization_consumption_result_id,
        authorization_consumption_result_digest=(claim.authorization_consumption_result_digest),
        expected_runtime_slot_post_generation=8,
        destination_deployment_id="deployment.imp-222",
        destination_generation=4,
        destination_fencing_token_digest="2" * 64,
        runtime_slot_commitment="3" * 64,
        scope=SCOPE,
        consumer_subject_id=source_policy.consumer_subject_id,
        consumer_audience=source_policy.consumer_audience,
        consumer_contract_id=source_policy.consumer_contract_id,
        consumer_contract_version=source_policy.consumer_contract_version,
        authority=zero,
    )
    receipt = _Evidence(
        "receipt",
        "imp-222",
        state=state,
        runtime_slot_post_generation=8,
        use_count_post=1,
        context_adopted=True,
        protected_runtime_context_use_performed=True,
        context_terminal_non_reusable=True,
        transient_material_zeroized=True,
        completed_at=NOW - timedelta(seconds=2),
        signing_key_id=source_policy.receipt_verification_signing_key_id,
    )
    result = _Evidence(
        "result",
        "imp-222",
        result_id="runtime-use-result.imp-222",
        use_id=attempt.use_id,
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        claim_id=claim.claim_id,
        claim_digest=claim.canonical_digest,
        authorization_consumption_result_id=attempt.authorization_consumption_result_id,
        authorization_consumption_result_digest=(attempt.authorization_consumption_result_digest),
        destination_deployment_id=attempt.destination_deployment_id,
        destination_generation=attempt.destination_generation,
        destination_fencing_token_digest=attempt.destination_fencing_token_digest,
        runtime_slot_commitment=attempt.runtime_slot_commitment,
        runtime_slot_pre_generation=7,
        runtime_slot_post_generation=8,
        use_count_pre=0,
        use_count_post=1,
        use_profile_id=source_policy.use_profile_id,
        use_profile_version=source_policy.use_profile_version,
        use_profile_digest=source_policy.use_profile_digest,
        executor_receipt_digest=receipt.canonical_digest,
        state=state,
        failure_class=(
            None
            if state
            is WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
            else WorkflowProtectedRuntimeContextUseFailureClass.TRUSTED_EXECUTOR_REJECTED
        ),
        outcome_known=True,
        context_adopted=True,
        protected_runtime_context_use_performed=True,
        context_terminal_non_reusable=True,
        transient_material_zeroized=True,
        completed_at=receipt.completed_at,
        recorded_at=NOW - timedelta(seconds=1),
        use_deadline=NOW - timedelta(seconds=1, milliseconds=500),
        authority=zero,
    )
    return WorkflowProtectedRuntimeStartAuthorizationSource(
        result=cast(Any, result),
        attempt=cast(Any, attempt),
        use_claim=cast(Any, claim),
        use_receipt=cast(Any, receipt),
    )


class _Repository:
    durable = True

    def __init__(
        self,
        source: WorkflowProtectedRuntimeStartAuthorizationSource,
        events: list[str],
    ) -> None:
        self.source = source
        self.events = events
        self.preflight_status = WorkflowProtectedRuntimeStartAuthorizationPreflightStatus.NONE
        self.replay_lease: WorkflowProtectedRuntimeStartAuthorizationLease | None = None
        self.requests: list[WorkflowProtectedRuntimeStartAuthorizationLeaseRequest] = []

    async def preflight_protected_runtime_start_authorization(
        self, request: WorkflowProtectedRuntimeStartAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeStartAuthorizationPreflightResult:
        del request
        self.events.append("preflight")
        return WorkflowProtectedRuntimeStartAuthorizationPreflightResult(
            status=self.preflight_status,
            lease=self.replay_lease,
            evaluated_at=NOW,
        )

    async def get_protected_runtime_start_authorization_source(
        self, *, use_result_id: str
    ) -> WorkflowProtectedRuntimeStartAuthorizationSource:
        self.events.append("source")
        assert use_result_id == self.source.result.result_id
        return self.source

    async def get_authoritative_time(self) -> datetime:
        self.events.append("authoritative_time")
        return NOW + timedelta(milliseconds=200)

    async def authorize_protected_runtime_start(
        self, request: WorkflowProtectedRuntimeStartAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeStartAuthorizationLeaseResult:
        self.events.append("authorize")
        validate_workflow_protected_runtime_start_authorization_request(request)
        self.requests.append(request)
        return WorkflowProtectedRuntimeStartAuthorizationLeaseResult(
            status=WorkflowProtectedRuntimeStartAuthorizationLeaseStatus.AUTHORIZED,
            lease=request.candidate,
            evaluated_at=NOW + timedelta(milliseconds=200),
        )


class _Attestor:
    available = True

    def __init__(self, events: list[str], *, unsafe: bool = False) -> None:
        self.events = events
        self.unsafe = unsafe

    async def attest_runtime_start_lifecycle(
        self, request: WorkflowProtectedRuntimeStartLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeStartLifecycleAttestation:
        self.events.append("attest")
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        values: dict[str, object] = {
            **request_values,
            "attestation_id": "runtime-start-attestation.imp-223",
            "attestor_id": "attestor.workflow-protected-runtime-start-lifecycle",
            "attestor_version": "1.0",
            "signing_key_id": "key.workflow-protected-runtime-start-lifecycle.v1",
            "signature_algorithm": "hmac-sha256",
            "observed_at": NOW + timedelta(milliseconds=100),
            "valid_until": NOW + timedelta(milliseconds=800),
            "runtime_envelope_eligible_until": NOW + timedelta(seconds=1),
            "exact_use_result_confirmed": True,
            "context_adoption_confirmed": True,
            "context_terminal_non_reusable": True,
            "runtime_envelope_current": True,
            "runtime_envelope_inactive": True,
            "runtime_start_attempt_absent": True,
            "runtime_start_attempt_pending": False,
            "runtime_start_attempt_terminal": False,
            "scheduling_absent": True,
            "competing_runtime_start_authorization_absent": True,
            "competing_runtime_start_consumption_absent": True,
            "runtime_start_profile_eligible": True,
            "runtime_not_started": True,
            "runtime_not_resumed": True,
            "process_not_created": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "runtime_slot_generation_current": True,
            "raw_context_included": False,
            "runtime_payload_included": False,
            "runtime_envelope_locator_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "bearer_token_included": False,
            "runtime_use_authorized": False,
            "runtime_start_authorized": False,
            "runtime_resume_authorized": False,
            "process_creation_authorized": False,
            "scheduling_authorized": False,
            "prompt_construction_authorized": False,
            "model_inference_authorized": False,
            "connector_activity_authorized": False,
            "network_activity_authorized": False,
            "readiness_probe_authorized": False,
            "publication_authorized": False,
            "delivery_authorized": False,
            "dispatch_authorized": False,
            "execution_authorized": self.unsafe,
            "infrastructure_mutation_authorized": False,
            "integrity_signature": "4" * 64,
        }
        attestation = WorkflowProtectedRuntimeStartLifecycleAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        return replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )

    def verify_runtime_start_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeStartLifecycleAttestation
    ) -> bool:
        del attestation
        return True


class _ReceiptVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        self.calls += 1
        return True


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def record(self, record: object) -> None:
        self.records.append(record)


def _context(
    *, subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-223",
        decision_id="decision.imp-223",
        requested_at=NOW,
    )


def _service(
    repository: _Repository,
    attestor: _Attestor,
    verifier: _ReceiptVerifier,
) -> WorkflowProtectedRuntimeStartAuthorizationService:
    return WorkflowProtectedRuntimeStartAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=attestor,
        lifecycle_signature_verifier=attestor,
        use_receipt_signature_verifier=verifier,
        audit_sink=cast(Any, _AuditSink()),
    )


async def _authorize(
    service: WorkflowProtectedRuntimeStartAuthorizationService,
    source: WorkflowProtectedRuntimeStartAuthorizationSource,
) -> WorkflowProtectedRuntimeStartAuthorizationLease:
    return await service.authorize(
        use_result_id=source.result.result_id,
        use_result_digest=source.result.canonical_digest,
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        idempotency_key="imp-223-runtime-start",
        context=_context(),
    )


def test_public_authorize_surface_is_metadata_only() -> None:
    parameters = set(
        inspect.signature(WorkflowProtectedRuntimeStartAuthorizationService.authorize).parameters
    )

    assert parameters == {
        "self",
        "use_result_id",
        "use_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert not parameters.intersection(
        {
            "credential",
            "endpoint",
            "executor",
            "model",
            "prompt",
            "runtime_envelope",
            "runtime_slot_commitment",
            "start",
        }
    )


@pytest.mark.asyncio
async def test_authorize_replays_first_then_issues_bounded_nonoperational_lease() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)
    verifier = _ReceiptVerifier()

    lease = await _authorize(_service(repository, _Attestor(events), verifier), source)

    assert events == ["preflight", "source", "attest", "authoritative_time", "authorize"]
    assert lease.valid_until - lease.issued_at <= timedelta(seconds=1)
    assert lease.single_use is True
    assert lease.renewable is False
    assert lease.transferable is False
    assert lease.lease_is_bearer_capability is False
    authority = lease.authority.canonical_value()
    assert authority.pop("protected_runtime_start_authority_granted") is True
    assert not any(authority.values())
    assert lease.authority.runtime_start_authorized is False
    assert lease.authority.runtime_resume_authorized is False
    assert lease.authority.execution_authorized is False
    assert verifier.calls == 2

    replay_events: list[str] = []
    replay_repository = _Repository(source, replay_events)
    replay_repository.preflight_status = (
        WorkflowProtectedRuntimeStartAuthorizationPreflightStatus.REPLAY
    )
    replay_repository.replay_lease = lease
    replay = await _authorize(
        _service(replay_repository, _Attestor(replay_events), _ReceiptVerifier()), source
    )

    assert replay == lease
    assert replay_events == ["preflight"]


@pytest.mark.asyncio
async def test_full_adr_172_lineage_is_bound_into_claim_and_lease() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)

    lease = await _authorize(_service(repository, _Attestor(events), _ReceiptVerifier()), source)
    claim = repository.requests[0].candidate_claim

    assert claim.use_result_digest == source.result.canonical_digest
    assert claim.use_attempt_digest == source.attempt.canonical_digest
    assert claim.use_claim_digest == source.use_claim.canonical_digest
    assert claim.use_receipt_digest == source.use_receipt.canonical_digest
    assert lease.use_result_digest == claim.use_result_digest
    assert lease.use_attempt_digest == claim.use_attempt_digest
    assert lease.use_claim_digest == claim.use_claim_digest
    assert lease.use_receipt_digest == claim.use_receipt_digest


@pytest.mark.asyncio
async def test_non_consumer_identity_is_denied_before_protected_state_io() -> None:
    source = _source()
    events: list[str] = []
    service = _service(_Repository(source, events), _Attestor(events), _ReceiptVerifier())

    with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as exc_info:
        await service.authorize(
            use_result_id=source.result.result_id,
            use_result_digest=source.result.canonical_digest,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            idempotency_key="imp-223-runtime-start",
            context=_context(subject_id="human.user"),
        )

    assert exc_info.value.code == "workflow_protected_runtime_start_consumer_identity_required"
    assert events == []


@pytest.mark.asyncio
async def test_failed_adr_172_result_is_ineligible() -> None:
    source = _source(
        state=WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_FAILED_WITHOUT_USE
    )
    events: list[str] = []

    with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as exc_info:
        await _authorize(
            _service(_Repository(source, events), _Attestor(events), _ReceiptVerifier()),
            source,
        )

    assert exc_info.value.code == "workflow_protected_runtime_start_evidence_conflict"
    assert events == ["preflight", "source"]


@pytest.mark.asyncio
async def test_attestation_cannot_authorize_execution_or_start() -> None:
    source = _source()
    events: list[str] = []

    with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as exc_info:
        await _authorize(
            _service(
                _Repository(source, events),
                _Attestor(events, unsafe=True),
                _ReceiptVerifier(),
            ),
            source,
        )

    assert exc_info.value.code == "workflow_protected_runtime_start_attestation_invalid"
    assert events == ["preflight", "source", "attest", "authoritative_time"]


@pytest.mark.asyncio
async def test_unavailable_attestor_fails_closed_after_replay_preflight() -> None:
    source = _source()
    events: list[str] = []
    attestor = _Attestor(events)
    attestor.available = False

    with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as exc_info:
        await _authorize(
            _service(_Repository(source, events), attestor, _ReceiptVerifier()), source
        )

    assert exc_info.value.code == "workflow_protected_runtime_start_trusted_attestor_unavailable"
    assert events == ["preflight"]


@pytest.mark.asyncio
async def test_nondurable_repository_fails_closed_before_replay_lookup() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)
    repository.durable = False

    with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as exc_info:
        await _authorize(_service(repository, _Attestor(events), _ReceiptVerifier()), source)

    assert exc_info.value.code == "workflow_protected_runtime_start_durable_repository_required"
    assert events == []


def test_policy_identity_is_not_inherited_as_runtime_start_permission() -> None:
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()

    assert (
        policy.source_policy_id
        == code_owned_workflow_protected_runtime_context_use_policy().policy_id
    )
    assert policy.runtime_start_forbidden is True
    assert policy.model_inference_forbidden is True
