from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows import domain

_REQUIRED_DOMAIN_NAMES = (
    "WorkflowProtectedResidentContextAccessConsumptionAttempt",
    "WorkflowProtectedResidentContextAccessConsumptionAuthority",
    "WorkflowProtectedResidentContextAccessConsumptionFailureClass",
    "WorkflowProtectedResidentContextAccessConsumptionPolicy",
    "WorkflowProtectedResidentContextAccessConsumptionResult",
    "WorkflowProtectedResidentContextAccessConsumptionResultState",
    "WorkflowProtectedResidentContextTrustedAccessorInstruction",
    "WorkflowProtectedResidentContextTrustedAccessorReceipt",
    "code_owned_workflow_protected_resident_context_access_consumption_policy",
)
if not all(hasattr(domain, name) for name in _REQUIRED_DOMAIN_NAMES):
    pytest.skip("IMP-217 domain slice is merged separately", allow_module_level=True)

from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E402, E501
    WorkflowProtectedResidentContextAccessConsumptionClaimStatus,
    WorkflowProtectedResidentContextAccessConsumptionClaimWrite,
    WorkflowProtectedResidentContextAccessConsumptionError,
    WorkflowProtectedResidentContextAccessConsumptionReplayLookup,
    WorkflowProtectedResidentContextAccessConsumptionReplayStatus,
    WorkflowProtectedResidentContextAccessConsumptionResultWrite,
    WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus,
)
from atlas.modules.workflows.application.protected_resident_context_access_consumptions import (  # noqa: E402
    WorkflowProtectedResidentContextAccessConsumptionService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E402, E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain import WorkflowScope  # noqa: E402

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class _AuditSink:
    def __init__(self, order: list[str]) -> None:
        self.order = order

    async def record(self, record: object) -> None:
        del record
        self.order.append("audit")


class _Repository:
    durable = True

    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.replay = WorkflowProtectedResidentContextAccessConsumptionReplayLookup(
            status=WorkflowProtectedResidentContextAccessConsumptionReplayStatus.NONE,
            attempt=None,
            result=None,
        )
        self.claim: WorkflowProtectedResidentContextAccessConsumptionClaimWrite | None = None
        self.result_write: WorkflowProtectedResidentContextAccessConsumptionResultWrite | None = (
            None
        )
        self.source: object | None = None

    async def lookup_protected_resident_context_access_consumption_replay(
        self, request: object
    ) -> WorkflowProtectedResidentContextAccessConsumptionReplayLookup:
        del request
        self.order.append("replay")
        return self.replay

    async def get_protected_resident_context_access_consumption_source(
        self, *, authorization_lease_id: str
    ) -> object | None:
        del authorization_lease_id
        self.order.append("source")
        return self.source

    async def claim_protected_resident_context_access_consumption(
        self, request: object
    ) -> WorkflowProtectedResidentContextAccessConsumptionClaimWrite:
        del request
        self.order.append("claim")
        assert self.claim is not None
        return self.claim

    async def record_protected_resident_context_access_consumption_result(
        self, request: object
    ) -> WorkflowProtectedResidentContextAccessConsumptionResultWrite:
        del request
        self.order.append("result")
        assert self.result_write is not None
        return self.result_write

    async def get_authoritative_time(self) -> datetime:
        self.order.append("time")
        return NOW + timedelta(milliseconds=200)


class _UnavailableExternal:
    available = False
    calls: list[object] = []  # noqa: RUF012


class _Accessor:
    available = True
    accessor_contract_id = "contract.accessor"
    accessor_contract_version = "1.0"
    accessor_id = "accessor.test"
    accessor_version = "1.0"
    runtime_handle_profile_id = "profile.handle"
    runtime_handle_profile_version = "1.0"
    runtime_handle_profile_digest = "a" * 64

    def __init__(self, order: list[str], *, raises: bool = False) -> None:
        self.order = order
        self.raises = raises
        self.calls: list[object] = []

    async def establish_access(self, instruction: object) -> object:
        self.order.append("accessor")
        self.calls.append(instruction)
        if self.raises:
            raise RuntimeError("uncertain")
        return SimpleNamespace(canonical_digest="b" * 64)

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


def _policy() -> Any:
    return SimpleNamespace(
        policy_id="policy.access-consumption",
        policy_version="1.0",
        canonical_digest="c" * 64,
        required_lifecycle_attestor_id="attestor.lifecycle",
        required_lifecycle_attestor_version="1.0",
        required_readiness_attestor_id="attestor.readiness",
        required_readiness_attestor_version="1.0",
        required_accessor_contract_id="contract.accessor",
        required_accessor_contract_version="1.0",
        approved_accessor_id="accessor.test",
        approved_accessor_version="1.0",
        runtime_handle_profile_id="profile.handle",
        runtime_handle_profile_version="1.0",
        runtime_handle_profile_digest="a" * 64,
        verification_signing_key_id="key.test",
        minimum_remaining_budget_milliseconds=100,
        destination_boundary_id="boundary.test",
        destination_deployment_id="deployment.test",
        destination_generation=1,
        destination_fencing_token_digest="d" * 64,
    )


def _context(
    *, subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=WorkflowScope("organization.test", "environment.test", "site.test"),
        correlation_id="correlation.test",
        decision_id="decision.test",
        requested_at=NOW,
    )


def _service(
    repository: _Repository, accessor: object, order: list[str]
) -> WorkflowProtectedResidentContextAccessConsumptionService:
    external = _UnavailableExternal()
    return WorkflowProtectedResidentContextAccessConsumptionService(
        repository=cast(Any, repository),
        lifecycle_attestor=cast(Any, external),
        readiness_attestor=cast(Any, external),
        lifecycle_signature_verifier=cast(Any, external),
        readiness_signature_verifier=cast(Any, external),
        accessor=cast(Any, accessor),
        audit_sink=_AuditSink(order),
        policy=_policy(),
    )


def _request() -> dict[str, object]:
    return {
        "authorization_lease_id": "workflow-protected-resident-context-access-lease.abcdef123456",
        "policy_id": "policy.access-consumption",
        "policy_version": "1.0",
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "idempotency-test-001",
        "context": _context(),
    }


def test_public_command_accepts_lease_id_but_no_caller_digest() -> None:
    parameters = inspect.signature(
        WorkflowProtectedResidentContextAccessConsumptionService.consume
    ).parameters
    assert "authorization_lease_id" in parameters
    assert "authorization_lease_digest" not in parameters


@pytest.mark.asyncio
async def test_terminal_replay_precedes_all_attestor_and_accessor_io() -> None:
    order: list[str] = []
    repository = _Repository(order)
    attempt = SimpleNamespace(consumption_id="consumption.test")
    result = SimpleNamespace(consumption_id="consumption.test")
    repository.replay = WorkflowProtectedResidentContextAccessConsumptionReplayLookup(
        status=WorkflowProtectedResidentContextAccessConsumptionReplayStatus.TERMINAL,
        attempt=cast(Any, attempt),
        result=cast(Any, result),
    )
    accessor = _Accessor(order)

    presentation = await cast(Any, _service(repository, accessor, order).consume)(**_request())

    assert cast(Any, presentation.attempt) is attempt
    assert cast(Any, presentation.result) is result
    assert order == ["replay"]
    assert accessor.calls == []


@pytest.mark.asyncio
async def test_wrong_workload_identity_fails_before_repository_io() -> None:
    order: list[str] = []
    repository = _Repository(order)
    service = _service(repository, _Accessor(order), order)
    request = _request()
    request["context"] = _context(subject_id="service.some-other-workload")

    with pytest.raises(WorkflowProtectedResidentContextAccessConsumptionError):
        await cast(Any, service.consume)(**request)

    assert order == []


@pytest.mark.asyncio
async def test_claim_commit_precedes_accessor_and_result_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    repository = _Repository(order)
    attempt = SimpleNamespace(
        consumption_id="consumption.test",
        consumption_claim_id="claim.test",
        canonical_digest="e" * 64,
        access_deadline=NOW + timedelta(seconds=1),
    )
    claim = SimpleNamespace(canonical_digest="f" * 64)
    result = SimpleNamespace(consumption_id="consumption.test")
    lease = SimpleNamespace(authorization_lease_id="lease.test", canonical_digest="1" * 64)
    evidence = SimpleNamespace(
        source=SimpleNamespace(authorization_lease=lease),
        lifecycle=SimpleNamespace(request_nonce_digest="2" * 64),
        readiness=SimpleNamespace(),
    )
    repository.claim = WorkflowProtectedResidentContextAccessConsumptionClaimWrite(
        status=WorkflowProtectedResidentContextAccessConsumptionClaimStatus.CLAIMED,
        claim=cast(Any, claim),
        attempt=cast(Any, attempt),
        result=None,
    )
    repository.result_write = WorkflowProtectedResidentContextAccessConsumptionResultWrite(
        status=WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus.RECORDED,
        result=cast(Any, result),
    )
    accessor = _Accessor(order)
    service = _service(repository, accessor, order)
    monkeypatch.setattr(service, "_require_trusted_components", lambda: None)

    async def load_and_attest(**values: object) -> object:
        del values
        order.append("attest")
        return evidence

    monkeypatch.setattr(service, "_load_and_attest", load_and_attest)
    monkeypatch.setattr(service, "_build_instruction", lambda value: SimpleNamespace())
    monkeypatch.setattr(service, "_verify_receipt", lambda receipt, instruction: None)
    monkeypatch.setattr(service, "_build_receipted_result", lambda **values: result)

    presentation = await cast(Any, service.consume)(**_request())

    assert cast(Any, presentation.result) is result
    assert order.index("replay") < order.index("attest") < order.index("claim")
    assert order.index("claim") < order.index("accessor") < order.index("result")
    assert order.count("accessor") == 1


@pytest.mark.asyncio
async def test_postcommit_accessor_failure_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    repository = _Repository(order)
    attempt = SimpleNamespace(
        consumption_id="consumption.test",
        consumption_claim_id="claim.test",
        canonical_digest="e" * 64,
        access_deadline=NOW + timedelta(seconds=1),
    )
    repository.claim = WorkflowProtectedResidentContextAccessConsumptionClaimWrite(
        status=WorkflowProtectedResidentContextAccessConsumptionClaimStatus.CLAIMED,
        claim=cast(Any, SimpleNamespace(canonical_digest="f" * 64)),
        attempt=cast(Any, attempt),
        result=None,
    )
    lease = SimpleNamespace(authorization_lease_id="lease.test", canonical_digest="1" * 64)
    evidence = SimpleNamespace(
        source=SimpleNamespace(authorization_lease=lease),
        lifecycle=SimpleNamespace(request_nonce_digest="2" * 64),
        readiness=SimpleNamespace(),
    )
    accessor = _Accessor(order, raises=True)
    service = _service(repository, accessor, order)
    monkeypatch.setattr(service, "_require_trusted_components", lambda: None)

    async def load_and_attest(**values: object) -> object:
        del values
        return evidence

    monkeypatch.setattr(service, "_load_and_attest", load_and_attest)
    monkeypatch.setattr(service, "_build_instruction", lambda value: SimpleNamespace())

    presentation = await cast(Any, service.consume)(**_request())

    assert cast(Any, presentation.attempt) is attempt
    assert presentation.result is None
    assert order.count("accessor") == 1
