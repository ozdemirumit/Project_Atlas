from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.protected_runtime_slot_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorization_ports import (
    WorkflowProtectedRuntimeContextUseAuthorizationError,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseResult,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationPreflightResult,
    WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeContextUseAuthorizationSource,
    validate_workflow_protected_runtime_context_use_authorization_request,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorizations import (
    WorkflowProtectedRuntimeContextUseAuthorizationService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_injection_consumption_domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionAuthority,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationLease,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


class _Evidence(SimpleNamespace):
    def __init__(self, kind: str, key: str, **values: object) -> None:
        super().__init__(**values)
        self._digest_values: dict[str, object] = {"kind": kind, "key": key}
        self.canonical_digest = canonical_digest(self._digest_values)

    def digest_payload(self) -> dict[str, object]:
        return self._digest_values


def _source(
    *, injected_context_usable_until: datetime | None = None
) -> WorkflowProtectedRuntimeContextUseAuthorizationSource:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    zero = WorkflowProtectedRuntimeContextInjectionConsumptionAuthority()
    claim = _Evidence("claim", "imp-220", claim_id="injection-claim.imp-220", authority=zero)
    attempt = _Evidence(
        "attempt",
        "imp-220",
        attempt_id="injection-attempt.imp-220",
        consumption_claim_id=claim.claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id="injection-lease.imp-219",
        authorization_lease_digest="1" * 64,
        expected_runtime_slot_post_generation=8,
        protected_runtime_handle_usable_until=(
            injected_context_usable_until or NOW + timedelta(milliseconds=750)
        ),
        runtime_slot_commitment="2" * 64,
        destination_boundary_id="boundary.imp-220",
        destination_deployment_id="deployment.imp-220",
        destination_generation=4,
        destination_fencing_token_digest="3" * 64,
        scope=SCOPE,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        authority=zero,
    )
    receipt = _Evidence(
        "receipt",
        "imp-220",
        state=(
            WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT
        ),
        runtime_slot_pre_generation=7,
        runtime_slot_post_generation=8,
        protected_runtime_handle_consumed=True,
        inert_context_injected=True,
        runtime_slot_mutation_performed=True,
        completed_at=NOW - timedelta(seconds=2),
        signing_key_id=policy.receipt_verification_signing_key_id,
    )
    result = _Evidence(
        "result",
        "imp-220",
        result_id="injection-result.imp-220",
        injection_id="injection.imp-220",
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        consumption_claim_id=claim.claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id=attempt.authorization_lease_id,
        authorization_lease_digest=attempt.authorization_lease_digest,
        injector_receipt_digest=receipt.canonical_digest,
        state=receipt.state,
        outcome_known=True,
        protected_runtime_handle_consumed=True,
        inert_context_injected=True,
        runtime_slot_mutation_performed=True,
        completed_at=receipt.completed_at,
        recorded_at=NOW - timedelta(seconds=1),
        injection_deadline=NOW - timedelta(seconds=1, milliseconds=500),
        runtime_slot_pre_generation=receipt.runtime_slot_pre_generation,
        runtime_slot_post_generation=receipt.runtime_slot_post_generation,
        runtime_slot_commitment=attempt.runtime_slot_commitment,
        destination_boundary_id=attempt.destination_boundary_id,
        destination_deployment_id=attempt.destination_deployment_id,
        destination_generation=attempt.destination_generation,
        destination_fencing_token_digest=attempt.destination_fencing_token_digest,
        runtime_slot_profile_id=policy.runtime_slot_profile_id,
        runtime_slot_profile_version=policy.runtime_slot_profile_version,
        runtime_slot_profile_digest=policy.runtime_slot_profile_digest,
        authority=zero,
    )
    return WorkflowProtectedRuntimeContextUseAuthorizationSource(
        result=cast(Any, result),
        attempt=cast(Any, attempt),
        consumption_claim=cast(Any, claim),
        injector_receipt=cast(Any, receipt),
    )


class _Repository:
    durable = True

    def __init__(
        self,
        source: WorkflowProtectedRuntimeContextUseAuthorizationSource,
        events: list[str],
    ) -> None:
        self.source = source
        self.events = events
        self.preflight_status = WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus.NONE
        self.replay_lease: WorkflowProtectedRuntimeContextUseAuthorizationLease | None = None
        self.requests: list[WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest] = []

    async def preflight_protected_runtime_context_use_authorization(
        self, request: WorkflowProtectedRuntimeContextUseAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationPreflightResult:
        del request
        self.events.append("preflight")
        return WorkflowProtectedRuntimeContextUseAuthorizationPreflightResult(
            status=self.preflight_status,
            lease=self.replay_lease,
            evaluated_at=NOW,
        )

    async def get_protected_runtime_context_use_authorization_source(
        self, *, injection_result_id: str
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationSource:
        self.events.append("source")
        assert injection_result_id == self.source.result.result_id
        return self.source

    async def get_authoritative_time(self) -> datetime:
        self.events.append("authoritative_time")
        return NOW + timedelta(milliseconds=200)

    async def authorize_protected_runtime_context_use(
        self, request: WorkflowProtectedRuntimeContextUseAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationLeaseResult:
        self.events.append("authorize")
        validate_workflow_protected_runtime_context_use_authorization_request(request)
        self.requests.append(request)
        return WorkflowProtectedRuntimeContextUseAuthorizationLeaseResult(
            status=WorkflowProtectedRuntimeContextUseAuthorizationLeaseStatus.AUTHORIZED,
            lease=request.candidate,
            evaluated_at=NOW + timedelta(milliseconds=200),
        )


class _Attestor:
    def __init__(self, events: list[str]) -> None:
        self._delegate = DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor(
            development_enabled=True,
            clock=lambda: NOW + timedelta(milliseconds=100),
        )
        self.events = events

    @property
    def available(self) -> bool:
        return self._delegate.available

    async def attest_runtime_slot_lifecycle(self, request: object) -> object:
        self.events.append("attest")
        return await self._delegate.attest_runtime_slot_lifecycle(cast(Any, request))

    def verify_runtime_slot_lifecycle_attestation(self, attestation: object) -> bool:
        return self._delegate.verify_runtime_slot_lifecycle_attestation(cast(Any, attestation))


class _MismatchedCeilingAttestor(_Attestor):
    async def attest_runtime_slot_lifecycle(self, request: object) -> object:
        attestation = await super().attest_runtime_slot_lifecycle(request)
        return replace(
            cast(Any, attestation),
            injected_context_usable_until=(
                cast(Any, attestation).injected_context_usable_until + timedelta(milliseconds=1)
            ),
        )

    def verify_runtime_slot_lifecycle_attestation(self, attestation: object) -> bool:
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
        correlation_id="correlation.imp-220",
        decision_id="decision.imp-220",
        requested_at=NOW,
    )


def _service(
    repository: _Repository,
    attestor: _Attestor,
    verifier: _ReceiptVerifier,
) -> WorkflowProtectedRuntimeContextUseAuthorizationService:
    return WorkflowProtectedRuntimeContextUseAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=cast(Any, attestor),
        lifecycle_signature_verifier=cast(Any, attestor),
        injector_receipt_signature_verifier=verifier,
        audit_sink=cast(Any, _AuditSink()),
    )


async def _authorize(
    service: WorkflowProtectedRuntimeContextUseAuthorizationService,
    source: WorkflowProtectedRuntimeContextUseAuthorizationSource,
) -> WorkflowProtectedRuntimeContextUseAuthorizationLease:
    return await service.authorize(
        injection_result_id=source.result.result_id,
        injection_result_digest=source.result.canonical_digest,
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        idempotency_key="imp-220-runtime-context-use",
        context=_context(),
    )


def test_public_authorize_surface_exposes_only_result_policy_and_idempotency() -> None:
    parameters = set(
        inspect.signature(
            WorkflowProtectedRuntimeContextUseAuthorizationService.authorize
        ).parameters
    )

    assert parameters == {
        "self",
        "injection_result_id",
        "injection_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert not parameters.intersection(
        {
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            "endpoint",
            "credential",
            "runtime_use",
            "authority",
        }
    )


@pytest.mark.asyncio
async def test_authorize_replays_durably_before_attestor_io_and_issues_zero_use_lease() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)
    attestor = _Attestor(events)
    verifier = _ReceiptVerifier()

    lease = await _authorize(_service(repository, attestor, verifier), source)

    assert events == ["preflight", "source", "attest", "authoritative_time", "authorize"]
    assert lease.valid_until - lease.issued_at <= timedelta(seconds=1)
    assert lease.injected_context_usable_until == NOW + timedelta(milliseconds=750)
    assert lease.single_use is True
    assert lease.renewable is False
    assert lease.transferable is False
    assert lease.lease_is_bearer_capability is False
    authority = lease.authority.canonical_value()
    assert authority.pop("protected_runtime_context_use_authority_granted") is True
    assert not any(authority.values())
    assert verifier.calls == 2

    replay_events: list[str] = []
    replay_repository = _Repository(source, replay_events)
    replay_repository.preflight_status = (
        WorkflowProtectedRuntimeContextUseAuthorizationPreflightStatus.REPLAY
    )
    replay_repository.replay_lease = lease
    replay = await _authorize(
        _service(replay_repository, _Attestor(replay_events), _ReceiptVerifier()), source
    )

    assert replay == lease
    assert replay_events == ["preflight"]


@pytest.mark.asyncio
async def test_valid_until_is_capped_by_canonical_context_ceiling_and_excludes_boundary() -> None:
    ceiling = NOW + timedelta(milliseconds=350)
    source = _source(injected_context_usable_until=ceiling)
    events: list[str] = []
    repository = _Repository(source, events)

    lease = await _authorize(_service(repository, _Attestor(events), _ReceiptVerifier()), source)

    assert lease.valid_until == ceiling
    assert lease.effective_until == ceiling
    assert lease.injected_context_usable_until == ceiling
    assert repository.requests[0].candidate_claim.injected_context_usable_until == ceiling
    assert lease.is_active(evaluated_at=ceiling - timedelta(microseconds=1)) is True
    assert lease.is_active(evaluated_at=ceiling) is False


@pytest.mark.asyncio
async def test_mismatched_signed_context_ceiling_is_rejected() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)
    service = _service(repository, _MismatchedCeilingAttestor(events), _ReceiptVerifier())

    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError) as exc_info:
        await _authorize(service, source)

    assert exc_info.value.code == "workflow_protected_runtime_context_use_attestation_invalid"
    assert events == ["preflight", "source", "attest", "authoritative_time"]


@pytest.mark.asyncio
async def test_non_positive_context_ceiling_at_second_db_time_fails_closed() -> None:
    source = _source(injected_context_usable_until=NOW + timedelta(milliseconds=200))
    events: list[str] = []
    repository = _Repository(source, events)

    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError):
        await _authorize(_service(repository, _Attestor(events), _ReceiptVerifier()), source)

    assert events == ["preflight", "source", "attest", "authoritative_time"]


@pytest.mark.asyncio
async def test_non_consumer_identity_is_denied_before_repository_or_attestor() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)
    service = _service(repository, _Attestor(events), _ReceiptVerifier())

    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError) as exc_info:
        await service.authorize(
            injection_result_id=source.result.result_id,
            injection_result_digest=source.result.canonical_digest,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            idempotency_key="imp-220-runtime-context-use",
            context=_context(subject_id="human.user"),
        )

    assert exc_info.value.code == (
        "workflow_protected_runtime_context_use_consumer_identity_required"
    )
    assert events == []


@pytest.mark.asyncio
async def test_unavailable_attestor_fails_closed_after_durable_preflight() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events)
    unavailable = _Attestor(events)
    unavailable._delegate = DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor()

    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError):
        await _authorize(_service(repository, unavailable, _ReceiptVerifier()), source)

    assert events == ["preflight"]
