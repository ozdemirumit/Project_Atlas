from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationError,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseResult,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightResult,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationSource,
    WorkflowProtectedRuntimeReadinessLifecycleAttestation,
    WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest,
    validate_workflow_protected_runtime_readiness_authorization_request,
)
from atlas.modules.workflows.application.protected_runtime_readiness_authorizations import (
    WorkflowProtectedRuntimeReadinessAuthorizationService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationLease,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationAuthority,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionAuthority,
    WorkflowProtectedRuntimeStartConsumptionFailureClass,
    WorkflowProtectedRuntimeStartConsumptionResultState,
    code_owned_workflow_protected_runtime_start_consumption_policy,
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
    state: WorkflowProtectedRuntimeStartConsumptionResultState = (
        WorkflowProtectedRuntimeStartConsumptionResultState
    ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY,
) -> WorkflowProtectedRuntimeReadinessAuthorizationSource:
    source_policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    zero = WorkflowProtectedRuntimeStartConsumptionAuthority()
    authorization_claim = _Evidence(
        "start-authorization-claim",
        "imp-223",
        claim_id="runtime-start-authorization-claim.imp-223",
    )
    authorization_lease = _Evidence(
        "start-authorization-lease",
        "imp-223",
        authorization_lease_id="runtime-start-authorization-lease.imp-223",
        claim_id=authorization_claim.claim_id,
        claim_digest=authorization_claim.canonical_digest,
        authority=WorkflowProtectedRuntimeStartAuthorizationAuthority(
            protected_runtime_start_authority_granted=True
        ),
    )
    start_claim = _Evidence(
        "start-claim",
        "imp-224",
        claim_id="runtime-start-claim.imp-224",
        consumption_id="runtime-start.imp-224",
        attempt_id="runtime-start-attempt.imp-224",
        authorization_lease_id=authorization_lease.authorization_lease_id,
        authorization_lease_digest=authorization_lease.canonical_digest,
        authority=zero,
    )
    attempt = _Evidence(
        "start-attempt",
        "imp-224",
        attempt_id=start_claim.attempt_id,
        consumption_id=start_claim.consumption_id,
        claim_id=start_claim.claim_id,
        claim_digest=start_claim.canonical_digest,
        authorization_lease_id=authorization_lease.authorization_lease_id,
        authorization_lease_digest=authorization_lease.canonical_digest,
        destination_deployment_id="deployment.imp-224",
        destination_generation=5,
        destination_fencing_token_digest="1" * 64,
        runtime_slot_commitment="2" * 64,
        runtime_slot_generation=9,
        runtime_envelope_id="runtime-envelope.imp-224",
        runtime_envelope_commitment="3" * 64,
        runtime_envelope_generation=9,
        runtime_start_profile_id=source_policy.runtime_start_profile_id,
        runtime_start_profile_version=source_policy.runtime_start_profile_version,
        runtime_start_profile_digest=source_policy.runtime_start_profile_digest,
        consumer_subject_id=source_policy.consumer_subject_id,
        consumer_audience=source_policy.consumer_audience,
        consumer_contract_id=source_policy.consumer_contract_id,
        consumer_contract_version=source_policy.consumer_contract_version,
        scope=SCOPE,
        authority=zero,
    )
    receipt = _Evidence(
        "start-receipt",
        "imp-224",
        result_state=state,
        runtime_started=(
            state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
        ),
        runtime_start_count_pre=0,
        runtime_start_count_post=(
            1
            if state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
            else 0
        ),
        runtime_envelope_current=True,
        runtime_envelope_inactive=(
            state
            is not (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
        ),
        scheduling_performed=False,
        runtime_resumed=False,
        generic_process_created=False,
        prompt_constructed=False,
        model_inference_performed=False,
        network_activity_performed=False,
        readiness_probe_performed=False,
        publication_performed=False,
        delivery_performed=False,
        connector_activity_performed=False,
        dispatch_performed=False,
        execution_performed=False,
        infrastructure_mutation_performed=False,
        signing_key_id=source_policy.receipt_verification_signing_key_id,
        completed_at=NOW - timedelta(seconds=2),
    )
    success = (
        state
        is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
    )
    result = _Evidence(
        "start-result",
        "imp-224",
        result_id="runtime-start-result.imp-224",
        consumption_id=attempt.consumption_id,
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        claim_id=start_claim.claim_id,
        claim_digest=start_claim.canonical_digest,
        authorization_lease_id=authorization_lease.authorization_lease_id,
        authorization_lease_digest=authorization_lease.canonical_digest,
        runtime_start_profile_id=attempt.runtime_start_profile_id,
        runtime_start_profile_version=attempt.runtime_start_profile_version,
        runtime_start_profile_digest=attempt.runtime_start_profile_digest,
        destination_deployment_id=attempt.destination_deployment_id,
        destination_generation=attempt.destination_generation,
        runtime_envelope_commitment=attempt.runtime_envelope_commitment,
        runtime_envelope_generation=attempt.runtime_envelope_generation,
        state=state,
        failure_class=(
            None
            if success
            else (
                WorkflowProtectedRuntimeStartConsumptionFailureClass
            ).PROTECTED_STARTER_REJECTED_WITHOUT_START
        ),
        outcome_known=True,
        runtime_started=success,
        starter_receipt_digest=receipt.canonical_digest,
        completed_at=receipt.completed_at,
        recorded_at=NOW - timedelta(seconds=1),
        scope=SCOPE,
        authority=zero,
    )
    return WorkflowProtectedRuntimeReadinessAuthorizationSource(
        result=cast(Any, result),
        attempt=cast(Any, attempt),
        start_claim=cast(Any, start_claim),
        starter_receipt=cast(Any, receipt),
        start_authorization_lease=cast(Any, authorization_lease),
        start_authorization_claim=cast(Any, authorization_claim),
    )


class _Repository:
    durable = True

    def __init__(
        self,
        source: WorkflowProtectedRuntimeReadinessAuthorizationSource,
        events: list[str],
    ) -> None:
        self.source = source
        self.events = events
        self.preflight_status = WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus.NONE
        self.replay_lease: WorkflowProtectedRuntimeReadinessAuthorizationLease | None = None
        self.requests: list[WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest] = []

    async def preflight_protected_runtime_readiness_authorization(
        self, request: WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationPreflightResult:
        del request
        self.events.append("preflight")
        return WorkflowProtectedRuntimeReadinessAuthorizationPreflightResult(
            status=self.preflight_status,
            lease=self.replay_lease,
            evaluated_at=NOW,
        )

    async def get_protected_runtime_readiness_authorization_source(
        self, *, start_result_id: str
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationSource:
        self.events.append("source")
        assert start_result_id == self.source.result.result_id
        return self.source

    async def get_authoritative_time(self) -> datetime:
        self.events.append("authoritative_time")
        return NOW + timedelta(milliseconds=200)

    async def authorize_protected_runtime_readiness(
        self, request: WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationLeaseResult:
        self.events.append("authorize")
        validate_workflow_protected_runtime_readiness_authorization_request(request)
        self.requests.append(request)
        return WorkflowProtectedRuntimeReadinessAuthorizationLeaseResult(
            status=WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus.AUTHORIZED,
            lease=request.candidate,
            evaluated_at=NOW + timedelta(milliseconds=200),
        )


class _Attestor:
    available = True

    def __init__(self, events: list[str], *, unsafe_probe: bool = False) -> None:
        self.events = events
        self.unsafe_probe = unsafe_probe

    async def attest_runtime_readiness_lifecycle(
        self, request: WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeReadinessLifecycleAttestation:
        self.events.append("attest")
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        values: dict[str, object] = {
            **request_values,
            "attestation_id": "runtime-readiness-attestation.imp-225",
            "attestor_id": "attestor.workflow-protected-runtime-readiness-lifecycle",
            "attestor_version": "1.0",
            "signing_key_id": "key.workflow-protected-runtime-readiness-lifecycle.v1",
            "signature_algorithm": "hmac-sha256",
            "observed_at": NOW + timedelta(milliseconds=100),
            "valid_until": NOW + timedelta(milliseconds=800),
            "runtime_envelope_eligible_until": NOW + timedelta(seconds=1),
            "exact_start_result_confirmed": True,
            "runtime_started_confirmed": True,
            "runtime_envelope_current": True,
            "runtime_envelope_started": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "protected_slot_generation_current": True,
            "readiness_profile_eligible": True,
            "prior_readiness_claim_absent": True,
            "prior_readiness_lease_absent": True,
            "prior_readiness_attempt_absent": True,
            "prior_readiness_result_absent": True,
            "runtime_resumed": False,
            "runtime_stopped": False,
            "runtime_restarted": False,
            "generic_process_created": False,
            "scheduling_performed": False,
            "readiness_probe_performed": self.unsafe_probe,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "publication_performed": False,
            "delivery_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
            "runtime_locator_included": False,
            "process_identifier_included": False,
            "context_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "command_included": False,
            "integrity_signature": "4" * 64,
        }
        attestation = WorkflowProtectedRuntimeReadinessLifecycleAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        return replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )

    def verify_runtime_readiness_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeReadinessLifecycleAttestation
    ) -> bool:
        del attestation
        return True


class _ReceiptVerifier:
    available = True

    def __init__(self) -> None:
        self.calls = 0

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        self.calls += 1
        return True


class _AuditSink:
    async def record(self, record: object) -> None:
        del record


def _context(
    *, subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-225",
        decision_id="decision.imp-225",
        requested_at=NOW,
    )


def _service(
    repository: _Repository,
    attestor: _Attestor,
    verifier: _ReceiptVerifier,
) -> WorkflowProtectedRuntimeReadinessAuthorizationService:
    return WorkflowProtectedRuntimeReadinessAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=attestor,
        lifecycle_signature_verifier=attestor,
        start_receipt_signature_verifier=verifier,
        audit_sink=cast(Any, _AuditSink()),
    )


async def _authorize(
    service: WorkflowProtectedRuntimeReadinessAuthorizationService,
    source: WorkflowProtectedRuntimeReadinessAuthorizationSource,
) -> WorkflowProtectedRuntimeReadinessAuthorizationLease:
    return await service.authorize(
        start_result_id=source.result.result_id,
        start_result_digest=source.result.canonical_digest,
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        idempotency_key="imp-225-runtime-readiness",
        context=_context(),
    )


def test_public_authorize_surface_is_metadata_only() -> None:
    parameters = set(
        inspect.signature(
            WorkflowProtectedRuntimeReadinessAuthorizationService.authorize
        ).parameters
    )

    assert parameters == {
        "self",
        "start_result_id",
        "start_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert not parameters.intersection(
        {
            "connector",
            "credential",
            "endpoint",
            "executor",
            "network",
            "probe",
            "runtime_locator",
        }
    )


@pytest.mark.asyncio
async def test_replay_first_then_issues_bounded_nonoperational_lease() -> None:
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
    assert authority.pop("protected_runtime_readiness_authority_granted") is True
    assert not any(authority.values())
    assert lease.authority.readiness_probe_authorized is False
    assert lease.authority.network_access_authorized is False
    assert lease.authority.connector_activity_authorized is False
    assert lease.authority.execution_authorized is False
    assert verifier.calls == 2

    replay_events: list[str] = []
    replay_repository = _Repository(source, replay_events)
    replay_repository.preflight_status = (
        WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus.REPLAY
    )
    replay_repository.replay_lease = lease

    replay = await _authorize(
        _service(replay_repository, _Attestor(replay_events), _ReceiptVerifier()), source
    )

    assert replay == lease
    assert replay_events == ["preflight"]


@pytest.mark.asyncio
async def test_only_successful_adr_174_result_is_eligible() -> None:
    source = _source(
        state=(
            WorkflowProtectedRuntimeStartConsumptionResultState
        ).RUNTIME_START_FAILED_WITHOUT_START
    )
    events: list[str] = []

    with pytest.raises(WorkflowProtectedRuntimeReadinessAuthorizationError) as exc_info:
        await _authorize(
            _service(_Repository(source, events), _Attestor(events), _ReceiptVerifier()),
            source,
        )

    assert exc_info.value.code == "workflow_protected_runtime_readiness_evidence_conflict"
    assert events == ["preflight", "source"]


@pytest.mark.asyncio
async def test_probe_effect_in_attestation_fails_closed_without_authorization() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)

    with pytest.raises(WorkflowProtectedRuntimeReadinessAuthorizationError) as exc_info:
        await _authorize(
            _service(repository, _Attestor(events, unsafe_probe=True), _ReceiptVerifier()),
            source,
        )

    assert exc_info.value.code == "workflow_protected_runtime_readiness_attestation_invalid"
    assert events == ["preflight", "source", "attest", "authoritative_time"]
    assert repository.requests == []


@pytest.mark.asyncio
async def test_non_consumer_is_denied_before_protected_state_io() -> None:
    source = _source()
    events: list[str] = []
    service = _service(_Repository(source, events), _Attestor(events), _ReceiptVerifier())

    with pytest.raises(WorkflowProtectedRuntimeReadinessAuthorizationError) as exc_info:
        await service.authorize(
            start_result_id=source.result.result_id,
            start_result_digest=source.result.canonical_digest,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            idempotency_key="imp-225-runtime-readiness",
            context=_context(subject_id="human.user"),
        )

    assert exc_info.value.code == "workflow_protected_runtime_readiness_consumer_identity_required"
    assert events == []
